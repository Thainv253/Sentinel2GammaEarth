# =============================================
# Sentinel-2 Super Resolution — Docker Image
# =============================================
# Hỗ trợ cả GPU (NVIDIA CUDA) và CPU mode
# Chạy Web UI hoặc Pipeline CLI
#
# Build:
#   docker compose --profile cpu build
#
# Chạy Web UI:
#   docker compose --profile cpu up
#   → http://localhost:5050
# =============================================

# ── Build argument: chọn base image ──
ARG BASE_IMAGE=ubuntu:24.04
FROM --platform=linux/amd64 ${BASE_IMAGE}

# Tránh interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ── Cài đặt system dependencies ──
# python3-numpy + python3-gdal cùng apt → đảm bảo ABI tương thích
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-numpy \
    python3-gdal \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    wget \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# ── Tạo Python venv (dùng system-site-packages cho GDAL + NumPy) ──
# --system-site-packages: cho phép venv dùng python3-gdal, python3-numpy
# từ apt (compiled cùng nhau → tương thích ABI)
RUN python3 -m venv --system-site-packages /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# ── Upgrade pip trong venv ──
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# ── Cài đặt Python dependencies ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Cài S2DR3 hidden dependencies ──
RUN pip install --no-cache-dir opencv-python-headless \
    || echo "⚠️  opencv install failed"

# ── Cài đặt S2DR3 wheel (linux_x86_64 only) ──
ARG S2DR3_WHEEL_URL=https://storage.googleapis.com/0x7ff601307fa5/s2dr3-20260129.1-cp312-cp312-linux_x86_64.whl
RUN pip install --no-cache-dir ${S2DR3_WHEEL_URL} \
    || echo "⚠️  S2DR3 wheel install failed — URL may have changed."

# ── Tạo thư mục cần thiết ──
RUN mkdir -p /app/data /app/output /app/credentials /var/log/journal

# ── Force downgrade NumPy → 1.x (GDAL system compiled cho NumPy 1.x) ──
# S2DR3/torch wheel kéo numpy 2.x → crash GDAL gdal_array
# Phải chạy SAU tất cả pip install
RUN pip install --no-cache-dir "numpy>=1.26.0,<2.0" --force-reinstall

# ── Copy source code ──
COPY . .

# ── Port cho Web UI ──
EXPOSE 5050

# ── Healthcheck ──
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import flask; print('ok')" || exit 1

# ── Default: chạy Web UI ──
CMD ["python", "app.py"]
