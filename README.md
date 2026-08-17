# Dynamic Line Rating (DLR) – Đường Dây 220kV Tháp Chàm - Vĩnh Tân 🇻🇳

> **Mô hình tính toán khả năng tải dòng điện động (Dynamic Line Rating) theo tiêu chuẩn IEEE Std 738-2023**  
> Dữ liệu khí tượng lịch sử: [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) (Độ phân giải 1 giờ)  
> Múi giờ hệ thống: **UTC+7 (Asia/Ho_Chi_Minh)**

---

## 1. Giới thiệu Dự án & Cơ sở Khoa học

Dự án nghiên cứu và triển khai giải pháp **Dynamic Line Rating (DLR)** ứng dụng thực tế cho tuyến đường dây truyền tải **220kV Tháp Chàm - Vĩnh Tân** (kết nối tỉnh Ninh Thuận và Bình Thuận – khu vực có mật độ nguồn điện gió và điện mặt trời tập trung cao).

Dự án được cấu trúc thành **2 phân hệ cốt lõi**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│               HỆ THỐNG DYNAMIC LINE RATING 220KV THÁP CHÀM - VĨNH TÂN        │
├──────────────────────────────────────┬──────────────────────────────────────┤
│ PHẦN 1: DLR TIÊU CHUẨN (IEEE 738)    │ PHẦN 2: DLR XÉT LÃO HÓA HỆ SỐ ĐỘNG   │
├──────────────────────────────────────┼──────────────────────────────────────┤
│ • Hệ số phát xạ ε & hấp thụ α cố định│ • Hệ số ε & α biến thiên theo giờ:   │
│   (mặc định ε = α = 0.8 hoặc Excel)  │   y(x) = 0.23 + 0.7·x / (1.22 + x)   │
│ • Phân đoạn tuyến theo góc phương vị │ • Mô phỏng 5 chu kỳ 2 năm (2014-2024)│
│   (≥ 5°) và cự ly ~5km (gộp < 3km)   │ • So sánh song song:                 │
│ • Tải dữ liệu Open-Meteo từng giờ    │   - Kịch bản A: Cố định đầu chu kỳ   │
│ • Tính Ampacity phân đoạn & DLR tuyến│   - Kịch bản B: Động theo thời gian  │
│ • So sánh định mức tĩnh SLR          │ • Tính Ampacity Gain (%), tìm điểm   │
│ • Phân tích tắc nghẽn & đoạn nút thắt│   max difference, vẽ đồ thị đa trục Y│
└──────────────────────────────────────┴──────────────────────────────────────┘
```

---

## 2. Chi tiết Phương pháp & Thuật toán

### 2.1. Nhiệt động học IEEE Std 738-2023
Phương trình cân bằng nhiệt trạng thái dừng trên một đơn vị chiều dài dây dẫn:
$$q_c + q_r = q_s + I^2 \cdot R(T_c)$$
$$\implies I = \sqrt{\frac{\max(q_c + q_r - q_s, 0)}{R(T_c)}}$$

Trong đó:
- **$q_c$ (Làm mát đối lưu - Convective Cooling)**: Tính toán qua số Reynolds $N_{Re}$, nhiệt độ màng khí $T_{film} = (T_c + T_a)/2$, hệ số góc gió $K_{angle}$, độ dẫn nhiệt $k_f$, độ nhớt động học $\mu_f$ và mật độ không khí ẩm $\rho_f$. Lấy giá trị lớn nhất giữa đối lưu tự nhiên ($q_{c0}$), đối lưu cưỡng bức gió thấp ($q_{c1}$) và gió cao ($q_{c2}$).
- **$q_r$ (Tản nhiệt bức xạ - Radiative Cooling)**: $q_r = \pi \cdot D \cdot \epsilon \cdot \sigma \cdot (T_c^4 - T_a^4)$.
- **$q_s$ (Hấp thụ bức xạ mặt trời - Solar Heating)**: $q_s = \alpha \cdot GHI \cdot D$.
- **$R(T_c)$**: Điện trở AC của dây dẫn tại nhiệt độ vận hành tối đa $T_c$ (thường là 75°C hoặc 90°C).

### 2.2. Thuật toán Phân đoạn Hình học Tuyến dây
1. **Chuyển đổi hệ tọa độ**: Chuyển đổi Shapefile từ WGS84 sang tọa độ phẳng **UTM Zone 48N (`EPSG:32648`)** để đo đạc khoảng cách chính xác theo mét.
2. **Nhóm phương vị (Azimuth Clustering)**: Lấy mẫu phương vị góc dọc tuyến (~1km/điểm). Gom các đoạn liên tục có độ lệch hướng $< 5^\circ$ thành một nhóm.
3. **Phân đoạn cự ly ~5km**: Chia mỗi nhóm phương vị thành các phân đoạn nhỏ có độ dài mục tiêu ~5km.
4. **Xử lý đoạn lẻ**: Nếu đoạn cuối $\ge 3$ km thì giữ nguyên; nếu $< 3$ km thì tự động gộp vào phân đoạn liền trước.
5. **Trích xuất tọa độ**: Xác định điểm giữa (Midpoint WGS84) của từng phân đoạn để truy vấn dữ liệu thời tiết riêng biệt.

### 2.3. Mô hình Lão hóa Hệ số Phát xạ & Hấp thụ (Phần 2)
Sau thời gian vận hành trong môi trường tự nhiên, bề mặt dây nhôm trần bị oxy hóa và bám bụi bẩn, dẫn đến sự tăng dần của hệ số phát xạ $\epsilon$ và hệ số hấp thụ $\alpha$. Mô hình thực nghiệm phi tuyến theo số năm vận hành $x$ (kể từ năm 2014):
$$y(x) = 0.23 + \frac{0.7 \cdot x}{1.22 + x}$$
- Tại $x = 0$ (năm 2014, dây mới): $y = 0.23$.
- Khi $x \to \infty$: $y \to 0.93$.
- Bước nhảy tính toán theo giờ: $\Delta x = \frac{1}{8760}$ năm.

**Mô phỏng 5 chu kỳ 2 năm:**
- **Chu kỳ 1 (2014–2016)**: $x \in [0, 2]$ | Kịch bản A cố định $\epsilon = \alpha = 0.2300$.
- **Chu kỳ 2 (2016–2018)**: $x \in [2, 4]$ | Kịch bản A cố định $\epsilon = \alpha = 0.6647$.
- **Chu kỳ 3 (2018–2020)**: $x \in [4, 6]$ | Kịch bản A cố định $\epsilon = \alpha = 0.7663$.
- **Chu kỳ 4 (2020–2022)**: $x \in [6, 8]$ | Kịch bản A cố định $\epsilon = \alpha = 0.8091$.
- **Chu kỳ 5 (2022–2024)**: $x \in [8, 10]$ | Kịch bản A cố định $\epsilon = \alpha = 0.8384$.

---

## 3. Cấu trúc Thư mục

```
dlr_vietnam/
├── data/                               # Dữ liệu đầu vào
│   ├── conductor_params.xlsx           # File Excel thông số kỹ thuật dây dẫn
│   └── shapefile/                      # Shapefile đường dây 220kV Tháp Chàm - Vĩnh Tân
│       ├── ThapCham_VinhTan_220kV.shp
│       ├── ThapCham_VinhTan_220kV.shx
│       ├── ThapCham_VinhTan_220kV.dbf
│       └── ThapCham_VinhTan_220kV.prj
│
├── outputs/                            # Kết quả tính toán & đồ thị
│   ├── ratings/                        # File CSV, TXT, JSON, PKL
│   └── figures/                        # File ảnh đồ thị PNG độ phân giải cao
│
├── core/                               # GÓI MODULE LÕI KHOA HỌC
│   ├── __init__.py                     # Package export
│   ├── config.py                       # Đường dẫn, hằng số vật lý, CRS
│   ├── conductor.py                    # Đọc thông số dây dẫn từ Excel
│   ├── geometry.py                     # Phân đoạn không gian & tính phương vị
│   ├── weather.py                      # Client API Open-Meteo (múi giờ UTC+7)
│   ├── physics.py                      # Mô hình nhiệt động học IEEE Std 738
│   ├── aging.py                        # Mô hình lão hóa hệ số phát xạ / hấp thụ
│   ├── statistics.py                   # Thống kê, phân vị, tắc nghẽn, Ampacity Gain
│   ├── visualization.py                # Vẽ đồ thị chuỗi thời gian & đồ thị zoom đa trục Y
│   ├── standard_dlr.py                 # Điều phối pipeline Phần 1 (DLR tiêu chuẩn)
│   └── dynamic_dlr.py                  # Điều phối pipeline Phần 2 (DLR lão hóa 5 chu kỳ)
│
├── main.py                             # Giao diện CLI trung tâm (Khuyến nghị sử dụng)
├── run_vn.py                           # Điểm chạy tương thích ngược cho Phần 1
├── run_dlr_upgrade.py                  # Điểm chạy tương thích ngược cho Phần 2
├── setup_template.py                   # Tiện ích tạo file Excel thông số mẫu
├── test_analysis.py                    # Suite kiểm thử tự động toàn bộ module
├── requirements.txt                    # Danh sách các thư viện Python
└── README.md                           # Tài liệu hướng dẫn sử dụng
```

---

## 4. Cài đặt Môi trường

```bash
# 1. Tạo môi trường ảo Python (khuyến nghị Python 3.10 - 3.12)
python -m venv venv

# 2. Kích hoạt môi trường ảo
# Trên Windows:
venv\Scripts\activate
# Trên Linux/macOS:
source venv/bin/activate

# 3. Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

---

## 5. Hướng dẫn Sử dụng Chi tiết

### 5.1. Chuẩn bị Dữ liệu Đầu vào
- **Thông số dây dẫn**: Chạy `python setup_template.py` để tạo file mẫu `data/conductor_params.xlsx`. Điền các thông số kỹ thuật thực tế (`diameter_mm`, `resistance_25C_ohm_per_km`, `resistance_75C_ohm_per_km`, `max_conductor_temp_C`, `nominal_rating_A`).
- **Shapefile đường dây**: Đặt các file shapefile (`.shp`, `.shx`, `.dbf`, `.prj`) vào thư mục `data/shapefile/`.

---

### 5.2. Chạy qua CLI Trung tâm (`main.py`)

#### Chạy Phần 1: DLR Tiêu chuẩn
```bash
# Chạy DLR năm 2023, tự động xuất biểu đồ và báo cáo nhận xét
python main.py standard --start_date 2023-01-01 --end_date 2023-12-31 --plot --save-analysis

# Chạy với biên an toàn khí tượng (bảo thủ hơn)
python main.py standard \
  --start_date 2023-01-01 \
  --end_date 2023-12-31 \
  --margin_wind -1.0 \
  --margin_temp 2.0 \
  --plot \
  --save-analysis
```

#### Chạy Phần 2: DLR Xét Biến thiên Hệ số (5 chu kỳ 2014-2024)
```bash
# Chạy toàn bộ 5 chu kỳ 2 năm, xuất báo cáo và 5 đồ thị zoom so sánh
python main.py dynamic --output outputs/ratings/ --figures outputs/figures/ --baseline 850 --zoom-window 7
```

#### Chạy Toàn bộ (Phần 1 + Phần 2)
```bash
python main.py all --start_date 2023-01-01 --end_date 2023-12-31
```

---

### 5.3. Sử dụng các Script Tương thích ngược

Các tập lệnh cũ vẫn hoạt động 100% không đổi cú pháp:
```bash
# Chạy Phần 1
python run_vn.py --start_date 2023-01-01 --end_date 2023-12-31 --plot --save-analysis

# Chạy Phần 2
python run_dlr_upgrade.py --output outputs/ --baseline 850 --zoom-window 7
```

---

### 5.4. Sử dụng qua Python API

```python
from core.standard_dlr import run_standard_dlr
from core.dynamic_dlr import run_dynamic_aging_dlr

# 1. Tính toán DLR Tiêu chuẩn (Phần 1)
df_dlr = run_standard_dlr(
    start_date="2023-01-01",
    end_date="2023-12-31",
    segment_km=5.0,
    plot=True,
    save_analysis=True,
)
print("DLR trung bình:", df_dlr["DLR"].mean(), "A")

# 2. Mô phỏng DLR Lão hóa (Phần 2)
results_5_cycles = run_dynamic_aging_dlr(
    baseline_A=850.0,
    zoom_window_days=7,
)
```

---

## 6. Định dạng và Ý nghĩa File Đầu ra (Outputs)

Tất cả các định dạng file đầu ra được bảo toàn nguyên vẹn:

| Thư mục | File | Định dạng | Nội dung |
|---------|------|-----------|----------|
| `outputs/ratings/` | `dlr_thap_cham_vinh_tan_*.csv` | CSV | Dữ liệu từng giờ: cột `DLR` (toàn tuyến), `seg_0`..`seg_n` (từng phân đoạn), `SLR`, `DLR_vs_SLR_pct`. |
| `outputs/ratings/` | `dlr_analysis_report_*.txt` | TXT | Báo cáo văn bản chi tiết: Thống kê DLR, tỷ lệ giờ DLR > SLR, phân tích giờ nghẽn mạch, phân đoạn hạn chế nhất, khuyến nghị vận hành. |
| `outputs/ratings/` | `dlr_analysis_*.json` | JSON | Dữ liệu số học phân tích thống kê theo định dạng JSON có cấu trúc. |
| `outputs/ratings/` | `comparison_report.txt` | TXT | Báo cáo so sánh Kịch bản A vs Kịch bản B cho từng chu kỳ 2 năm trong 5 chu kỳ. |
| `outputs/ratings/` | `detailed_statistics.txt` | TXT | Bảng tổng hợp Ampacity Gain (%), thống kê theo năm, xu hướng thay đổi hệ số và nhận xét khoa học. |
| `outputs/ratings/` | `detailed_results.pkl` | Pickle | Toàn bộ dữ liệu tính toán chi tiết của 5 chu kỳ phục vụ truy xuất lập trình. |
| `outputs/figures/` | `dlr_*.png` | PNG (150 DPI) | Biểu đồ chuỗi thời gian DLR vs SLR và tỷ lệ tăng/giảm tải theo tháng. |
| `outputs/figures/` | `cycle_1..5_comparison.png` | PNG (150 DPI) | Biểu đồ so sánh Kịch bản A vs B phóng to xung quanh điểm chênh lệch lớn nhất (±7 ngày) kèm tốc độ gió trên trục Y thứ hai. |

---

## 7. Kiểm thử Tự động (Automated Verification)

Chạy bộ kiểm thử để xác nhận toàn bộ hệ thống hoạt động chính xác:
```bash
python test_analysis.py
```
Bộ kiểm thử sẽ tự động kiểm tra:
1. Độ chính xác các công thức nhiệt động học IEEE Std 738-2023.
2. Tính toán phương vị góc (Azimuth) không gian địa lý.
3. Hàm lão hóa phi tuyến hệ số phát xạ & hấp thụ $y(x)$.
4. Phân tích thống kê & xuất báo cáo nhận xét cho Phần 1.
5. So sánh kịch bản & tính Ampacity Gains cho Phần 2.
