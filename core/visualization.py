"""
core/visualization.py
---------------------
Trực quan hóa đồ thị khoa học chất lượng cao:
1. Đồ thị DLR chuỗi thời gian theo giờ vs Định mức tĩnh SLR (Phần 1).
2. Đồ thị so sánh 5 chu kỳ lão hóa (Phần 2):
   - Tự động phát hiện điểm chênh lệch cực đại giữa Kịch bản A (Cố định) và B (Động).
   - Phóng to cửa sổ thời gian (mặc định ±7 ngày quanh điểm max diff).
   - Biểu diễn đồng thời DLR (trục Y bên trái) và Tốc độ gió (trục Y bên phải).
"""

import os
import logging
import pickle
from datetime import timedelta
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from core.config import FIGURES_DIR, BASELINE_AMPACITY_A
from core.aging import get_cycle_range

logger = logging.getLogger(__name__)

# ── Cấu hình giao diện đồ thị ─────────────────────────────────────────────
FIGURE_DPI = 150
FIGURE_SIZE = (14, 8)
FONT_SIZE_TITLE = 13
FONT_SIZE_LABEL = 11
FONT_SIZE_TICK = 10

COLOR_FIXED = "#1f77b4"     # Xanh lam
COLOR_DYNAMIC = "#ff7f0e"   # Cam
COLOR_WIND = "#2ca02c"      # Xanh lá
COLOR_BASELINE = "#d62728"  # Đỏ


def plot_standard_dlr(
    df_dlr: pd.DataFrame,
    conductor: Dict[str, Any],
    start_date: str,
    end_date: str,
    output_path: Optional[str] = None,
) -> str:
    """
    Vẽ đồ thị DLR theo chuỗi thời gian cho Phần 1 (DLR Tiêu chuẩn).
    """
    if output_path is None:
        output_path = os.path.join(FIGURES_DIR, f"dlr_{start_date}_{end_date}.png")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # Subplot 1: DLR vs SLR
    ax1 = axes[0]
    ax1.fill_between(df_dlr.index, df_dlr["DLR"], alpha=0.6, color="#2196F3", label="DLR (Ampacity động)")
    if "SLR" in df_dlr.columns:
        slr_val = df_dlr["SLR"].iloc[0]
        ax1.axhline(slr_val, color="red", lw=1.5, ls="--", label=f"SLR (Định mức tĩnh = {slr_val:.0f} A)")
    ax1.set_ylabel("Dòng điện định mức [A]", fontsize=FONT_SIZE_LABEL)
    ax1.set_title(
        f"Dynamic Line Rating – {conductor.get('line_name', '220kV Tháp Chàm - Vĩnh Tân')}\n"
        f"Dây {conductor.get('conductor_type', 'ACSR')} | {start_date} → {end_date}",
        fontsize=FONT_SIZE_TITLE,
    )
    ax1.legend(loc="upper right", fontsize=FONT_SIZE_TICK)
    ax1.grid(True, ls=":", alpha=0.5)

    # Subplot 2: % Chênh lệch so với SLR
    ax2 = axes[1]
    if "DLR_vs_SLR_pct" in df_dlr.columns:
        ax2.fill_between(df_dlr.index, df_dlr["DLR_vs_SLR_pct"],
                         where=df_dlr["DLR_vs_SLR_pct"] >= 0,
                         alpha=0.6, color="#4CAF50", label="DLR > SLR (Khả năng truyền tải tăng)")
        ax2.fill_between(df_dlr.index, df_dlr["DLR_vs_SLR_pct"],
                         where=df_dlr["DLR_vs_SLR_pct"] < 0,
                         alpha=0.6, color="#F44336", label="DLR < SLR (Cần giảm tải an toàn)")
        ax2.axhline(0, color="black", lw=1)
        ax2.set_ylabel("DLR vs SLR [%]", fontsize=FONT_SIZE_LABEL)
        ax2.legend(loc="upper right", fontsize=FONT_SIZE_TICK)
        ax2.grid(True, ls=":", alpha=0.5)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y", tz=df_dlr.index.tz))
    ax2.xaxis.set_major_locator(mdates.MonthLocator())
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha="right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Đã lưu biểu đồ DLR tiêu chuẩn: %s", output_path)
    return output_path


def find_max_difference_point(dlr_fixed: pd.Series, dlr_dynamic: pd.Series) -> Tuple[pd.Timestamp, float, float]:
    """Tìm thời điểm có độ chênh lệch DLR tuyệt đối lớn nhất giữa hai kịch bản."""
    diff = dlr_dynamic - dlr_fixed
    max_idx = diff.abs().idxmax()
    max_val = float(diff.loc[max_idx])
    fixed_val = float(dlr_fixed.loc[max_idx])
    pct_val = (max_val / fixed_val * 100.0) if fixed_val != 0 else 0.0
    return max_idx, max_val, pct_val


def get_zoom_window(max_diff_time: pd.Timestamp,
                    time_index: pd.DatetimeIndex,
                    window_days: int = 7) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """Tạo khoảng thời gian phóng to ±window_days xung quanh điểm max difference."""
    w = timedelta(days=window_days)
    start_t = max(max_diff_time - w, time_index.min())
    end_t = min(max_diff_time + w, time_index.max())
    return start_t, end_t


def plot_cycle_comparison(
    cycle_num: int,
    results: Dict[str, Any],
    weather_for_viz: Dict[str, Any],
    output_path: str,
    zoom_window_days: int = 7,
    baseline_A: float = BASELINE_AMPACITY_A,
) -> str:
    """
    Vẽ đồ thị so sánh Kịch bản A vs Kịch bản B cho một chu kỳ lão hóa (Phần 2).
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    df_fixed = results["fixed"]
    df_dynamic = results["dynamic"]
    fixed_coeff = results["fixed_coeff"]

    dlr_fixed = df_fixed["DLR"]
    dlr_dynamic = df_dynamic["DLR"]

    max_diff_time, max_diff_value, max_diff_pct = find_max_difference_point(dlr_fixed, dlr_dynamic)
    zoom_start, zoom_end = get_zoom_window(max_diff_time, dlr_fixed.index, window_days=zoom_window_days)

    mask = (dlr_fixed.index >= zoom_start) & (dlr_fixed.index <= zoom_end)
    dlr_fix_zoom = dlr_fixed[mask]
    dlr_dyn_zoom = dlr_dynamic[mask]

    if "windspeed" in weather_for_viz and weather_for_viz["windspeed"] is not None:
        windspeed_zoom = weather_for_viz["windspeed"][mask]
    else:
        windspeed_zoom = pd.Series(0.0, index=dlr_fix_zoom.index)

    fig, ax1 = plt.subplots(figsize=FIGURE_SIZE, dpi=FIGURE_DPI)

    # Trục Y trái: DLR
    ax1.set_xlabel("Thời gian", fontsize=FONT_SIZE_LABEL)
    ax1.set_ylabel("Dòng điện động DLR [A]", fontsize=FONT_SIZE_LABEL, color="black")
    ax1.tick_params(axis="y", labelsize=FONT_SIZE_TICK)
    ax1.tick_params(axis="x", labelsize=FONT_SIZE_TICK)

    line_fix = ax1.plot(dlr_fix_zoom.index, dlr_fix_zoom.values,
                        color=COLOR_FIXED, linewidth=2, label="DLR (Hệ số cố định)",
                        marker="o", markersize=2, alpha=0.8)
    line_dyn = ax1.plot(dlr_dyn_zoom.index, dlr_dyn_zoom.values,
                        color=COLOR_DYNAMIC, linewidth=2, label="DLR (Hệ số động)",
                        marker="s", markersize=2, alpha=0.8)
    line_base = ax1.axhline(y=baseline_A, color=COLOR_BASELINE, linestyle="--", linewidth=1.5,
                            label=f"Dòng cơ sở ({baseline_A:.0f}A)", alpha=0.7)

    # Đánh dấu sao đỏ tại điểm chênh lệch cực đại
    point_max = ax1.plot(max_diff_time, dlr_dynamic.loc[max_diff_time], "r*", markersize=14,
                         label=f"Chênh lệch cực đại: {max_diff_value:.1f}A ({max_diff_time.strftime('%Y-%m-%d %H:%M')})")

    ax1.grid(True, alpha=0.3, linestyle=":", linewidth=0.5)
    ax1.set_ylim(bottom=0)

    # Trục Y phải: Tốc độ gió
    ax2 = ax1.twinx()
    ax2.set_ylabel("Tốc độ gió [m/s]", fontsize=FONT_SIZE_LABEL, color=COLOR_WIND)
    ax2.tick_params(axis="y", labelcolor=COLOR_WIND, labelsize=FONT_SIZE_TICK)
    line_wind = ax2.plot(windspeed_zoom.index, windspeed_zoom.values,
                         color=COLOR_WIND, linewidth=1.2, linestyle="-", alpha=0.5,
                         label="Tốc độ gió (m/s)")

    start_yr, end_yr = get_cycle_range(cycle_num)
    title = f"Chu kỳ {cycle_num} (Năm {start_yr}-{end_yr}): So sánh DLR Hệ số Cố định vs Hệ số Động\n"
    title += f"Khoảng phóng to: {dlr_fix_zoom.index.min().strftime('%Y-%m-%d')} → {dlr_fix_zoom.index.max().strftime('%Y-%m-%d')}"
    ax1.set_title(title, fontsize=FONT_SIZE_TITLE, fontweight="bold", pad=15)

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=24))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Legend tổng hợp
    all_lines = line_fix + line_dyn + [line_base] + point_max + line_wind
    all_labels = [l.get_label() for l in all_lines]
    ax1.legend(all_lines, all_labels, loc="upper left", fontsize=FONT_SIZE_TICK)

    # Khung thông tin thống kê tóm tắt
    info_text = (
        f"Hệ số cố định: {fixed_coeff:.4f}\n"
        f"Chênh lệch cực đại: {max_diff_value:.2f} A ({max_diff_pct:.2f}%)\n"
        f"DLR Cố định (TB): {dlr_fix_zoom.mean():.1f} A\n"
        f"DLR Động (TB):   {dlr_dyn_zoom.mean():.1f} A"
    )
    ax1.text(0.02, 0.72, info_text, transform=ax1.transAxes, fontsize=FONT_SIZE_TICK - 1,
             verticalalignment="top", bbox=dict(boxstyle="round,pad=0.5", facecolor="wheat", alpha=0.6))

    plt.tight_layout()
    plt.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Đã lưu đồ thị chu kỳ %d: %s", cycle_num, output_path)
    return output_path


def plot_all_cycles(
    results_pkl_path: str,
    output_dir: str,
    zoom_window_days: int = 7,
    baseline_A: float = BASELINE_AMPACITY_A,
) -> None:
    """Đọc dữ liệu từ file pickle và vẽ toàn bộ 5 đồ thị chu kỳ."""
    with open(results_pkl_path, "rb") as f:
        all_results = pickle.load(f)

    os.makedirs(output_dir, exist_ok=True)
    for cycle_num in range(1, 6):
        if cycle_num not in all_results:
            continue
        res = all_results[cycle_num]
        out_file = os.path.join(output_dir, f"cycle_{cycle_num}_comparison.png")
        plot_cycle_comparison(
            cycle_num=cycle_num,
            results=res,
            weather_for_viz=res.get("weather", {}),
            output_path=out_file,
            zoom_window_days=zoom_window_days,
            baseline_A=baseline_A,
        )
