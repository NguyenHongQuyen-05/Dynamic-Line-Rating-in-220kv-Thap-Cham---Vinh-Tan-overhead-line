"""
core/dynamic_dlr.py
-------------------
Quy trình mô phỏng Dynamic Line Rating (DLR) xét sự biến thiên của hệ số phát xạ (ε)
và hệ số hấp thụ (α) theo thời gian vận hành và lão hóa dây dẫn (Phần 2 của dự án):
1. Mô phỏng 5 chu kỳ vận hành 2 năm (2014-2016, 2016-2018, 2018-2020, 2020-2022, 2022-2024).
2. So sánh song song:
   - Kịch bản A: Hệ số cố định tại đầu mỗi chu kỳ.
   - Kịch bản B: Hệ số biến thiên liên tục theo từng giờ vận hành.
3. Tính toán Ampacity Gains (%), chênh lệch công suất truyền tải, phân tích theo năm.
4. Xuất các file báo cáo và biểu đồ chuyên sâu:
   - comparison_report.txt
   - detailed_statistics.txt
   - detailed_results.pkl
   - cycle_1_comparison.png ... cycle_5_comparison.png
"""

import os
import pickle
import logging
from typing import Dict, Any, Optional
import pandas as pd

from core.config import (
    RATINGS_DIR, FIGURES_DIR, CONDUCTOR_PARAMS_XLSX, DEFAULT_LINE_SHAPEFILE,
    BASELINE_AMPACITY_A, OPERATIONAL_START_YEAR
)
from core.conductor import read_conductor_params
from core.geometry import load_line_shapefile, divide_line_into_segments
from core.weather import fetch_weather_for_segments
from core.physics import calc_dlr_for_line
from core.aging import (
    get_cycle_range, get_cycle_dates, get_coefficient_at_year_end, get_coefficient_series
)
from core.statistics import (
    generate_comparison_report, generate_full_report
)
from core.visualization import plot_cycle_comparison

logger = logging.getLogger(__name__)


def run_cycle_comparison(
    cycle_num: int,
    df_segments: pd.DataFrame,
    conductor: Dict[str, Any],
) -> Dict[str, Any]:
    """
    So sánh DLR giữa Kịch bản A (Cố định) và Kịch bản B (Động) cho 1 chu kỳ 2 năm.

    Parameters
    ----------
    cycle_num : int (1 đến 5)
    df_segments : pd.DataFrame
    conductor : dict

    Returns
    -------
    dict:
        - fixed: pd.DataFrame kết quả Kịch bản A
        - dynamic: pd.DataFrame kết quả Kịch bản B
        - weather: dict thông tin thời tiết phục vụ vẽ đồ thị
        - time_index: DatetimeIndex
        - fixed_coeff: float
        - dynamic_coeff_series: pd.Series
    """
    start_year_offset, end_year_offset = get_cycle_range(cycle_num)
    start_date, end_date = get_cycle_dates(cycle_num)

    logger.info("═" * 60)
    logger.info("CHU KỲ %d: Năm vận hành %d-%d (%s → %s)",
                cycle_num, start_year_offset, end_year_offset,
                start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    logger.info("═" * 60)

    # 1. Xác định giá trị hệ số cho Kịch bản A (Cố định)
    if cycle_num == 1:
        fixed_coeff = 0.23  # Giá trị ban đầu khi dây mới lắp đặt (2014)
    else:
        fixed_coeff = get_coefficient_at_year_end(start_year_offset)

    logger.info("  Kịch bản A (Hệ số cố định): ε = α = %.6f", fixed_coeff)

    # 2. Tải dữ liệu thời tiết cho chu kỳ
    weather_data = fetch_weather_for_segments(
        segment_points=df_segments,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )

    if not weather_data:
        raise RuntimeError(f"Không nhận được dữ liệu thời tiết cho chu kỳ {cycle_num}")

    first_seg_id = list(weather_data.keys())[0]
    time_index = weather_data[first_seg_id].index

    # 3. Tính toán Kịch bản A: Hệ số cố định
    fixed_emit = pd.Series(fixed_coeff, index=time_index)
    fixed_absorb = pd.Series(fixed_coeff, index=time_index)

    df_fixed = calc_dlr_for_line(
        df_segments=df_segments,
        weather_data=weather_data,
        conductor=conductor,
        forecast_margin={},
        emissivity_series=fixed_emit,
        absorptivity_series=fixed_absorb,
    )
    logger.info("  -> DLR Kịch bản A (Cố định): TB = %.1f A | Min = %.1f A | Max = %.1f A",
                df_fixed["DLR"].mean(), df_fixed["DLR"].min(), df_fixed["DLR"].max())

    # 4. Tính toán Kịch bản B: Hệ số động
    logger.info("  Kịch bản B (Hệ số động): Biến thiên liên tục theo từng giờ vận hành")
    dynamic_emit = get_coefficient_series(time_index, scenario="dynamic")
    dynamic_absorb = get_coefficient_series(time_index, scenario="dynamic")

    df_dynamic = calc_dlr_for_line(
        df_segments=df_segments,
        weather_data=weather_data,
        conductor=conductor,
        forecast_margin={},
        emissivity_series=dynamic_emit,
        absorptivity_series=dynamic_absorb,
    )
    logger.info("  -> DLR Kịch bản B (Động):     TB = %.1f A | Min = %.1f A | Max = %.1f A",
                df_dynamic["DLR"].mean(), df_dynamic["DLR"].min(), df_dynamic["DLR"].max())

    # Trích xuất dữ liệu khí tượng phục vụ trực quan hóa
    weather_for_viz = {}
    if first_seg_id in weather_data:
        w = weather_data[first_seg_id]
        weather_for_viz["time_index"] = time_index
        weather_for_viz["windspeed"] = w.get("windspeed_ms", pd.Series(0.0, index=time_index))
        weather_for_viz["temperature"] = w.get("temperature_K", pd.Series(273.15, index=time_index))
        weather_for_viz["ghi"] = w.get("ghi_Wm2", pd.Series(0.0, index=time_index))

    return {
        "fixed": df_fixed,
        "dynamic": df_dynamic,
        "weather": weather_for_viz,
        "time_index": time_index,
        "fixed_coeff": fixed_coeff,
        "dynamic_coeff_series": dynamic_absorb,
    }


def run_dynamic_aging_dlr(
    shapefile: str | os.PathLike = DEFAULT_LINE_SHAPEFILE,
    conductor_xlsx: str | os.PathLike = CONDUCTOR_PARAMS_XLSX,
    output_dir: str | os.PathLike = RATINGS_DIR,
    figures_dir: str | os.PathLike = FIGURES_DIR,
    baseline_A: float = BASELINE_AMPACITY_A,
    zoom_window_days: int = 7,
    skip_visualization: bool = False,
) -> Dict[int, Any]:
    """
    Thực thi toàn bộ quy trình mô phỏng DLR lão hóa 5 chu kỳ (Phần 2).

    Parameters
    ----------
    shapefile : str hoặc Path
        Đường dẫn file shapefile
    conductor_xlsx : str hoặc Path
        Đường dẫn file Excel thông số dây dẫn
    output_dir : str hoặc Path
        Thư mục lưu báo cáo và dữ liệu
    figures_dir : str hoặc Path
        Thư mục lưu đồ thị
    baseline_A : float
        Dòng cơ sở so sánh (mặc định 850A)
    zoom_window_days : int
        Cửa sổ phóng to đồ thị xung quanh điểm chênh lệch cực đại (ngày)
    skip_visualization : bool
        Có bỏ qua bước vẽ biểu đồ hay không

    Returns
    -------
    dict: {cycle_num: cycle_results}
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(figures_dir, exist_ok=True)

    logger.info("═" * 70)
    logger.info("PHẦN 2: DYNAMIC LINE RATING VỚI HỆ SỐ PHÁT XẠ & HẤP THỤ BIẾN THIÊN")
    logger.info("Đường dây: 220kV Tháp Chàm - Vĩnh Tân | Mô phỏng 5 chu kỳ 2 năm (2014-2024)")
    logger.info("═" * 70)

    # 1. Đọc thông số và hình học
    logger.info("[1/4] Đọc thông số dây dẫn và phân đoạn tuyến...")
    conductor = read_conductor_params(conductor_xlsx)
    line_shape = load_line_shapefile(str(shapefile))
    df_segments = divide_line_into_segments(line_shape, segment_length_km=5.0)

    # 2. Chạy mô phỏng từng chu kỳ
    logger.info("[2/4] Bắt đầu mô phỏng 5 chu kỳ vận hành...")
    all_results: Dict[int, Any] = {}
    full_comparison_text = ""

    for cycle_num in range(1, 6):
        try:
            res = run_cycle_comparison(cycle_num, df_segments, conductor)
            all_results[cycle_num] = res

            cycle_report = generate_comparison_report(cycle_num, res)
            full_comparison_text += cycle_report
        except Exception as exc:
            logger.error("Lỗi khi mô phỏng chu kỳ %d: %s", cycle_num, exc)
            raise

    # 3. Xuất các báo cáo thống kê
    logger.info("[3/4] Tạo và xuất các báo cáo so sánh chi tiết...")
    comp_report_path = os.path.join(output_dir, "comparison_report.txt")
    with open(comp_report_path, "w", encoding="utf-8") as f:
        f.write(full_comparison_text)
    logger.info("✓ Đã lưu: %s", comp_report_path)

    stats_report_text = generate_full_report(all_results, baseline_A)
    stats_report_path = os.path.join(output_dir, "detailed_statistics.txt")
    with open(stats_report_path, "w", encoding="utf-8") as f:
        f.write(stats_report_text)
    logger.info("✓ Đã lưu: %s", stats_report_path)

    pkl_path = os.path.join(output_dir, "detailed_results.pkl")
    with open(pkl_path, "wb") as f:
        pickle.dump(all_results, f)
    logger.info("✓ Đã lưu: %s", pkl_path)

    # 4. Trực quan hóa 5 đồ thị chu kỳ
    if not skip_visualization:
        logger.info("[4/4] Vẽ đồ thị so sánh 5 chu kỳ (đa trục Y & phóng to điểm max difference)...")
        for cycle_num in range(1, 6):
            fig_out = os.path.join(figures_dir, f"cycle_{cycle_num}_comparison.png")
            plot_cycle_comparison(
                cycle_num=cycle_num,
                results=all_results[cycle_num],
                weather_for_viz=all_results[cycle_num].get("weather", {}),
                output_path=fig_out,
                zoom_window_days=zoom_window_days,
                baseline_A=baseline_A,
            )
            logger.info("✓ Đã lưu đồ thị chu kỳ %d: %s", cycle_num, fig_out)

    logger.info("═" * 70)
    logger.info("HOÀN THÀNH TOÀN BỘ QUY TRÌNH PHẦN 2 (DLR LÃO HÓA)")
    logger.info("═" * 70)
    return all_results
