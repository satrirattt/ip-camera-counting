import sqlite3
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

BASE_DIR = Path(__file__).resolve().parent
CLEAN_CSV = BASE_DIR / "camera_counts_clean.csv"
DATABASE_FILE = BASE_DIR / "camera_counting.db"

ACCENT = "#6366F1"
ACCENT_CYAN = "#06B6D4"
ACCENT_VIOLET = "#8B5CF6"

st.set_page_config(
    page_title="IP Camera Counting Dashboard",
    layout="wide",
)

CUSTOM_CSS = """
<style>
:root {
    --ink: #0F172A;
    --muted: #64748B;
    --line: #E2E8F0;
    --card: #FFFFFF;
}
html, body, [class*="css"] {
    font-family: "Segoe UI", "Noto Sans Thai", sans-serif;
}
.stApp {
    background:
        radial-gradient(1000px 520px at 8% -10%, #EEF2FF 0%, rgba(238,242,255,0) 55%),
        radial-gradient(900px 500px at 100% 0%, #ECFEFF 0%, rgba(236,254,255,0) 50%),
        #F8FAFC;
}
.block-container {
    max-width: 1400px;
    padding-top: 1.6rem;
    padding-bottom: 3rem;
}
section[data-testid="stSidebar"] > div {
    background: #FFFFFF;
    border-right: 1px solid var(--line);
}
.hero {
    background: linear-gradient(120deg, #4F46E5 0%, #6366F1 45%, #06B6D4 100%);
    border-radius: 22px;
    padding: 28px 32px;
    color: #FFFFFF;
    box-shadow: 0 18px 40px rgba(79, 70, 229, 0.22);
    margin-bottom: 22px;
}
.hero-eyebrow {
    font-size: 12px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    opacity: 0.8;
    font-weight: 600;
}
.hero-title {
    font-size: 34px;
    font-weight: 700;
    margin-top: 6px;
    letter-spacing: -0.02em;
}
.hero-sub {
    font-size: 15px;
    opacity: 0.9;
    margin-top: 6px;
}
.hero-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 18px;
}
.pill {
    background: rgba(255, 255, 255, 0.16);
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 12.5px;
}
.kpi-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 18px 20px;
    box-shadow: 0 6px 20px rgba(15, 23, 42, 0.05);
    position: relative;
    overflow: hidden;
    height: 100%;
}
.kpi-card::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
    background: var(--accent);
}
.kpi-label {
    color: var(--muted);
    font-size: 13px;
    font-weight: 600;
}
.kpi-value {
    color: var(--ink);
    font-size: 30px;
    font-weight: 700;
    line-height: 1.15;
    margin-top: 8px;
    letter-spacing: -0.02em;
}
.kpi-note {
    color: #94A3B8;
    font-size: 12px;
    margin-top: 4px;
}
.section-title {
    font-size: 17px;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: -0.01em;
}
.section-sub {
    font-size: 13px;
    color: var(--muted);
    margin-top: 2px;
    margin-bottom: 6px;
}
.sidebar-brand {
    font-size: 18px;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 2px;
}
.sidebar-sub {
    font-size: 12.5px;
    color: var(--muted);
    margin-bottom: 14px;
}
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px;
    border-color: var(--line);
}
[data-testid="stDataFrame"] {
    border: 1px solid var(--line);
    border-radius: 14px;
    overflow: hidden;
}
.stButton > button, .stDownloadButton > button {
    border-radius: 10px;
    font-weight: 600;
}
.stDownloadButton > button {
    background: #4F46E5;
    color: #FFFFFF;
    border: none;
}
.stDownloadButton > button:hover {
    background: #4338CA;
    color: #FFFFFF;
}
</style>
"""


@st.cache_data(show_spinner=False)
def load_from_csv(path: Path, modified_time: float) -> pd.DataFrame:
    """อ่านข้อมูลที่ทำความสะอาดแล้ว (modified_time ใช้ล้าง cache เมื่อไฟล์เปลี่ยน)"""
    df = pd.read_csv(path)
    return normalize_data(df)


def load_from_database(path: Path) -> pd.DataFrame:
    """อ่านข้อมูลสดจาก SQLite (ไม่ cache เพื่อให้เห็นข้อมูลใหม่ทันที)"""
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    try:
        df = pd.read_sql_query("""
        SELECT
            captured_at AS timestamp,
            camera_id,
            object_count,
            qr_text
        FROM camera_detection_logs
        ORDER BY captured_at
        """, connection)
    finally:
        connection.close()

    return normalize_data(df)


def normalize_data(df: pd.DataFrame) -> pd.DataFrame:
    """แปลงชนิดข้อมูลและคัดแถวที่ใช้งานใน dashboard ไม่ได้ออก"""
    required_columns = ["timestamp", "camera_id", "object_count", "qr_text"]
    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(
            f"ไม่พบคอลัมน์ที่จำเป็น: {', '.join(missing_columns)}"
        )

    cleaned = df[required_columns].copy()
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

    cleaned = cleaned.dropna(subset=["timestamp", "object_count"])
    cleaned = cleaned[
        cleaned["camera_id"].ne("")
        & (cleaned["object_count"] >= 0)
    ].copy()

    cleaned["object_count"] = cleaned["object_count"].astype(int)
    cleaned = cleaned.sort_values("timestamp").reset_index(drop=True)

    return cleaned


@st.cache_data(show_spinner=False)
def build_product_summary(df: pd.DataFrame) -> pd.DataFrame:
    """สรุปจำนวนสินค้าตามรหัส QR"""
    summary = (
        df[df["qr_text"].ne("")]
        .groupby("qr_text", as_index=False)["object_count"]
        .sum()
        .sort_values("object_count", ascending=False)
        .rename(columns={
            "qr_text": "product_code",
            "object_count": "total_object_count",
        })
    )
    return summary


@st.cache_data(show_spinner=False)
def build_camera_summary(df: pd.DataFrame) -> pd.DataFrame:
    """สรุปจำนวนสินค้าตามกล้อง"""
    summary = (
        df.groupby("camera_id", as_index=False)
        .agg(
            total_object_count=("object_count", "sum"),
            total_detection_records=("object_count", "size"),
        )
        .sort_values("camera_id")
    )
    return summary


def load_data() -> tuple[pd.DataFrame | None, str]:
    """อ่าน SQLite แบบสดก่อน หากใช้ไม่ได้จึง fallback ไปที่ไฟล์ CSV"""
    errors: list[str] = []

    if DATABASE_FILE.exists():
        try:
            df = load_from_database(DATABASE_FILE)
            return df, "SQLite (อัปเดตสด)"
        except (sqlite3.Error, ValueError, OSError) as exc:
            errors.append(f"SQLite: {exc}")

    if CLEAN_CSV.exists():
        try:
            df = load_from_csv(CLEAN_CSV, CLEAN_CSV.stat().st_mtime)
            return df, f"CSV: {CLEAN_CSV.name}"
        except (ValueError, OSError) as exc:
            errors.append(f"CSV: {exc}")

    if errors:
        raise ValueError(" | ".join(errors))

    return None, ""


def format_number(value: int) -> str:
    """จัดรูปแบบตัวเลขให้มีตัวคั่นหลักพัน"""
    return f"{value:,}"


def render_hero(source: str, df: pd.DataFrame) -> None:
    """แสดงส่วนหัวของ dashboard"""
    start_date = df["timestamp"].min().strftime("%d/%m/%Y")
    end_date = df["timestamp"].max().strftime("%d/%m/%Y")
    st.markdown(f"""
    <div class="hero">
        <div class="hero-eyebrow">IP Camera Analytics</div>
        <div class="hero-title">Counting Dashboard</div>
        <div class="hero-sub">
            สรุปผลการนับสินค้าจากข้อมูลที่ผ่านการทำความสะอาด
        </div>
        <div class="hero-meta">
            <span class="pill">แหล่งข้อมูล: {source}</span>
            <span class="pill">{format_number(len(df))} รายการ</span>
            <span class="pill">{start_date} - {end_date}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_kpi(
    column,
    label: str,
    value: str,
    note: str,
    accent: str,
) -> None:
    """แสดงการ์ดตัวเลขสรุป"""
    column.markdown(f"""
    <div class="kpi-card" style="--accent: {accent};">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-note">{note}</div>
    </div>
    """, unsafe_allow_html=True)


def render_section(title: str, subtitle: str) -> None:
    """แสดงหัวข้อของแต่ละส่วน"""
    st.markdown(f"""
    <div class="section-title">{title}</div>
    <div class="section-sub">{subtitle}</div>
    """, unsafe_allow_html=True)


def style_chart(chart: alt.Chart) -> alt.Chart:
    """ปรับรูปแบบกราฟให้เรียบและอ่านง่าย"""
    return (
        chart
        .configure_view(strokeWidth=0)
        .configure_axis(
            grid=True,
            gridColor="#EEF2F7",
            gridDash=[4, 4],
            domain=False,
            tickColor="#CBD5E1",
            labelColor="#64748B",
            labelFontSize=12,
            titleColor="#475569",
            titleFontSize=12,
            titleFontWeight="normal",
        )
        .configure_legend(disable=True)
    )


def build_product_chart(summary: pd.DataFrame) -> alt.Chart:
    """กราฟแท่งแนวนอนแสดงจำนวนสินค้าตามรหัส"""
    chart = alt.Chart(summary).mark_bar(
        color=ACCENT,
        cornerRadiusEnd=8,
        height=22,
    ).encode(
        x=alt.X(
            "total_object_count:Q",
            title="จำนวนสินค้า",
        ),
        y=alt.Y(
            "product_code:N",
            title=None,
            sort="-x",
            axis=alt.Axis(labelFontSize=12),
        ),
        tooltip=[
            alt.Tooltip("product_code:N", title="รหัสสินค้า"),
            alt.Tooltip(
                "total_object_count:Q",
                title="จำนวน",
                format=",",
            ),
        ],
    ).properties(height=max(260, 48 * len(summary)))

    return style_chart(chart)


def build_camera_chart(summary: pd.DataFrame) -> alt.Chart:
    """กราฟแท่งแสดงจำนวนสินค้าตามกล้อง"""
    chart = alt.Chart(summary).mark_bar(
        color=ACCENT_CYAN,
        cornerRadiusTopLeft=8,
        cornerRadiusTopRight=8,
        size=54,
    ).encode(
        x=alt.X(
            "camera_id:N",
            title=None,
            axis=alt.Axis(labelFontSize=12),
        ),
        y=alt.Y(
            "total_object_count:Q",
            title="จำนวนสินค้า",
        ),
        tooltip=[
            alt.Tooltip("camera_id:N", title="กล้อง"),
            alt.Tooltip(
                "total_object_count:Q",
                title="จำนวนสินค้า",
                format=",",
            ),
            alt.Tooltip(
                "total_detection_records:Q",
                title="รายการตรวจจับ",
                format=",",
            ),
        ],
    ).properties(height=320)

    return style_chart(chart)


def build_timeline_chart(timeline: pd.DataFrame) -> alt.Chart:
    """กราฟพื้นที่แสดงจำนวนสินค้าตามช่วงเวลา"""
    base = alt.Chart(timeline).encode(
        x=alt.X(
            "timestamp:T",
            title=None,
            axis=alt.Axis(format="%d %b %H:%M"),
        ),
        y=alt.Y(
            "total_object_count:Q",
            title="จำนวนสินค้า",
        ),
        tooltip=[
            alt.Tooltip(
                "timestamp:T",
                title="ช่วงเวลา",
                format="%d/%m/%Y %H:%M",
            ),
            alt.Tooltip(
                "total_object_count:Q",
                title="จำนวน",
                format=",",
            ),
        ],
    )

    chart = (
        base.mark_area(
            color=ACCENT_VIOLET,
            opacity=0.14,
            line=False,
        )
        + base.mark_line(
            color=ACCENT_VIOLET,
            strokeWidth=3,
        )
        + base.mark_circle(
            color="#FFFFFF",
            stroke=ACCENT_VIOLET,
            strokeWidth=2,
            size=60,
        )
    ).properties(height=300)

    return style_chart(chart)


def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    try:
        df, source = load_data()
    except (ValueError, OSError, sqlite3.Error) as exc:
        st.error(f"ไม่สามารถโหลดข้อมูลได้: {exc}")
        st.stop()

    if df is None:
        st.warning(
            "ไม่พบข้อมูล กรุณารัน 'python clean_data.py' "
            "หรือ 'python load_csv_to_sqlite.py' ก่อน"
        )
        st.stop()

    if df.empty:
        st.warning("ไฟล์ข้อมูลไม่มีแถวที่ใช้งานได้")
        st.stop()

    render_hero(source, df)

    st.sidebar.markdown("""
    <div class="sidebar-brand">ตัวกรองข้อมูล</div>
    <div class="sidebar-sub">ปรับมุมมองของ dashboard</div>
    """, unsafe_allow_html=True)

    auto_refresh = st.sidebar.toggle(
        "อัปเดตอัตโนมัติ",
        value=True,
        help="ดึงข้อมูลล่าสุดจาก SQLite ตามช่วงเวลาที่กำหนด",
    )
    refresh_seconds = st.sidebar.selectbox(
        "ความถี่ในการอัปเดต (วินาที)",
        options=[5, 10, 30, 60],
        index=1,
        disabled=not auto_refresh,
    )

    if auto_refresh:
        st_autorefresh(
            interval=refresh_seconds * 1000,
            key="dashboard_autorefresh",
        )

    if st.sidebar.button("โหลดข้อมูลใหม่", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.divider()

    camera_options = sorted(df["camera_id"].unique())
    selected_cameras = st.sidebar.multiselect(
        "กล้อง",
        options=camera_options,
        default=camera_options,
    )

    product_options = sorted(df.loc[df["qr_text"].ne(""), "qr_text"].unique())
    selected_products = st.sidebar.multiselect(
        "รหัสสินค้า (QR)",
        options=product_options,
        default=product_options,
    )

    min_date = df["timestamp"].min().date()
    max_date = df["timestamp"].max().date()
    if min_date == max_date:
        start_date = end_date = min_date
        st.sidebar.caption(f"วันที่: {min_date}")
    else:
        date_range = st.sidebar.date_input(
            "ช่วงวันที่",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = min_date, max_date

    hide_missing_qr = st.sidebar.checkbox(
        "ซ่อนแถวที่ไม่มีรหัส QR",
        value=False,
    )

    st.sidebar.divider()
    st.sidebar.caption(f"แหล่งข้อมูล: {source}")
    st.sidebar.caption(f"อัปเดตล่าสุด: {datetime.now():%H:%M:%S}")

    filtered = df[df["camera_id"].isin(selected_cameras)].copy()
    filtered = filtered[
        (filtered["timestamp"].dt.date >= start_date)
        & (filtered["timestamp"].dt.date <= end_date)
    ]

    if selected_products:
        filtered = filtered[
            filtered["qr_text"].isin(selected_products)
            | filtered["qr_text"].eq("")
        ]

    if hide_missing_qr:
        filtered = filtered[filtered["qr_text"].ne("")]

    if filtered.empty:
        st.info("ไม่พบข้อมูลตามตัวกรองที่เลือก")
        st.stop()

    total_objects = int(filtered["object_count"].sum())
    total_records = len(filtered)
    total_cameras = filtered["camera_id"].nunique()
    total_products = filtered.loc[
        filtered["qr_text"].ne(""), "qr_text"
    ].nunique()
    missing_qr = int(filtered["qr_text"].eq("").sum())

    kpi_columns = st.columns(5)
    render_kpi(
        kpi_columns[0],
        "จำนวนสินค้าทั้งหมด",
        format_number(total_objects),
        "ชิ้น",
        ACCENT,
    )
    render_kpi(
        kpi_columns[1],
        "รายการตรวจจับ",
        format_number(total_records),
        "แถวข้อมูล",
        ACCENT_CYAN,
    )
    render_kpi(
        kpi_columns[2],
        "กล้อง",
        format_number(total_cameras),
        "กล้องที่ใช้งาน",
        ACCENT_VIOLET,
    )
    render_kpi(
        kpi_columns[3],
        "รหัสสินค้า",
        format_number(total_products),
        "รหัสที่พบ",
        "#10B981",
    )
    render_kpi(
        kpi_columns[4],
        "รายการไม่มี QR",
        format_number(missing_qr),
        "ต้องตรวจสอบ",
        "#F59E0B",
    )

    st.write("")

    product_summary = build_product_summary(filtered)
    camera_summary = build_camera_summary(filtered)

    left, right = st.columns(2)

    with left:
        with st.container(border=True):
            render_section(
                "จำนวนสินค้าตามรหัส",
                "รวมจำนวนชิ้นของแต่ละรหัสที่อ่านได้จาก QR Code",
            )
            if product_summary.empty:
                st.info("ไม่มีข้อมูลรหัสสินค้า")
            else:
                st.altair_chart(
                    build_product_chart(product_summary),
                    width="stretch",
                )

    with right:
        with st.container(border=True):
            render_section(
                "จำนวนสินค้าตามกล้อง",
                "เปรียบเทียบปริมาณสินค้าที่ตรวจจับได้ในแต่ละกล้อง",
            )
            st.altair_chart(
                build_camera_chart(camera_summary),
                width="stretch",
            )

    with st.container(border=True):
        render_section(
            "จำนวนสินค้าตามช่วงเวลา",
            "แนวโน้มปริมาณสินค้าที่ตรวจจับได้ในแต่ละช่วงเวลา",
        )
        timeline = (
            filtered
            .assign(period=filtered["timestamp"].dt.floor("h"))
            .groupby("period", as_index=False)["object_count"]
            .sum()
            .rename(columns={
                "period": "timestamp",
                "object_count": "total_object_count",
            })
        )
        st.altair_chart(
            build_timeline_chart(timeline),
            width="stretch",
        )

    with st.container(border=True):
        render_section(
            "รายละเอียดข้อมูล",
            f"แสดง {format_number(total_records)} รายการตามตัวกรองที่เลือก",
        )
        display_columns = {
            "timestamp": "วันเวลา",
            "camera_id": "กล้อง",
            "object_count": "จำนวนสินค้า",
            "qr_text": "รหัสสินค้า",
        }
        st.dataframe(
            filtered[list(display_columns)]
            .rename(columns=display_columns)
            .sort_values("วันเวลา", ascending=False),
            width="stretch",
            hide_index=True,
            column_config={
                "วันเวลา": st.column_config.DatetimeColumn(
                    "วันเวลา",
                    format="DD/MM/YYYY HH:mm",
                ),
                "จำนวนสินค้า": st.column_config.NumberColumn(
                    "จำนวนสินค้า",
                    format="%d",
                ),
            },
        )

        st.download_button(
            "ดาวน์โหลดข้อมูลที่กรองแล้ว (CSV)",
            data=filtered.to_csv(index=False).encode("utf-8-sig"),
            file_name="camera_counts_filtered.csv",
            mime="text/csv",
        )

    st.caption("IP Camera Counting Dashboard")


if __name__ == "__main__":
    main()
