
import hashlib
import json
import mimetypes
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from bson.binary import Binary
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "eduhub")
CHUNK = 255 * 1024
# Quy uoc nhom: 15 MB. Bien moi truong chi dung de THU NGHIEM (vd video nho muon thu chunked).
MAX_EMBED = int(float(os.getenv("EDUHUB_MAX_EMBED_MB", "15")) * 1024 * 1024)
MAX_TEXT_BYTES = 200 * 1000          # content.text < 200 KB (quy dinh nhom, de kiem soat text index)
QUERY_TIMEOUT_MS = 8000              # shard offline -> loi nhanh thay vi treo

VALID_TYPES = {"video", "lecture", "slide", "image", "file"}
VALID_ACCESS = {"public", "course", "private"}
REAL_ID_LIMIT = 100000               # id >= 100000 danh cho du lieu sinh cua TV3

MIME_OVERRIDE = {
    ".mp4": "video/mp4", ".mp3": "audio/mpeg", ".pdf": "application/pdf",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".zip": "application/zip", ".srt": "application/x-subrip", ".txt": "text/plain",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


# ----------------------------------------------------------------------------- ket noi
def get_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, socketTimeoutMS=60000)
    client.admin.command("ping")
    return client[MONGO_DB]


# ----------------------------------------------------------------------------- tien ich
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def guess_mime(path):
    ext = Path(path).suffix.lower()
    return MIME_OVERRIDE.get(ext) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def clean_text(text):
    """Lam sach + cat toi da MAX_TEXT_BYTES (cat theo byte UTF-8, khong cat giua ky tu)."""
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text.encode("utf-8")[:MAX_TEXT_BYTES].decode("utf-8", "ignore")


def next_id(db, khoa):
    """Sinh KX_HL_XXXXXX tiep theo trong dai du lieu that (000001-099999). Truy van kem khoaId."""
    top = db.resources.find_one(
        {"khoaId": khoa, "_id": {"$lt": f"{khoa}_HL_{REAL_ID_LIMIT:06d}"}},
        {"_id": 1}, sort=[("_id", -1)])
    n = int(top["_id"].split("_")[-1]) + 1 if top else 1
    if n >= REAL_ID_LIMIT:
        raise RuntimeError("Het dai ma du lieu that cua " + khoa)
    return f"{khoa}_HL_{n:06d}"


# ----------------------------------------------------------------------------- trich xuat noi dung
def parse_srt(path):
    """Doc file phu de .srt -> [{start, end, text}] (giay). Bo the HTML (<font ...>)."""
    raw = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")

    def sec(ts):
        h, m, s, ms = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)", ts).groups()
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000

    out = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [l for l in block.split("\n") if l.strip()]
        idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if idx is None:
            continue
        a, b = [x.strip().split()[0] for x in lines[idx].split("-->")[:2]]
        text = re.sub(r"<[^>]+>", "", " ".join(lines[idx + 1:]))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out.append({"start": round(sec(a), 2), "end": round(sec(b), 2), "text": text})
    return out


def probe_video(path):
    """ffprobe -> durationSec, width, height, codec (bo qua luong anh bia attached_pic)."""
    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    info = json.loads(subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True).stdout)
    v = next(s for s in info["streams"]
             if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic"))
    return {"durationSec": round(float(info["format"]["duration"]), 1),
            "width": int(v["width"]), "height": int(v["height"]), "codec": v["codec_name"]}


def extract_content(path):
    """Tra ve (media, text, warnings). Loi trich xuat KHONG lam hong viec nap: chi ghi canh bao."""
    path, ext = Path(path), Path(path).suffix.lower()
    media, text, warns = {}, None, []
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            media["pages"] = len(reader.pages)
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
        elif ext == ".pptx":
            from pptx import Presentation
            prs = Presentation(str(path))
            media["pages"] = len(prs.slides)
            parts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        parts.append(shape.text_frame.text)
            text = "\n".join(parts)
        elif ext in (".png", ".jpg", ".jpeg"):
            from PIL import Image
            with Image.open(path) as im:
                media["width"], media["height"] = im.size
        elif ext == ".mp4":
            media = probe_video(path)
    except FileNotFoundError:
        warns.append("Khong tim thay ffprobe (cai ffmpeg) - bo qua thong so video")
    except Exception as e:                                  # noqa: BLE001
        warns.append(f"Khong trich xuat duoc {path.name}: {e}")
    if text is not None:
        text = clean_text(text) or None
        if text is None:
            warns.append("Khong co van ban de trich xuat (PDF quet anh?)")
    return media, text, warns


# ----------------------------------------------------------------------------- nap hoc lieu
def ingest(db, path, meta):
    """Nap 1 tep: nhung BinData (<= 15 MB) hoac cat chunk 255 KB vao resource_chunks.

    meta bat buoc: _id, khoaId, courseId, type, title, description, caption, author{id,name}
    meta tuy chon: tags, access{level,groups}, media, content, course{name,credits}
    Tra ve ('OK', rid) hoac ('TRUNG', rid_da_co).
    """
    p = Path(path)
    if not p.is_file() or p.stat().st_size == 0:
        raise ValueError("Tep khong ton tai hoac rong")
    for k in ("_id", "khoaId", "courseId", "type", "title", "description", "caption", "author"):
        if not meta.get(k):
            raise ValueError(f"Thieu truong bat buoc: {k}")
    if meta["type"] not in VALID_TYPES:
        raise ValueError(f"type khong hop le: {meta['type']}")

    rid, khoa, course = meta["_id"], meta["khoaId"], meta["courseId"]
    size = p.stat().st_size
    sha = sha256_file(p)

    # Chong nap trung noi dung (idx_dedup cua TV3 la lop bao ve thu hai)
    dup = db.resources.find_one({"khoaId": khoa, "courseId": course, "file.checksum.value": sha}, {"_id": 1})
    if dup:
        return "TRUNG", dup["_id"]

    embedded = size <= MAX_EMBED
    now = datetime.now(timezone.utc)
    doc = {
        "_id": rid, "khoaId": khoa, "courseId": course,
        "type": meta["type"], "title": meta["title"], "description": meta["description"],
        "caption": meta["caption"], "tags": meta.get("tags", []), "author": meta["author"],
        "access": meta.get("access", {"level": "course", "groups": []}),
        "file": {"name": p.name, "extension": p.suffix.lower(), "mimeType": guess_mime(p),
                 "size": size, "storage": "embedded" if embedded else "chunked",
                 "checksum": {"algorithm": "sha256", "value": sha}},
        "media": meta.get("media", {}), "content": meta.get("content", {}),
        "status": "uploading", "version": 1, "stats": {"views": 0, "downloads": 0},
        "createdAt": now, "updatedAt": now,
    }
    if meta.get("course"):
        doc["course"] = meta["course"]

    key = {"_id": rid, "khoaId": khoa, "courseId": course}      # day du shard key -> dinh tuyen dung shard

    if embedded:
        doc["file"]["data"] = Binary(p.read_bytes())
        doc["status"] = "ready"
        db.resources.insert_one(doc)
        return "OK", rid

    doc["file"]["chunks"] = -(-size // CHUNK)
    db.resources.insert_one(doc)
    try:
        batch, n = [], 0
        with open(p, "rb") as f:
            while True:
                data = f.read(CHUNK)
                if not data:
                    break
                batch.append({"_id": f"{rid}#{n}", "khoaId": khoa, "resourceId": rid, "n": n, "data": Binary(data)})
                n += 1
                if len(batch) == 40:
                    db.resource_chunks.insert_many(batch, ordered=True)
                    batch = []
        if batch:
            db.resource_chunks.insert_many(batch, ordered=True)
        db.resources.update_one(key, {"$set": {"status": "ready"}})
    except Exception:
        db.resource_chunks.delete_many({"khoaId": khoa, "resourceId": rid})
        db.resources.update_one(key, {"$set": {"status": "failed"}})
        raise                                                    # khong nuot loi
    return "OK", rid


# ----------------------------------------------------------------------------- doi soat / tai ve
def _chunks(db, rid, khoa):
    return db.resource_chunks.find({"khoaId": khoa, "resourceId": rid}).sort("n", 1).max_time_ms(QUERY_TIMEOUT_MS)


def verify_file(db, rid, khoa):
    """Tai lai tu MongoDB, tinh lai SHA-256, doi chieu file.checksum.value.
    KHOP | KHONG_KHOP | KHONG_THE_KIEM_TRA (khong co doc, thieu chunk, shard offline, loi ket noi)."""
    try:
        doc = db.resources.find_one({"_id": rid, "khoaId": khoa}, max_time_ms=QUERY_TIMEOUT_MS)
        if doc is None:
            return "KHONG_THE_KIEM_TRA"
        if doc["file"]["storage"] == "embedded":
            h = hashlib.sha256(bytes(doc["file"]["data"]))
        else:
            h, expect = hashlib.sha256(), 0
            for c in _chunks(db, rid, khoa):
                if c["n"] != expect:                              # thieu/nhay chunk
                    return "KHONG_THE_KIEM_TRA"
                h.update(bytes(c["data"]))
                expect += 1
            if expect != doc["file"]["chunks"]:
                return "KHONG_THE_KIEM_TRA"
    except Exception:                                            # noqa: BLE001  shard offline, timeout...
        return "KHONG_THE_KIEM_TRA"
    return "KHOP" if h.hexdigest() == doc["file"]["checksum"]["value"] else "KHONG_KHOP"


def download_file(db, rid, khoa, out_dir):
    """Ghep chunk (hoac lay BinData) ghi ra dia. Tra ve (duong_dan, trang_thai_doi_soat)."""
    doc = db.resources.find_one({"_id": rid, "khoaId": khoa}, max_time_ms=QUERY_TIMEOUT_MS)
    if doc is None:
        raise FileNotFoundError(rid)
    out = Path(out_dir) / doc["file"]["name"]
    out.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with open(out, "wb") as f:
        if doc["file"]["storage"] == "embedded":
            data = bytes(doc["file"]["data"]); f.write(data); h.update(data)
        else:
            for c in _chunks(db, rid, khoa):
                data = bytes(c["data"]); f.write(data); h.update(data)
    ok = h.hexdigest() == doc["file"]["checksum"]["value"]
    return out, ("KHOP" if ok else "KHONG_KHOP")
