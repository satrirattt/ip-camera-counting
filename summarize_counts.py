import sys
from pathlib import Path

import pandas as pd

# ไฟล์นำเข้าและไฟล์ผลลัพธ์
CSV_FILE = Path("camera_counts.csv")
OUTPUT_FILE = Path("product_summary.csv")

# คอลัมน์ที่จำเป็นต้องมีในไฟล์ CSV
REQUIRED_COLUMNS = ["timestamp", "object_count", "qr_text"]


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
    cleaned["qr_text"] = (
        cleaned["qr_text"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # 3) สร้างเงื่อนไขระบุแถวที่ข้อมูลไม่ถูกต้อง
    invalid_timestamp = cleaned["timestamp"].isna()
    invalid_count = (
        cleaned["object_count"].isna()
        | (cleaned["object_count"] < 0)
        | (cleaned["object_count"] % 1 != 0)
    )
    invalid_qr = cleaned["qr_text"].eq("")

    invalid_mask = invalid_timestamp | invalid_count | invalid_qr

    # 4) สรุปเหตุผลของแต่ละแถวที่ถูกตัดออก เพื่อให้แก้ไขข้อมูลได้ง่าย
    if invalid_mask.any():
        reasons = pd.Series("", index=cleaned.index, dtype="object")
        reasons[invalid_timestamp] += "timestamp ไม่ถูกต้อง; "
        reasons[invalid_count] += (
            "object_count ไม่ใช่จำนวนเต็มที่ไม่ติดลบ; "
        )
        reasons[invalid_qr] += "qr_text ว่างหรือไม่ถูกต้อง; "

        rejected = cleaned.loc[invalid_mask].copy()
        rejected["reason"] = reasons[invalid_mask]

        print(f"พบข้อมูลไม่ถูกต้อง {len(rejected)} แถว (จะไม่ถูกนำมาสรุป):")
        print(rejected.to_string(index=False))
    else:
        print("ไม่พบข้อมูลที่ไม่ถูกต้อง")

    # 5) คัดเฉพาะแถวที่ผ่านการตรวจสอบ
    return cleaned.loc[~invalid_mask].copy()


def summarize(valid_df: pd.DataFrame) -> pd.DataFrame:
    """สรุปจำนวนสินค้าตามรหัสที่อ่านจาก QR Code"""
    summary = (
        valid_df
        .groupby("qr_text", as_index=False)["object_count"]
        .sum()
        .sort_values("qr_text")
    )

    # เปลี่ยนชื่อคอลัมน์ให้อ่านง่าย
    return summary.rename(columns={
        "qr_text": "product_code",
        "object_count": "total_object_count"
    })


def save_summary(summary: pd.DataFrame, file_path: Path) -> None:
    """บันทึกไฟล์ผลสรุป พร้อมแจ้งข้อผิดพลาดหากเขียนไฟล์ไม่ได้"""
    try:
        summary.to_csv(
            file_path,
            index=False,
            encoding="utf-8-sig"
        )
    except OSError as exc:
        raise OSError(
            f"ไม่สามารถบันทึกไฟล์ผลสรุป: {file_path} ({exc})"
        ) from exc


def main() -> None:
    configure_console()

    try:
        # 1) อ่านข้อมูลจากไฟล์ CSV
        df = load_csv(CSV_FILE)

        # 2) แสดงข้อมูลต้นฉบับ
        print("=== ข้อมูลจาก CSV ===")
        print(df)

        # 3) ตรวจสอบค่าว่าง
        print("\n=== ตรวจสอบค่าว่าง ===")
        print(df.isnull().sum())

        # 4) ตรวจสอบและกรองข้อมูลที่ไม่ถูกต้อง
        valid_df = validate_and_clean(df)

        if valid_df.empty:
            print("ไม่มีข้อมูลที่ผ่านการตรวจสอบ จึงไม่สร้างไฟล์ผลสรุป")
            return

        # 5) สรุปจำนวนสินค้าตามรหัสที่อ่านจาก QR Code
        summary = summarize(valid_df)

        # 6) แสดงผลลัพธ์
        print("\n=== สรุปจำนวนสินค้าตามรหัส ===")
        print(summary)

        # 7) บันทึกไฟล์ผลสรุป
        save_summary(summary, OUTPUT_FILE)

        print(f"\nบันทึกผลเรียบร้อย: {OUTPUT_FILE}")

    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"ข้อผิดพลาด: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
