# =============================================
# Sentinel-2 Super Resolution — Docker Image
# =============================================
# Hỗ trợ cả GPU (NVIDIA CUDA) và CPU mode
# Cấu hình qua biến DEVICE trong .env
# =============================================

# ── Build argument: chọn base image ──
ARG BASE_IMAGE=nvidia/cuda:12.4.1-runtime-ubuntu22.04
FROM ${BASE_IMAGE}

# Tránh interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Cài đặt system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3.12-distutils \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Đặt Python 3.12 làm mặc định + cài pip
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12

# Working directory
WORKDIR /app

# Cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt S2DR3 wheel (linux_x86_64)
# Lưu ý: URL có thể thay đổi khi có phiên bản mới
RUN pip install --no-cache-dir \
    https://storage.googleapis.com/0x7ff601307fa5/s2dr3-20260129.1-cp312-cp312-linux_x86_64.whl \
    || echo "⚠️  S2DR3 wheel install failed — URL may have changed."

# Copy source code
COPY . .

# Tạo thư mục data & output
RUN mkdir -p /app/data /app/output /app/credentials

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s \
    CMD python -c "import s2dr3; print('ok')" || exit 1

# Default command
CMD ["python", "run_pipeline.py"]
