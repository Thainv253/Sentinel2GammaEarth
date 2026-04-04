#!/usr/bin/env python3
"""
Generate Google Colab notebook (.ipynb) cho SuperResolutionV1 inference.

Tạo notebook pre-filled với tọa độ, ngày, tự động:
1. Cài SuperResolutionV1 wheel
2. Fetch ảnh từ GEE
3. Chạy inference
4. Download kết quả
"""

import json


def generate_colab_notebook(
    lat: float = 10.762622,
    lon: float = 106.660172,
    date: str = "2024-03-20",
    buffer_meters: int = 5000,
) -> dict:
    """Tạo Colab notebook JSON (.ipynb) với parameters pre-filled."""

    cells = [
        # ── Title cell ──
        _markdown_cell(
            "# 🛰️ Sentinel-2 Super Resolution — SuperResolutionV1\n"
            "**Nâng cấp ảnh vệ tinh 10m → 1m/pixel bằng Deep Learning**\n\n"
            f"- 📍 Tọa độ: `{lat}, {lon}`\n"
            f"- 📅 Ngày: `{date}`\n"
            f"- 📐 Buffer: `{buffer_meters}m`\n\n"
            "> ⚡ Notebook này tự động chạy tất cả. Bấm **Runtime → Run all** (Ctrl+F9)"
        ),

        # ── Step 1: Install SuperResolutionV1 ──
        _markdown_cell("## 1️⃣ Cài đặt SuperResolutionV1"),
        _code_cell(
            "%%capture\n"
            "# Cài SuperResolutionV1 wheel (Gamma Earth)\n"
            "!pip install https://storage.googleapis.com/0x7ff601307fa5/"
            "superresolutionv1-20260129.1-cp312-cp312-linux_x86_64.whl\n"
            "!pip install gspread oauth2client tifffile scikit-image\n"
            "print('✅ SuperResolutionV1 đã cài xong!')"
        ),

        # ── Step 2: Configure ──
        _markdown_cell("## 2️⃣ Cấu hình"),
        _code_cell(
            f'# === CẤU HÌNH — Sửa ở đây nếu cần ===\n'
            f'LATITUDE = {lat}\n'
            f'LONGITUDE = {lon}\n'
            f'DATE = "{date}"\n'
            f'BUFFER_METERS = {buffer_meters}\n'
            f'\n'
            f'print(f"📍 Tọa độ: {{LATITUDE}}, {{LONGITUDE}}")\n'
            f'print(f"📅 Ngày: {{DATE}}")\n'
            f'print(f"📐 Buffer: {{BUFFER_METERS}}m")'
        ),

        # ── Step 3: Run SuperResolutionV1 ──
        _markdown_cell("## 3️⃣ Chạy SuperResolutionV1 Super Resolution"),
        _code_cell(
            "import os\n"
            "os.makedirs('/content/output', exist_ok=True)\n"
            "os.makedirs('/var/log/journal', exist_ok=True)\n\n"
            "from superresolutionv1 import inferutils\n\n"
            "print('🚀 Bắt đầu SuperResolutionV1 inference...')\n"
            "print(f'   Tọa độ: ({LONGITUDE}, {LATITUDE})')\n"
            "print(f'   Ngày: {DATE}')\n"
            "print()\n\n"
            "result = inferutils.test(\n"
            "    (LONGITUDE, LATITUDE),\n"
            "    DATE,\n"
            "    savepath='/content/output'\n"
            ")\n\n"
            "print('\\n✅ SuperResolutionV1 inference hoàn tất!')"
        ),

        # ── Step 4: Show results ──
        _markdown_cell("## 4️⃣ Xem kết quả"),
        _code_cell(
            "import glob\n"
            "from IPython.display import display, Image\n\n"
            "# Liệt kê files output\n"
            "files = glob.glob('/content/output/*.*') + glob.glob('/content/*.tif')\n"
            "print(f'📁 {len(files)} files output:')\n"
            "for f in sorted(files):\n"
            "    size = os.path.getsize(f) / 1024 / 1024\n"
            "    print(f'   - {os.path.basename(f)} ({size:.1f} MB)')\n\n"
            "# Hiển thị ảnh PNG\n"
            "pngs = glob.glob('/content/output/*.png') + glob.glob('/content/*.png')\n"
            "for p in pngs[:4]:\n"
            "    print(f'\\n🖼️ {os.path.basename(p)}')\n"
            "    display(Image(filename=p, width=600))"
        ),

        # ── Step 5: Download ──
        _markdown_cell("## 5️⃣ Tải kết quả về máy"),
        _code_cell(
            "import shutil\n\n"
            "# Nén tất cả output\n"
            "output_zip = '/content/superresolutionv1_output'\n"
            "shutil.make_archive(output_zip, 'zip', '/content/output')\n\n"
            "# Download\n"
            "from google.colab import files\n"
            "files.download(f'{output_zip}.zip')\n"
            "print('📥 Đang tải xuống...')"
        ),
    ]

    notebook = {
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
            "colab": {
                "provenance": [],
                "gpuType": "T4",
                "name": f"SuperResolutionV1_SuperResolution_{date}",
            },
            "kernelspec": {
                "name": "python3",
                "display_name": "Python 3",
            },
            "accelerator": "GPU",
        },
        "cells": cells,
    }

    return notebook


def _markdown_cell(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source.split("\n"),
    }


def _code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "source": source.split("\n"),
        "execution_count": None,
        "outputs": [],
    }


if __name__ == "__main__":
    nb = generate_colab_notebook()
    with open("SuperResolutionV1_SuperResolution.ipynb", "w") as f:
        json.dump(nb, f, indent=2, ensure_ascii=False)
    print("✅ Notebook saved: SuperResolutionV1_SuperResolution.ipynb")
