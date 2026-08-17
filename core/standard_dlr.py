"""
core/standard_dlr.py
--------------------
Quy trình tính toán Dynamic Line Rating (DLR) tiêu chuẩn cho đường dây 220kV
Tháp Chàm - Vĩnh Tân (Phần 1 của dự án):
1. Đọc thông số kỹ thuật dây dẫn từ Excel.
2. Đọc shapefile tuyến và phân đoạn theo phương vị & cự ly ~5km.
3. Tải dữ liệu khí tượng từng giờ từ Open-Meteo API.
4. Tính toán dòng tải định mức động DLR theo IEEE Std 738.
5. So sánh với định mức tĩnh SLR, đánh giá khả năng truyền tải và tắc nghẽn.
6. Xuất các file kết quả: CSV/HDF5, Báo cáo TXT, Dữ liệu JSON, Đồ thị PNG.
"""

import os
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
import pandas as pd

from core.config import (
    RATINGS_DIR, FIGURES_DIR, CONDUCTOR_PARAMS_XLSX, DEFAULT_LINE_SHAPEFILE
)
from core.conductor import read_conductor_params
from core.geometry import load_line_shapefile, divide_line_into_segments
from core.weather import fetch_weather_for_segments
from core.physics import calc_dlr_for_line
from core.statistics import (
    analyze_dlr_detailed, generate_comments, save_analysis_report, save_analysis_json
)
from core.visualization import plot_standard_dlr

logger = logging.getLogger(__name__)


def run_standard_dlr(
    shapefile: str | os.PathLike = DEFAULT_LINE_SHAPEFILE,
    conductor_xlsx: str | os.PathLike = CONDUCTOR_PARAMS_XLSX,
    start_date: str = "2023-01-01",
    end_date: str = "2023-12-31",
    segment_km: float = 5.0,
    output: Optional[str] = None,
    margin_wind: float = 0.0,
    margin_temp: float = 0.0,
    margin_ghi: float = 0.0,
    margin_pressure: float = 0.0,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    plot: bool = False,
    save_analysis: bool = False,
) -> pd.DataFrame:
    """
    Thực thi toàn bộ luồng tính DLR tiêu chuẩn (Phần 1).

    Parameters
    ----------
    shapefile : str hoặc Path
        Đường dẫn file shapefile (.shp)
    conductor_xlsx : str hoặc Path
        Đường dẫn file Excel thông số dây dẫn
    start_date, end_date : str
        Khoảng thời gian tính toán 'YYYY-MM-DD'
    segment_km : float
        Chiều dài mục tiêu phân đoạn (mặc định 5km)
    output : str, optional
        Đường dẫn file kết quả CSV / HDF5 đầu ra
    margin_wind : float
        Biên an toàn tốc độ gió [m/s] (âm = bảo thủ)
    margin_temp : float
        Biên an toàn nhiệt độ môi trường [K] (dương = bảo thủ)
    margin_ghi : float
        Biên an toàn bức xạ mặt trời [W/m²]
    margin_pressure : float
        Biên an toàn áp suất khí quyển [Pa]
    bbox : tuple, optional
        (min_lat, max_lat, min_lon, max_lon)
    plot : bool
        Có xuất đồ thị chuỗi thời gian hay không
    save_analysis : bool
        Có lưu báo cáo phân tích chi tiết TXT và JSON hay không

    Returns
    -------
    pd.DataFrame : Bảng kết quả DLR (cột 'DLR', các cột 'seg_*', 'SLR', 'DLR_vs_SLR_pct')
    """
    logger.info("═" * 70)
    logger.info("PHẦN 1: DYNAMIC LINE RATING TIÊU CHUẨN (IEEE 738)")
    logger.info("Đường dây: 220kV Tháp Chàm - Vĩnh Tân | Khoảng thời gian: %s -> %s", start_date, end_date)
    logger.info("═" * 70)

    # 1. Đọc thông số dây dẫn
    logger.info("[1/5] Đọc thông số kỹ thuật dây dẫn...")
    conductor = read_conductor_params(conductor_xlsx)

    # 2. Đọc và phân đoạn tuyến đường dây
    logger.info("[2/5] Đọc shapefile và thực hiện thuật toán phân đoạn...")
    line_metric = load_line_shapefile(str(shapefile), bbox=bbox)
    df_segments = divide_line_into_segments(line_metric, segment_length_km=segment_km)

    # 3. Lấy dữ liệu khí tượng Open-Meteo
    logger.info("[3/5] Truy xuất dữ liệu khí tượng từ Open-Meteo API...")
    weather_data = fetch_weather_for_segments(
        segment_points=df_segments,
        start_date=start_date,
        end_date=end_date,
    )

    # 4. Tính toán DLR theo tiêu chuẩn IEEE 738
    logger.info("[4/5] Tính toán nhiệt động học và Ampacity DLR...")
    forecast_margin = {
        "windspeed": margin_wind,
        "temperature": margin_temp,
        "solar_ghi": margin_ghi,
        "pressure": margin_pressure,
    }

    df_dlr = calc_dlr_for_line(
        df_segments=df_segments,
        weather_data=weather_data,
        conductor=conductor,
        forecast_margin={k: v for k, v in forecast_margin.items() if v != 0.0},
    )

    df_dlr.index.name = "time_utc7"
    df_dlr.attrs["line_name"] = conductor["line_name"]
    df_dlr.attrs["conductor_type"] = conductor["conductor_type"]
    df_dlr.attrs["start_date"] = start_date
    df_dlr.attrs["end_date"] = end_date

    # Bổ sung cột so sánh SLR
    nominal_slr = conductor.get("nominal_rating_A")
    if not pd.isna(nominal_slr):
        df_dlr["SLR"] = nominal_slr
        df_dlr["DLR_vs_SLR_pct"] = (df_dlr["DLR"] / nominal_slr - 1.0) * 100.0

    # 5. Lưu kết quả và báo cáo
    logger.info("[5/5] Xuất kết quả và báo cáo đánh giá...")
    if output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = os.path.join(RATINGS_DIR, f"dlr_thap_cham_vinh_tan_{ts}.csv")

    os.makedirs(os.path.dirname(output), exist_ok=True)
    if output.endswith(".h5") or output.endswith(".hdf5"):
        df_dlr.to_hdf(output, key="dlr")
        logger.info("Đã lưu kết quả HDF5: %s", output)
    else:
        df_dlr.to_csv(output)
        logger.info("Đã lưu kết quả CSV: %s", output)

    if plot:
        fig_path = plot_standard_dlr(df_dlr, conductor, start_date, end_date)
        logger.info("Đã xuất đồ thị: %s", fig_path)

    if save_analysis:
        analysis = analyze_dlr_detailed(df_dlr, conductor, start_date, end_date)
        comments = generate_comments(analysis)
        report_file = save_analysis_report(analysis, comments, RATINGS_DIR, start_date, end_date)
        json_file = save_analysis_json(analysis, RATINGS_DIR, start_date, end_date)
        logger.info("Đã lưu báo cáo văn bản: %s", report_file)
        logger.info("Đã lưu dữ liệu JSON: %s", json_file)

    logger.info("═" * 70)
    logger.info("HOÀN THÀNH TÍNH TOÁN PHẦN 1 (DLR TIÊU CHUẨN)")
    logger.info("═" * 70)
    return df_dlr
