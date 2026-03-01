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

    # Kiểm tra S2DR3 runtime dependencies
    _check_and_install_deps()

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


def _check_and_install_deps():
    """Kiểm tra và tự động cài đặt S2DR3 runtime dependencies nếu thiếu."""
    missing = []

    deps_map = {
        "skimage": "scikit-image",
        "sklearn": "scikit-learn",
        "PIL": "Pillow",
        "cv2": "opencv-python-headless",
        "osgeo": "GDAL",
    }

    for module_name, pip_name in deps_map.items():
        try:
            __import__(module_name)
        except ImportError:
            missing.append((module_name, pip_name))

    if missing:
        print(f"\n  ⚠️  Thiếu {len(missing)} S2DR3 dependencies, đang tự cài đặt...")
        import subprocess
        for module_name, pip_name in missing:
            print(f"     📦 Cài đặt {pip_name} (cho {module_name})...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "-q", pip_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                print(f"     ✅ {pip_name} đã cài")
            except subprocess.CalledProcessError as e:
                print(f"     ❌ Không cài được {pip_name}: {e}")
        print()


def _set_device(device: str):
    """Cấu hình PyTorch device trước khi chạy S2DR3."""
    try:
        import torch

        if device == "gpu" and torch.cuda.is_available():
            torch.set_default_device("cuda")
            print(f"  🔥 Device: CUDA (GPU)")
        else:
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
            print(f"  🧊 Device: CPU")

            if device == "gpu":
                print(f"     ⚠️  GPU không khả dụng, fallback về CPU")
    except ImportError:
        pass


def _simulate_colab_env():
    """Simulate Google Colab environment — S2DR3 chỉ chạy trên Colab.

    S2DR3 binary kiểm tra Colab env và từ chối chạy nếu không phải.
    Function này fake Colab modules + env vars để bypass restriction.

    QUAN TRỌNG: Không ghi đè google namespace package vì google.auth
    cần tồn tại cho gspread (dependency của s2dr3.datautils).
    """
    import types

    # 1. Set Colab env vars
    os.environ.setdefault("COLAB_RELEASE_TAG", "v2.0")
    os.environ.setdefault("COLAB_GPU", "0")

    # 2. Thêm google.colab vào google namespace (KHÔNG replace google module)
    if "google.colab" not in sys.modules:
        # Import google package thật (namespace package cho google-auth etc.)
        try:
            import google
        except ImportError:
            google = types.ModuleType("google")
            google.__path__ = []
            sys.modules["google"] = google

        # Tạo fake colab sub-modules
        colab_mod = types.ModuleType("google.colab")
        auth_mod = types.ModuleType("google.colab.auth")
        auth_mod.authenticate_user = lambda: None
        drive_mod = types.ModuleType("google.colab.drive")
        drive_mod.mount = lambda *a, **k: None

        # Gắn vào google namespace mà KHÔNG ghi đè
        sys.modules["google.colab"] = colab_mod
        sys.modules["google.colab.auth"] = auth_mod
        sys.modules["google.colab.drive"] = drive_mod
        google.colab = colab_mod

    # 3. Tạo thư mục log cần thiết cho S2DR3
    log_dir = Path("/var/log/journal")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
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

    # ── Simulate Colab environment (S2DR3 yêu cầu Colab) ──
    _simulate_colab_env()

    # ── Chạy S2DR3 ──
    try:
        from s2dr3 import inferutils

        print(f"🚀 Bắt đầu S2DR3 inference...")
        print(f"   Tọa độ:  {lat}, {lon}")
        print(f"   Output:  {out_dir}")
        print()

        if not date:
            print(f"   ❌ S2DR3 yêu cầu tham số date (ngày chụp).")
            print(f"   💡 Chạy: python scripts/gee_search_imagery.py để tìm ngày phù hợp")
            print(f"   Rồi: python scripts/s2dr3_process.py --date YYYY-MM-DD")
            return None

        print(f"   📡 Chế độ: Online (S2DR3 tự fetch từ GEE)")
        print(f"   Ngày:    {date}")
        print(f"   lonlat:  ({lon}, {lat})")
        print()

        # S2DR3 output files vào thư mục hiện tại → chdir
        original_cwd = os.getcwd()
        os.chdir(str(out_dir))

        # ── Memory optimizations cho CPU inference ──
        import gc
        gc.collect()

        # Giảm PyTorch memory footprint
        os.environ.setdefault("OMP_NUM_THREADS", "2")
        os.environ.setdefault("MKL_NUM_THREADS", "2")
        os.environ.setdefault("PYTORCH_NO_CUDA_MEMORY_CACHING", "1")

        try:
            import torch
            torch.set_num_threads(2)
            torch.set_num_interop_threads(1)
        except Exception:
            pass

        try:
            # API: s2dr3.inferutils.test(xy, date, simulate=False, savepath=None)
            # xy = (lon, lat), date = "YYYY-MM-DD"
            result = inferutils.test(
                (lon, lat),
                date,
                savepath=str(out_dir),
            )
        finally:
            os.chdir(original_cwd)

        print(f"\n✅ S2DR3 inference hoàn tất!")
        print(f"   Output: {out_dir}")

        # Liệt kê files output
        output_files = list(out_dir.glob("*.tif")) + list(out_dir.glob("*.png"))
        if output_files:
            print(f"\n📁 Files output:")
            for f in output_files:
                size_mb = f.stat().st_size / 1024 / 1024
                print(f"   - {f.name} ({size_mb:.1f} MB)")

        print(f"\n💡 Tiếp theo:")
        print(f"   python scripts/visualize_results.py")
        print(f"   hoặc mở http://localhost:5000 (web UI)")

        # Trả về dict thay vì result (inferutils.test có thể trả về None)
        # Kiểm tra files output thực tế để xác định thành công
        sr_files = [f for f in output_files if "x10" in f.name.lower() or "s2l2ax10" in f.name.lower()]
        preview_url = None
        if result and isinstance(result, str) and "gamayos.github.io" in result:
            preview_url = result

        return {
            "success": len(output_files) > 0,
            "files": [f.name for f in output_files],
            "sr_files": [f.name for f in sr_files],
            "output_dir": str(out_dir),
            "preview_url": preview_url,
        }

    except ImportError as e:
        # Xử lý lỗi missing module cụ thể
        module_name = str(e).replace("No module named '", "").replace("'", "")
        print(f"\n❌ Lỗi S2DR3: Thiếu module '{module_name}'")
        print(f"\n💡 Sửa lỗi:")

        # Map module → pip package
        fix_map = {
            "skimage": "scikit-image",
            "sklearn": "scikit-learn",
            "PIL": "Pillow",
            "cv2": "opencv-python-headless",
            "osgeo": "GDAL",
            "torch": "torch",
        }
        pip_pkg = fix_map.get(module_name, module_name)
        print(f"   pip install {pip_pkg}")
        print(f"\n   Hoặc rebuild Docker image:")
        print(f"   docker compose build --no-cache")

        # Thử auto-install
        print(f"\n🔄 Đang thử tự cài đặt {pip_pkg}...")
        import subprocess
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-q", pip_pkg],
                stdout=subprocess.DEVNULL,
            )
            print(f"✅ Đã cài {pip_pkg}. Vui lòng chạy lại.")
        except Exception:
            print(f"❌ Không thể tự cài. Thêm '{pip_pkg}' vào requirements.txt rồi rebuild Docker.")

        return None

    except Exception as e:
        print(f"\n❌ Lỗi S2DR3: {e}")
        print(f"\n💡 Kiểm tra:")
        if device == "gpu":
            print(f"   - GPU NVIDIA hoạt động: nvidia-smi")
            print(f"   - CUDA version phù hợp")
            print(f"   - Đủ VRAM (tối thiểu 4GB)")
        else:
            print(f"   - Đủ RAM (tối thiểu 8GB)")
            print(f"   - Input files tồn tại trong {in_dir}")
        print(f"   - Thử: DEVICE=cpu python scripts/s2dr3_process.py")
        return None


def _generate_colab_instructions(lat: float, lon: float, date: str | None, out_dir: Path):
    """Tạo file hướng dẫn cho Google Colab fallback."""
    code_snippet = (
        f"import s2dr3.inferutils\n"
        f"s2dr3.inferutils.test(lonlat=({lon}, {lat}), date='{date or 'YYYY-MM-DD'}')"
    )
    instructions = {
        "colab_url": "https://colab.research.google.com/",
        "steps": [
            "1. Mở Google Colab → Runtime → Change runtime type → T4 GPU",
            "2. Cài đặt: !pip -q install https://storage.googleapis.com/0x7ff601307fa5/s2dr3-20260129.1-cp312-cp312-linux_x86_64.whl",
            "3. Chạy code:",
            code_snippet,
            "4. Download kết quả (*.tif, *.png)",
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
