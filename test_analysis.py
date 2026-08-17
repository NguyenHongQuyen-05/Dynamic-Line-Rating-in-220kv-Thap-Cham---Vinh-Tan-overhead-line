#!/usr/bin/env python
"""
test_analysis.py
----------------
Bộ kiểm thử tự động toàn diện kiểm tra tính đúng đắn của toàn bộ hệ thống DLR:
  - Kiểm tra các hàm tính toán nhiệt động học IEEE 738 (đối lưu, bức xạ, mặt trời, ampacity).
  - Kiểm tra hàm tính toán hệ số phát xạ / hấp thụ theo mô hình lão hóa.
  - Kiểm tra logic phân đoạn hình học và tính toán phương vị.
  - Kiểm tra quy trình phân tích thống kê và tạo báo cáo cho cả Phần 1 và Phần 2.
"""

import sys
import os
import io

# Thiết lập UTF-8 cho console output trên mọi hệ điều hành
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from core.config import C2K, BASELINE_AMPACITY_A, OPERATIONAL_START_YEAR
from core.physics import (
    wind_direction_factor,
    convective_cooling,
    radiative_cooling,
    solar_heating,
    ampacity_ieee738,
)
from core.geometry import calculate_azimuth
from core.aging import (
    calculate_coefficient,
    get_coefficient_series,
    get_cycle_range,
    get_cycle_dates,
    get_coefficient_at_year_end,
)
from core.statistics import (
    analyze_dlr_detailed,
    generate_comments,
    calculate_ampacity_gains,
    calculate_hourly_statistics,
    generate_cycle_summary,
)


def run_tests():
    print("=" * 80)
    print("KIỂM THỬ TOÀN DIỆN HỆ THỐNG DYNAMIC LINE RATING (DLR)")
    print("=" * 80)
    print()

    # ── Test 1: Nhiệt động học IEEE 738 ───────────────────────────────────────
    print("[1/5] Kiểm thử nhiệt động học IEEE Std 738-2023...")
    t_cond_k = 75.0 + C2K
    t_air_k = 35.0 + C2K
    diameter_m = 0.0231
    r_ohm_m = 0.1060 / 1000.0

    k_ang = wind_direction_factor(90.0)  # Gió vuông góc
    assert 0.99 <= k_ang <= 1.0, f"Lỗi K_angle: {k_ang}"

    k_ang_par = wind_direction_factor(0.0)  # Gió dọc tuyến
    assert 0.38 <= k_ang_par <= 0.42, f"Lỗi K_angle (song song): {k_ang_par}"

    q_c = convective_cooling(t_cond_k, t_air_k, windspeed_ms=2.0, k_angle=k_ang,
                             diameter_m=diameter_m, pressure_pa=101325.0)
    q_r = radiative_cooling(diameter_m=diameter_m, emissivity=0.8,
                            t_cond_k=t_cond_k, t_air_k=t_air_k)
    q_s = solar_heating(solar_ghi=800.0, diameter_m=diameter_m, absorptivity=0.8)

    amp = ampacity_ieee738(
        windspeed=2.0,
        wind_conductor_angle=90.0,
        temp_ambient_air=t_air_k,
        pressure_Pa=101325.0,
        solar_ghi=800.0,
        temp_conductor_K=t_cond_k,
        diameter_m=diameter_m,
        resistance_ohm_per_m=r_ohm_m,
        emissivity=0.8,
        absorptivity=0.8,
    )
    assert amp > 0, f"Ampacity phải > 0: {amp}"
    print(f"  ✓ q_c = {q_c:.2f} W/m | q_r = {q_r:.2f} W/m | q_s = {q_s:.2f} W/m | Ampacity = {amp:.1f} A")

    # ── Test 2: Hình học & Phương vị ─────────────────────────────────────────
    print("[2/5] Kiểm thử tính toán phương vị (Azimuth)...")
    # Điểm (lon1, lat1) -> (lon2, lat2): đi về hướng Đông
    az_east = calculate_azimuth((108.0, 11.0), (109.0, 11.0))
    assert 85.0 <= az_east <= 95.0, f"Phương vị Đông không đúng: {az_east}"
    # Đi về hướng Bắc
    az_north = calculate_azimuth((108.0, 11.0), (108.0, 12.0))
    assert -5.0 <= az_north <= 5.0, f"Phương vị Bắc không đúng: {az_north}"
    print(f"  ✓ Hướng Đông: {az_east:.1f}° | Hướng Bắc: {az_north:.1f}°")

    # ── Test 3: Mô hình Lão hóa Hệ số ────────────────────────────────────────
    print("[3/5] Kiểm thử mô hình lão hóa hệ số phát xạ & hấp thụ...")
    y_0 = calculate_coefficient(0.0)
    assert abs(y_0 - 0.23) < 1e-6, f"y(0) phải bằng 0.23: {y_0}"
    y_10 = calculate_coefficient(10.0)
    assert 0.80 <= y_10 <= 0.90, f"y(10) không đúng dải: {y_10}"

    s_range, e_range = get_cycle_range(1)
    assert (s_range, e_range) == (0, 2), f"Chu kỳ 1 range: {(s_range, e_range)}"
    s_dt, e_dt = get_cycle_dates(1)
    assert s_dt.year == 2014 and e_dt.year == 2016, f"Chu kỳ 1 dates: {s_dt} -> {e_dt}"
    print(f"  ✓ y(0 năm) = {y_0:.4f} | y(10 năm) = {y_10:.4f} | Chu kỳ 1: {s_dt.year}-{e_dt.year}")

    # ── Test 4: Phân tích Thống kê Phần 1 (DLR Tiêu chuẩn) ───────────────────
    print("[4/5] Kiểm thử phân tích thống kê Phần 1...")
    dates = pd.date_range("2023-01-01", "2023-12-31 23:00", freq="h", tz="Asia/Ho_Chi_Minh")
    np.random.seed(42)
    dlr_sim = 650.0 + 100.0 * np.sin(np.arange(len(dates)) * 2 * np.pi / len(dates)) + np.random.normal(0, 30, len(dates))
    dlr_sim = np.maximum(dlr_sim, 300.0)

    df_test = pd.DataFrame({
        "DLR": dlr_sim,
        "seg_0": dlr_sim * 1.05,
        "seg_1": dlr_sim,
        "SLR": 500.0,
        "DLR_vs_SLR_pct": (dlr_sim / 500.0 - 1.0) * 100.0,
    }, index=dates)

    conductor_info = {
        "line_name": "220kV Tháp Chàm - Vĩnh Tân",
        "conductor_type": "ACSR-330/43",
        "nominal_rating_A": 500.0,
    }

    analysis = analyze_dlr_detailed(df_test, conductor_info, "2023-01-01", "2023-12-31")
    assert analysis["mean"] > 500.0, f"DLR mean không hợp lệ: {analysis['mean']}"
    assert analysis["limiting_segment"][0] == "seg_1", "Segment giới hạn phải là seg_1"

    comments = generate_comments(analysis)
    assert "BÁO CÁO PHÂN TÍCH DYNAMIC LINE RATING" in comments
    print(f"  ✓ Thống kê: DLR TB = {analysis['mean']:.1f} A | P50 = {analysis['p50']:.1f} A | Giờ DLR>SLR = {analysis['pct_hours_above_slr']:.1f}%")

    # ── Test 5: Thống kê So sánh Phần 2 (DLR Lão hóa) ────────────────────────
    print("[5/5] Kiểm thử thống kê so sánh 2 kịch bản chu kỳ...")
    df_fixed_mock = pd.DataFrame({"DLR": dlr_sim * 0.95}, index=dates)
    df_dyn_mock = pd.DataFrame({"DLR": dlr_sim}, index=dates)

    mock_res = {
        "fixed": df_fixed_mock,
        "dynamic": df_dyn_mock,
        "fixed_coeff": 0.23,
        "time_index": dates,
    }
    summary = generate_cycle_summary(1, mock_res, baseline_A=850.0)
    assert summary["difference"]["mean_A"] > 0, "Chênh lệch Động - Cố định phải dương"
    print(f"  ✓ Chu kỳ 1: Chênh lệch TB = {summary['difference']['mean_A']:.2f} A ({summary['difference']['mean_pct']:.2f}%)")

    print()
    print("=" * 80)
    print("✓ TẤT CẢ 5 BƯỚC KIỂM THỬ ĐÃ THÀNH CÔNG 100%!")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
