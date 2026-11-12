#!/usr/bin/env bash
# Chay trong thu muc EduHub (Git Bash):  bash collect_evidence.sh
# Tao thu muc minh_chung/ chua toan bo log goc. Chay SAU KHI "docker compose up -d" va init da xong.
export MSYS_NO_PATHCONV=1          # Git Bash tren Windows khong duoc doi /tmp/... thanh C:/...
D=minh_chung
mkdir -p "$D/anh"

echo "[1/5] log khoi tao cluster"
docker compose logs init --no-log-prefix > "$D/log_init.txt" 2>&1

echo "[2/5] trang thai container"
docker compose ps -a > "$D/docker_ps.txt" 2>&1

echo "[3/5] kiem tra phan manh"
bash verify.sh > "$D/log_kiem_tra_phan_manh.txt" 2>&1

echo "[4/5] kiem tra toan ven + zone"
docker cp scripts/03_integrity_test.js eduhub-mongos:/tmp/t.js
docker compose exec -T mongos mongosh --quiet /tmp/t.js > "$D/log_toan_ven.txt" 2>&1

echo "[5/5] kiem tra truy van K2 chi toi rsB"
docker compose exec -T mongos mongosh --quiet eduhub --eval \
 "print(JSON.stringify(db.resources.find({khoaId:'K2'}).explain().queryPlanner.winningPlan.shards.map(s=>s.shardName)))" \
 > "$D/targeted_K2.txt" 2>&1

echo; echo "=== Kiem tra nhanh ==="
echo "So dong WARN trong log_init (ky vong 0): $(grep '\[WARN\]' "$D/log_init.txt" | grep -v 'Chua xong' | wc -l)"
grep "TONG KET" "$D/log_toan_ven.txt"
echo "Truy van khoaId=K2 toi shard (ky vong [\"rsB\"]): $(cat "$D/targeted_K2.txt")"
echo "Xong. Log nam trong thu muc $D/"