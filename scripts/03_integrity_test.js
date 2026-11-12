// 03_integrity_test.js - kich ban 5 (toan ven) + 6 (zone / phan manh dan xuat), dung mon + tac gia cua dataset
// Chay (Git Bash):  MSYS_NO_PATHCONV=1 docker cp scripts/03_integrity_test.js eduhub-mongos:/tmp/t.js
//                   MSYS_NO_PATHCONV=1 docker compose exec -T mongos mongosh --quiet /tmp/t.js | tee log_toan_ven.txt
// (hoac chay collect_evidence.sh de lam tat ca). Test tu don du lieu thu (_id 999001-999009, khong dung du lieu that).
const E = db.getSiblingDB('eduhub');
const COURSE = { K1: 'Physics', K2: 'KNTU' };                      // thu muc cap 2 cua dataset
const AUTHOR = { K1: 'K1_GV_000007', K2: 'K2_GV_000003' };          // tac gia trong manifest.json
const SAMPLE = BinData(0, 'SGVsbG8=');

const mkFile = (over = {}) => Object.assign({
  name: 't.txt', extension: '.txt', mimeType: 'text/plain', size: 5, storage: 'embedded',
  checksum: { algorithm: 'sha256', value: 'a'.repeat(64) }, data: SAMPLE }, over);
const mk = (id, khoa, over = {}) => Object.assign({
  _id: id, khoaId: khoa, courseId: COURSE[khoa], type: 'lecture', title: 'Test', description: 'Test', caption: 'Test',
  tags: ['test'], author: { id: AUTHOR[khoa], name: 'Tester' }, access: { level: 'course', groups: [] },
  file: mkFile(), media: { pages: 1 }, content: { language: 'vi', text: 'noi dung thu' },
  status: 'ready', createdAt: new Date() }, over);
const mkChunk = (rid, khoa, n = 0, over = {}) =>
  Object.assign({ _id: rid + '#' + n, khoaId: khoa, resourceId: rid, n: n, data: SAMPLE }, over);

let nPass = 0, nFail = 0;
function report(ok, label, detail) {
  if (ok) nPass++; else nFail++;
  print((ok ? 'PASS ' : 'FAIL ') + '| ' + label + (detail ? ' | ' + detail : ''));
}
function expect(label, coll, doc, shouldPass) {
  let ok, msg = '';
  try { coll.insertOne(doc); ok = true; } catch (e) { ok = false; msg = (e.code || '') + ' ' + e.message.split('\n')[0]; }
  report(ok === shouldPass, label, ok ? 'da chen' : 'bi chan: ' + msg);
}
function expectShard(label, coll, filter, want) {
  const got = coll.find(filter).explain('queryPlanner').queryPlanner.winningPlan.shards.map(s => s.shardName);
  report(got.length === 1 && got[0] === want, label, 'shard ' + JSON.stringify(got) + ' (ky vong ["' + want + '"], targeted 1 shard)');
}

const RES_IDS = ['K1_HL_999001', 'K2_HL_999002', 'K1_HL_999003', 'K1_HL_999004', 'K1_HL_999005',
                 'K1_HL_999006', 'K1_HL_999007', 'K1_HL_999008', 'K1_HL_999009'];
function cleanup() {
  E.resource_chunks.deleteMany({ resourceId: { $in: RES_IDS } });
  E.resources.deleteMany({ _id: { $in: RES_IDS } });
}
cleanup();

print('--- Tien dieu kien cho dataset ---');
['Physics', 'KNTU'].forEach(c =>
  report(E.monhoc.countDocuments({ _id: c }) === 1, 'monhoc co courseId ' + c, 'pipeline TV2 lay courseId tu ten thu muc'));
['K1_GV_000007', 'K2_GV_000003'].forEach(u =>
  report(E.nguoidung.countDocuments({ _id: u, khoaId: u.substring(0, 2) }) === 1, 'nguoidung co tac gia ' + u, 'dung trong manifest.json'));

print('--- Kich ban 6: zone + phan manh dan xuat ---');
expect('chen hoc lieu K1 (' + COURSE.K1 + ')', E.resources, mk('K1_HL_999001', 'K1'), true);
expect('chen hoc lieu K2 (' + COURSE.K2 + ')', E.resources, mk('K2_HL_999002', 'K2'), true);
expect('chen chunk K1 cua hoc lieu K1', E.resource_chunks, mkChunk('K1_HL_999001', 'K1'), true);
expect('chen chunk K2 cua hoc lieu K2', E.resource_chunks, mkChunk('K2_HL_999002', 'K2'), true);
expectShard('resources K1_HL_999001', E.resources, { khoaId: 'K1', _id: 'K1_HL_999001' }, 'rsA');
expectShard('resources K2_HL_999002', E.resources, { khoaId: 'K2', _id: 'K2_HL_999002' }, 'rsB');
expectShard('resource_chunks cua K1 nam cung Site A voi hoc lieu cha', E.resource_chunks, { khoaId: 'K1', resourceId: 'K1_HL_999001' }, 'rsA');
expectShard('resource_chunks cua K2 nam cung Site B voi hoc lieu cha', E.resource_chunks, { khoaId: 'K2', resourceId: 'K2_HL_999002' }, 'rsB');

print('--- Kich ban 5: toan ven ---');
expect('trung _id',                                   E.resources, mk('K1_HL_999001', 'K1'), false);
expect('khoaId sai tien to (_id K1, khoaId K2)',      E.resources, mk('K1_HL_999003', 'K2'), false);
expect('size <= 0',                                   E.resources, mk('K1_HL_999004', 'K1', { file: mkFile({ size: 0 }) }), false);
expect('type khong hop le (pdf)',                     E.resources, mk('K1_HL_999005', 'K1', { type: 'pdf' }), false);
expect('checksum khong phai sha256 hex 64',           E.resources, mk('K1_HL_999006', 'K1', { file: mkFile({ checksum: { algorithm: 'sha256', value: 'abc' } }) }), false);
expect('content.text > 200 KB (van ban trich xuat)',  E.resources, mk('K1_HL_999007', 'K1', { content: { language: 'en', text: 'x'.repeat(200001) } }), false);
expect('tags khong phai mang',                        E.resources, mk('K1_HL_999008', 'K1', { tags: 'gravity' }), false);
expect('chunk sai tien to (_id K1, khoaId K2)',       E.resource_chunks, mkChunk('K1_HL_999001', 'K2', 1), false);
expect('nguoidung vaiTro sai',                        E.nguoidung, { _id: 'K1_GV_000099', hoTen: 'X', email: 'x@example.com', vaiTro: 'SV', khoaId: 'K1' }, false);
expect('nguoidung trung email',                       E.nguoidung, { _id: 'K1_SV_000099', hoTen: 'X', email: 'nguyenvana@example.com', vaiTro: 'SV', khoaId: 'K1' }, false);
if (E.resources.getIndexes().some(i => i.name === 'idx_dedup'))
  expect('trung checksum cung khoa + mon (idx_dedup)', E.resources, mk('K1_HL_999009', 'K1'), false);
else
  print('SKIP | trung checksum (idx_dedup): TV3 chua tao chi muc nay, pipeline TV2 van chong trung o tang ung dung');
print('(courseId khong ton tai trong monhoc: kiem tra o tang ung dung - MongoDB khong co FK)');

cleanup();
print('Da don du lieu test.');
print('=== TONG KET: ' + nPass + ' PASS, ' + nFail + ' FAIL ===');
