"""
setup_template.py
-----------------
Tạo file Excel mẫu cho thông số dây dẫn của đường dây 220kV Tháp Chàm - Vĩnh Tân.

Chạy lệnh:
    python setup_template.py

Sau đó mở file  data/conductor_params.xlsx  và điền thông số thực tế.

Dây ACSR-400 (RABBIT) và các loại phổ biến ở lưới 220kV Việt Nam đã được
điền sẵn một ví dụ – hãy kiểm tra và chỉnh lại theo hồ sơ đường dây thực tế.
"""

import os
import sys
import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter

# Thiết lập UTF-8 cho console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from core.config import CONDUCTOR_PARAMS_XLSX as OUTPUT_PATH

# ── Định nghĩa cột ─────────────────────────────────────────────────────────
COLUMNS = [
    ("line_name",                   "Tên đường dây"),
    ("conductor_type",              "Loại dây dẫn"),
    ("diameter_mm",                 "Đường kính tổng [mm]"),
    ("resistance_25C_ohm_per_km",   "Điện trở AC tại 25°C [Ω/km]"),
    ("resistance_75C_ohm_per_km",   "Điện trở AC tại 75°C [Ω/km]"),
    ("max_conductor_temp_C",        "Nhiệt độ tối đa cho phép [°C]"),
    ("emissivity",                  "Hệ số phát xạ ε [0–1]"),
    ("absorptivity",                "Hệ số hấp thụ α [0–1]"),
    ("voltage_kV",                  "Điện áp định mức [kV]"),
    ("nominal_rating_A",            "Dòng tải định mức SLR [A]"),
]

# ── Dữ liệu mẫu – dây ACSR-330 (loại phổ biến trên lưới 220kV VN) ─────────
# !! Vui lòng kiểm tra và thay bằng thông số thực tế từ hồ sơ đường dây !!
SAMPLE_DATA = {
    "line_name":                  "ThapCham_VinhTan_220kV",
    "conductor_type":             "ACSR-330/43",
    "diameter_mm":                23.1,
    "resistance_25C_ohm_per_km":  0.0888,
    "resistance_75C_ohm_per_km":  0.1060,
    "max_conductor_temp_C":       75.0,
    "emissivity":                 0.8,
    "absorptivity":               0.8,
    "voltage_kV":                 220.0,
    "nominal_rating_A":           680.0,
}

# ── Bảng tham khảo một số loại dây ACSR phổ biến (chỉ để tham khảo) ──────
REFERENCE_TABLE = [
    # conductor_type, diameter_mm, R_25C Ω/km, R_75C Ω/km, rating_A (typical)
    ("ACSR-240/32",   21.6, 0.1188, 0.1421, 590),
    ("ACSR-330/43",   23.1, 0.0888, 0.1060, 680),
    ("ACSR-400/51",   27.0, 0.0719, 0.0859, 820),
    ("ACSR-500/45",   30.6, 0.0576, 0.0687, 950),
    ("ACSR-600/72",   33.9, 0.0492, 0.0588, 1080),
]


def _header_style():
    return {
        "font":      Font(bold=True, color="FFFFFF", size=10),
        "fill":      PatternFill("solid", fgColor="1565C0"),
        "alignment": Alignment(horizontal="center", vertical="center",
                               wrap_text=True),
        "border":    Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"),
        ),
    }


def _cell_style():
    return {
        "alignment": Alignment(horizontal="center", vertical="center"),
        "border":    Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"),
        ),
    }


def create_template(output_path: str = OUTPUT_PATH) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    wb = openpyxl.Workbook()

    # ── Sheet 1: conductor_params ──────────────────────────────────────────
    ws = wb.active
    ws.title = "conductor_params"

    hs = _header_style()
    cs = _cell_style()

    # Tiêu đề cột
    for col_idx, (field, label) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=label)
        cell.font      = hs["font"]
        cell.fill      = hs["fill"]
        cell.alignment = hs["alignment"]
        cell.border    = hs["border"]

    # Hàng 2: tên kỹ thuật của cột (để code đọc)
    for col_idx, (field, _) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=2, column=col_idx, value=field)
        cell.font      = Font(italic=True, color="555555", size=9)
        cell.alignment = Alignment(horizontal="center")
        cell.border    = cs["border"]

    # Hàng 3: ghi chú đơn vị
    NOTES = ["", "", "mm", "Ω/km", "Ω/km", "°C", "0–1", "0–1", "kV", "A"]
    for col_idx, note in enumerate(NOTES, start=1):
        cell = ws.cell(row=3, column=col_idx, value=f"[{note}]" if note else "")
        cell.font      = Font(italic=True, color="888888", size=9)
        cell.alignment = Alignment(horizontal="center")
        cell.border    = cs["border"]

    # Hàng 4: dữ liệu mẫu
    for col_idx, (field, _) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=4, column=col_idx, value=SAMPLE_DATA[field])
        cell.alignment = cs["alignment"]
        cell.border    = cs["border"]

    # Điều chỉnh độ rộng cột
    col_widths = [28, 18, 20, 26, 26, 26, 18, 18, 20, 24]
    for col_idx, w in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = w

    ws.row_dimensions[1].height = 30
    ws.row_dimensions[4].height = 20

    ws.freeze_panes = "A4"

    # ── Sheet 2: reference ─────────────────────────────────────────────────
    ws2 = wb.create_sheet("reference_conductors")
    ws2.append(["Loại dây", "Đường kính [mm]", "R_25°C [Ω/km]",
                "R_75°C [Ω/km]", "Dòng tải điển hình [A]"])
    for row in REFERENCE_TABLE:
        ws2.append(list(row))

    ws2["A1"].font = Font(bold=True)
    ws2.column_dimensions["A"].width = 18

    # ── Sheet 3: instructions ──────────────────────────────────────────────
    ws3 = wb.create_sheet("huong_dan")
    instructions = [
        ["HƯỚNG DẪN SỬ DỤNG FILE THÔNG SỐ DÂY DẪN"],
        [],
        ["1. Vào sheet 'conductor_params' và điền thông số thực tế vào hàng số 4."],
        ["2. Lấy thông số từ: hồ sơ lắp đặt đường dây, catalogue dây, hoặc EVN NPT."],
        ["3. Đường kính phải là đường kính NGOÀI của dây tổng hợp (mm)."],
        ["4. Điện trở AC phải đo ở tần số 50 Hz (lưới điện VN)."],
        ["5. Nếu không có R_25C, tính ngược từ R_75C: R_25C ≈ R_75C / 1.195."],
        ["6. Nhiệt độ tối đa 75°C là tiêu chuẩn chung cho ACSR theo IEEE 738."],
        ["   EVN NPT có thể dùng 90°C hoặc 100°C – kiểm tra hồ sơ kỹ thuật."],
        ["7. emissivity & absorptivity: dây mới = 0.5, dây cũ/oxy hoá = 0.7–0.9."],
        ["8. nominal_rating_A: dòng tải định mức theo hồ sơ gốc, dùng để so sánh."],
        [],
        ["Liên hệ hỗ trợ kỹ thuật: ghi chú tại đây nếu cần."],
    ]
    for row_data in instructions:
        ws3.append(row_data)
    ws3["A1"].font = Font(bold=True, size=12, color="1565C0")
    ws3.column_dimensions["A"].width = 75

    wb.save(output_path)
    print(f"\n✅ Đã tạo file mẫu: {output_path}")
    print("   → Mở file và điền thông số thực tế của dây dẫn vào hàng 4 của sheet 'conductor_params'.\n")


if __name__ == "__main__":
    create_template()
