#!/usr/bin/env python3
"""
S2DR3 Super Resolution Processing
====================================
Chạy mô hình S2DR3 để nâng cấp ảnh Sentinel-2 từ 10m/20m/60m → 1m/px.

Hỗ trợ 2 chế độ compute (cấu hình trong .env):
  - DEVICE=cpu  → chạy trên CPU (chậm hơn, ~10-30 phút)
  - DEVICE=gpu  → chạy trên GPU NVIDIA (nhanh, ~1-2 phút)

Sử dụng:
    python scripts/s2dr3_process.py
    python scripts/s2dr3_process.py --device cpu
    python scripts/s2dr3_process.py --input-dir ./data --output-dir ./output
"""

import sys
import os
import json
import platform
from pathlib import Path

import click

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def check_environment(device: str = "cpu"):
    """Kiểm tra môi trường chạy S2DR3."""
    issues = []
    warnings = []

    print(f"🔍 Kiểm tra môi trường (device={device})...")
    print()

    # Kiểm tra OS
    os_name = platform.system()
    arch = platform.machine()
    print(f"  OS:           {os_name} {arch}")

    if os_name != "Linux":
        issues.append(
            f"❌ OS: {os_name} — S2DR3 wheel chỉ hỗ trợ Linux x86_64.\n"
            f"   💡 Sử dụng Docker hoặc Google Colab."
        )

    if arch not in ("x86_64", "AMD64"):
        issues.append(
            f"❌ Architecture: {arch} — cần x86_64.\n"
            f"   💡 Trên Mac Apple Silicon, sử dụng Docker hoặc Google Colab."
        )

    # Kiểm tra GPU nếu device=gpu
    try:
        import torch
        print(f"  PyTorch:      {torch.__version__}")

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_mem / 1024**3
            print(f"  GPU:          ✅ {gpu_name} ({gpu_mem:.1f} GB)")

            if device == "cpu":
                warnings.append(
                    "💡 GPU phát hiện nhưng đang dùng DEVICE=cpu.\n"
                    "   Đổi DEVICE=gpu trong .env để tận dụng GPU."
                )
        else:
            print(f"  GPU:          ❌ Không có")
            if device == "gpu":
                warnings.append(
                    "⚠️  DEVICE=gpu nhưng không tìm thấy GPU NVIDIA.\n"
                    "   S2DR3 sẽ tự động fallback về CPU (chậm hơn).\n"
                    "   Kiểm tra: nvidia-smi"
                )
    except ImportError:
        print(f"  PyTorch:      ❌ Chưa cài")
        if device == "gpu":
            warnings.append(
                "⚠️  PyTorch chưa cài — không thể dùng GPU.\n"
                "   pip install torch"
            )

    # Kiểm tra s2dr3
    try:
        import s2dr3
        print(f"  S2DR3:        ✅ Đã cài đặt")
    except ImportError:
        issues.append(
            "❌ s2dr3 chưa cài đặt!\n"
            "   pip install https://storage.googleapis.com/0x7ff601307fa5/"
            "s2dr3-20260129.1-cp312-cp312-linux_x86_64.whl"
        )

    # In warnings
    if warnings:
        print()
        for w in warnings:
            print(f"  {w}")

    # In issues
    if issues:
        print()
        print("⚠️  Các vấn đề:")
        for issue in issues:
            print(f"  {issue}")

    print()
    return len(issues) == 0


def _set_device(device: str):
    """Cấu hình PyTorch device trước khi chạy S2DR3."""
    try:
        import torch

        if device == "gpu" and torch.cuda.is_available():
            torch.set_default_device("cuda")
            print(f"  🔥 Device: CUDA (GPU)")
        else:
            # Force CPU mode
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
            print(f"  🧊 Device: CPU")

            if device == "gpu":
                print(f"     ⚠️  GPU không khả dụng, fallback về CPU")
    except ImportError:
        pass


def process_with_s2dr3(
    lat: float | None = None,
    lon: float | None = None,
    date: str | None = None,
    input_dir: str | None = None,
    output_dir: str | None = None,
    device: str | None = None,
):
    """
    Chạy S2DR3 super resolution.

    S2DR3 có 2 chế độ:
    1. Online: Tự fetch dữ liệu từ GEE bằng tọa độ + ngày
    2. Offline: Xử lý file GeoTIFF đã tải về

    Args:
        lat: Vĩ độ (cho chế độ online)
        lon: Kinh độ (cho chế độ online)
        date: Ngày chụp YYYY-MM-DD (cho chế độ online)
        input_dir: Thư mục chứa GeoTIFF input
        output_dir: Thư mục output
        device: cpu hoặc gpu (ghi đè .env)
    """
    from config.settings import LATITUDE, LONGITUDE, DATA_DIR, OUTPUT_DIR, DEVICE

    lat = lat or LATITUDE
    lon = lon or LONGITUDE
    device = device or DEVICE
    in_dir = Path(input_dir) if input_dir else DATA_DIR
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("🛰️  S2DR3 Super Resolution Pipeline")
    print("=" * 60)
    print()

    # Kiểm tra môi trường
    env_ok = check_environment(device)

    if not env_ok:
        print("=" * 60)
        print("⚠️  Không thể chạy S2DR3 trực tiếp trên máy này.")
        print()
        print("📋 Phương án thay thế:")
        print()
        print("   1. 🐳 Docker (khuyến nghị):")
        print("      docker-run.bat cpu         # Chạy bằng CPU")
        print("      docker-run.bat gpu         # Chạy bằng GPU")
        print()
        print("   2. 🌐 Google Colab (miễn phí GPU T4):")
        print("      Mở notebooks/S2DR3_SuperResolution.ipynb")
        print()
        print("   3. 🖥️  WSL2 trên Windows:")
        print("      wsl --install")
        print("      # Trong WSL Ubuntu terminal:")
        print("      pip install s2dr3-*.whl && python scripts/s2dr3_process.py")
        print("=" * 60)

        _generate_colab_instructions(lat, lon, date, out_dir)
        return None

    # ── Cấu hình device ──
    _set_device(device)

    # ── Chạy S2DR3 ──
    try:
        import s2dr3

        print(f"🚀 Bắt đầu S2DR3 inference...")
        print(f"   Tọa độ:  {lat}, {lon}")
        print(f"   Output:  {out_dir}")
        print()

        if date:
            # Chế độ online: S2DR3 tự fetch dữ liệu
            print(f"   📡 Chế độ: Online (fetch từ GEE)")
            print(f"   Ngày:    {date}")
            print()

            result = s2dr3.process(
                lat=lat,
                lon=lon,
                date=date,
                output_dir=str(out_dir),
            )
        else:
            # Chế độ offline: xử lý file đã tải
            print(f"   📁 Chế độ: Offline (từ file local)")
            print(f"   Input:   {in_dir}")

            # Tìm file GeoTIFF trong input dir
            tif_files = list(in_dir.glob("sentinel2_*.tif"))
            if not tif_files:
                print(f"   ❌ Không tìm thấy file GeoTIFF trong {in_dir}")
                print(f"   💡 Chạy: python scripts/gee_export_bands.py trước")
                return None

            print(f"   Files:   {len(tif_files)}")
            for f in tif_files:
                print(f"            - {f.name}")
            print()

            result = s2dr3.process(
                input_dir=str(in_dir),
                output_dir=str(out_dir),
            )

        print(f"\n✅ S2DR3 inference hoàn tất!")
        print(f"   Output: {out_dir}")

        # Liệt kê files output
        output_files = list(out_dir.glob("*.tif"))
        if output_files:
            print(f"\n📁 Files output:")
            for f in output_files:
                size_mb = f.stat().st_size / 1024 / 1024
                print(f"   - {f.name} ({size_mb:.1f} MB)")

        print(f"\n💡 Tiếp theo:")
        print(f"   python scripts/visualize_results.py")

        return result

    except Exception as e:
        print(f"\n❌ Lỗi S2DR3: {e}")
        print(f"\n💡 Kiểm tra:")
        if device == "gpu":
            print(f"   1. GPU NVIDIA hoạt động: nvidia-smi")
            print(f"   2. CUDA version phù hợp")
            print(f"   3. Đủ VRAM (tối thiểu 4GB)")
        else:
            print(f"   1. Đủ RAM (tối thiểu 8GB)")
            print(f"   2. Input files tồn tại trong {in_dir}")
        print(f"   3. Thử: DEVICE=cpu python scripts/s2dr3_process.py")
        return None


def _generate_colab_instructions(lat: float, lon: float, date: str | None, out_dir: Path):
    """Tạo file hướng dẫn cho Google Colab fallback."""
    instructions = {
        "colab_url": "https://colab.research.google.com/",
        "steps": [
            "1. Mở Google Colab → Runtime → Change runtime type → T4 GPU",
            f"2. Cài đặt: !pip install s2dr3",
            f"3. Import: import s2dr3",
            f"4. Chạy: s2dr3.process(lat={lat}, lon={lon}" +
            (f", date='{date}'" if date else "") + ")",
            "5. Download kết quả về thư mục output/",
        ],
        "lat": lat,
        "lon": lon,
        "date": date,
    }

    instructions_file = out_dir / "colab_instructions.json"
    instructions_file.parent.mkdir(parents=True, exist_ok=True)
    with open(instructions_file, "w", encoding="utf-8") as f:
        json.dump(instructions, f, indent=2, ensure_ascii=False)

    print(f"\n📝 Hướng dẫn Colab đã lưu: {instructions_file}")


@click.command()
@click.option("--lat", type=float, help="Vĩ độ")
@click.option("--lon", type=float, help="Kinh độ")
@click.option("--date", type=str, help="Ngày chụp (YYYY-MM-DD) — chế độ online")
@click.option("--input-dir", type=str, help="Thư mục GeoTIFF input — chế độ offline")
@click.option("--output-dir", type=str, help="Thư mục output")
@click.option(
    "--device",
    type=click.Choice(["cpu", "gpu"]),
    help="Chế độ tính toán (ghi đè .env)",
)
def main(lat, lon, date, input_dir, output_dir, device):
    """Chạy S2DR3 super resolution (10m/20m → 1m/px)."""
    process_with_s2dr3(lat, lon, date, input_dir, output_dir, device)


if __name__ == "__main__":
    main()
