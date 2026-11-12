"""Tai lai 1 hoc lieu tu MongoDB (ghep chunk) ra thu muc downloads/ va doi soat SHA-256.
Chay:  python run_download.py K1_HL_000001
"""
import sys
from pathlib import Path

import eduhub as E

sys.stdout.reconfigure(encoding="utf-8")   # Windows: tranh loi hien thi tieng Viet

rid = sys.argv[1]
db = E.get_db()
path, state = E.download_file(db, rid, rid[:2], Path(__file__).resolve().parent.parent / "downloads")
print(f"{state} | {rid} -> {path} ({path.stat().st_size} byte)")
