import sqlite3
import pandas as pd

# ชื่อไฟล์ CSV และฐานข้อมูล
CSV_FILE = "camera_counts.csv"
DATABASE_FILE = "camera_counting.db"

# 1) อ่านข้อมูลจาก CSV
df = pd.read_csv(CSV_FILE)

# 2) ตรวจสอบว่ามีคอลัมน์ที่จำเป็นครบหรือไม่
required_columns = [
    "timestamp",
    "camera_id",
    "object_count",
    "qr_text"
]

missing_columns = [
    column for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(
        f"ไม่พบคอลัมน์ที่จำเป็น: {', '.join(missing_columns)}"
    )

# 3) แปลง timestamp เป็นวันเวลา
df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce"
)

# 4) ตรวจสอบและกรองข้อมูลที่ไม่ถูกต้อง
valid_df = df[
    df["timestamp"].notna()
    & df["camera_id"].notna()
    & (df["camera_id"].str.strip() != "")
    & df["object_count"].notna()
    & (df["object_count"] >= 0)
].copy()

# แปลง timestamp กลับเป็นข้อความในรูปแบบที่ SQLite อ่านง่าย
valid_df["timestamp"] = valid_df["timestamp"].dt.strftime(
    "%Y-%m-%d %H:%M:%S"
)

# ให้ QR ว่างเป็น NULL ใน Database
valid_df["qr_text"] = valid_df["qr_text"].fillna("")

# 5) เชื่อมต่อ SQLite
connection = sqlite3.connect(DATABASE_FILE)
cursor = connection.cursor()

# 6) สร้างตาราง หากยังไม่มี
cursor.execute("""
CREATE TABLE IF NOT EXISTS camera_detection_logs (
    detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    object_count INTEGER NOT NULL CHECK (object_count >= 0),
    qr_text TEXT
)
""")

# 7) ลบข้อมูลเก่าออกก่อน
# ใช้ตอนฝึก เพื่อไม่ให้รันซ้ำแล้วข้อมูลเพิ่มซ้ำ
cursor.execute("DELETE FROM camera_detection_logs")

# 8) เตรียมข้อมูลสำหรับ Insert
records = [
    (
        row["timestamp"],
        row["camera_id"],
        int(row["object_count"]),
        row["qr_text"] if row["qr_text"] != "" else None
    )
    for _, row in valid_df.iterrows()
]

# 9) บันทึกข้อมูลลงฐานข้อมูล
cursor.executemany("""
INSERT INTO camera_detection_logs (
    captured_at,
    camera_id,
    object_count,
    qr_text
)
VALUES (?, ?, ?, ?)
""", records)

# บันทึกการเปลี่ยนแปลง
connection.commit()

# 10) ตรวจสอบว่าบันทึกสำเร็จกี่แถว
cursor.execute("""
SELECT COUNT(*)
FROM camera_detection_logs
""")

total_rows = cursor.fetchone()[0]

print(f"อ่าน CSV ทั้งหมด: {len(df)} แถว")
print(f"ข้อมูลที่ผ่านการตรวจสอบ: {len(valid_df)} แถว")
print(f"บันทึกลง SQLite สำเร็จ: {total_rows} แถว")

# ปิดการเชื่อมต่อฐานข้อมูล
connection.close()