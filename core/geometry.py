"""
core/geometry.py
----------------
Xử lý không gian và thuật toán phân đoạn đường dây truyền tải:
1. Đọc và hợp nhất shapefile tuyến đường dây.
2. Tự động chuyển đổi sang hệ tọa độ phẳng UTM Zone 48N (EPSG:32648).
3. Lấy mẫu phương vị (azimuth) dọc theo tuyến.
4. Nhóm các đoạn có cùng hướng (sai số góc < 5°).
5. Chia nhỏ mỗi nhóm thành các đoạn ~5km.
6. Xử lý đoạn lẻ: giữ nguyên nếu 3-5km, gộp vào đoạn trước nếu < 3km.
7. Trích xuất tọa độ điểm giữa (WGS84) phục vụ truy vấn khí tượng.
"""

import math
import logging
from typing import Optional, Tuple, List
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, box
from shapely.ops import unary_union

from core.config import METRIC_CRS, WGS84_CRS

logger = logging.getLogger(__name__)


def load_line_shapefile(
    fpath: str,
    src_crs: str = WGS84_CRS,
    line_name_col: Optional[str] = None,
    bbox: Optional[Tuple[float, float, float, float]] = None,
) -> gpd.GeoSeries:
    """
    Đọc shapefile đường dây và chuyển đổi thành một đối tượng GeoSeries đơn (CRS metric).

    Parameters
    ----------
    fpath : str
        Đường dẫn file .shp
    src_crs : str
        CRS nguồn (mặc định EPSG:4326)
    line_name_col : str, optional
        Cột tên đường dây để ghi log
    bbox : tuple of float, optional
        (min_lat, max_lat, min_lon, max_lon) để lọc phạm vi địa lý.

    Returns
    -------
    gpd.GeoSeries : chứa 1 phần tử LineString/MultiLineString với CRS = METRIC_CRS (EPSG:32648)
    """
    gdf = gpd.read_file(fpath)

    if gdf.crs is None:
        gdf = gdf.set_crs(src_crs)
    elif str(gdf.crs).upper() != src_crs.upper():
        logger.info("Chuyển đổi CRS từ %s sang %s", gdf.crs, src_crs)
        gdf = gdf.to_crs(src_crs)

    if bbox is not None:
        min_lat, max_lat, min_lon, max_lon = bbox
        logger.info("Lọc bounding box: lat [%.3f, %.3f], lon [%.3f, %.3f]",
                    min_lat, max_lat, min_lon, max_lon)
        bbox_geom = box(min_lon, min_lat, max_lon, max_lat)
        gdf = gdf[gdf.geometry.intersects(bbox_geom)]

        if gdf.empty:
            raise ValueError(f"Không có dữ liệu hình học trong bounding box: {bbox}")
        logger.info("Tìm thấy %d đối tượng hình học trong bounding box", len(gdf))

    if line_name_col and line_name_col in gdf.columns:
        logger.info("Tên đường dây trong shapefile: %s", gdf[line_name_col].iloc[0])

    merged = unary_union(gdf.geometry)
    line_wgs84 = gpd.GeoSeries([merged], crs=src_crs)
    line_metric = line_wgs84.to_crs(METRIC_CRS)

    total_len_km = line_metric.length.iloc[0] / 1000.0
    logger.info("Tổng chiều dài đường dây: %.2f km (Hệ tọa độ %s)", total_len_km, METRIC_CRS)

    return line_metric


def calculate_azimuth(pt1: Tuple[float, float], pt2: Tuple[float, float]) -> float:
    """
    Tính phương vị (góc từ hướng Bắc theo chiều kim đồng hồ) giữa hai điểm WGS84.
    Đơn vị: độ [°], phạm vi [-180, 180].

    pt1, pt2: (lon, lat)
    """
    lon1, lat1 = math.radians(pt1[0]), math.radians(pt1[1])
    lon2, lat2 = math.radians(pt2[0]), math.radians(pt2[1])
    d_lon = lon2 - lon1
    x = math.sin(d_lon) * math.cos(lat2)
    y = (math.cos(lat1) * math.sin(lat2)
         - math.sin(lat1) * math.cos(lat2) * math.cos(d_lon))
    return math.degrees(math.atan2(x, y))


def divide_line_into_segments(
    line_metric: gpd.GeoSeries,
    segment_length_km: float = 5.0,
    azimuth_tolerance_deg: float = 5.0,
    min_segment_length_km: float = 3.0,
) -> pd.DataFrame:
    """
    Phân đoạn đường dây theo logic kết hợp:
      1. Phương vị (nhóm các đoạn thẳng có cùng hướng, dung sai <= 5°).
      2. Chiều dài mục tiêu (mỗi nhóm phương vị chia thành các đoạn ~5km).
      3. Xử lý đoạn lẻ cuối nhóm (3-5km giữ nguyên, < 3km gộp vào đoạn trước).

    Parameters
    ----------
    line_metric : GeoSeries (CRS = METRIC_CRS)
    segment_length_km : float
        Chiều dài mục tiêu của từng đoạn (mặc định: 5.0 km)
    azimuth_tolerance_deg : float
        Ngưỡng dung sai góc phương vị để nhóm (mặc định: 5.0 độ)
    min_segment_length_km : float
        Chiều dài tối thiểu để coi là một đoạn độc lập (mặc định: 3.0 km)

    Returns
    -------
    pd.DataFrame :
        Index: segment_id (int)
        Columns: azimuth_deg, lat, lon, length_km
    """
    geom_m = line_metric.iloc[0]
    total_len_km = geom_m.length / 1000.0

    geom_wgs84 = (
        gpd.GeoSeries([geom_m], crs=METRIC_CRS)
        .to_crs(WGS84_CRS)
        .iloc[0]
    )

    # 1. Lấy mẫu phương vị dọc tuyến (~1km mỗi điểm)
    n_samples = max(int(total_len_km / 1.0) + 1, 100)
    sample_fractions = np.linspace(0, 1, n_samples)
    azimuths_sampled = []

    for frac in sample_fractions:
        pt_cur = geom_wgs84.interpolate(frac, normalized=True)
        next_frac = min(frac + 0.01, 1.0)
        pt_next = geom_wgs84.interpolate(next_frac, normalized=True)
        az = calculate_azimuth((pt_cur.x, pt_cur.y), (pt_next.x, pt_next.y))
        azimuths_sampled.append({"frac": frac, "azimuth_deg": az})

    df_azimuths = pd.DataFrame(azimuths_sampled)

    # 2. Nhóm theo dung sai góc phương vị
    azimuth_segments = []
    current_azimuth = df_azimuths.iloc[0]["azimuth_deg"]
    seg_start_frac = 0.0

    for _, row in df_azimuths.iterrows():
        az = row["azimuth_deg"]
        az_diff = abs(az - current_azimuth)
        az_diff = min(az_diff, 360 - az_diff)

        if az_diff > azimuth_tolerance_deg:
            azimuth_segments.append({
                "frac_start": seg_start_frac,
                "frac_end": row["frac"],
                "azimuth_deg": current_azimuth,
            })
            current_azimuth = az
            seg_start_frac = row["frac"]

    azimuth_segments.append({
        "frac_start": seg_start_frac,
        "frac_end": 1.0,
        "azimuth_deg": current_azimuth,
    })

    df_az_segs = pd.DataFrame(azimuth_segments)
    logger.info("Phát hiện %d nhóm phương vị chính", len(df_az_segs))

    # 3. Phân chia cự ly ~5km và gộp đoạn < 3km
    seg_len_m = segment_length_km * 1000.0
    min_seg_len_m = min_segment_length_km * 1000.0

    rows = []
    seg_id = 0

    for _, az_seg in df_az_segs.iterrows():
        frac_start = az_seg["frac_start"]
        frac_end = az_seg["frac_end"]

        pt_start_m = geom_m.interpolate(frac_start, normalized=True)
        pt_end_m = geom_m.interpolate(frac_end, normalized=True)
        az_seg_len_m = LineString([pt_start_m, pt_end_m]).length

        n_small_segs = max(1, int(np.ceil(az_seg_len_m / seg_len_m)))

        small_segs = []
        for i in range(n_small_segs):
            s_frac = frac_start + i * (frac_end - frac_start) / n_small_segs
            e_frac = frac_start + (i + 1) * (frac_end - frac_start) / n_small_segs
            p_s = geom_m.interpolate(s_frac, normalized=True)
            p_e = geom_m.interpolate(e_frac, normalized=True)
            small_seg_len_m = LineString([p_s, p_e]).length

            small_segs.append({
                "frac_start": s_frac,
                "frac_end": e_frac,
                "length_m": small_seg_len_m,
            })

        # Xử lý đoạn lẻ < 3km: gộp vào đoạn trước
        processed_segs = []
        for small_seg in small_segs:
            if small_seg["length_m"] < min_seg_len_m:
                if processed_segs:
                    last_seg = processed_segs.pop()
                    merged_seg = {
                        "frac_start": last_seg["frac_start"],
                        "frac_end": small_seg["frac_end"],
                        "length_m": last_seg["length_m"] + small_seg["length_m"],
                    }
                    processed_segs.append(merged_seg)
                else:
                    processed_segs.append(small_seg)
            else:
                processed_segs.append(small_seg)

        # 4. Trích xuất thông số từng đoạn hoàn chỉnh
        for small_seg in processed_segs:
            frac_s = small_seg["frac_start"]
            frac_e = small_seg["frac_end"]
            frac_m = (frac_s + frac_e) / 2.0

            pt_mid = geom_wgs84.interpolate(frac_m, normalized=True)
            pt_s = geom_wgs84.interpolate(frac_s, normalized=True)
            pt_e = geom_wgs84.interpolate(frac_e, normalized=True)
            azimuth_actual = calculate_azimuth((pt_s.x, pt_s.y), (pt_e.x, pt_e.y))

            rows.append({
                "segment_id": seg_id,
                "azimuth_deg": azimuth_actual,
                "lat": pt_mid.y,
                "lon": pt_mid.x,
                "length_km": small_seg["length_m"] / 1000.0,
            })
            seg_id += 1

    df_segments = pd.DataFrame(rows).set_index("segment_id")
    logger.info("Đường dây được phân chia thành %d phân đoạn tính toán", len(df_segments))
    return df_segments
