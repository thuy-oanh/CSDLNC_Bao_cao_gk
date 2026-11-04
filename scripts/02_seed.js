// 02_seed.js - nap danh muc dung chung + nguoi dung mau (idempotent bang upsert)
const E = db.getSiblingDB('eduhub');

const khoa = [{ _id: 'K1', tenKhoa: 'Khoa 1' }, { _id: 'K2', tenKhoa: 'Khoa 2' }];   // thay bang ten khoa thuc te, GIU ma K1/K2
const monhoc = [
  { _id: 'CSDLNC', tenMon: 'Cơ sở dữ liệu nâng cao', soTinChi: 3 },
  { _id: 'LTHDT',  tenMon: 'Lập trình hướng đối tượng', soTinChi: 3 },     // soTinChi: chinh lai theo thuc te
  { _id: 'CTDLGT', tenMon: 'Cấu trúc dữ liệu và giải thuật', soTinChi: 3 }
];
const nguoidung = [
  { _id: 'K1_QT_000001', hoTen: 'Quản trị K1',     email: 'qt.k1@example.com',  vaiTro: 'QT', khoaId: 'K1' },
  { _id: 'K1_GV_000007', hoTen: 'Nguyễn Văn A',    email: 'nguyenvana@example.com', vaiTro: 'GV', khoaId: 'K1' },
  { _id: 'K1_SV_000001', hoTen: 'Lê Minh C',       email: 'leminhc@example.com', vaiTro: 'SV', khoaId: 'K1' },
  { _id: 'K2_QT_000001', hoTen: 'Quản trị K2',     email: 'qt.k2@example.com',  vaiTro: 'QT', khoaId: 'K2' },
  { _id: 'K2_GV_000003', hoTen: 'Trần Thị B',      email: 'tranthib@example.com', vaiTro: 'GV', khoaId: 'K2' },
  { _id: 'K2_SV_000001', hoTen: 'Phạm Quốc D',     email: 'phamquocd@example.com', vaiTro: 'SV', khoaId: 'K2' },
  { _id: 'K2_SV_000002', hoTen: 'Võ Thu E',        email: 'vothue@example.com', vaiTro: 'SV', khoaId: 'K2' }
];

khoa.forEach(d => E.khoa.replaceOne({ _id: d._id }, d, { upsert: true }));
monhoc.forEach(d => E.monhoc.replaceOne({ _id: d._id }, d, { upsert: true }));
// collection shard: filter upsert phai chua day du shard key
nguoidung.forEach(d => E.nguoidung.replaceOne({ _id: d._id, khoaId: d.khoaId }, d, { upsert: true }));

print('khoa=' + E.khoa.countDocuments({}) + ' monhoc=' + E.monhoc.countDocuments({}) + ' nguoidung=' + E.nguoidung.countDocuments({}));
