import sqlite3
import sys
from pathlib import Path

import pandas as pd

# ชื่อไฟล์ CSV และฐานข้อมูล
CSV_FILE = Path("camera_counts.csv")
DATABASE_FILE = Path("camera_counting.db")

# คอลัมน์ที่จำเป็นต้องมีในไฟล์ CSV
REQUIRED_COLUMNS = [
    "timestamp",
    "camera_id",
    "object_count",
    "qr_text",
]


def configure_console() -> None:
    """ตั้งค่า console ให้รองรับข้อความภาษาไทย และไม่หยุดทำงานเมื่อพิมพ์ไม่ได้"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def load_csv(file_path: Path) -> pd.DataFrame:
    """อ่านไฟล์ CSV พร้อมตรวจสอบว่าไฟล์มีอยู่จริงและอ่านได้"""
    if not file_path.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์ CSV: {file_path}")

    try:
        return pd.read_csv(file_path)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"ไฟล์ CSV ว่างเปล่า: {file_path}") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(
            f"ไฟล์ CSV มีรูปแบบไม่ถูกต้อง: {file_path} ({exc})"
        ) from exc
    except OSError as exc:
        raise OSError(f"ไม่สามารถอ่านไฟล์ CSV: {file_path} ({exc})") from exc


def validate_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    """ตรวจสอบความถูกต้องของข้อมูล และคืนเฉพาะแถวที่ใช้งานได้"""
    # 1) ตรวจสอบว่ามีคอลัมน์ที่จำเป็นครบหรือไม่
    missing_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"ไม่พบคอลัมน์ที่จำเป็น: {', '.join(missing_columns)}"
        )

    if df.empty:
        print("แจ้งเตือน: ไฟล์ CSV ไม่มีข้อมูล")
        return df.iloc[0:0]

    # 2) แปลงชนิดข้อมูล โดยค่าที่แปลงไม่ได้จะกลายเป็นค่าว่าง (NaN)
    cleaned = df.copy()
    cleaned["timestamp"] = pd.to_datetime(
        cleaned["timestamp"],
        errors="coerce"
    )
    cleaned["object_count"] = pd.to_numeric(
        cleaned["object_count"],
        errors="coerce"
    )
    cleaned["camera_id"] = (
        cleaned["camera_id"]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    cleaned["qr_text"] = (
        cleaned["qr_text"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # 3) สร้างเงื่อนไขระบุแถวที่ข้อมูลไม่ถูกต้อง
    invalid_timestamp = cleaned["timestamp"].isna()
    invalid_camera = cleaned["camera_id"].eq("")
    invalid_count = (
        cleaned["object_count"].isna()
        | (cleaned["object_count"] < 0)
        | (cleaned["object_count"] % 1 != 0)
    )

    invalid_mask = invalid_timestamp | invalid_camera | invalid_count

    # 4) สรุปเหตุผลของแต่ละแถวที่ถูกตัดออก เพื่อให้แก้ไขข้อมูลได้ง่าย
    if invalid_mask.any():
        reasons = pd.Series("", index=cleaned.index, dtype="object")
        reasons[invalid_timestamp] += "timestamp ไม่ถูกต้อง; "
        reasons[invalid_camera] += "camera_id ว่างหรือไม่ถูกต้อง; "
        reasons[invalid_count] += (
            "object_count ไม่ใช่จำนวนเต็มที่ไม่ติดลบ; "
        )

        rejected = cleaned.loc[invalid_mask].copy()
        rejected["reason"] = reasons[invalid_mask]

        print(f"พบข้อมูลไม่ถูกต้อง {len(rejected)} แถว (จะไม่ถูกบันทึก):")
        print(rejected.to_string(index=False))
    else:
        print("ไม่พบข้อมูลที่ไม่ถูกต้อง")

    # 5) คัดเฉพาะแถวที่ผ่านการตรวจสอบ
    valid_df = cleaned.loc[~invalid_mask].copy()

    # แปลง timestamp กลับเป็นข้อความในรูปแบบที่ SQLite อ่านง่าย
    valid_df["timestamp"] = valid_df["timestamp"].dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    return valid_df


def save_to_database(records: list, db_path: Path) -> int:
    """บันทึกข้อมูลลง SQLite แบบ transaction และคืนจำนวนแถวทั้งหมด"""
    connection = sqlite3.connect(db_path)

    try:
        cursor = connection.cursor()

        # สร้างตาราง หากยังไม่มี
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS camera_detection_logs (
            detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            object_count INTEGER NOT NULL CHECK (object_count >= 0),
            qr_text TEXT
        )
        """)

        # ลบข้อมูลเก่าออกก่อน
        # ใช้ตอนฝึก เพื่อไม่ให้รันซ้ำแล้วข้อมูลเพิ่มซ้ำ
        cursor.execute("DELETE FROM camera_detection_logs")

        # บันทึกข้อมูลลงฐานข้อมูล
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

        # ตรวจสอบว่าบันทึกสำเร็จกี่แถว
        cursor.execute("""
        SELECT COUNT(*)
        FROM camera_detection_logs
        """)

        return cursor.fetchone()[0]

    except sqlite3.Error:
        # ยกเลิกการเปลี่ยนแปลงทั้งหมดหากเกิดข้อผิดพลาด
        connection.rollback()
        raise
    finally:
        # ปิดการเชื่อมต่อฐานข้อมูลเสมอ
        connection.close()


def main() -> None:
    configure_console()

    try:
        # 1) อ่านข้อมูลจาก CSV
        df = load_csv(CSV_FILE)

        # 2) ตรวจสอบและกรองข้อมูลที่ไม่ถูกต้อง
        valid_df = validate_and_clean(df)

        if valid_df.empty:
            print("ไม่มีข้อมูลที่ผ่านการตรวจสอบ จึงไม่บันทึกลงฐานข้อมูล")
            return

        # 3) เตรียมข้อมูลสำหรับ Insert
        records = [
            (
                row["timestamp"],
                row["camera_id"],
                int(row["object_count"]),
                row["qr_text"] if row["qr_text"] != "" else None
            )
            for _, row in valid_df.iterrows()
        ]

        # 4) บันทึกข้อมูลลงฐานข้อมูล
        total_rows = save_to_database(records, DATABASE_FILE)

        print(f"อ่าน CSV ทั้งหมด: {len(df)} แถว")
        print(f"ข้อมูลที่ผ่านการตรวจสอบ: {len(valid_df)} แถว")
        print(f"บันทึกลง SQLite สำเร็จ: {total_rows} แถว")

    except (FileNotFoundError, ValueError, OSError, sqlite3.Error) as exc:
        print(f"ข้อผิดพลาด: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
