#!/usr/bin/env python
"""
run_dlr_upgrade.py
------------------
Script chạy Phần 2 – Dynamic Line Rating xét biến thiên hệ số phát xạ & hấp thụ (5 chu kỳ)
cho đường dây 220kV Tháp Chàm - Vĩnh Tân.
(Wrapper tương thích ngược gọi trực tiếp vào module core.dynamic_dlr)
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

from core.config import DEFAULT_LINE_SHAPEFILE, CONDUCTOR_PARAMS_XLSX, BASELINE_AMPACITY_A
from core.dynamic_dlr import run_dynamic_aging_dlr


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Chạy mô hình DLR nâng cấp với hệ số phát xạ & hấp thụ động (5 chu kỳ)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--shapefile", default=str(DEFAULT_LINE_SHAPEFILE), help="Đường dẫn file shapefile (.shp)")
    parser.add_argument("--conductor", default=str(CONDUCTOR_PARAMS_XLSX), help="Đường dẫn file Excel thông số dây dẫn")
    parser.add_argument("--output", default="outputs/", help="Thư mục gốc lưu kết quả (ratings & figures)")
    parser.add_argument("--baseline", type=float, default=BASELINE_AMPACITY_A, help="Dòng điện cơ sở [A] để tính gain")
    parser.add_argument("--zoom-window", type=int, default=7, help="Cửa sổ zoom cho đồ thị [ngày]")
    parser.add_argument("--skip-visualization", action="store_true", help="Bỏ qua vẽ đồ thị")

    args = parser.parse_args()

    ratings_dir = os.path.join(args.output, "ratings") if not args.output.endswith("ratings") else args.output
    figures_dir = os.path.join(args.output, "figures") if not args.output.endswith("figures") else args.output

    run_dynamic_aging_dlr(
        shapefile=args.shapefile,
        conductor_xlsx=args.conductor,
        output_dir=ratings_dir,
        figures_dir=figures_dir,
        baseline_A=args.baseline,
        zoom_window_days=args.zoom_window,
        skip_visualization=args.skip_visualization,
    )


if __name__ == "__main__":
    main()
