#!/usr/bin/env bash
# Chay tren may host, trong thu muc co docker-compose.yml:  bash verify.sh | tee log_kiem_tra_phan_manh.txt
M="docker compose exec -T mongos mongosh --quiet eduhub --eval"
A="docker compose exec -T siteA  mongosh --quiet eduhub --eval"
B="docker compose exec -T siteB  mongosh --quiet eduhub --eval"

echo "===== 1. sh.status() ====="; $M "sh.status()"
for c in resources resource_chunks nguoidung access_logs; do
  echo "===== 2. getShardDistribution: $c ====="; $M "db.$c.getShardDistribution()"
done

echo "===== 3. Dieu kien TAI TAO: count qua mongos = tong hai shard ====="
for c in resources nguoidung resource_chunks access_logs; do
  m=$($M "db.$c.countDocuments({})"); a=$($A "db.$c.countDocuments({})"); b=$($B "db.$c.countDocuments({})")
  echo "$c: mongos=$m | ShardA=$a | ShardB=$b | tong=$((a+b))"
done

echo "===== 4. Dieu kien DAY DU: khoaId ngoai {K1,K2} (ky vong 0) ====="
for c in resources nguoidung resource_chunks access_logs; do
  echo "$c: $($M "db.$c.countDocuments({khoaId:{\$nin:['K1','K2']}})")"
done

echo "===== 5. Dieu kien TACH BIET: _id trung giua hai shard (ky vong rong) ====="
for c in resources resource_chunks nguoidung; do
  $A "db.$c.find({},{_id:1}).toArray().map(d=>d._id).join('\n')" | sort > /tmp/ids_a.txt
  $B "db.$c.find({},{_id:1}).toArray().map(d=>d._id).join('\n')" | sort > /tmp/ids_b.txt
  echo "$c: trung = [$(comm -12 /tmp/ids_a.txt /tmp/ids_b.txt | tr '\n' ' ')]"
done

echo "===== 6. K1 chi o ShardA, K2 chi o ShardB ====="
for c in resources resource_chunks nguoidung; do
  echo "$c  ShardA co K2? $($A "db.$c.countDocuments({khoaId:'K2'})")  | ShardB co K1? $($B "db.$c.countDocuments({khoaId:'K1'})")  (ky vong 0 va 0)"
done
