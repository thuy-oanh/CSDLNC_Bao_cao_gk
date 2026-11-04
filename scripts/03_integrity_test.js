// 03_integrity_test.js - kich ban 5 (toan ven) + 6 (zone).
// Chay (Git Bash):  MSYS_NO_PATHCONV=1 docker cp scripts/03_integrity_test.js eduhub-mongos:/tmp/t.js
//                   MSYS_NO_PATHCONV=1 docker compose exec -T mongos mongosh --quiet /tmp/t.js | tee log_toan_ven.txt
// (hoac chay collect_evidence.sh de lam tat ca)
const E = db.getSiblingDB('eduhub');
const mk = (id, khoa, over = {}) => Object.assign({
  _id: id, khoaId: khoa, courseId: 'CSDLNC', type: 'lecture', title: 'Test', description: 'Test', caption: 'Test',
  author: { id: khoa + '_GV_000001', name: 'Tester' },
  file: { name: 't.txt', extension: '.txt', mimeType: 'text/plain', size: 5, storage: 'embedded',
          checksum: { algorithm: 'sha256', value: 'a'.repeat(64) }, data: BinData(0, 'SGVsbG8=') },
  status: 'ready', createdAt: new Date() }, over);

let nPass = 0, nFail = 0;
function expect(label, coll, doc, shouldPass) {
  let ok, msg = '';
  try { coll.insertOne(doc); ok = true; } catch (e) { ok = false; msg = (e.code || '') + ' ' + e.message.split('\n')[0]; }
  if (ok === shouldPass) nPass++; else nFail++;
  print((ok === shouldPass ? 'PASS ' : 'FAIL ') + '| ' + label + ' | ' + (ok ? 'da chen' : 'bi chan: ' + msg));
}
const ids = ['K1_HL_999001', 'K2_HL_999002'];
E.resources.deleteMany({ _id: { $in: ids.concat(['K1_HL_999003', 'K1_HL_999004', 'K1_HL_999005', 'K1_HL_999006']) } });

print('--- Kich ban 6: zone ---');
expect('chen hoc lieu K1', E.resources, mk('K1_HL_999001', 'K1'), true);
expect('chen hoc lieu K2', E.resources, mk('K2_HL_999002', 'K2'), true);
ids.forEach(id => {
  const k = id.substring(0, 2), want = (k === 'K1') ? 'rsA' : 'rsB';
  const got = E.resources.find({ khoaId: k, _id: id }).explain('queryPlanner')
                .queryPlanner.winningPlan.shards.map(s => s.shardName);
  const ok = got.length === 1 && got[0] === want;
  if (ok) nPass++; else nFail++;
  print((ok ? 'PASS ' : 'FAIL ') + '| ' + id + ' -> shard ' + JSON.stringify(got) + ' (ky vong ["' + want + '"], truy van targeted 1 shard)');
});

print('--- Kich ban 5: toan ven ---');
expect('trung _id',                      E.resources, mk('K1_HL_999001', 'K1'), false);
expect('khoaId sai tien to (_id K1, khoaId K2)', E.resources, mk('K1_HL_999003', 'K2'), false);
expect('size <= 0',                      E.resources, mk('K1_HL_999004', 'K1', { file: Object.assign(mk('x', 'K1').file, { size: 0 }) }), false);
expect('type khong hop le',              E.resources, mk('K1_HL_999005', 'K1', { type: 'pdf' }), false);
expect('checksum khong phai sha256 hex 64', E.resources, mk('K1_HL_999006', 'K1', { file: Object.assign(mk('x', 'K1').file, { checksum: { algorithm: 'sha256', value: 'abc' } }) }), false);
expect('nguoidung vaiTro sai',           E.nguoidung, { _id: 'K1_GV_000099', hoTen: 'X', email: 'x@example.com', vaiTro: 'SV', khoaId: 'K1' }, false);
expect('nguoidung trung email',          E.nguoidung, { _id: 'K1_SV_000099', hoTen: 'X', email: 'nguyenvana@example.com', vaiTro: 'SV', khoaId: 'K1' }, false);
print('(courseId khong ton tai trong monhoc: kiem tra o tang ung dung - MongoDB khong co FK)');

E.resources.deleteMany({ _id: { $in: ids } });
print('Da don du lieu test.');
print('=== TONG KET: ' + nPass + ' PASS, ' + nFail + ' FAIL ===');
