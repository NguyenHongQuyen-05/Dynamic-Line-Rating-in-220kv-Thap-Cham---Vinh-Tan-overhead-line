#!/usr/bin/env python
"""
run_vn.py
---------
Script chạy Phần 1 – Dynamic Line Rating tiêu chuẩn theo IEEE 738
cho đường dây 220kV Tháp Chàm - Vĩnh Tân.
(Wrapper tương thích ngược gọi trực tiếp vào module core.standard_dlr)
"""

import sys
import os
import argparse
import logging

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import DEFAULT_LINE_SHAPEFILE, CONDUCTOR_PARAMS_XLSX
from core.standard_dlr import run_standard_dlr


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Tính Dynamic Line Rating (DLR) – Đường dây 220kV Tháp Chàm - Vĩnh Tân",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--shapefile", default=str(DEFAULT_LINE_SHAPEFILE), help="Đường dẫn file shapefile .shp")
    parser.add_argument("--conductor", default=str(CONDUCTOR_PARAMS_XLSX), help="Đường dẫn file Excel thông số dây dẫn")
    parser.add_argument("--start_date", required=True, help="Ngày bắt đầu YYYY-MM-DD")
    parser.add_argument("--end_date", required=True, help="Ngày kết thúc YYYY-MM-DD")
    parser.add_argument("--segment_km", type=float, default=5.0, help="Chiều dài mục tiêu phân đoạn [km]")
    parser.add_argument("--output", default=None, help="File kết quả đầu ra (.csv hoặc .h5)")
    parser.add_argument("--margin_wind", type=float, default=0.0, help="Biên an toàn gió [m/s]")
    parser.add_argument("--margin_temp", type=float, default=0.0, help="Biên an toàn nhiệt độ [K]")
    parser.add_argument("--margin_ghi", type=float, default=0.0, help="Biên an toàn bức xạ [W/m²]")
    parser.add_argument("--bbox", type=float, nargs=4, default=None,
                        metavar=("MIN_LAT", "MAX_LAT", "MIN_LON", "MAX_LON"),
                        help="Giới hạn vùng đọc bounding box")
    parser.add_argument("--plot", action="store_true", help="Vẽ biểu đồ DLR")
    parser.add_argument("--save-analysis", action="store_true", help="Lưu báo cáo phân tích chi tiết TXT/JSON")

    args = parser.parse_args()
    bbox_tuple = tuple(args.bbox) if args.bbox else None

    run_standard_dlr(
        shapefile=args.shapefile,
        conductor_xlsx=args.conductor,
        start_date=args.start_date,
        end_date=args.end_date,
        segment_km=args.segment_km,
        output=args.output,
        margin_wind=args.margin_wind,
        margin_temp=args.margin_temp,
        margin_ghi=args.margin_ghi,
        bbox=bbox_tuple,
        plot=args.plot,
        save_analysis=args.save_analysis,
    )


if __name__ == "__main__":
    main()
