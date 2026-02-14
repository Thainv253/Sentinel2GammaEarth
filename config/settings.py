"""
Cấu hình chung cho Sentinel-2 Super Resolution Pipeline.
Load biến môi trường từ .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ── Paths ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", PROJECT_ROOT / "output"))
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"

# Tạo thư mục nếu chưa tồn tại
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

# ── Google Cloud ────────────────────────────────────────
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GEE_SERVICE_ACCOUNT_KEY = os.getenv("GEE_SERVICE_ACCOUNT_KEY", "")

# ── Khu vực quan tâm (AOI) ──────────────────────────────
LATITUDE = float(os.getenv("LATITUDE", "10.762622"))   # Mặc định: TP.HCM
LONGITUDE = float(os.getenv("LONGITUDE", "106.660172"))
BUFFER_METERS = int(os.getenv("BUFFER_METERS", "5000"))

# ── Thời gian ───────────────────────────────────────────
START_DATE = os.getenv("START_DATE", "2024-01-01")
END_DATE = os.getenv("END_DATE", "2024-06-01")

# ── Lọc mây ─────────────────────────────────────────────
CLOUD_THRESHOLD = int(os.getenv("CLOUD_THRESHOLD", "20"))

# ── Sentinel-2 Bands ────────────────────────────────────
# B1 (Coastal Aerosol, 60m) — không xử lý bởi S2DR3
# B10 (Cirrus) — không có trong SR dataset
BANDS_10M = ["B2", "B3", "B4", "B8"]           # Blue, Green, Red, NIR
BANDS_20M = ["B5", "B6", "B7", "B8A", "B11", "B12"]  # Red Edge, SWIR
BANDS_60M = ["B9"]                               # Water Vapour
ALL_BANDS = BANDS_10M + BANDS_20M + BANDS_60M   # 11 bands total cho S2DR3

# S2DR3 xử lý 10 bands: B2-B8, B8A, B11, B12 (loại B1, B9, B10)
S2DR3_BANDS = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]

# Band resolution mapping (meters)
BAND_RESOLUTION = {
    "B1": 60, "B2": 10, "B3": 10, "B4": 10,
    "B5": 20, "B6": 20, "B7": 20, "B8": 10,
    "B8A": 20, "B9": 60, "B10": 60,
    "B11": 20, "B12": 20,
}

# ── Google Earth Engine ──────────────────────────────────
GEE_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
GEE_CLOUD_COLLECTION = "COPERNICUS/S2_CLOUD_PROBABILITY"
GEE_SCALE = 10  # Export scale mặc định (meters)

# ── Compute / Docker ─────────────────────────────────────
# cpu = chạy trên CPU (chậm hơn nhưng không cần GPU)
# gpu = chạy trên GPU NVIDIA (nhanh, cần driver)
DEVICE = os.getenv("DEVICE", "cpu").lower().strip()
MEMORY_LIMIT = os.getenv("MEMORY_LIMIT", "8g")

# ── S2DR3 ────────────────────────────────────────────────
S2DR3_TARGET_RESOLUTION = 1  # meters per pixel
S2DR3_WHEEL_URL = (
    "https://storage.googleapis.com/0x7ff601307fa5/"
    "s2dr3-20260129.1-cp312-cp312-linux_x86_64.whl"
)


def print_config():
    """In cấu hình hiện tại."""
    print("=" * 50)
    print("🛰️  Sentinel-2 Super Resolution — Cấu hình")
    print("=" * 50)
    print(f"  GCP Project:     {GCP_PROJECT_ID or '⚠️  CHƯA CẤU HÌNH'}")
    print(f"  Tọa độ:          {LATITUDE}, {LONGITUDE}")
    print(f"  Buffer:          {BUFFER_METERS}m")
    print(f"  Thời gian:       {START_DATE} → {END_DATE}")
    print(f"  Cloud threshold: {CLOUD_THRESHOLD}%")
    print(f"  Data dir:        {DATA_DIR}")
    print(f"  Output dir:      {OUTPUT_DIR}")
    print(f"  Device:          {'🔥 GPU (NVIDIA CUDA)' if DEVICE == 'gpu' else '🧊 CPU'}")
    print(f"  Memory limit:    {MEMORY_LIMIT}")
    print(f"  Bands (S2DR3):   {', '.join(S2DR3_BANDS)}")
    print("=" * 50)


if __name__ == "__main__":
    print_config()
