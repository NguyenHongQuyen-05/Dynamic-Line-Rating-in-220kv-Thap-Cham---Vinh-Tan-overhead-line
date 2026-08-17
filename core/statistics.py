"""
core/statistics.py
------------------
Tính toán thống kê toàn diện, đánh giá hiệu quả và tạo báo cáo nhận xét:
1. Thống kê DLR chuẩn, so sánh SLR, xác định thời gian tắc nghẽn, đoạn nghẽn mạch.
2. Thống kê so sánh 5 chu kỳ lão hóa, tính Ampacity Gains (%), phân tích năm/chu kỳ.
3. Xuất báo cáo TXT, JSON và bảng thống kê chi tiết.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Union
import numpy as np
import pandas as pd

from core.config import OPERATIONAL_START_YEAR, BASELINE_AMPACITY_A
from core.aging import get_cycle_range

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# THỐNG KÊ CHO PHẦN 1: DLR TIÊU CHUẨN
# ═══════════════════════════════════════════════════════════════════════════

def analyze_dlr_detailed(
    df_dlr: pd.DataFrame,
    conductor: Dict[str, Any],
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    """
    Phân tích chi tiết các chỉ số vận hành DLR và so sánh với định mức tĩnh SLR.
    """
    analysis: Dict[str, Any] = {}
    dlr = df_dlr["DLR"]

    # 1. Thống kê cơ bản
    analysis["mean"] = float(dlr.mean())
    analysis["std"] = float(dlr.std())
    analysis["min"] = float(dlr.min())
    analysis["max"] = float(dlr.max())
    analysis["p10"] = float(dlr.quantile(0.10))
    analysis["p25"] = float(dlr.quantile(0.25))
    analysis["p50"] = float(dlr.quantile(0.50))
    analysis["p75"] = float(dlr.quantile(0.75))
    analysis["p90"] = float(dlr.quantile(0.90))

    analysis["coeff_var"] = (analysis["std"] / analysis["mean"]) * 100.0 if analysis["mean"] > 0 else 0.0
    analysis["range"] = analysis["max"] - analysis["min"]

    # 2. So sánh với SLR
    nominal_slr = conductor.get("nominal_rating_A")
    if "SLR" in df_dlr.columns and not pd.isna(nominal_slr):
        slr_val = float(df_dlr["SLR"].iloc[0])
        analysis["slr_value"] = slr_val
        analysis["pct_hours_above_slr"] = float((dlr > slr_val).mean() * 100.0)
        analysis["pct_hours_below_slr"] = float((dlr < slr_val).mean() * 100.0)
        analysis["mean_vs_slr_pct"] = float(((analysis["mean"] / slr_val) - 1.0) * 100.0)
        analysis["min_vs_slr_pct"] = float(((analysis["min"] / slr_val) - 1.0) * 100.0)
        analysis["max_vs_slr_pct"] = float(((analysis["max"] / slr_val) - 1.0) * 100.0)
        analysis["avg_utilization_pct"] = float((analysis["mean"] / slr_val) * 100.0)
        analysis["peak_utilization_pct"] = float((analysis["max"] / slr_val) * 100.0)
        analysis["increase_potential_pct"] = float(max(0.0, ((analysis["max"] - slr_val) / slr_val) * 100.0))

        # Phân tích nguy cơ tắc nghẽn (< 90% SLR)
        congestion_threshold = slr_val * 0.9
        congestion_hours = int((dlr < congestion_threshold).sum())
        analysis["congestion_hours"] = congestion_hours
        analysis["congestion_pct"] = float((congestion_hours / len(dlr)) * 100.0)
    else:
        analysis["slr_value"] = None
        analysis["pct_hours_above_slr"] = None
        analysis["pct_hours_below_slr"] = None
        analysis["mean_vs_slr_pct"] = None
        analysis["min_vs_slr_pct"] = None
        analysis["max_vs_slr_pct"] = None
        analysis["avg_utilization_pct"] = None
        analysis["peak_utilization_pct"] = None
        analysis["increase_potential_pct"] = None

        congestion_hours = int((dlr < analysis["p10"]).sum())
        analysis["congestion_hours"] = congestion_hours
        analysis["congestion_pct"] = float((congestion_hours / len(dlr)) * 100.0)

    # 3. Phân bố mức độ DLR
    dlr_ranges = {
        "rất_thấp": (0.0, analysis["p25"]),
        "thấp": (analysis["p25"], analysis["p50"]),
        "trung_bình": (analysis["p50"], analysis["p75"]),
        "cao": (analysis["p75"], analysis["p90"]),
        "rất_cao": (analysis["p90"], float("inf")),
    }
    analysis["dlr_range_pct"] = {
        k: float(((dlr >= low) & (dlr < high)).mean() * 100.0)
        for k, (low, high) in dlr_ranges.items()
    }

    # 4. Phân tích phân đoạn nút thắt (Limiting Segment)
    seg_cols = [c for c in df_dlr.columns if c.startswith("seg_")]
    if seg_cols:
        analysis["num_segments"] = len(seg_cols)
        analysis["segment_means"] = {col: float(df_dlr[col].mean()) for col in seg_cols}
        analysis["segment_mins"] = {col: float(df_dlr[col].min()) for col in seg_cols}
        limiting_seg = min(analysis["segment_mins"].items(), key=lambda x: x[1])
        analysis["limiting_segment"] = (str(limiting_seg[0]), float(limiting_seg[1]))
    else:
        analysis["num_segments"] = 0
        analysis["limiting_segment"] = ("N/A", 0.0)

    # 5. Phân tích theo tháng
    df_copy = df_dlr.copy()
    df_copy["month"] = df_copy.index.month
    monthly = df_copy.groupby("month")["DLR"].agg(["mean", "min", "max", "std"])
    analysis["monthly_stats"] = monthly

    # 6. Thông tin tổng quát
    analysis["line_name"] = str(conductor.get("line_name", "220kV Tháp Chàm - Vĩnh Tân"))
    analysis["conductor_type"] = str(conductor.get("conductor_type", "N/A"))
    analysis["start_date"] = str(start_date)
    analysis["end_date"] = str(end_date)
    analysis["total_hours"] = len(df_dlr)
    analysis["total_days"] = len(df_dlr) / 24.0

    return analysis


def generate_comments(analysis: Dict[str, Any]) -> str:
    """Tạo văn bản báo cáo nhận xét chi tiết DLR."""
    lines = []
    lines.append("=" * 80)
    lines.append("BÁO CÁO PHÂN TÍCH DYNAMIC LINE RATING (DLR)")
    lines.append("ĐƯỜNG DÂY 220KV THÁP CHÀM - VĨNH TÂN")
    lines.append("=" * 80)
    lines.append("")

    lines.append("1. THÔNG TIN CHUNG")
    lines.append("-" * 80)
    lines.append(f"  Đường dây:        {analysis['line_name']}")
    lines.append(f"  Loại dây dẫn:     {analysis['conductor_type']}")
    lines.append(f"  Thời gian:        {analysis['start_date']} → {analysis['end_date']}")
    lines.append(f"  Tổng thời gian:   {analysis['total_hours']:,} giờ ({analysis['total_days']:.1f} ngày)")
    lines.append(f"  Số phân đoạn:     {analysis['num_segments']}")
    lines.append("")

    lines.append("2. THỐNG KÊ DÒNG ĐIỆN ĐỊNH MỨC ĐỘNG DLR [A]")
    lines.append("-" * 80)
    lines.append(f"  Trung bình:       {analysis['mean']:.1f} A")
    lines.append(f"  Độ lệch chuẩn:    {analysis['std']:.1f} A")
    lines.append(f"  Hệ số biến động:  {analysis['coeff_var']:.1f}%")
    lines.append(f"  Khoảng biến thiên:{analysis['range']:.1f} A")
    lines.append(f"  P10: {analysis['p10']:.1f} A | P50 (Median): {analysis['p50']:.1f} A | P90: {analysis['p90']:.1f} A")
    lines.append(f"  Min: {analysis['min']:.1f} A | Max: {analysis['max']:.1f} A")
    lines.append("")

    if analysis["slr_value"] is not None:
        lines.append("3. SO SÁNH VỚI ĐỊNH MỨC TĨNH (SLR)")
        lines.append("-" * 80)
        lines.append(f"  Định mức tĩnh SLR:     {analysis['slr_value']:.1f} A")
        lines.append(f"  DLR trung bình vs SLR: {analysis['mean_vs_slr_pct']:+.1f}%")
        lines.append(f"  DLR tối đa vs SLR:     {analysis['max_vs_slr_pct']:+.1f}%")
        lines.append(f"  Tỷ lệ giờ DLR > SLR:   {analysis['pct_hours_above_slr']:.1f}% (tận dụng thêm công suất)")
        lines.append(f"  Tỷ lệ giờ DLR <= SLR:  {analysis['pct_hours_below_slr']:.1f}% (cần giảm tải an toàn)")
        lines.append("")

    lines.append("4. PHÂN TÍCH TẮC NGHẼN & ĐOẠN NÚT THẮT")
    lines.append("-" * 80)
    lines.append(f"  Số giờ nguy cơ nghẽn:  {analysis['congestion_hours']:,} giờ ({analysis['congestion_pct']:.1f}%)")
    seg_name, seg_val = analysis["limiting_segment"]
    lines.append(f"  Phân đoạn hạn chế nhất:{seg_name} (Dòng Min = {seg_val:.1f} A)")
    lines.append("")

    lines.append("5. KẾT LUẬN & KHUYẾN NGHỊ VẬN HÀNH")
    lines.append("-" * 80)
    if analysis.get("mean_vs_slr_pct") and analysis["mean_vs_slr_pct"] > 15:
        lines.append("  ✓ Tiềm năng nâng tải cao: DLR trung bình vượt định mức tĩnh > 15%.")
        lines.append("    -> Khuyến nghị ứng dụng DLR thời gian thực để giải tỏa công suất năng lượng tái tạo.")
    if analysis["congestion_pct"] > 10:
        lines.append("  ⚠️ Chú ý tắc nghẽn: Tỷ lệ thời gian có nguy cơ nghẽn tải > 10%.")
        lines.append("    -> Cần giám sát chặt chẽ các phân đoạn trọng điểm.")
    else:
        lines.append("  ✓ Tình trạng đường dây ổn định và vận hành an toàn.")
    lines.append("=" * 80)

    return "\n".join(lines)


def save_analysis_report(
    analysis: Dict[str, Any],
    comments: str,
    output_dir: Union[str, os.PathLike],
    start_date: str,
    end_date: str,
) -> str:
    """Lưu văn bản báo cáo ra file .txt."""
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"dlr_analysis_report_{start_date}_{end_date}_{ts}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(comments)
    logger.info("Lưu báo cáo phân tích thành công: %s", filepath)
    return filepath


def save_analysis_json(
    analysis: Dict[str, Any],
    output_dir: Union[str, os.PathLike],
    start_date: str,
    end_date: str,
) -> str:
    """Lưu dữ liệu phân tích ra file .json."""
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"dlr_analysis_{start_date}_{end_date}_{ts}.json")

    export_dict = {}
    for k, v in analysis.items():
        if isinstance(v, (pd.DataFrame, pd.Series)):
            export_dict[k] = v.to_dict()
        elif isinstance(v, (np.integer, np.floating)):
            export_dict[k] = float(v)
        else:
            export_dict[k] = v

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_dict, f, indent=2, ensure_ascii=False)
    logger.info("Lưu dữ liệu phân tích JSON thành công: %s", filepath)
    return filepath


# ═══════════════════════════════════════════════════════════════════════════
# THỐNG KÊ CHO PHẦN 2: DLR LÃO HÓA (5 CHU KỲ)
# ═══════════════════════════════════════════════════════════════════════════

def calculate_ampacity_gains(dlr_series: pd.Series, baseline_A: float = BASELINE_AMPACITY_A) -> pd.Series:
    """Tính tỷ lệ tăng khả năng tải (Ampacity Gain %) so với dòng điện cơ sở."""
    if baseline_A <= 0:
        return pd.Series(0.0, index=dlr_series.index)
    return (dlr_series - baseline_A) / baseline_A * 100.0


def calculate_hourly_statistics(dlr_series: pd.Series) -> Dict[str, float]:
    """Tính các đại lượng thống kê mô tả cho chuỗi DLR."""
    return {
        "mean": float(dlr_series.mean()),
        "median": float(dlr_series.median()),
        "std": float(dlr_series.std()),
        "min": float(dlr_series.min()),
        "max": float(dlr_series.max()),
        "q25": float(dlr_series.quantile(0.25)),
        "q75": float(dlr_series.quantile(0.75)),
    }


def generate_yearly_report(cycle_num: int, results: Dict[str, Any], baseline_A: float = BASELINE_AMPACITY_A) -> Dict[int, Any]:
    """Tạo thống kê chi tiết theo từng năm trong chu kỳ 2-năm."""
    df_fixed = results["fixed"]
    df_dynamic = results["dynamic"]
    time_index = results["time_index"]
    start_year_offset, end_year_offset = get_cycle_range(cycle_num)

    yearly_stats: Dict[int, Any] = {}

    for y_offset in range(start_year_offset, end_year_offset):
        year_actual = OPERATIONAL_START_YEAR + y_offset
        y_start = pd.Timestamp(year_actual, 1, 1).tz_localize("Asia/Ho_Chi_Minh")
        y_end = pd.Timestamp(year_actual, 12, 31, 23, 59, 59).tz_localize("Asia/Ho_Chi_Minh")

        mask = (time_index >= y_start) & (time_index <= y_end)
        if mask.sum() == 0:
            continue

        dlr_fix = df_fixed.loc[mask, "DLR"]
        dlr_dyn = df_dynamic.loc[mask, "DLR"]

        diff = dlr_dyn - dlr_fix

        yearly_stats[year_actual] = {
            "fixed": {
                "stats": calculate_hourly_statistics(dlr_fix),
                "gain_pct": float(calculate_ampacity_gains(dlr_fix, baseline_A).mean()),
                "count": len(dlr_fix),
            },
            "dynamic": {
                "stats": calculate_hourly_statistics(dlr_dyn),
                "gain_pct": float(calculate_ampacity_gains(dlr_dyn, baseline_A).mean()),
                "count": len(dlr_dyn),
            },
            "difference": {
                "mean_A": float(diff.mean()),
                "mean_pct": float((diff.mean() / dlr_fix.mean() * 100.0) if dlr_fix.mean() != 0 else 0.0),
                "max_A": float(diff.max()),
                "min_A": float(diff.min()),
            }
        }
    return yearly_stats


def generate_cycle_summary(cycle_num: int, results: Dict[str, Any], baseline_A: float = BASELINE_AMPACITY_A) -> Dict[str, Any]:
    """Tạo thống kê tóm tắt cho toàn bộ một chu kỳ 2 năm."""
    df_fixed = results["fixed"]
    df_dynamic = results["dynamic"]
    fixed_coeff = results["fixed_coeff"]

    dlr_fix = df_fixed["DLR"]
    dlr_dyn = df_dynamic["DLR"]
    diff = dlr_dyn - dlr_fix

    return {
        "cycle": cycle_num,
        "fixed_coeff": fixed_coeff,
        "fixed": {
            "stats": calculate_hourly_statistics(dlr_fix),
            "gain_pct": float(calculate_ampacity_gains(dlr_fix, baseline_A).mean()),
        },
        "dynamic": {
            "stats": calculate_hourly_statistics(dlr_dyn),
            "gain_pct": float(calculate_ampacity_gains(dlr_dyn, baseline_A).mean()),
        },
        "difference": {
            "mean_A": float(diff.mean()),
            "mean_pct": float((diff.mean() / dlr_fix.mean() * 100.0) if dlr_fix.mean() != 0 else 0.0),
            "median_A": float(diff.median()),
            "max_A": float(diff.max()),
            "min_A": float(diff.min()),
            "std_A": float(diff.std()),
            "pct_dynamic_greater": float((diff > 0).sum() / len(diff) * 100.0),
        }
    }


def generate_comparison_report(cycle_num: int, results: Dict[str, Any]) -> str:
    """Tạo báo cáo so sánh Kịch bản A (Cố định) vs Kịch bản B (Động) cho một chu kỳ."""
    df_fixed = results["fixed"]
    df_dynamic = results["dynamic"]
    gains_fixed = calculate_ampacity_gains(df_fixed["DLR"])
    gains_dynamic = calculate_ampacity_gains(df_dynamic["DLR"])

    diff = df_dynamic["DLR"] - df_fixed["DLR"]
    diff_pct = (diff / df_fixed["DLR"] * 100.0).replace([np.inf, -np.inf], 0.0)
    max_diff_idx = diff.abs().idxmax()
    max_diff_val = diff.loc[max_diff_idx]
    max_diff_pct = diff_pct.loc[max_diff_idx]

    report = f"""
╔═══════════════════════════════════════════════════════════════════════════╗
║ CHU KỲ {cycle_num}: SO SÁNH HỆ SỐ CỐ ĐỊNH vs ĐỘNG
╚═══════════════════════════════════════════════════════════════════════════╝

KỊCH BẢN A (HỆ SỐ CỐ ĐỊNH):
  Hệ số: {results['fixed_coeff']:.6f}
  DLR trung bình: {df_fixed['DLR'].mean():.2f} A
  DLR min: {df_fixed['DLR'].min():.2f} A
  DLR max: {df_fixed['DLR'].max():.2f} A
  Ampacity gain: {gains_fixed.mean():.3f}% (so với 850A)

KỊCH BẢN B (HỆ SỐ ĐỘNG):
  DLR trung bình: {df_dynamic['DLR'].mean():.2f} A
  DLR min: {df_dynamic['DLR'].min():.2f} A
  DLR max: {df_dynamic['DLR'].max():.2f} A
  Ampacity gain: {gains_dynamic.mean():.3f}% (so với 850A)

SO SÁNH:
  Độ khác biệt trung bình (Động - Cố định): {diff.mean():.3f} A ({diff_pct.mean():.3f}%)
  Độ khác biệt tối đa: {max_diff_val:.3f} A ({max_diff_pct:.3f}%)
    → Lúc: {max_diff_idx}
  Độ khác biệt tối thiểu: {diff.min():.3f} A
  Tỷ lệ thời gian Động > Cố định: {(diff > 0).sum() / len(diff) * 100:.1f}%

THỐNG KÊ YEARLY (theo năm):
"""
    time_index = results["time_index"]
    start_year, end_year = get_cycle_range(cycle_num)

    for year_offset in range(start_year, end_year):
        year_actual = OPERATIONAL_START_YEAR + year_offset
        y_start = pd.Timestamp(year_actual, 1, 1).tz_localize("Asia/Ho_Chi_Minh")
        y_end = pd.Timestamp(year_actual, 12, 31, 23, 59, 59).tz_localize("Asia/Ho_Chi_Minh")

        mask = (time_index >= y_start) & (time_index <= y_end)
        if mask.sum() == 0:
            continue

        dlr_fix_yr = df_fixed.loc[mask, "DLR"]
        dlr_dyn_yr = df_dynamic.loc[mask, "DLR"]
        gain_fix_yr = calculate_ampacity_gains(dlr_fix_yr).mean()
        gain_dyn_yr = calculate_ampacity_gains(dlr_dyn_yr).mean()

        report += f"""  Năm {year_actual}:
    Cố định: avg DLR={dlr_fix_yr.mean():.1f}A, gain={gain_fix_yr:.3f}%
    Động:   avg DLR={dlr_dyn_yr.mean():.1f}A, gain={gain_dyn_yr:.3f}%
"""
    report += "\n"
    return report


def generate_full_report(all_results: Dict[int, Any], baseline_A: float = BASELINE_AMPACITY_A) -> str:
    """Tạo báo cáo chi tiết tổng hợp toàn bộ 5 chu kỳ lão hóa."""
    lines = []
    lines.append("╔" + "═" * 78 + "╗")
    lines.append("║" + " " * 78 + "║")
    lines.append("║" + "BÁO CÁO CHI TIẾT: SO SÁNH HỆ SỐ CỐ ĐỊNH vs ĐỘNG (5 CHU KỲ)".center(78) + "║")
    lines.append("║" + "Dynamic Line Rating - Đường dây 220kV Tháp Chàm - Vĩnh Tân".center(78) + "║")
    lines.append("║" + " " * 78 + "║")
    lines.append("╚" + "═" * 78 + "╝")
    lines.append("")

    lines.append("═" * 80)
    lines.append("TÓM TẮT TOÀN BỘ 5 CHU KỲ")
    lines.append("═" * 80)
    lines.append("")

    all_cycle_summaries = []
    for c_num in range(1, 6):
        if c_num in all_results:
            all_cycle_summaries.append(generate_cycle_summary(c_num, all_results[c_num], baseline_A))

    lines.append(f"{'Chu kỳ':<10} {'Năm':<10} {'Hệ số':<12} {'DLR Cố định':<15} {'DLR Động':<15} {'Chênh lệch':<15}")
    lines.append("─" * 80)

    for summary in all_cycle_summaries:
        c = summary["cycle"]
        s_yr, e_yr = get_cycle_range(c)
        yr_str = f"{s_yr}-{e_yr}"
        f_mean = summary["fixed"]["stats"]["mean"]
        d_mean = summary["dynamic"]["stats"]["mean"]
        diff_m = summary["difference"]["mean_A"]
        coeff = summary["fixed_coeff"]
        lines.append(f"{c:<10} {yr_str:<10} {coeff:<12.6f} {f_mean:<15.2f} {d_mean:<15.2f} {diff_m:+15.2f}")

    lines.append("")
    lines.append("")

    for summary in all_cycle_summaries:
        c = summary["cycle"]
        s_yr, e_yr = get_cycle_range(c)
        lines.append("═" * 80)
        lines.append(f"CHU KỲ {c} (NĂM {s_yr}-{e_yr})")
        lines.append("═" * 80)
        lines.append("")
        lines.append(f"Hệ số phát xạ/hấp thụ cố định: {summary['fixed_coeff']:.6f}")
        lines.append("")
        lines.append("── KỊCH BẢN A: HỆ SỐ CỐ ĐỊNH ──")
        lines.append(f"  Ampacity gain: {summary['fixed']['gain_pct']:+7.3f}% (so với {baseline_A}A cơ sở)")
        lines.append(f"  DLR trung bình: {summary['fixed']['stats']['mean']:.2f} A")
        lines.append(f"  DLR min/max: {summary['fixed']['stats']['min']:.2f} / {summary['fixed']['stats']['max']:.2f} A")
        lines.append("")
        lines.append("── KỊCH BẢN B: HỆ SỐ ĐỘNG ──")
        lines.append(f"  Ampacity gain: {summary['dynamic']['gain_pct']:+7.3f}% (so với {baseline_A}A cơ sở)")
        lines.append(f"  DLR trung bình: {summary['dynamic']['stats']['mean']:.2f} A")
        lines.append(f"  DLR min/max: {summary['dynamic']['stats']['min']:.2f} / {summary['dynamic']['stats']['max']:.2f} A")
        lines.append("")
        lines.append("── SO SÁNH (ĐỘNG - CỐ ĐỊNH) ──")
        lines.append(f"  Chênh lệch trung bình: {summary['difference']['mean_A']:+.3f} A ({summary['difference']['mean_pct']:+.3f}%)")
        lines.append(f"  Chênh lệch cực đại: {summary['difference']['max_A']:+.3f} A")
        lines.append(f"  Chênh lệch tối thiểu: {summary['difference']['min_A']:+.3f} A")
        lines.append(f"  Tỷ lệ thời gian ĐỘNG > CỐ ĐỊNH: {summary['difference']['pct_dynamic_greater']:.1f}%")
        lines.append("")

        yearly = generate_yearly_report(c, all_results[c], baseline_A)
        lines.append("── PHÂN TÍCH THEO NĂM ──")
        for y_act in sorted(yearly.keys()):
            y_s = yearly[y_act]
            lines.append(f"  Năm {y_act}:")
            lines.append(f"    Cố định: DLR={y_s['fixed']['stats']['mean']:.2f}A, gain={y_s['fixed']['gain_pct']:+.3f}%")
            lines.append(f"    Động:   DLR={y_s['dynamic']['stats']['mean']:.2f}A, gain={y_s['dynamic']['gain_pct']:+.3f}%")
            lines.append(f"    Chênh:  {y_s['difference']['mean_A']:+.2f}A ({y_s['difference']['mean_pct']:+.3f}%)")
        lines.append("")

    lines.append("═" * 80)
    lines.append("NHẬN XÉT TỔNG QUÁT")
    lines.append("═" * 80)
    all_fix_gain = np.mean([s["fixed"]["gain_pct"] for s in all_cycle_summaries])
    all_dyn_gain = np.mean([s["dynamic"]["gain_pct"] for s in all_cycle_summaries])

    lines.append(f"Ampacity gain trung bình toàn bộ 5 chu kỳ:")
    lines.append(f"  - Hệ số cố định: {all_fix_gain:+.3f}%")
    lines.append(f"  - Hệ số động:   {all_dyn_gain:+.3f}%")
    lines.append(f"  - Chênh lệch hiệu quả: {all_dyn_gain - all_fix_gain:+.3f}%")
    lines.append("")
    lines.append("Ý nghĩa khoa học:")
    lines.append("  - Sự biến thiên của hệ số phát xạ và hấp thụ do lão hóa bề mặt dây dẫn làm tăng khả năng tản nhiệt bức xạ.")
    lines.append("  - Việc mô phỏng chính xác hệ số động theo thời gian phản ánh đúng thực tế vận hành và giúp khai thác tối đa năng lực truyền tải.")
    lines.append("")

    return "\n".join(lines)
