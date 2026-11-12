from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from faker import Faker
import random

# 1. Kết nối qua mongos (Thành viên 1 phải đang bật Docker)
client = MongoClient('mongodb://26.124.186.249:27017/')
db = client["eduhub"]
collection = db['resources']
fake = Faker()

# 2. HÀM TẠO DỮ LIỆU (1000 - 5000 docs)
def generate_data(num_docs=2000):
    print(f"Đang tạo {num_docs} documents...")
    docs = []
    for _ in range(num_docs):
        dept = random.choice(['K1', 'K2'])
        docs.append({
            "department": dept,
            "course": "CSDLNC" if dept == 'K1' else "CTDLGT",
            "file_type": random.choice(['pdf', 'pptx', 'mp4', 'png']),
            "author": fake.name(),
            "upload_time": fake.date_time_this_year(),
            "tags": [fake.word(), fake.word()],
            "content_text": fake.text(max_nb_chars=100),
            "checksum": fake.sha256()
        })
    collection.insert_many(docs)
    print("Tạo dữ liệu hoàn tất!")

# 3. HÀM CHẠY EXPLAIN CHO Q2, Q3, Q4, Q9
def run_queries(stage):
    print(f"\n--- THỐNG KÊ EXPLAIN ({stage} KHI CÓ INDEX) ---")
    
    # Q2: Tìm file PDF môn CSDLNC, sắp xếp mới nhất
    q2 = db.command("explain", {"find": "resources", "filter": {"course": "CSDLNC", "file_type": "pdf"}, "sort": {"upload_time": -1}}, verbosity="executionStats")
    print(f"[Q2] Time: {q2['executionStats']['executionTimeMillis']}ms | Docs Examined: {q2['executionStats']['totalDocsExamined']}")

    # Q3: Tìm kiếm Full-text (chỉ chạy được khi ĐÃ CÓ idx_text)
    if stage == "SAU":
        q3 = db.command("explain", {"find": "resources", "filter": {"$text": {"$search": "database"}}}, verbosity="executionStats")
        print(f"[Q3] Time: {q3['executionStats']['executionTimeMillis']}ms | Docs Examined: {q3['executionStats']['totalDocsExamined']}")

    # Q4: Tìm theo tag
    q4 = db.command("explain", {"find": "resources", "filter": {"tags": {"$in": ["data", "index"]}}}, verbosity="executionStats")
    print(f"[Q4] Time: {q4['executionStats']['executionTimeMillis']}ms | Docs Examined: {q4['executionStats']['totalDocsExamined']}")

    # Q9: Tìm tài liệu của tác giả cụ thể
    sample_author = collection.find_one()['author']
    q9 = db.command("explain", {"find": "resources", "filter": {"author": sample_author}, "sort": {"upload_time": -1}}, verbosity="executionStats")
    print(f"[Q9] Time: {q9['executionStats']['executionTimeMillis']}ms | Docs Examined: {q9['executionStats']['totalDocsExamined']}")

# 4. HÀM TẠO INDEX
def build_indexes():
    print("\nĐang tạo các Index trọng tâm...")
    # shard key (Thường TV1 tạo, TV3 có thể tạo index hỗ trợ)
    collection.create_index([("department", ASCENDING)])
    # idx_course_type_time
    collection.create_index([("course", 1), ("file_type", 1), ("upload_time", -1)], name="idx_course_type_time")
    # idx_text
    collection.create_index([("content_text", TEXT)], name="idx_text")
    # idx_tags
    collection.create_index([("tags", 1)], name="idx_tags")
    # idx_author_time
    collection.create_index([("author", 1), ("upload_time", -1)], name="idx_author_time")
    # Unique checksum (phải kèm shard key department để hợp lệ trên sharded cluster)
    collection.create_index([("department", 1), ("checksum", 1)], unique=True, name="idx_unique_checksum")
    print("Tạo Index hoàn tất!")

if __name__ == "__main__":
    # collection.drop() 
    # generate_data(5000) 
    
    run_queries("TRƯỚC") 
    build_indexes()      
    run_queries("SAU")