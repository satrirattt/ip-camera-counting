import argparse
import sys
from pathlib import Path

import pandas as pd

# ไฟล์เริ่มต้นสำหรับนำเข้าและส่งออก
DEFAULT_INPUT_FILE = Path("camera_counts.csv")
DEFAULT_OUTPUT_FILE = Path("camera_counts_clean.csv")

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


def parse_args() -> argparse.Namespace:
    """รับพารามิเตอร์ไฟล์เข้า/ออกจาก command line"""
    parser = argparse.ArgumentParser(
        description="ทำความสะอาดข้อมูลการนับสินค้าจากไฟล์ CSV"
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help=f"ไฟล์ CSV ต้นฉบับ (ค่าเริ่มต้น: {DEFAULT_INPUT_FILE})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help=f"ไฟล์ CSV ผลลัพธ์ (ค่าเริ่มต้น: {DEFAULT_OUTPUT_FILE})",
    )
    parser.add_argument(
        "--drop-missing-qr",
        action="store_true",
        help="ลบแถวที่ไม่มีรหัส QR ออกด้วย",
    )
    return parser.parse_args()


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


def clean_data(
    df: pd.DataFrame,
    drop_missing_qr: bool = False
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """ทำความสะอาดข้อมูล และคืน (ข้อมูลที่สะอาด, แถวที่ถูกลบ, จำนวนแถวซ้ำ)"""
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
        return df.reindex(columns=REQUIRED_COLUMNS), df, 0

    cleaned = df.copy()

    # 2) ตัดช่องว่างหัว-ท้าย และปรับ camera_id เป็นตัวพิมพ์ใหญ่
    cleaned["camera_id"] = (
        cleaned["camera_id"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )
    cleaned["qr_text"] = (
        cleaned["qr_text"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # 3) แปลงชนิดข้อมูล โดยค่าที่แปลงไม่ได้จะกลายเป็นค่าว่าง (NaN)
    cleaned["timestamp"] = pd.to_datetime(
        cleaned["timestamp"],
        errors="coerce"
    )
    cleaned["object_count"] = pd.to_numeric(
        cleaned["object_count"],
        errors="coerce"
    )

    # 4) สร้างเงื่อนไขระบุแถวที่ข้อมูลไม่ถูกต้อง
    invalid_timestamp = cleaned["timestamp"].isna()
    invalid_camera = cleaned["camera_id"].eq("")
    invalid_count = (
        cleaned["object_count"].isna()
        | (cleaned["object_count"] < 0)
        | (cleaned["object_count"] % 1 != 0)
    )
    missing_qr = cleaned["qr_text"].eq("")

    invalid_mask = invalid_timestamp | invalid_camera | invalid_count
    if drop_missing_qr:
        invalid_mask = invalid_mask | missing_qr

    # 5) สรุปเหตุผลของแต่ละแถวที่ถูกลบ เพื่อให้แก้ไขต้นฉบับได้ง่าย
    reasons = pd.Series("", index=cleaned.index, dtype="object")
    reasons[invalid_timestamp] += "timestamp ไม่ถูกต้อง; "
    reasons[invalid_camera] += "camera_id ว่างหรือไม่ถูกต้อง; "
    reasons[invalid_count] += "object_count ไม่ใช่จำนวนเต็มที่ไม่ติดลบ; "
    if drop_missing_qr:
        reasons[missing_qr] += "qr_text ว่างหรือไม่ถูกต้อง; "

    removed = cleaned.loc[invalid_mask].copy()
    if not removed.empty:
        removed["reason"] = reasons[invalid_mask]
    else:
        removed = removed.reindex(columns=[*REQUIRED_COLUMNS, "reason"])

    # 6) คัดเฉพาะแถวที่ผ่านการตรวจสอบ
    cleaned = cleaned.loc[~invalid_mask].copy()

    # 7) จัดรูปแบบวันเวลาให้เป็นมาตรฐานเดียวกัน
    cleaned["timestamp"] = cleaned["timestamp"].dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # 8) ลบแถวที่ซ้ำกันทุกคอลัมน์
    before_dedup = len(cleaned)
    cleaned = (
        cleaned[REQUIRED_COLUMNS]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    duplicates_removed = before_dedup - len(cleaned)

    return cleaned, removed, duplicates_removed


def save_csv(df: pd.DataFrame, file_path: Path) -> None:
    """บันทึกไฟล์ CSV พร้อมแจ้งข้อผิดพลาดหากเขียนไฟล์ไม่ได้"""
    try:
        df.to_csv(
            file_path,
            index=False,
            encoding="utf-8-sig"
        )
    except OSError as exc:
        raise OSError(
            f"ไม่สามารถบันทึกไฟล์ผลลัพธ์: {file_path} ({exc})"
        ) from exc


def main() -> None:
    configure_console()
    args = parse_args()

    try:
        # 1) อ่านข้อมูลจากไฟล์ CSV
        df = load_csv(args.input)

        # 2) ทำความสะอาดข้อมูล
        cleaned, removed, duplicates_removed = clean_data(
            df,
            drop_missing_qr=args.drop_missing_qr
        )

        # 3) แสดงรายละเอียดแถวที่ถูกลบ
        if not removed.empty:
            print(f"ลบข้อมูลไม่ถูกต้อง {len(removed)} แถว:")
            print(removed.to_string(index=False))
        else:
            print("ไม่พบข้อมูลที่ไม่ถูกต้อง")

        if duplicates_removed:
            print(f"ลบข้อมูลซ้ำ {duplicates_removed} แถว")

        # 4) แจ้งจำนวนแถวที่ยังไม่มีรหัส QR (ไม่ได้ถูกลบ)
        if not args.drop_missing_qr:
            missing_qr_rows = int(cleaned["qr_text"].eq("").sum())
            if missing_qr_rows:
                print(
                    f"แจ้งเตือน: ยังมี {missing_qr_rows} แถวที่ไม่มีรหัส QR "
                    "(ใช้ --drop-missing-qr เพื่อลบ)"
                )

        # 5) บันทึกผลลัพธ์
        save_csv(cleaned, args.output)

        print(f"\nก่อนทำความสะอาด: {len(df)} แถว")
        print(f"หลังทำความสะอาด: {len(cleaned)} แถว")
        print(f"บันทึกผลเรียบร้อย: {args.output}")

    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"ข้อผิดพลาด: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
