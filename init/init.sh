
#!/bin/bash
# Luu file voi dinh dang LF, khong phai CRLF.

set -euo pipefail

MAX_RETRIES=60
SLEEP_SECONDS=2

wait_ping() {
  local host="$1"
  local count=0

  until mongosh --host "$host" --port 27017 --quiet \
    --eval "db.adminCommand('ping').ok" 2>/dev/null | grep -q 1; do

    count=$((count + 1))

    if [ "$count" -ge "$MAX_RETRIES" ]; then
      echo "[ERROR] Khong the ket noi MongoDB: $host"
      exit 1
    fi

    echo "[init] Cho MongoDB $host san sang..."
    sleep "$SLEEP_SECONDS"
  done

  echo "[init] $host da san sang."
}

init_rs() {
  local host="$1"
  local rs_name="$2"
  local extra="$3"

  echo "[init] Kiem tra replica set $rs_name..."

  mongosh --host "$host" --port 27017 --quiet --eval "
    try {
      rs.status();
      print('[init] $rs_name da duoc initiate.');
    } catch (e) {
      print('[init] Dang initiate $rs_name...');
      printjson(rs.initiate({
        _id: '$rs_name',
        $extra
        members: [{_id: 0, host: '$host:27017'}]
      }));
    }
  "
}

wait_primary() {
  local host="$1"
  local count=0

  until mongosh --host "$host" --port 27017 --quiet \
    --eval "db.hello().isWritablePrimary" 2>/dev/null | grep -q true; do

    count=$((count + 1))

    if [ "$count" -ge "$MAX_RETRIES" ]; then
      echo "[ERROR] $host khong tro thanh PRIMARY."
      exit 1
    fi

    echo "[init] Cho PRIMARY tren $host..."
    sleep "$SLEEP_SECONDS"
  done

  echo "[init] $host da la PRIMARY."
}

# Buoc 1: Cho cac MongoDB server san sang.
for h in cfg siteA siteB; do
  wait_ping "$h"
done

# Buoc 2: Khoi tao replica sets.
init_rs cfg rsCfg "configsvr: true,"
init_rs siteA rsA ""
init_rs siteB rsB ""

# Buoc 3: Cho cac replica set co PRIMARY.
for h in cfg siteA siteB; do
  wait_primary "$h"
done

# Buoc 4: Cho Mongos san sang.
wait_ping mongos

# Buoc 5: Cau hinh cluster, shard va zone.
echo "[init] === Cau hinh cluster + zone ==="
mongosh --host mongos --port 27017 --quiet /scripts/01_cluster.js

# Buoc 6: Nap du lieu mau.
echo "[init] === Nap khoa / monhoc / nguoidung ==="
mongosh --host mongos --port 27017 --quiet /scripts/02_seed.js

echo "[init] ================================="
echo "[init] KHOI TAO HOAN TAT."
echo "[init] Ket noi: mongodb://localhost:27017"
echo "[init] Database: eduhub"
echo "[init] ================================="
