#!/usr/bin/env python
"""
main.py
-------
Giao diện dòng lệnh (CLI) trung tâm cho dự án Dynamic Line Rating (DLR)
đường dây 220kV Tháp Chàm - Vĩnh Tân.

Cung cấp các chế độ chạy:
  1. standard : Chạy Phần 1 – Dynamic Line Rating tiêu chuẩn (IEEE 738)
  2. dynamic  : Chạy Phần 2 – Dynamic Line Rating xét biến thiên hệ số phát xạ/hấp thụ (5 chu kỳ)
  3. all      : Chạy đồng thời cả hai phần

Ví dụ sử dụng:
  # Chạy Phần 1 (DLR tiêu chuẩn năm 2023)
  python main.py standard --start_date 2023-01-01 --end_date 2023-12-31 --plot --save-analysis

  # Chạy Phần 2 (DLR lão hóa 5 chu kỳ 2014-2024)
  python main.py dynamic --output outputs/ratings/ --figures outputs/figures/

  # Chạy toàn bộ cả 2 phần
  python main.py all --start_date 2023-01-01 --end_date 2023-12-31 --plot --save-analysis
"""

import sys
import os
import argparse
import logging

# Thiết lập mã hóa UTF-8 cho console trên Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Thêm thư mục gốc vào sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import (
    DEFAULT_LINE_SHAPEFILE, CONDUCTOR_PARAMS_XLSX, RATINGS_DIR, FIGURES_DIR, BASELINE_AMPACITY_A
)
from core.standard_dlr import run_standard_dlr
from core.dynamic_dlr import run_dynamic_aging_dlr


def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
        datefmt="%H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dlr_vietnam",
        description="Chương trình tính toán Dynamic Line Rating (DLR) – Đường dây 220kV Tháp Chàm - Vĩnh Tân",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Chế độ tính toán DLR")

    # ── Subcommand: standard (Phần 1) ──────────────────────────────────────
    p_std = subparsers.add_parser(
        "standard",
        help="Phần 1: DLR tiêu chuẩn theo tiêu chuẩn IEEE 738",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_std.add_argument("--shapefile", default=str(DEFAULT_LINE_SHAPEFILE), help="Đường dẫn file shapefile (.shp)")
    p_std.add_argument("--conductor", default=str(CONDUCTOR_PARAMS_XLSX), help="Đường dẫn file Excel thông số dây dẫn")
    p_std.add_argument("--start_date", required=True, help="Ngày bắt đầu (YYYY-MM-DD)")
    p_std.add_argument("--end_date", required=True, help="Ngày kết thúc (YYYY-MM-DD)")
    p_std.add_argument("--segment_km", type=float, default=5.0, help="Chiều dài mục tiêu phân đoạn [km]")
    p_std.add_argument("--output", default=None, help="Đường dẫn file kết quả CSV / HDF5")
    p_std.add_argument("--margin_wind", type=float, default=0.0, help="Biên an toàn tốc độ gió [m/s]")
    p_std.add_argument("--margin_temp", type=float, default=0.0, help="Biên an toàn nhiệt độ môi trường [K]")
    p_std.add_argument("--margin_ghi", type=float, default=0.0, help="Biên an toàn bức xạ mặt trời [W/m²]")
    p_std.add_argument("--bbox", type=float, nargs=4, default=None,
                       metavar=("MIN_LAT", "MAX_LAT", "MIN_LON", "MAX_LON"),
                       help="Giới hạn tọa độ địa lý bounding box")
    p_std.add_argument("--plot", action="store_true", help="Vẽ và lưu đồ thị chuỗi thời gian DLR")
    p_std.add_argument("--save-analysis", action="store_true", help="Lưu báo cáo phân tích chi tiết TXT và JSON")

    # ── Subcommand: dynamic (Phần 2) ───────────────────────────────────────
    p_dyn = subparsers.add_parser(
        "dynamic",
        help="Phần 2: DLR xét biến thiên hệ số phát xạ & hấp thụ (5 chu kỳ 2014-2024)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_dyn.add_argument("--shapefile", default=str(DEFAULT_LINE_SHAPEFILE), help="Đường dẫn file shapefile (.shp)")
    p_dyn.add_argument("--conductor", default=str(CONDUCTOR_PARAMS_XLSX), help="Đường dẫn file Excel thông số dây dẫn")
    p_dyn.add_argument("--output", default=str(RATINGS_DIR), help="Thư mục lưu báo cáo kết quả")
    p_dyn.add_argument("--figures", default=str(FIGURES_DIR), help="Thư mục lưu biểu đồ so sánh")
    p_dyn.add_argument("--baseline", type=float, default=BASELINE_AMPACITY_A, help="Dòng điện cơ sở [A] để tính gain")
    p_dyn.add_argument("--zoom-window", type=int, default=7, help="Cửa sổ phóng to đồ thị quanh điểm max diff (ngày)")
    p_dyn.add_argument("--skip-visualization", action="store_true", help="Bỏ qua bước vẽ biểu đồ")

    # ── Subcommand: all ────────────────────────────────────────────────────
    p_all = subparsers.add_parser(
        "all",
        help="Chạy toàn bộ cả Phần 1 (DLR tiêu chuẩn) và Phần 2 (DLR lão hóa 5 chu kỳ)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_all.add_argument("--shapefile", default=str(DEFAULT_LINE_SHAPEFILE), help="Đường dẫn file shapefile (.shp)")
    p_all.add_argument("--conductor", default=str(CONDUCTOR_PARAMS_XLSX), help="Đường dẫn file Excel thông số dây dẫn")
    p_all.add_argument("--start_date", default="2023-01-01", help="Ngày bắt đầu cho Phần 1 (YYYY-MM-DD)")
    p_all.add_argument("--end_date", default="2023-12-31", help="Ngày kết thúc cho Phần 1 (YYYY-MM-DD)")
    p_all.add_argument("--segment_km", type=float, default=5.0, help="Chiều dài mục tiêu phân đoạn [km]")
    p_all.add_argument("--plot", action="store_true", default=True, help="Vẽ biểu đồ Phần 1")
    p_all.add_argument("--save-analysis", action="store_true", default=True, help="Lưu báo cáo phân tích Phần 1")
    p_all.add_argument("--baseline", type=float, default=BASELINE_AMPACITY_A, help="Dòng điện cơ sở [A] cho Phần 2")
    p_all.add_argument("--zoom-window", type=int, default=7, help="Cửa sổ zoom đồ thị cho Phần 2 (ngày)")

    return parser


def main():
    setup_logger()
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "standard":
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

    elif args.command == "dynamic":
        run_dynamic_aging_dlr(
            shapefile=args.shapefile,
            conductor_xlsx=args.conductor,
            output_dir=args.output,
            figures_dir=args.figures,
            baseline_A=args.baseline,
            zoom_window_days=args.zoom_window,
            skip_visualization=args.skip_visualization,
        )

    elif args.command in ["all", "full"]:
        print("\n" + "=" * 80)
        print("BẮT ĐẦU CHẠY TOÀN BỘ DỰ ÁN DYNAMIC LINE RATING (PHẦN 1 + PHẦN 2)")
        print("=" * 80 + "\n")

        # 1. Chạy Phần 1
        run_standard_dlr(
            shapefile=args.shapefile,
            conductor_xlsx=args.conductor,
            start_date=args.start_date,
            end_date=args.end_date,
            segment_km=args.segment_km,
            plot=args.plot,
            save_analysis=args.save_analysis,
        )

        # 2. Chạy Phần 2
        run_dynamic_aging_dlr(
            shapefile=args.shapefile,
            conductor_xlsx=args.conductor,
            baseline_A=args.baseline,
            zoom_window_days=args.zoom_window,
        )

        print("\n" + "=" * 80)
        print("✓ TẤT CẢ CÁC QUY TRÌNH ĐÃ HOÀN THÀNH XUẤT SẮC!")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
