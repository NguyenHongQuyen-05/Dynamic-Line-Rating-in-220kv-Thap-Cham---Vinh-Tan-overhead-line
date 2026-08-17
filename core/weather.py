"""
core/weather.py
---------------
Truy xuất dữ liệu thời tiết lịch sử theo từng giờ từ Open-Meteo Historical API:
- temperature_2m        [°C]  → [K]
- wind_speed_10m        [m/s]
- wind_direction_10m    [°]
- surface_pressure      [hPa] → [Pa]
- shortwave_radiation   [W/m²] = GHI
"""

import time
import logging
from typing import Dict, Union
import requests
import numpy as np
import pandas as pd
from tqdm import tqdm

from core.config import C2K, TIMEZONE_VN

logger = logging.getLogger(__name__)

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARIABLES = [
    "temperature_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "surface_pressure",
    "shortwave_radiation",
]


def fetch_weather_single_point(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    retries: int = 3,
    retry_delay: float = 3.0,
    timeout: int = 120,
) -> pd.DataFrame:
    """
    Tải dữ liệu thời tiết từng giờ cho 1 điểm tọa độ (lat, lon) từ Open-Meteo.

    Parameters
    ----------
    lat, lon : float
        Tọa độ WGS84
    start_date, end_date : str
        Chuỗi ngày 'YYYY-MM-DD'
    retries : int
        Số lần thử lại nếu kết nối lỗi
    retry_delay : float
        Thời gian chờ giữa các lần thử lại (giây)

    Returns
    -------
    pd.DataFrame :
        Index: DatetimeIndex (Múi giờ Asia/Ho_Chi_Minh)
        Columns: [temperature_K, windspeed_ms, wind_direction_deg, pressure_Pa, ghi_Wm2]
    """
    params = {
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "start_date": str(start_date)[:10],
        "end_date": str(end_date)[:10],
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": TIMEZONE_VN,
        "wind_speed_unit": "ms",
    }

    raw = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            raw = resp.json()
            break
        except Exception as exc:
            logger.warning("Lần thử %d/%d: Lỗi tải thời tiết (lat=%.4f, lon=%.4f): %s",
                           attempt, retries, lat, lon, exc)
            if attempt == retries:
                raise
            time.sleep(retry_delay * attempt)

    if raw is None or "hourly" not in raw:
        raise RuntimeError(f"Dữ liệu API trả về không hợp lệ cho tọa độ ({lat}, {lon})")

    hourly = raw["hourly"]
    time_index = pd.to_datetime(hourly["time"]).tz_localize(TIMEZONE_VN)

    df_weather = pd.DataFrame(
        {
            "temperature_K": np.array(hourly["temperature_2m"], dtype=float) + C2K,
            "windspeed_ms": np.array(hourly["wind_speed_10m"], dtype=float).clip(min=0.0),
            "wind_direction_deg": np.array(hourly["wind_direction_10m"], dtype=float),
            "pressure_Pa": (np.array(hourly["surface_pressure"], dtype=float) * 100.0).clip(min=40_000.0),
            "ghi_Wm2": np.array(hourly["shortwave_radiation"], dtype=float).clip(min=0.0),
        },
        index=time_index,
    )
    df_weather.index.name = "time_utc7"
    return df_weather


def fetch_weather_for_segments(
    segment_points: pd.DataFrame,
    start_date: Union[str, pd.Timestamp],
    end_date: Union[str, pd.Timestamp],
    request_delay: float = 0.3,
    df_segments: pd.DataFrame = None,
) -> Dict[int, pd.DataFrame]:
    """
    Tải dữ liệu thời tiết cho toàn bộ các điểm đại diện của các phân đoạn đường dây.

    Parameters
    ----------
    segment_points : pd.DataFrame
        DataFrame chứa các cột 'lat', 'lon', index là segment_id
    start_date, end_date : str hoặc Timestamp
        Khoảng thời gian cần truy xuất
    request_delay : float
        Khoảng nghỉ giữa các requests để tránh rate-limit API (giây)

    Returns
    -------
    dict: {segment_id: pd.DataFrame}
    """
    # Hỗ trợ truyền qua df_segments để tương thích ngược
    if segment_points is None and df_segments is not None:
        segment_points = df_segments

    start_str = str(start_date)[:10]
    end_str = str(end_date)[:10]

    weather_data: Dict[int, pd.DataFrame] = {}

    logger.info("Đang tải dữ liệu thời tiết cho %d phân đoạn từ %s đến %s...",
                len(segment_points), start_str, end_str)

    for seg_id, row in tqdm(segment_points.iterrows(), total=len(segment_points), desc="Open-Meteo API"):
        df_w = fetch_weather_single_point(
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            start_date=start_str,
            end_date=end_str,
        )
        weather_data[int(seg_id)] = df_w
        if request_delay > 0:
            time.sleep(request_delay)

    return weather_data
