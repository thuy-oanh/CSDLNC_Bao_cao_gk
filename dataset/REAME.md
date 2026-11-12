HỆ THỐNG QUẢN LÝ KHO HỌC LIỆU TRỰC TUYẾN (EDUHUB)

1. Giới thiệu tổng quan

EduHub là hệ thống quản lý kho học liệu trực tuyến phân tán, ứng dụng MongoDB Sharded Cluster để lưu trữ hợp nhất dữ liệu có cấu trúc, bán cấu trúc và phi cấu trúc (nhị phân, văn bản) trong cùng một hệ quản trị CSDL. Hệ thống thực hiện phân mảnh dữ liệu theo Khoa (Zone Sharding), phân mảnh dẫn xuất cho các khối nhị phân (chunks) và tích hợp cơ chế kiểm chứng toàn vẹn nghiêm ngặt bằng mã băm SHA-256**.

## 2. Cấu trúc thư mục dự án

```text
EduHub/
│
├── docker-compose.yml         # Cấu hình cụm 5 container Docker (mongos, cfg, siteA, siteB, init)
├── dataset/                   # Thư mục chứa học liệu thực nghiệm (Khoa 1 và Khoa 2)
│   ├── K1/                    # Dữ liệu Khoa 1 (Physics / Cơ học cổ điển MIT)
│   └── K2/                    # Dữ liệu Khoa 2 (Môn KNTU - Kỹ năng thích ứng)
│
├── init/                      # Script tự động hóa khởi tạo cụm MongoDB
│   └── init.sh                # Kịch bản rs.initiate(), addShard, zone, validator
│
├── pipeline/                  # Tầng ứng dụng Python & các script kiểm chứng
│   ├── .venv/                 # Môi trường ảo Python (Virtual Environment)
│   ├── eduhub.py              # Thư viện lõi xử lý kết nối, ingestion, verify, download
│   ├── run_ingest.py          # Script nạp học liệu tự động (hỗ trợ --clean)
│   ├── run_verify.py          # Script kiểm định toàn vẹn 3 trạng thái (KHOP, KHONG_KHOP, ...)
│   ├── run_download.py        # Script tải xuống và giải mã tệp từ CSDL
│   └── requirements.txt       # Danh sách thư viện Python phụ thuộc
│
├── scripts/                   # Các kịch bản JavaScript chạy trực tiếp trên MongoDB
│   ├── 01_cluster.js          # Cấu hình cluster và zone sharding
│   ├── 02_seed.js             # Khởi tạo danh mục dùng chung (khoa, monhoc, nguoidung)
│   └── 03_integrity_test.js   # Kịch bản kiểm thử ràng buộc toàn vẹn Schema Validator (22 PASS)
│
└── minh_chung/                # Thư mục lưu trữ log và ảnh chụp màn hình minh chứng
    ├── anh/                   # Hình ảnh kết quả thực nghiệm (.png)
    └── log_*.txt              # Các tệp log thực thi pipeline
```

## 3. Yêu cầu hệ thống và Công cụ chuẩn bị

* **Hệ điều hành:** Windows 10/11 (chạy qua Git Bash hoặc PowerShell) hoặc Linux/macOS.
* **Công cụ cốt lõi:**
  * Docker & Docker Compose (để chạy cụm MongoDB phân tán).
  * Python 3.10 trở lên.
  * FFmpeg / FFprobe (bắt buộc cài đặt để trích xuất thông số video tự động).

## 4. Hướng dẫn Cài đặt và Cấu hình chi tiết

### Bước 1: Khởi động cụm MongoDB Sharded Cluster (Docker)

1. Mở cửa sổ terminal (Git Bash hoặc PowerShell) tại thư mục gốc của dự án (`EduHub/`).
2. Khởi chạy toàn bộ cụm 5 container ở chế độ nền:
   ```bash
   docker compose up -d
   ```
3. Kiểm tra trạng thái các container để đảm bảo mọi dịch vụ đang hoạt động ổn định:
   ```bash
   docker compose ps -a
   ```
   *(Hệ thống hiển thị `eduhub-cfg`, `eduhub-mongos`, `eduhub-siteA`, `eduhub-siteB` ở trạng thái `Up`, và `eduhub-init` ở trạng thái `Exited (0)` sau khi cấu hình xong).*

### Bước 2: Thiết lập môi trường Python và Thư viện phụ thuộc

1. Di chuyển vào thư mục `pipeline/`:
   ```bash
   cd pipeline
   ```
2. Kích hoạt môi trường ảo Python:
   * **Trên Windows PowerShell:**
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
     *(Nếu gặp lỗi script execution, chạy lệnh: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)*
   * **Trên Git Bash (Windows):**
     ```bash
     source .venv/Scripts/activate
     ```
   * **Trên Linux / macOS:**
     ```bash
     source .venv/bin/activate
     ```
3. Cài đặt các gói thư viện Python cần thiết:
   ```bash
   pip install -r requirements.txt
   ```
4. Cài đặt công cụ trích xuất thông số media `ffmpeg` (trên Windows thông qua winget):
   ```powershell
   winget install Gyan.FFmpeg
   ```

---

## 5. Hướng dẫn Vận hành và Kiểm chứng Thực nghiệm

> **LƯU Ý QUAN TRỌNG (Xử lý sự cố E11000):** 
> Nếu khi nạp dữ liệu phát sinh lỗi `duplicate key error collection: eduhub.resources index: idx_unique_checksum`, hãy xóa chỉ mục xung đột cũ bằng lệnh sau trước khi chạy nạp:
> ```bash
> docker compose exec -it mongos mongosh eduhub --eval "db.resources.dropIndex('idx_unique_checksum')"
> ```

### 1. Chạy quy trình nạp học liệu tự động (Ingestion Pipeline)
Đảm bảo bạn đang đứng ở thư mục `pipeline/` và đã kích hoạt môi trường ảo (`.venv`):
```bash
python run_ingest.py --clean
```
* **Kết quả kỳ vọng:** In ra màn hình log 6/6 học liệu đạt trạng thái `OK`, kiểm tra toàn vẹn đạt `KHOP`, với dòng tổng kết: `# Tong ket: 6 OK, 0 trung, 0 loi`.

### 2. Chạy kịch bản kiểm chứng toàn vẹn dữ liệu (`verify_file`)
Kiểm chứng đối soát toàn bộ học liệu thật và chạy kịch bản giả lập lỗi (sửa checksum, xóa chunk):
```bash
python run_verify.py
```
* **Kết quả kỳ vọng:** Hiển thị danh sách 6 học liệu đạt `KHOP`, và các ca giả lập trả về đúng trạng thái `KHONG_KHOP`, `KHONG_THE_KIEM_TRA` trước khi khôi phục về `KHOP`.

### 3. Kiểm chứng tải xuống và lắp ráp chunk ra đĩa
Tải và ghép lại tệp video 158 chunks của Khoa 1:
```bash
python run_download.py K1_HL_000001
```
* **Kết quả kỳ vọng:** Xuất thành công tệp `Classical_Mechanics_Gravity.mp4` vào thư mục `downloads/` với trạng thái `KHOP`.

### 4. Kiểm chứng khả năng chịu lỗi cục bộ (Dừng `siteB`)
1. Lùi về thư mục gốc của dự án từ thư mục pipeline/:
  
   cd ..
2. Dừng container Shard B (siteB) để mô phỏng sự cố mất kết nối:
docker compose stop siteB
3. Chạy trực tiếp lệnh kiểm chứng khoanh vùng dữ liệu Khoa 2 (do bạn vẫn đang đứng ở thư mục gốc hoặc có thể di chuyển lại pipeline/ nếu cần:
cd pipeline
python run_verify.py --k2-only  

   *(Xác nhận dữ liệu phân vùng Khoa 2 vẫn đáp ứng kiểm định nhờ tính độc lập phân vùng).*
4. Lùi về thư mục gốc và khôi phục lại cụm container sau khi kiểm chứng xong:
   
   cd ..
   docker compose start siteB

## 6. Tổng kết Minh chứng
Toàn bộ kết quả thực thi, tệp log chi tiết (`log_*.txt`) được lưu tự động trong thư mục **`minh_chung/`** phục vụ cho báo cáo giữa kỳ.