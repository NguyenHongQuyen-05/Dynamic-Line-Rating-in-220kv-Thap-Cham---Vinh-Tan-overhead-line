"""
core/conductor.py
-----------------
Đọc và xử lý thông số kỹ thuật dây dẫn từ file Excel.
"""

import logging
import os
from typing import Optional, Dict, Any
import pandas as pd

from core.config import CONDUCTOR_PARAMS_XLSX

logger = logging.getLogger(__name__)


def read_conductor_params(
    fpath: str | os.PathLike = CONDUCTOR_PARAMS_XLSX,
    sheet_name: str = "conductor_params",
    operating_temp_C: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Đọc thông số dây dẫn từ file Excel và chuyển đổi đơn vị về hệ SI.

    Parameters
    ----------
    fpath : str hoặc Path
        Đường dẫn file .xlsx
    sheet_name : str
        Tên sheet chứa thông số dây dẫn (mặc định: 'conductor_params')
    operating_temp_C : float, optional
        Nhiệt độ vận hành để nội suy điện trở giữa R_25C và R_75C.
        Nếu None, mặc định sử dụng R_75C.

    Returns
    -------
    dict :
        - line_name: str
        - conductor_type: str
        - diameter_m: float [m]
        - resistance_ohm_per_m: float [Ω/m]
        - max_temp_C: float [°C]
        - emissivity: float [0-1]
        - absorptivity: float [0-1]
        - voltage_kV: float [kV]
        - nominal_rating_A: float [A]
    """
    fpath_str = str(fpath)
    if not os.path.exists(fpath_str):
        raise FileNotFoundError(
            f"Không tìm thấy file thông số dây dẫn: {fpath_str}\n"
            "Vui lòng chạy 'python setup_template.py' để tạo file mẫu."
        )

    df = pd.read_excel(fpath_str, sheet_name=sheet_name)

    if df.empty:
        raise ValueError("Sheet Excel rỗng – vui lòng nhập thông số kỹ thuật dây dẫn.")
    if len(df) > 1:
        logger.warning("File Excel có %d dòng; sử dụng dòng đầu tiên.", len(df))

    row = df.iloc[0]

    # Chuyển đổi điện trở từ Ω/km sang Ω/m
    r_25 = float(row["resistance_25C_ohm_per_km"]) / 1000.0
    r_75 = float(row["resistance_75C_ohm_per_km"]) / 1000.0

    if operating_temp_C is not None:
        t_op = max(25.0, min(float(operating_temp_C), 75.0))
        r_op = r_25 + (r_75 - r_25) / (75.0 - 25.0) * (t_op - 25.0)
        logger.info("Nội suy điện trở tại %.1f°C: %.6e Ω/m", t_op, r_op)
    else:
        r_op = r_75
        logger.info("Sử dụng điện trở AC tại 75°C: %.6e Ω/m", r_op)

    diameter_m = float(row["diameter_mm"]) / 1000.0

    params = {
        "line_name": str(row["line_name"]),
        "conductor_type": str(row["conductor_type"]),
        "diameter_m": diameter_m,
        "resistance_ohm_per_m": r_op,
        "max_temp_C": float(row["max_conductor_temp_C"]),
        "emissivity": float(row.get("emissivity", 0.8)),
        "absorptivity": float(row.get("absorptivity", 0.8)),
        "voltage_kV": float(row.get("voltage_kV", 220.0)),
        "nominal_rating_A": float(row.get("nominal_rating_A", float("nan"))),
    }

    logger.info("Thông số kỹ thuật dây dẫn:\n%s",
                "\n".join(f"  - {k}: {v}" for k, v in params.items()))

    return params
