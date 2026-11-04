// 01_cluster.js - chay tren mongos (hoan thien xu ly loi va kiem tra trang thai)
const E = db.getSiblingDB('eduhub');
const cfgdb = db.getSiblingDB('config');

const criticalErrors = [];

// Ham step thong minh: bo qua loi "da ton tai", ghi nhan loi nghiem trong
function step(label, fn) {
  try {
    const r = fn();
    print('[OK]   ' + label);
    return r;
  } catch (e) {
    const msg = e.message || '';
    // Cac loi do da chay roi thi an tam bo qua (Idempotent)
    const ignorable = [
      'already exists',
      'already sharded',
      'already initialized',
      'already in target zone',
      'is already a shard'
    ];
    const canIgnore = ignorable.some(errText => msg.toLowerCase().includes(errText.toLowerCase()));
    
    if (canIgnore) {
      print('[SKIP] ' + label + ' (Da ton tai hoac da cau hinh truoc do)');
    } else {
      print('[ERROR] ' + label + ' -> ' + msg);
      criticalErrors.push(label + ': ' + msg);
    }
  }
}

// =====================================================
// 1. THEM SHARD + GAN ZONE
// =====================================================
step('addShard rsA', () => sh.addShard('rsA/siteA:27017'));
step('addShard rsB', () => sh.addShard('rsB/siteB:27017'));
step('zone K1 -> rsA', () => sh.addShardToZone('rsA', 'K1'));
step('zone K2 -> rsB', () => sh.addShardToZone('rsB', 'K2'));

// =====================================================
// 2. BAT SHARDING CHO DATABASE
// Primary Shard = rsA de khoa/monhoc khong nam o Site B
// =====================================================
step('enableSharding eduhub (primary rsA)', () => sh.enableSharding('eduhub', 'rsA'));

// =====================================================
// 3. TAO 6 COLLECTION KEM VALIDATOR
// =====================================================
const prefixOk = (f) => ({ $expr: { $eq: [{$substrBytes: ['$' + f, 0, 2] }, '$khoaId'] } });
const validators = {
  khoa: { $jsonSchema: { bsonType: 'object', required: ['_id', 'tenKhoa'],
    properties: { _id: { enum: ['K1', 'K2'] }, tenKhoa: { bsonType: 'string', minLength: 1 } } } },

  monhoc: { $jsonSchema: { bsonType: 'object', required: ['_id', 'tenMon', 'soTinChi'],
    properties: { _id: { bsonType: 'string', minLength: 1 }, tenMon: { bsonType: 'string', minLength: 1 },
                  soTinChi: { bsonType: ['int', 'long'], minimum: 1 } } } },

  nguoidung: { $and: [
    prefixOk('_id'),
    { $expr: { $eq: [{$substrBytes: ['$_id', 3, 2] }, '$vaiTro'] } },
    { $jsonSchema: { bsonType: 'object', required: ['_id', 'hoTen', 'email', 'vaiTro', 'khoaId'],
      properties: { _id: { bsonType: 'string', pattern: '^K[12]_(GV|SV|QT)_[0-9]{6}$' },
                    khoaId: { enum: ['K1', 'K2'] }, vaiTro: { enum: ['GV', 'SV', 'QT'] },
                    hoTen: { bsonType: 'string', minLength: 1 }, email: { bsonType: 'string', minLength: 3 } } } } ] },

  resources: { $and: [
    prefixOk('_id'),
    { $jsonSchema: { bsonType: 'object',
      required: ['_id', 'khoaId', 'courseId', 'type', 'title', 'description', 'caption', 'author', 'file', 'status', 'createdAt'],
      properties: {
        _id: { bsonType: 'string', pattern: '^K[12]_HL_[0-9]{6}$' },
        khoaId: { enum: ['K1', 'K2'] }, courseId: { bsonType: 'string', minLength: 1 },
        type: { enum: ['video', 'lecture', 'slide', 'image', 'file'] },
        title: { bsonType: 'string', minLength: 1 }, description: { bsonType: 'string', minLength: 1 },
        caption: { bsonType: 'string', minLength: 1 },
        status: { enum: ['uploading', 'ready', 'failed'] },
        access: { bsonType: 'object', properties: { level: { enum: ['public', 'course', 'private'] } } },
        file: { bsonType: 'object', required: ['name', 'extension', 'mimeType', 'size', 'storage', 'checksum'],
          properties: {
            size: { bsonType: ['int', 'long'], minimum: 1 },
            storage: { enum: ['embedded', 'chunked'] },
            checksum: { bsonType: 'object', required: ['algorithm', 'value'],
              properties: { algorithm: { enum: ['sha256'] }, value: { bsonType: 'string', pattern: '^[0-9a-f]{64}$' } } } } },
        createdAt: { bsonType: 'date' } } } } ] },

  resource_chunks: { $and: [
    prefixOk('_id'), prefixOk('resourceId'),
    { $jsonSchema: { bsonType: 'object', required: ['_id', 'khoaId', 'resourceId', 'n', 'data'],
      properties: { _id: { bsonType: 'string', pattern: '^K[12]_HL_[0-9]{6}#[0-9]+$' },
                    khoaId: { enum: ['K1', 'K2'] }, resourceId: { bsonType: 'string' },
                    n: { bsonType: ['int', 'long'], minimum: 0 }, data: { bsonType: 'binData' } } } } ] },

  access_logs: { $jsonSchema: { bsonType: 'object', required: ['_id', 'khoaId', 'resourceId', 'userId', 'hanhDong', 'ts'],
    properties: { khoaId: { enum: ['K1', 'K2'] }, hanhDong: { enum: ['view', 'download'] }, ts: { bsonType: 'date' } } } }
};

for (const [name, validator] of Object.entries(validators)) {
  step('collection ' + name, () => {
    if (E.getCollectionNames().includes(name))
      return E.runCommand({ collMod: name, validator, validationLevel: 'strict', validationAction: 'error' });
    return E.createCollection(name, { validator });
  });
}

// =====================================================
// 4. SHARD KEY CHO 4 COLLECTION
// =====================================================
step('shard resources',       () => sh.shardCollection('eduhub.resources',       { khoaId: 1, courseId: 1 }));
step('shard nguoidung',       () => sh.shardCollection('eduhub.nguoidung',       { khoaId: 1 }));
step('shard resource_chunks', () => sh.shardCollection('eduhub.resource_chunks', { khoaId: 1, resourceId: 1, n: 1 }));
step('shard access_logs',     () => sh.shardCollection('eduhub.access_logs',     { khoaId: 1 }));

// =====================================================
// 5. ZONE KEY RANGE (Giu dung thiet ke goc tu tai lieu nhom)
// =====================================================
const MIN = MinKey(), MAX = MaxKey();
for (const k of ['K1', 'K2']) {
  step('zone resources ' + k,       () => sh.updateZoneKeyRange('eduhub.resources',       { khoaId: k, courseId: MIN }, { khoaId: k, courseId: MAX }, k));
  step('zone resource_chunks ' + k, () => sh.updateZoneKeyRange('eduhub.resource_chunks', { khoaId: k, resourceId: MIN, n: MIN }, { khoaId: k, resourceId: MAX, n: MAX }, k));
}
step('zone nguoidung K1',   () => sh.updateZoneKeyRange('eduhub.nguoidung',   { khoaId: 'K1' }, { khoaId: 'K2' }, 'K1'));
step('zone nguoidung K2',   () => sh.updateZoneKeyRange('eduhub.nguoidung',   { khoaId: 'K2' }, { khoaId: 'K3' }, 'K2'));
step('zone access_logs K1', () => sh.updateZoneKeyRange('eduhub.access_logs', { khoaId: 'K1' }, { khoaId: 'K2' }, 'K1'));
step('zone access_logs K2', () => sh.updateZoneKeyRange('eduhub.access_logs', { khoaId: 'K2' }, { khoaId: 'K3' }, 'K2'));

// =====================================================
// 6. UNIQUE EMAIL (unique index trên collection shard phải có tiền tố shard key)
// =====================================================
step('unique email nguoidung', () => E.nguoidung.createIndex({ khoaId: 1, email: 1 }, { unique: true, name: 'idx_email_unique' }));

// =====================================================
// 7. CHỜ BALANCER ĐƯA CHUNK VỀ ĐÚNG ZONE
// =====================================================
function zonesPlaced(ns) {
  const c = cfgdb.collections.findOne({ _id: ns });
  if (!c) return false;
  const ch = cfgdb.chunks.find({ uuid: c.uuid }).toArray();
  const a = ch.some(x => x.min.khoaId === 'K1' && x.shard === 'rsA');
  const b = ch.some(x => x.min.khoaId === 'K2' && x.shard === 'rsB');
  const bad = ch.some(x => (x.min.khoaId === 'K1' && x.shard !== 'rsA') || (x.min.khoaId === 'K2' && x.shard !== 'rsB'));
  return a && b && !bad;
}
const nss = ['eduhub.resources', 'eduhub.nguoidung', 'eduhub.resource_chunks', 'eduhub.access_logs'];
for (let i = 0; i < 40; i++) {
  const pending = nss.filter(n => !zonesPlaced(n));
  if (pending.length === 0) { print('[OK]   Tat ca chunk da nam dung zone (K1->rsA, K2->rsB)'); break; }
  if (i === 39) { print('[WARN] Chua xong: ' + pending.join(', ') + ' -> chay sh.status() sau it phut'); }
  sleep(3000);
}
print('Balancer state: ' + sh.getBalancerState());

// =====================================================
// 8. TỔNG KẾT
// =====================================================
if (criticalErrors.length > 0) {
  print('[FAILED] Co ' + criticalErrors.length + ' loi nghiem trong:');
  criticalErrors.forEach(e => print('  - ' + e));
  quit(1);          // init.sh dung voi set -e, de ban thay loi ngay
}
print('[DONE] 01_cluster.js hoan tat khong loi.');