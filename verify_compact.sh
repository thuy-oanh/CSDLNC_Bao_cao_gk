#!/usr/bin/env bash
set -euo pipefail

docker compose exec -T mongos mongosh --quiet eduhub --eval '
const E = db.getSiblingDB("eduhub");
const cfg = db.getSiblingDB("config");
let nFail = 0;

function assertCheck(label, condition, detail = "") {
  const status = condition ? "PASS" : "FAIL";
  print(label.padEnd(18) + ": " + status + (detail ? " (" + detail + ")" : ""));
  if (!condition) nFail++;
}

print("==================== EDUHUB DISTRIBUTED VERIFICATION ====================");

// 1. CẤU HÌNH SHARD VÀ ZONE RANGE
print("\n===== 1. SHARD & ZONE CONFIGURATION =====");
const shards = cfg.shards.find().toArray();
if (!shards || shards.length === 0) throw new Error("Khong truy cap duoc config.shards");
shards.forEach(s => {
  const tags = (s.tags && s.tags.length > 0) ? s.tags.join(",") : "NO_TAG";
  print("• " + s._id + " (" + s.host + ") -> Zone: [" + tags + "]");
});
print("• Zone Key Ranges:");
cfg.tags.find().sort({ ns: 1, tag: 1 }).forEach(t => {
  const ns = t.ns.replace("eduhub.", "");
  print("  - " + ns.padEnd(16) + ": " + t.tag + " " + JSON.stringify(t.min) + " -> " + JSON.stringify(t.max));
});

// 2. PHÂN BỔ DỮ LIỆU THỰC TẾ
print("\n===== 2. DATA DISTRIBUTION (COLLECTION STATS TRÊN TỪNG SHARD) =====");
const colls = ["resources", "resource_chunks", "nguoidung", "access_logs"];
colls.forEach(c => {
  const stats = E[c].aggregate([
    { $collStats: { storageStats: {} } },
    { $project: { shard: 1, count: "$storageStats.count", size: "$storageStats.size" } }
  ]).toArray();
  
  let aCount = 0, aSize = 0, bCount = 0, bSize = 0;
  stats.forEach(s => {
    if (s.shard === "rsA") { aCount = s.count; aSize = s.size; }
    if (s.shard === "rsB") { bCount = s.count; bSize = s.size; }
  });
  const fmt = b => b >= 1048576 ? (b/1048576).toFixed(2)+" KiB" && (b/1048576).toFixed(2)+" MiB" : (b >= 1024 ? (b/1024).toFixed(2)+" KiB" : b+" B");
  print("• " + c.padEnd(16) + ": rsA=" + String(aCount).padStart(3) + " docs (" + fmt(aSize).padEnd(12) + ") | rsB=" + String(bCount).padStart(3) + " docs (" + fmt(bSize).padEnd(12) + ") | Total=" + (aCount + bCount));
});

// 3. ĐIỀU KIỆN TÁI TẠO (Count mongos = Count rsA + Count rsB)
print("\n===== 3. DIEU KIEN TAI TAO (Reconstruction: mongos = rsA + rsB) =====");
colls.forEach(c => {
  const nGlobal = E[c].countDocuments({});
  const stats = E[c].aggregate([
    { $collStats: { storageStats: {} } },
    { $project: { shard: 1, count: "$storageStats.count" } }
  ]).toArray();
  
  let a = 0, b = 0;
  stats.forEach(s => { if (s.shard === "rsA") a = s.count; if (s.shard === "rsB") b = s.count; });
  const pass = (nGlobal === (a + b));
  assertCheck(c, pass, "mongos=" + nGlobal + " | rsA=" + a + " | rsB=" + b);
});

// 4. ĐIỀU KIỆN ĐẦY ĐỦ (Miền giá trị khoaId)
print("\n===== 4. DIEU KIEN DAY DU (Domain Validation: khoaId in {K1,K2}) =====");
colls.forEach(c => {
  const nBad = E[c].countDocuments({ khoaId: { $nin: ["K1", "K2"] } });
  assertCheck(c, nBad === 0, "invalid=" + nBad);
});

// 5. ĐIỀU KIỆN TÁCH BIỆT (_id trùng giữa các shard)
print("\n===== 5. DIEU KIEN TACH BIET (Disjointness: Duplicate _id = 0) =====");
colls.forEach(c => {
  const dup = E[c].aggregate([
    { $group: { _id: "$_id", count: { $sum: 1 } } },
    { $match: { count: { $gt: 1 } } },
    { $limit: 1 }
  ]).toArray();
  const count = E[c].countDocuments({});
  assertCheck(c, dup.length === 0, count === 0 ? "EMPTY" : "trung=" + dup.length);
});

// 6. KIỂM TRA ZONE PLACEMENT (K1 ở rsA, K2 ở rsB)
print("\n===== 6. KIEM TRA ZONE PLACEMENT (Data Placement) =====");
colls.forEach(c => {
  const collMeta = cfg.collections.findOne({ _id: "eduhub." + c });
  if (!collMeta) {
    assertCheck(c, false, "Chua duoc shard");
    return;
  }
  const query = collMeta.uuid ? { uuid: collMeta.uuid } : { ns: "eduhub." + c };
  const chunks = cfg.chunks.find(query).toArray();
  const badA = chunks.some(x => x.min && x.min.khoaId === "K1" && x.shard !== "rsA");
  const badB = chunks.some(x => x.min && x.min.khoaId === "K2" && x.shard !== "rsB");
  const total = E[c].countDocuments({});
  const pass = (!badA && !badB);
  assertCheck(c, pass, total === 0 ? "EMPTY" : "K1->rsA, K2->rsB");
});

print("=========================================================================");
if (nFail > 0) {
  throw new Error("Phat hien " + nFail + " phep kiem tra THAT BAI!");
}
'
