"""อ่าน QR Code จากไฟล์ภาพด้วย OpenCV QRCodeDetector

โครงสร้างการทำงานแยกส่วนกันชัดเจน:
- load_image(): โหลดและตรวจสอบไฟล์ภาพ
- read_qr(): อ่าน QR Code พร้อมลองหลายกลยุทธ์เมื่ออ่านรอบแรกไม่สำเร็จ

หมายเหตุด้านความปลอดภัย:
สคริปต์นี้ทำงานกับไฟล์ภาพเท่านั้น จึงไม่มี username/password ของ RTSP ฝังในโค้ด
หากภายหลังต้องต่อสตรีม RTSP ให้ดึงค่าจาก environment variable เช่น
RTSP_URL, RTSP_USERNAME, RTSP_PASSWORD แล้วประกอบ URL ตอน runtime
และห้าม commit ค่าจริงลงใน repository
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class QRResult:
    """ผลลัพธ์การอ่าน QR Code"""

    text: str | None
    points: np.ndarray | None
    attempts: int
    strategy: str | None

    @property
    def success(self) -> bool:
        return self.text is not None


def configure_console() -> None:
    """ตั้งค่า console ให้รองรับข้อความภาษาไทย และไม่หยุดทำงานเมื่อพิมพ์ไม่ได้"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def load_image(file_path: Path) -> np.ndarray:
    """โหลดภาพจากไฟล์ และตรวจสอบว่าไฟล์มีอยู่จริงและอ่านได้"""
    if not file_path.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์ภาพ: {file_path}")

    if not file_path.is_file():
        raise IsADirectoryError(f"พาธที่ระบุไม่ใช่ไฟล์: {file_path}")

    try:
        # ใช้ np.fromfile + imdecode เพื่อรองรับพาธภาษาไทยบน Windows
        buffer = np.fromfile(str(file_path), dtype=np.uint8)
    except OSError as exc:
        raise OSError(
            f"ไม่สามารถอ่านไฟล์ภาพ: {file_path} ({exc})"
        ) from exc

    if buffer.size == 0:
        raise ValueError(f"ไฟล์ภาพว่างเปล่า: {file_path}")

    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(
            f"ไม่สามารถถอดรหัสไฟล์ภาพได้ (ไฟล์เสียหรือไม่ใช่รูปแบบภาพ): {file_path}"
        )

    return image


def build_strategies(
    image: np.ndarray,
    upscale: float,
    try_rotations: bool,
) -> list[tuple[str, np.ndarray]]:
    """สร้างภาพหลายรูปแบบเพื่อให้โอกาสอ่าน QR สำเร็จสูงขึ้น"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    strategies: list[tuple[str, np.ndarray]] = [
        ("original", image),
        ("grayscale", gray),
    ]

    if upscale > 1.0:
        # ขยายภาพช่วยกรณี QR มีขนาดเล็กมาก
        strategies.append((
            f"grayscale x{upscale:g}",
            cv2.resize(
                gray,
                None,
                fx=upscale,
                fy=upscale,
                interpolation=cv2.INTER_CUBIC,
            ),
        ))
        strategies.append((
            f"original x{upscale:g}",
            cv2.resize(
                image,
                None,
                fx=upscale,
                fy=upscale,
                interpolation=cv2.INTER_CUBIC,
            ),
        ))

    if try_rotations:
        rotations = [
            ("90", cv2.ROTATE_90_CLOCKWISE),
            ("180", cv2.ROTATE_180),
            ("270", cv2.ROTATE_90_COUNTERCLOCKWISE),
        ]
        rotated_strategies = [
            (f"{name} rotate {angle}", cv2.rotate(candidate, rotate_code))
            for name, candidate in strategies
            for angle, rotate_code in rotations
        ]
        strategies.extend(rotated_strategies)

    return strategies


def read_qr(
    image: np.ndarray,
    upscale: float = 2.0,
    try_rotations: bool = True,
    detector: cv2.QRCodeDetector | None = None,
    debug: bool = False,
) -> QRResult:
    """อ่าน QR Code จากภาพ โดยลองหลายกลยุทธ์หากอ่านรอบแรกไม่สำเร็จ"""
    if image is None or image.size == 0:
        raise ValueError("ภาพว่างเปล่า ไม่สามารถอ่าน QR Code ได้")

    if upscale < 1.0:
        raise ValueError("ค่า upscale ต้องมีค่าตั้งแต่ 1.0 ขึ้นไป")

    detector = detector or cv2.QRCodeDetector()
    attempts = 0

    for name, candidate in build_strategies(
        image,
        upscale=upscale,
        try_rotations=try_rotations,
    ):
        attempts += 1
        decoded_text, points, _ = detector.detectAndDecode(candidate)
        decoded_text = (decoded_text or "").strip()

        if debug:
            status = "OK" if decoded_text else "not found"
            print(f"[{attempts:02d}] {name}: {status}")

        if decoded_text:
            return QRResult(
                text=decoded_text,
                points=points,
                attempts=attempts,
                strategy=name,
            )

    return QRResult(
        text=None,
        points=None,
        attempts=attempts,
        strategy=None,
    )


def save_annotated_image(
    image: np.ndarray,
    result: QRResult,
    file_path: Path,
) -> None:
    """บันทึกภาพพร้อมกรอบตำแหน่ง QR Code ที่ตรวจพบ"""
    annotated = image.copy()

    if result.points is not None:
        points = result.points.astype(int).reshape(-1, 1, 2)
        thickness = max(2, min(image.shape[:2]) // 300)
        cv2.polylines(
            annotated,
            [points],
            isClosed=True,
            color=(0, 200, 0),
            thickness=thickness,
        )

    suffix = file_path.suffix or ".png"
    success, buffer = cv2.imencode(suffix, annotated)
    if not success:
        raise ValueError(f"ไม่สามารถเข้ารหัสภาพเพื่อบันทึก: {file_path}")

    try:
        buffer.tofile(str(file_path))
    except OSError as exc:
        raise OSError(
            f"ไม่สามารถบันทึกไฟล์ภาพ: {file_path} ({exc})"
        ) from exc


def parse_args():
    """อ่านพารามิเตอร์จาก command line"""
    import argparse

    parser = argparse.ArgumentParser(
        description="อ่าน QR Code จากไฟล์ภาพด้วย OpenCV QRCodeDetector"
    )
    parser.add_argument("image", type=Path, help="พาธของไฟล์ภาพ")
    parser.add_argument(
        "--upscale",
        type=float,
        default=2.0,
        help="อัตราขยายภาพสำหรับ QR ขนาดเล็ก (ค่าเริ่มต้น: 2.0)",
    )
    parser.add_argument(
        "--no-rotate",
        action="store_true",
        help="ไม่ต้องลองหมุนภาพ 90/180/270 องศา",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="แสดงผลการลองแต่ละกลยุทธ์",
    )
    parser.add_argument(
        "--save-annotated",
        type=Path,
        help="บันทึกภาพที่วาดกรอบ QR Code ลงไฟล์นี้",
    )
    return parser.parse_args()


def main() -> None:
    configure_console()
    args = parse_args()

    try:
        image = load_image(args.image)
        result = read_qr(
            image,
            upscale=args.upscale,
            try_rotations=not args.no_rotate,
            debug=args.debug,
        )
    except (FileNotFoundError, IsADirectoryError, ValueError, OSError) as exc:
        print(f"ข้อผิดพลาด: {exc}", file=sys.stderr)
        sys.exit(1)

    if not result.success:
        print(
            f"อ่าน QR Code ไม่สำเร็จ (ลองไปทั้งสิ้น {result.attempts} รูปแบบ)",
            file=sys.stderr,
        )
        print("คำแนะนำ:", file=sys.stderr)
        print("- ลองเพิ่มขนาดภาพด้วย --upscale 3 หรือ 4", file=sys.stderr)
        print("- ตรวจว่าภาพไม่เบลอหรือมืดเกินไป", file=sys.stderr)
        print("- ถ่ายใหม่ให้เห็นมุมทั้งสี่ของ QR ชัดเจน", file=sys.stderr)
        print("- ใช้ --debug เพื่อดูผลของแต่ละรูปแบบ", file=sys.stderr)
        sys.exit(1)

    print(f"อ่าน QR Code สำเร็จ: {result.text}")
    print(f"รูปแบบที่ใช้: {result.strategy}")
    print(f"จำนวนครั้งที่ลอง: {result.attempts}")

    if args.save_annotated:
        try:
            save_annotated_image(image, result, args.save_annotated)
        except (ValueError, OSError) as exc:
            print(f"ข้อผิดพลาด: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"บันทึกภาพพร้อมกรอบ QR: {args.save_annotated}")


if __name__ == "__main__":
    main()
