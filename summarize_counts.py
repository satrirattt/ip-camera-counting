import pandas as pd

# 1) อ่านข้อมูลจากไฟล์ CSV
df = pd.read_csv("camera_counts.csv")

# 2) แสดงข้อมูลต้นฉบับ
print("=== ข้อมูลจาก CSV ===")
print(df)

# 3) แปลง timestamp เป็นรูปแบบวันเวลา
df["timestamp"] = pd.to_datetime(df["timestamp"])

# 4) ตรวจสอบข้อมูลที่ไม่สมบูรณ์
print("\n=== ตรวจสอบค่าว่าง ===")
print(df.isnull().sum())

# 5) กรองเฉพาะรายการที่นับสินค้าได้ตั้งแต่ 0 ขึ้นไป
valid_df = df[
    (df["object_count"] >= 0)
    & (df["qr_text"].notna())
    & (df["qr_text"] != "")
].copy()

# 6) สรุปจำนวนสินค้าตามรหัสที่อ่านจาก QR Code
summary = (
    valid_df
    .groupby("qr_text", as_index=False)["object_count"]
    .sum()
    .sort_values("qr_text")
)

# 7) เปลี่ยนชื่อคอลัมน์ให้อ่านง่าย
summary = summary.rename(columns={
    "qr_text": "product_code",
    "object_count": "total_object_count"
})

# 8) แสดงผลลัพธ์
print("\n=== สรุปจำนวนสินค้าตามรหัส ===")
print(summary)

# 9) บันทึกไฟล์ผลสรุป
summary.to_csv(
    "product_summary.csv",
    index=False,
    encoding="utf-8-sig"
)

print("\nบันทึกผลเรียบร้อย: product_summary.csv")