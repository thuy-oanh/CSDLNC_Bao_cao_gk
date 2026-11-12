"""Nap toan bo dataset theo dataset/manifest.json, doi soat SHA-256 tung tep, ghi log.

Chay:  python run_ingest.py            (nap)
       python run_ingest.py --clean    (xoa du lieu THAT 000001-099999 roi nap lai; khong dong toi du lieu TV3)
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import eduhub as E

import pypdf
_orig_extract_text = pypdf.PageObject.extract_text
def _safe_extract_text(self, *args, **kwargs):
    t = _orig_extract_text(self, *args, **kwargs)
    if t:
        return "".join(c for c in t if not (0xD800 <= ord(c) <= 0xDFFF))
    return t
pypdf.PageObject.extract_text = _safe_extract_text


sys.stdout.reconfigure(encoding="utf-8")   # Windows: tranh loi hien thi tieng Viet

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset"
LOG = ROOT / "minh_chung" / "log_nap_hoc_lieu.txt"


def build_meta(db, entry):
    rel = Path(entry["path"])
    khoa, course = rel.parts[0], rel.parts[1]                       # K1/Physics/xxx.mp4
    path = DATASET / rel
    if khoa not in ("K1", "K2"):
        raise ValueError(f"Thu muc cap 1 phai la K1 hoac K2, dang la {khoa}")

    mon = db.monhoc.find_one({"_id": course})
    if mon is None:
        raise ValueError(f"courseId '{course}' chua co trong monhoc - nho TV1 them vao scripts/02_seed.js")
    user = db.nguoidung.find_one({"_id": entry["authorId"], "khoaId": khoa})
    if user is None:
        raise ValueError(f"authorId '{entry['authorId']}' khong ton tai trong khoa {khoa}")

    media, text, warns = E.extract_content(path)
    if text:
        text = "".join(c for c in text if not (0xD800 <= ord(c) <= 0xDFFF))
    content = {"language": entry.get("language", "vi")}
    if text:
        content["text"] = text
    if entry.get("transcript"):
        tr = E.parse_srt(DATASET / entry["transcript"])
        if tr:
            content["transcript"] = tr
        else:
            warns.append("transcript rong")
    level = entry.get("access", "course")
    meta = {
        "khoaId": khoa, "courseId": course, "type": entry["type"],
        "title": entry["title"], "description": entry["description"], "caption": entry["caption"],
        "tags": entry.get("tags", []), "author": {"id": user["_id"], "name": user["hoTen"]},
        "access": {"level": level, "groups": [f"{khoa}_{course}_01"] if level == "course" else []},
        "course": {"name": mon["tenMon"], "credits": mon["soTinChi"]},
        "media": media, "content": content,
    }
    return path, meta, warns


def clean(db):
    for k in ("K1", "K2"):
        lim = f"{k}_HL_{E.REAL_ID_LIMIT:06d}"
        r1 = db.resource_chunks.delete_many({"khoaId": k, "resourceId": {"$lt": lim}})
        r2 = db.resources.delete_many({"khoaId": k, "_id": {"$lt": lim}})
        print(f"[clean] {k}: xoa {r2.deleted_count} hoc lieu, {r1.deleted_count} chunk")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--manifest", default=str(DATASET / "manifest.json"))
    args = ap.parse_args()

    db = E.get_db()
    if args.clean:
        clean(db)
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    LOG.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Log nap hoc lieu {datetime.now():%Y-%m-%d %H:%M:%S}  URI={E.MONGO_URI} DB={E.MONGO_DB}",
             "ket_qua | ma_hoc_lieu | khoa/mon | tep | kich_thuoc | kieu_luu | doi_soat_sha256 | ghi_chu"]
    n_ok = n_dup = n_err = 0
    for entry in manifest:
        name = entry.get("path", "?")
        try:
            path, meta, warns = build_meta(db, entry)
            meta["_id"] = E.next_id(db, meta["khoaId"])
            state, rid = E.ingest(db, path, meta)
            if state == "TRUNG":
                n_dup += 1
                lines.append(f"TRUNG | {rid} | {meta['khoaId']}/{meta['courseId']} | {name} | - | - | - | da co noi dung giong, bo qua")
                continue
            doc = db.resources.find_one({"_id": rid, "khoaId": meta["khoaId"]}, {"file": 1})
            vf = E.verify_file(db, rid, meta["khoaId"])
            n_ok += 1
            lines.append(f"OK | {rid} | {meta['khoaId']}/{meta['courseId']} | {name} | {doc['file']['size']} | "
                         f"{doc['file']['storage']} | {vf} | {'; '.join(warns)}")
        except Exception as e:                                       # noqa: BLE001  1 tep loi khong dung ca lo
            n_err += 1
            lines.append(f"LOI | - | - | {name} | - | - | - | {e}")
        print(lines[-1])

    lines.append(f"# Tong ket: {n_ok} OK, {n_dup} trung, {n_err} loi")
    print(lines[-1])
    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi log: {LOG}")
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
