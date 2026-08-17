"""
core/config.py
--------------
Cấu hình đường dẫn, hằng số vật lý và thiết lập hệ tọa độ (CRS) cho dự án DLR
đường dây 220kV Tháp Chàm - Vĩnh Tân.
"""

import os
from pathlib import Path

# ── Đường dẫn thư mục gốc ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Thư mục dữ liệu & kết quả ──────────────────────────────────────────────
DATA_DIR = BASE_DIR / "data"
SHAPEFILE_DIR = DATA_DIR / "shapefile"
OUTPUTS_DIR = BASE_DIR / "outputs"
RATINGS_DIR = OUTPUTS_DIR / "ratings"
FIGURES_DIR = OUTPUTS_DIR / "figures"

# ── File mặc định ──────────────────────────────────────────────────────────
CONDUCTOR_PARAMS_XLSX = DATA_DIR / "conductor_params.xlsx"
DEFAULT_LINE_SHAPEFILE = SHAPEFILE_DIR / "ThapCham_VinhTan_220kV.shp"

# ── Hằng số vật lý & Địa lý ───────────────────────────────────────────────
C2K = 273.15                    # 0°C sang Kelvin [K]
STEFAN_BOLTZMANN = 5.67e-8      # Hằng số Stefan-Boltzmann [W m⁻² K⁻⁴]
METRIC_CRS = "EPSG:32648"       # WGS 84 / UTM Zone 48N (dùng đo đạc khoảng cách mét)
WGS84_CRS = "EPSG:4326"         # Kinh/Vĩ độ WGS84
TIMEZONE_VN = "Asia/Ho_Chi_Minh"# Múi giờ Việt Nam (UTC+7)

# ── Thông số mô phỏng lão hóa (Phần 2) ────────────────────────────────────
OPERATIONAL_START_YEAR = 2014   # Năm bắt đầu vận hành tuyến đường dây
HOURS_PER_YEAR = 8760.0         # Số giờ trong 1 năm tiêu chuẩn
BASELINE_AMPACITY_A = 850.0     # Dòng cơ sở so sánh hiệu suất tải (Ampacity Gain)

# ── Tự động tạo thư mục cần thiết ─────────────────────────────────────────
for directory in [DATA_DIR, SHAPEFILE_DIR, OUTPUTS_DIR, RATINGS_DIR, FIGURES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
