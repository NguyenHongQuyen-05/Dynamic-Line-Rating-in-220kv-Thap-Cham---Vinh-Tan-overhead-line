"""
core – Package xử lý Dynamic Line Rating (DLR) cho đường dây 220kV Tháp Chàm - Vĩnh Tân.
"""

from core.config import (
    C2K,
    STEFAN_BOLTZMANN,
    METRIC_CRS,
    WGS84_CRS,
    TIMEZONE_VN,
    OPERATIONAL_START_YEAR,
    BASELINE_AMPACITY_A,
    DATA_DIR,
    SHAPEFILE_DIR,
    OUTPUTS_DIR,
    RATINGS_DIR,
    FIGURES_DIR,
    CONDUCTOR_PARAMS_XLSX,
    DEFAULT_LINE_SHAPEFILE,
)

from core.conductor import read_conductor_params
from core.geometry import load_line_shapefile, calculate_azimuth, divide_line_into_segments
from core.weather import fetch_weather_single_point, fetch_weather_for_segments
from core.physics import (
    wind_direction_factor,
    film_temperature,
    dynamic_viscosity,
    thermal_conductivity,
    air_density,
    convective_cooling,
    radiative_cooling,
    solar_heating,
    ampacity_ieee738,
    calc_dlr_for_line,
)
from core.aging import (
    datetime_to_operational_years,
    calculate_coefficient,
    get_coefficient_series,
    get_cycle_range,
    get_cycle_dates,
    get_coefficient_at_year_end,
)
from core.statistics import (
    analyze_dlr_detailed,
    generate_comments,
    save_analysis_report,
    save_analysis_json,
    calculate_ampacity_gains,
    calculate_hourly_statistics,
    generate_yearly_report,
    generate_cycle_summary,
    generate_comparison_report,
    generate_full_report,
)
from core.visualization import (
    plot_standard_dlr,
    find_max_difference_point,
    get_zoom_window,
    plot_cycle_comparison,
    plot_all_cycles,
)
from core.standard_dlr import run_standard_dlr
from core.dynamic_dlr import run_dynamic_aging_dlr, run_cycle_comparison

__all__ = [
    # Config
    "C2K",
    "STEFAN_BOLTZMANN",
    "METRIC_CRS",
    "WGS84_CRS",
    "TIMEZONE_VN",
    "OPERATIONAL_START_YEAR",
    "BASELINE_AMPACITY_A",
    "DATA_DIR",
    "SHAPEFILE_DIR",
    "OUTPUTS_DIR",
    "RATINGS_DIR",
    "FIGURES_DIR",
    "CONDUCTOR_PARAMS_XLSX",
    "DEFAULT_LINE_SHAPEFILE",
    # Conductor
    "read_conductor_params",
    # Geometry
    "load_line_shapefile",
    "calculate_azimuth",
    "divide_line_into_segments",
    # Weather
    "fetch_weather_single_point",
    "fetch_weather_for_segments",
    # Physics
    "wind_direction_factor",
    "film_temperature",
    "dynamic_viscosity",
    "thermal_conductivity",
    "air_density",
    "convective_cooling",
    "radiative_cooling",
    "solar_heating",
    "ampacity_ieee738",
    "calc_dlr_for_line",
    # Aging
    "datetime_to_operational_years",
    "calculate_coefficient",
    "get_coefficient_series",
    "get_cycle_range",
    "get_cycle_dates",
    "get_coefficient_at_year_end",
    # Statistics
    "analyze_dlr_detailed",
    "generate_comments",
    "save_analysis_report",
    "save_analysis_json",
    "calculate_ampacity_gains",
    "calculate_hourly_statistics",
    "generate_yearly_report",
    "generate_cycle_summary",
    "generate_comparison_report",
    "generate_full_report",
    # Visualization
    "plot_standard_dlr",
    "find_max_difference_point",
    "get_zoom_window",
    "plot_cycle_comparison",
    "plot_all_cycles",
    # Pipelines
    "run_standard_dlr",
    "run_dynamic_aging_dlr",
    "run_cycle_comparison",
]
