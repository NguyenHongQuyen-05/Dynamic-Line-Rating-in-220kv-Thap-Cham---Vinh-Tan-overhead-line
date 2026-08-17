"""
core/physics.py
---------------
Triển khai mô hình nhiệt động học tính toán dòng điện định mức động (Ampacity)
cho dây dẫn trần trên không theo tiêu chuẩn IEEE Std 738-2023 / IEEE Std 738-2012.

Phương trình cân bằng nhiệt trạng thái dừng:
    q_c + q_r = q_s + I² · R(T_c)
    ⟹ I = √[ max(q_c + q_r - q_s, 0) / R(T_c) ]

Trong đó:
    - q_c: Nhiệt làm mát đối lưu (tự nhiên & cưỡng bức) [W/m]
    - q_r: Nhiệt tản xạ bức xạ [W/m]
    - q_s: Nhiệt hấp thụ từ bức xạ mặt trời (GHI) [W/m]
    - R(T_c): Điện trở AC ở nhiệt độ vận hành tối đa của dây [Ω/m]
"""

import math
import logging
from typing import Dict, Union, Optional
import numpy as np
import pandas as pd

from core.config import C2K, STEFAN_BOLTZMANN

logger = logging.getLogger(__name__)


def wind_direction_factor(phi_deg: Union[float, np.ndarray, pd.Series]) -> Union[float, np.ndarray, pd.Series]:
    """
    Tính hệ số hướng gió K_angle tác dụng lên dây dẫn (IEEE 738-2023 eq. 19).

    Parameters
    ----------
    phi_deg : góc hợp bởi hướng gió và trục đường dây [°]
    """
    phi180 = np.remainder(np.abs(phi_deg), 180.0)
    phi90 = 90.0 - np.abs(phi180 - 90.0)
    phi_rad = np.deg2rad(phi90)

    k_angle = (
        1.194
        - np.cos(phi_rad)
        + 0.194 * np.cos(2 * phi_rad)
        + 0.368 * np.sin(2 * phi_rad)
    )
    return np.clip(k_angle, 0.0, 1.0)


def film_temperature(t_cond_k: float, t_air_k: Union[float, pd.Series]) -> Union[float, pd.Series]:
    """Nhiệt độ màng không khí bao quanh dây dẫn T_film = (T_cond + T_air) / 2 [K]."""
    return (t_cond_k + t_air_k) / 2.0


def dynamic_viscosity(t_film_k: Union[float, pd.Series]) -> Union[float, pd.Series]:
    """Độ nhớt động học của không khí [kg m⁻¹ s⁻¹] (IEEE 738-2023 eq. 13)."""
    return 1.458e-6 * (t_film_k ** 1.5) / (t_film_k - C2K + 383.4)


def thermal_conductivity(t_film_k: Union[float, pd.Series]) -> Union[float, pd.Series]:
    """Độ dẫn nhiệt của không khí [W m⁻¹ °C⁻¹] (IEEE 738-2023 eq. 17)."""
    t_c = t_film_k - C2K
    return 2.424e-2 + 7.477e-5 * t_c - 4.407e-9 * (t_c ** 2)


def air_density(pressure_pa: Union[float, pd.Series],
                temperature_k: Union[float, pd.Series],
                relative_humidity: float = 0.5) -> Union[float, pd.Series]:
    """Mật độ không khí ẩm theo phương trình khí lý tưởng [kg m⁻³]."""
    r_dry = 287.058
    r_wv = 461.495
    t_c = temperature_k - C2K
    # Áp suất bão hòa theo công thức Tetens [Pa]
    p_sat = 610.78 * np.exp(17.27 * t_c / (t_c + 237.3))
    p_wv = 0.01 * relative_humidity * p_sat
    return (pressure_pa - p_wv) / (r_dry * temperature_k) + p_wv / (r_wv * temperature_k)


def convective_cooling(
    t_cond_k: float,
    t_air_k: Union[float, pd.Series],
    windspeed_ms: Union[float, pd.Series],
    k_angle: Union[float, pd.Series],
    diameter_m: float,
    pressure_pa: Union[float, pd.Series],
) -> Union[float, pd.Series]:
    """
    Nhiệt lượng làm mát đối lưu q_c [W/m] (IEEE 738-2023).
    q_c = max(q_c0: đối lưu tự nhiên, q_c1: đối lưu cưỡng bức gió thấp, q_c2: đối lưu cưỡng bức gió cao).
    """
    t_film = film_temperature(t_cond_k, t_air_k)
    kf = thermal_conductivity(t_film)
    mu_f = dynamic_viscosity(t_film)
    rho_f = air_density(pressure_pa, t_film)
    n_re = (diameter_m * rho_f * windspeed_ms) / mu_f
    dt = t_cond_k - t_air_k

    # Đối lưu tự nhiên (không có gió)
    q_c0 = 3.645 * (rho_f ** 0.5) * (diameter_m ** 0.75) * (dt ** 1.25)
    # Đối lưu cưỡng bức - gió thấp
    q_c1 = k_angle * (1.01 + 1.35 * (n_re ** 0.52)) * kf * dt
    # Đối lưu cưỡng bức - gió cao
    q_c2 = k_angle * 0.754 * (n_re ** 0.6) * kf * dt

    if isinstance(q_c0, pd.Series):
        return pd.concat([q_c0, q_c1, q_c2], axis=1).max(axis=1)
    return max(q_c0, q_c1, q_c2)


def radiative_cooling(
    diameter_m: float,
    emissivity: Union[float, pd.Series],
    t_cond_k: float,
    t_air_k: Union[float, pd.Series],
) -> Union[float, pd.Series]:
    """Nhiệt lượng tản nhiệt bức xạ q_r [W/m] = π · D · ε · σ · (T_c⁴ - T_a⁴)."""
    return math.pi * diameter_m * emissivity * STEFAN_BOLTZMANN * (t_cond_k ** 4 - t_air_k ** 4)


def solar_heating(
    solar_ghi: Union[float, pd.Series],
    diameter_m: float,
    absorptivity: Union[float, pd.Series],
) -> Union[float, pd.Series]:
    """Nhiệt lượng hấp thụ từ mặt trời q_s [W/m] = α · GHI · D."""
    return solar_ghi * diameter_m * absorptivity


def ampacity_ieee738(
    windspeed: Union[float, pd.Series],
    wind_conductor_angle: Union[float, pd.Series],
    temp_ambient_air: Union[float, pd.Series],
    pressure_Pa: Union[float, pd.Series],
    solar_ghi: Union[float, pd.Series],
    temp_conductor_K: float,
    diameter_m: float,
    resistance_ohm_per_m: float,
    emissivity: Union[float, pd.Series] = 0.8,
    absorptivity: Union[float, pd.Series] = 0.8,
) -> Union[float, pd.Series]:
    """
    Tính khả năng tải dòng điện định mức (Ampacity) theo IEEE Std 738.

    Parameters
    ----------
    windspeed : float hoặc Series
        Tốc độ gió [m/s]
    wind_conductor_angle : float hoặc Series
        Góc hợp bởi hướng gió và trục đường dây [°]
    temp_ambient_air : float hoặc Series
        Nhiệt độ môi trường [K]
    pressure_Pa : float hoặc Series
        Áp suất khí quyển [Pa]
    solar_ghi : float hoặc Series
        Bức xạ mặt trời tổng cộng (GHI) [W/m²]
    temp_conductor_K : float
        Nhiệt độ tối đa cho phép của dây dẫn [K]
    diameter_m : float
        Đường kính ngoài của dây dẫn [m]
    resistance_ohm_per_m : float
        Điện trở AC của dây dẫn tại nhiệt độ tối đa [Ω/m]
    emissivity : float hoặc Series
        Hệ số phát xạ nhiệt ε [0-1] (cố định hoặc động)
    absorptivity : float hoặc Series
        Hệ số hấp thụ bức xạ mặt trời α [0-1] (cố định hoặc động)

    Returns
    -------
    float hoặc pd.Series : Khả năng tải dòng điện cho phép [A]
    """
    k_ang = wind_direction_factor(wind_conductor_angle)

    q_c = convective_cooling(
        t_cond_k=temp_conductor_K,
        t_air_k=temp_ambient_air,
        windspeed_ms=windspeed,
        k_angle=k_ang,
        diameter_m=diameter_m,
        pressure_pa=pressure_Pa,
    )
    q_r = radiative_cooling(
        diameter_m=diameter_m,
        emissivity=emissivity,
        t_cond_k=temp_conductor_K,
        t_air_k=temp_ambient_air,
    )
    q_s = solar_heating(
        solar_ghi=solar_ghi,
        diameter_m=diameter_m,
        absorptivity=absorptivity,
    )

    heat_balance_numerator = q_c + q_r - q_s
    if isinstance(heat_balance_numerator, pd.Series):
        heat_balance_numerator = heat_balance_numerator.clip(lower=0.0)
    else:
        heat_balance_numerator = max(heat_balance_numerator, 0.0)

    current_ampacity = np.sqrt(heat_balance_numerator / resistance_ohm_per_m)
    return current_ampacity


def calc_dlr_for_line(
    df_segments: pd.DataFrame,
    weather_data: Dict[int, pd.DataFrame],
    conductor: Dict[str, any],
    forecast_margin: Optional[Dict[str, float]] = None,
    emissivity_series: Optional[Union[float, pd.Series]] = None,
    absorptivity_series: Optional[Union[float, pd.Series]] = None,
) -> pd.DataFrame:
    """
    Tính DLR từng giờ cho tất cả các phân đoạn và xác định DLR tuyến (giá trị nhỏ nhất).

    Parameters
    ----------
    df_segments : pd.DataFrame
        Bảng phân đoạn từ divide_line_into_segments()
    weather_data : dict
        Dữ liệu thời tiết từng phân đoạn {segment_id: pd.DataFrame}
    conductor : dict
        Thông số kỹ thuật dây dẫn
    forecast_margin : dict, optional
        Biên an toàn dự báo khí tượng {'windspeed': -1.0, 'temperature': 2.0, ...}
    emissivity_series : float hoặc pd.Series, optional
        Hệ số phát xạ tùy chỉnh (ghi đè thông số conductor)
    absorptivity_series : float hoặc pd.Series, optional
        Hệ số hấp thụ tùy chỉnh (ghi đè thông số conductor)

    Returns
    -------
    pd.DataFrame :
        - Cột 'DLR': Dòng tải định mức toàn tuyến (min các phân đoạn) [A]
        - Cột 'seg_{id}': Dòng tải từng phân đoạn [A]
        - Index: DatetimeIndex (Múi giờ Asia/Ho_Chi_Minh)
    """
    if forecast_margin is None:
        forecast_margin = {}

    t_cond_k = conductor["max_temp_C"] + C2K
    diameter = conductor["diameter_m"]
    resistance = conductor["resistance_ohm_per_m"]
    static_emissivity = conductor.get("emissivity", 0.8)
    static_absorptivity = conductor.get("absorptivity", 0.8)

    seg_ratings: Dict[str, pd.Series] = {}

    for seg_id, seg_row in df_segments.iterrows():
        seg_id_int = int(seg_id)
        if seg_id_int not in weather_data:
            logger.warning("Không có dữ liệu thời tiết cho đoạn %d, bỏ qua.", seg_id_int)
            continue

        w = weather_data[seg_id_int].copy()

        # Áp dụng biên an toàn khí tượng
        windspeed_adj = (w["windspeed_ms"] + forecast_margin.get("windspeed", 0.0)).clip(lower=0.0)
        temp_adj = w["temperature_K"] + forecast_margin.get("temperature", 0.0)
        ghi_adj = (w["ghi_Wm2"] + forecast_margin.get("solar_ghi", 0.0)).clip(lower=0.0)
        pressure_adj = (w["pressure_Pa"] + forecast_margin.get("pressure", 0.0)).clip(lower=40_000.0)

        # Góc gió tương đối so với trục dây
        wind_conductor_angle = w["wind_direction_deg"] - float(seg_row["azimuth_deg"])

        emit = emissivity_series if emissivity_series is not None else static_emissivity
        absorb = absorptivity_series if absorptivity_series is not None else static_absorptivity

        amp = ampacity_ieee738(
            windspeed=windspeed_adj,
            wind_conductor_angle=wind_conductor_angle,
            temp_ambient_air=temp_adj,
            pressure_Pa=pressure_adj,
            solar_ghi=ghi_adj,
            temp_conductor_K=t_cond_k,
            diameter_m=diameter,
            resistance_ohm_per_m=resistance,
            emissivity=emit,
            absorptivity=absorb,
        )
        seg_ratings[f"seg_{seg_id_int}"] = amp

    if not seg_ratings:
        raise RuntimeError("Không có phân đoạn nào tính toán được Ampacity!")

    df_ratings = pd.DataFrame(seg_ratings)
    # DLR của đường dây bằng giá trị nhỏ nhất của tất cả các phân đoạn
    df_ratings.insert(0, "DLR", df_ratings.min(axis=1))

    logger.info("Hoàn thành tính DLR: Trung bình = %.1f A | Min = %.1f A | Max = %.1f A",
                df_ratings["DLR"].mean(), df_ratings["DLR"].min(), df_ratings["DLR"].max())

    return df_ratings
