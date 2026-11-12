"""Doi soat SHA-256 toan bo du lieu that + chung minh du 3 trang thai cua verify_file().
Chay:  python run_verify.py            -> log: minh_chung/log_verify_file.txt
Trang thai 3 (shard offline) lam THU CONG: docker compose stop siteB, chay: python run_verify.py --k2-only
"""
import sys
from datetime import datetime
from pathlib import Path

import eduhub as E

sys.stdout.reconfigure(encoding="utf-8")   # Windows: tranh loi hien thi tieng Viet

LOG = Path(__file__).resolve().parent.parent / "minh_chung" / "log_verify_file.txt"
out = []


def say(s):
    print(s)
    out.append(s)


def real_docs(db, khoas=("K1", "K2")):
    for k in khoas:
        lim = f"{k}_HL_{E.REAL_ID_LIMIT:06d}"
        yield from db.resources.find({"khoaId": k, "_id": {"$lt": lim}},
                                     {"file.name": 1, "file.storage": 1, "file.chunks": 1, "courseId": 1}).sort("_id", 1)


def main():
    db = E.get_db()
    khoas = ("K2",) if "--k2-only" in sys.argv else ("K1", "K2")
    say(f"# verify_file {datetime.now():%Y-%m-%d %H:%M:%S}")
    say("== A. Doi soat toan bo hoc lieu that ==")
    first_chunked = None
    for d in real_docs(db, khoas):
        r = E.verify_file(db, d["_id"], d["_id"][:2])
        say(f"{r:20} | {d['_id']} | {d['file']['storage']:8} | {d['file']['name']}")
        if d["file"]["storage"] == "chunked" and first_chunked is None:
            first_chunked = d
    if "--k2-only" in sys.argv or first_chunked is None:
        say("(bo qua phan B: can it nhat 1 hoc lieu chunked va khong dung --k2-only)")
    else:
        rid, khoa, course = first_chunked["_id"], first_chunked["_id"][:2], first_chunked["courseId"]
        key = {"_id": rid, "khoaId": khoa, "courseId": course}
        say(f"== B. Gia lap loi tren {rid} (khoi phuc ngay sau khi thu) ==")
        # B1: sua checksum -> KHONG_KHOP
        old = db.resources.find_one(key)["file"]["checksum"]["value"]
        try:
            db.resources.update_one(key, {"$set": {"file.checksum.value": "a" * 64}})
            say(f"{E.verify_file(db, rid, khoa):20} | sua checksum trong CSDL (ky vong KHONG_KHOP)")
        finally:
            db.resources.update_one(key, {"$set": {"file.checksum.value": old}})
        # B2: xoa 1 chunk -> KHONG_THE_KIEM_TRA
        ck = db.resource_chunks.find_one({"khoaId": khoa, "resourceId": rid, "n": 1})
        try:
            db.resource_chunks.delete_one({"khoaId": khoa, "resourceId": rid, "n": 1})
            say(f"{E.verify_file(db, rid, khoa):20} | xoa chunk n=1 (ky vong KHONG_THE_KIEM_TRA)")
        finally:
            db.resource_chunks.insert_one(ck)
        say(f"{E.verify_file(db, rid, khoa):20} | sau khi khoi phuc (ky vong KHOP)")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Da ghi log: {LOG}")


if __name__ == "__main__":
    main()
