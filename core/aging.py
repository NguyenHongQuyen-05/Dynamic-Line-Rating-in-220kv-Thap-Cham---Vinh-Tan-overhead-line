"""
core/aging.py
-------------
Mô hình biến thiên hệ số phát xạ (ε) và hệ số hấp thụ (α) theo thời gian vận hành
và lão hóa bề mặt của dây dẫn truyền tải.

Công thức thực nghiệm:
    y = 0.23 + 0.7 · x / (1.22 + x)

Trong đó:
    - y: Hệ số phát xạ ε hoặc hệ số hấp thụ α (0.23 ≤ y ≤ 0.93)
    - x: Thời gian vận hành tích lũy tính từ năm 2014 (năm)
    - Mốc t = 0 ứng với năm 2014 (dây mới lắp đặt)
    - Bước nhảy thời gian: 1 giờ = 1 / 8760 năm
"""

from datetime import datetime
from typing import Tuple, Union
import numpy as np
import pandas as pd

from core.config import OPERATIONAL_START_YEAR


def datetime_to_operational_years(dt: Union[datetime, pd.Timestamp]) -> float:
    """
    Chuyển đổi mốc thời gian thành số năm vận hành kể từ năm 2014.

    Parameters
    ----------
    dt : datetime hoặc pd.Timestamp

    Returns
    -------
    float : Số năm vận hành tích lũy (x >= 0.0)
    """
    if isinstance(dt, pd.Timestamp):
        year_decimal = dt.year + (dt.dayofyear - 1) / 365.25 + dt.hour / (365.25 * 24.0)
    else:
        year_decimal = dt.year + (dt.timetuple().tm_yday - 1) / 365.25 + dt.hour / (365.25 * 24.0)

    operational_years = year_decimal - OPERATIONAL_START_YEAR
    return max(float(operational_years), 0.0)


def calculate_coefficient(x: Union[float, np.ndarray, pd.Series]) -> Union[float, np.ndarray, pd.Series]:
    """
    Tính hệ số phát xạ / hấp thụ theo công thức phi tuyến:
    y = 0.23 + 0.7 * x / (1.22 + x)

    Parameters
    ----------
    x : float, np.ndarray hoặc pd.Series
        Thời gian vận hành (năm)

    Returns
    -------
    float, np.ndarray hoặc pd.Series
        Giá trị hệ số tương ứng (0.23 khi x=0, tiệm cận 0.93 khi x lớn)
    """
    return 0.23 + 0.7 * x / (1.22 + x)


def get_coefficient_series(
    time_index: pd.DatetimeIndex,
    scenario: str = "dynamic",
    fixed_value: float = None,
) -> pd.Series:
    """
    Tạo chuỗi giá trị hệ số phát xạ / hấp thụ cho toàn bộ chuỗi thời gian.

    Parameters
    ----------
    time_index : pd.DatetimeIndex
    scenario : str
        - 'dynamic': Hệ số biến thiên liên tục theo từng giờ vận hành
        - 'fixed': Hệ số cố định nhận giá trị fixed_value
    fixed_value : float, optional
        Giá trị cố định khi scenario='fixed'

    Returns
    -------
    pd.Series : Chuỗi hệ số tương ứng với time_index
    """
    if scenario == "dynamic":
        operational_years = np.array([datetime_to_operational_years(dt) for dt in time_index])
        coefficients = calculate_coefficient(operational_years)
        return pd.Series(coefficients, index=time_index, name="dynamic_coefficient")

    elif scenario == "fixed":
        if fixed_value is None:
            raise ValueError("Cần cung cấp fixed_value khi scenario='fixed'")
        return pd.Series(float(fixed_value), index=time_index, name="fixed_coefficient")

    else:
        raise ValueError(f"Kịch bản không hợp lệ: '{scenario}'. Chỉ chấp nhận 'dynamic' hoặc 'fixed'.")


def get_cycle_range(cycle_num: int) -> Tuple[int, int]:
    """
    Lấy khoảng năm vận hành (độ lệch so với 2014) cho chu kỳ 2 năm.

    Parameters
    ----------
    cycle_num : int (1 đến 5)

    Returns
    -------
    tuple : (start_year_offset, end_year_offset)
        Ví dụ: Chu kỳ 1 -> (0, 2), Chu kỳ 2 -> (2, 4), ...
    """
    if not (1 <= cycle_num <= 5):
        raise ValueError(f"Số chu kỳ phải từ 1 đến 5, nhận {cycle_num}")
    start_year_offset = (cycle_num - 1) * 2
    end_year_offset = cycle_num * 2
    return (start_year_offset, end_year_offset)


def get_cycle_dates(cycle_num: int) -> Tuple[datetime, datetime]:
    """
    Lấy ngày bắt đầu và kết thúc chuẩn theo dương lịch cho chu kỳ 2 năm.
    """
    start_offset, end_offset = get_cycle_range(cycle_num)
    start_date = datetime(OPERATIONAL_START_YEAR + start_offset, 1, 1)
    end_date = datetime(OPERATIONAL_START_YEAR + end_offset, 1, 1)
    return (start_date, end_date)


def get_coefficient_at_year_end(year_offset: int) -> float:
    """
    Lấy hệ số phát xạ / hấp thụ tại thời điểm cuối của một năm vận hành.
    """
    return float(calculate_coefficient(float(year_offset)))
