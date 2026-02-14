# 🛰️ Sentinel-2 Super Resolution với S2DR3

Nâng cấp độ phân giải ảnh vệ tinh **Sentinel-2** từ 10m/20m/60m lên **1m/px** sử dụng mô hình deep learning **S2DR3** (Sentinel-2 Deep Resolution 3.0) của [Gamma Earth](https://gammaearth.com) / Yosef Akhtman.

## 📋 Tổng quan

| Thành phần | Mô tả |
|------------|--------|
| **Google Earth Engine** | Tìm kiếm & export ảnh Sentinel-2 không bị mây |
| **S2DR3** | Mô hình deep learning nâng cấp 10 bands (B2-B12) → 1m/px |
| **Docker** | Container hóa toàn bộ pipeline (cho PC Windows) |
| **Google Colab** | Chạy S2DR3 inference (cho Mac / không có GPU NVIDIA) |

## 🏗️ Kiến trúc

```
┌─────────────────────────────────────────────────┐
│                  run_pipeline.py                 │
├──────────┬──────────┬──────────┬─────────────────┤
│   GEE    │  Export  │  S2DR3   │  Visualization  │
│  Search  │  Bands   │  Infer   │   & Compare     │
│ (cloud-  │ (B2-B12) │ (10m→1m) │  (RGB, NDVI)    │
│  free)   │ GeoTIFF  │          │                 │
└──────────┴──────────┴──────────┴─────────────────┘
```

## ⚙️ Yêu cầu tiên quyết

### 1. Google Cloud Project + Earth Engine API

> **Bắt buộc** — Cần hoàn thành trước khi sử dụng.

#### Bước 1: Tạo Google Cloud Project

1. Truy cập [Google Cloud Console](https://console.cloud.google.com/)
2. Đăng nhập bằng tài khoản Google
3. Click **"Select a project"** → **"New Project"**
4. Nhập tên project (VD: `sentinel2-super-res`)
5. Click **"Create"**
6. **Ghi lại Project ID** (VD: `sentinel2-super-res-12345`) — sẽ cần cho bước sau

#### Bước 2: Enable Earth Engine API

1. Trong Google Cloud Console, vào [API Library](https://console.cloud.google.com/apis/library)
2. Tìm kiếm **"Earth Engine API"**
3. Click vào **"Google Earth Engine API"**
4. Click **"Enable"**
5. Đợi vài giây để API được kích hoạt

#### Bước 3: Đăng ký Earth Engine

1. Truy cập [Earth Engine Sign Up](https://code.earthengine.google.com/register)
2. Chọn loại account phù hợp:
   - **Noncommercial** (miễn phí, cho nghiên cứu/giáo dục)
   - **Commercial** (có phí)
3. Liên kết với Cloud Project vừa tạo
4. Chấp nhận Terms of Service
5. Đợi phê duyệt (thường tức thì cho Noncommercial)

#### Bước 4: Tạo Service Account (Tùy chọn - cho Docker)

1. Vào [IAM & Admin > Service Accounts](https://console.cloud.google.com/iam-admin/service-accounts)
2. Click **"Create Service Account"**
3. Tên: `sentinel2-worker`
4. Vai trò: **Earth Engine Resource Admin**
5. Click **"Done"**
6. Click vào service account vừa tạo → tab **"Keys"**
7. **"Add Key"** → **"Create new key"** → JSON
8. Lưu file JSON vào `credentials/service-account.json`

### 2. Môi trường chạy

#### Phương án A: MacBook Pro M4 (Demo / Phát triển)

```bash
# Cài Python 3.12+
brew install python@3.12

# Cài dependencies
pip install -r requirements.txt

# Xác thực Earth Engine
python scripts/gee_authenticate.py
```

> ⚠️ **S2DR3 không chạy trên Mac** (chỉ hỗ trợ linux_x86_64 + NVIDIA GPU).
> Dùng **Google Colab notebook** kèm theo để chạy S2DR3 inference.

#### Phương án B: PC Windows với Docker (Khuyến nghị)

**Yêu cầu:**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) + WSL2 backend
- GPU NVIDIA (tùy chọn — không bắt buộc, có thể chạy CPU)

**Cài đặt Docker Desktop:**
1. Tải [Docker Desktop](https://www.docker.com/products/docker-desktop/) → cài đặt
2. Bật WSL2 backend trong Settings
3. Nếu có GPU: cài [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

**Cấu hình CPU/GPU trong `.env`:**
```env
# Chạy bằng CPU (mặc định, chậm hơn, ~10-30 phút)
DEVICE=cpu

# Chạy bằng GPU NVIDIA (nhanh, ~1-2 phút)
DEVICE=gpu
```

**Chạy pipeline:**
```batch
REM Chạy CPU mode
docker-run.bat cpu

REM Chạy GPU mode
docker-run.bat gpu

REM Chỉ chạy 1 bước cụ thể
docker-run.bat cpu search
docker-run.bat gpu s2dr3

REM Mở shell vào container
docker-run.bat cpu shell
```

#### Phương án C: Google Colab (Miễn phí GPU)

Mở file `notebooks/S2DR3_SuperResolution.ipynb` trên Google Colab. Notebook đã bao gồm toàn bộ pipeline.

## 🚀 Cách sử dụng

### Bước 1: Cấu hình

```bash
# Copy file cấu hình mẫu
cp .env.example .env

# Chỉnh sửa .env với thông tin của bạn
```

Sửa file `.env`:
```env
# Google Cloud Project ID (bắt buộc)
GCP_PROJECT_ID=your-project-id

# Khu vực quan tâm — tọa độ trung tâm
LATITUDE=10.762622
LONGITUDE=106.660172

# Khoảng thời gian tìm ảnh
START_DATE=2024-01-01
END_DATE=2024-06-01

# Ngưỡng mây tối đa (%)
CLOUD_THRESHOLD=20

# Chế độ tính toán: cpu hoặc gpu
DEVICE=cpu
```

### Bước 2: Xác thực Google Earth Engine

```bash
python scripts/gee_authenticate.py
```

Lần đầu sẽ mở trình duyệt để đăng nhập Google.

### Bước 3: Tìm ảnh không bị mây

```bash
python scripts/gee_search_imagery.py
```

Kết quả hiển thị danh sách ảnh phù hợp với metadata.

### Bước 4: Export ảnh Sentinel-2

```bash
python scripts/gee_export_bands.py
```

Tải về các band B2-B12 dưới dạng GeoTIFF.

### Bước 5: Chạy S2DR3 Super Resolution

**Docker trên Windows (CPU hoặc GPU):**
```batch
REM CPU mode
docker-run.bat cpu s2dr3

REM GPU mode (cần NVIDIA)
docker-run.bat gpu s2dr3
```

**Trên Mac / không có Docker:**
Sử dụng Google Colab notebook `notebooks/S2DR3_SuperResolution.ipynb`

### Bước 6: Xem kết quả

```bash
python scripts/visualize_results.py
```

## 📁 Cấu trúc thư mục

```
Sentinel2GammaEarth/
├── scripts/
│   ├── gee_authenticate.py      # Xác thực Earth Engine
│   ├── gee_search_imagery.py    # Tìm ảnh cloud-free
│   ├── gee_export_bands.py      # Export bands GeoTIFF
│   ├── s2dr3_process.py         # S2DR3 super resolution
│   └── visualize_results.py     # So sánh kết quả
├── notebooks/
│   └── S2DR3_SuperResolution.ipynb  # Google Colab notebook
├── config/
│   └── settings.py              # Cấu hình chung
├── data/                        # Ảnh Sentinel-2 gốc (auto-created)
├── output/                      # Kết quả 1m/px (auto-created)
├── credentials/                 # GEE credentials (git-ignored)
├── Dockerfile                   # Docker image (CPU/GPU)
├── docker-compose.yml           # Docker compose (2 profiles)
├── docker-run.sh                # Script chạy Docker (Linux/Mac)
├── docker-run.bat               # Script chạy Docker (Windows)
├── requirements.txt             # Python dependencies
├── run_pipeline.py              # Pipeline orchestrator
├── .env.example                 # Template cấu hình
├── .gitignore
└── README.md
```

## 📊 Sentinel-2 Bands

| Band | Tên | Bước sóng (nm) | Độ phân giải gốc | S2DR3 Output |
|------|-----|-----------------|-------------------|--------------|
| B1 | Coastal Aerosol | 443 | 60m | ❌ Không xử lý |
| B2 | Blue | 490 | 10m | ✅ → 1m |
| B3 | Green | 560 | 10m | ✅ → 1m |
| B4 | Red | 665 | 10m | ✅ → 1m |
| B5 | Red Edge 1 | 705 | 20m | ✅ → 1m |
| B6 | Red Edge 2 | 740 | 20m | ✅ → 1m |
| B7 | Red Edge 3 | 783 | 20m | ✅ → 1m |
| B8 | NIR | 842 | 10m | ✅ → 1m |
| B8A | Red Edge 4 | 865 | 20m | ✅ → 1m |
| B9 | Water Vapour | 945 | 60m | ✅ → 1m |
| B11 | SWIR 1 | 1610 | 20m | ✅ → 1m |
| B12 | SWIR 2 | 2190 | 20m | ✅ → 1m |

## 📚 Tài liệu tham khảo

- [S2DR3 — Gamma Earth](https://medium.com/@yosef.akhtman)
- [Google Earth Engine Python API](https://developers.google.com/earth-engine/guides/python_install)
- [Sentinel-2 Bands — ESA](https://sentinels.copernicus.eu/web/sentinel/user-guides/sentinel-2-msi/resolutions/spatial)
- [Video hướng dẫn gốc](https://www.youtube.com/watch?v=X077bA4aqco)

## 📄 License

MIT License — Sử dụng S2DR3 tuân theo điều khoản của Gamma Earth.
