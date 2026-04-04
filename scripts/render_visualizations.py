#!/usr/bin/env python3
"""
Render Visualizations — Tạo ảnh RGB, NDVI, Infrared từ GeoTIFF
================================================================
Đọc các band Sentinel-2 đã export (GeoTIFF) và render thành ảnh PNG
để hiển thị trên web UI.

Các loại visualization:
  - RGB (True Color):   B4 (Red), B3 (Green), B2 (Blue)
  - NDVI:               (B8 - B4) / (B8 + B4) → colormap RdYlGn
  - Infrared (IRP):     B11 (SWIR), B8 (NIR), B5 (Red Edge)
  - False Color:        B8 (NIR), B4 (Red), B3 (Green)

Tham khảo:
  - Gamma Earth SuperResolutionV1 demo: TCI (RGB), NDVI, IRP layers
  - Sentinel-2 band reference: https://sentinels.copernicus.eu/

Sử dụng:
    python scripts/render_visualizations.py
    python scripts/render_visualizations.py --input-dir data --output-dir output
"""

import sys
import warnings
from pathlib import Path

import numpy as np

# Tắt cảnh báo matplotlib backend
warnings.filterwarnings("ignore", category=UserWarning)

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Hằng số ──────────────────────────────────────────────

# Mapping band name → index trong file GeoTIFF
# File 10m: B2(0), B3(1), B4(2), B8(3)
BANDS_10M_INDEX = {"B2": 0, "B3": 1, "B4": 2, "B8": 3}

# File 20m: B5(0), B6(1), B7(2), B8A(3), B11(4), B12(5)
BANDS_20M_INDEX = {"B5": 0, "B6": 1, "B7": 2, "B8A": 3, "B11": 4, "B12": 5}


def _read_band(tif_path: Path, band_index: int) -> np.ndarray:
    """
    Đọc một band từ file GeoTIFF multi-band.

    Args:
        tif_path: Đường dẫn tới file .tif
        band_index: Index của band (0-based trong array, 1-based trong rasterio)

    Returns:
        numpy array 2D chứa giá trị pixel (float32)
    """
    import rasterio

    with rasterio.open(tif_path) as src:
        # rasterio dùng 1-based index
        band = src.read(band_index + 1).astype(np.float32)
    return band


def _get_geotransform(tif_path: Path):
    """
    Lấy thông tin geotransform và CRS từ file GeoTIFF.

    Returns:
        tuple: (transform, crs, width, height)
    """
    import rasterio

    with rasterio.open(tif_path) as src:
        return src.transform, src.crs, src.width, src.height


def _resample_20m_to_10m(band_20m: np.ndarray, target_shape: tuple) -> np.ndarray:
    """
    Resample band 20m lên kích thước 10m grid bằng bilinear interpolation.

    Các band 20m (B5, B6, B7, B8A, B11, B12) có kích thước bằng 1/2 band 10m.
    Cần upscale để overlay lên cùng grid.

    Args:
        band_20m: Array 2D từ band 20m
        target_shape: (height, width) của grid 10m

    Returns:
        Array 2D đã resample lên kích thước target
    """
    from scipy.ndimage import zoom

    # Tính tỷ lệ zoom
    zoom_h = target_shape[0] / band_20m.shape[0]
    zoom_w = target_shape[1] / band_20m.shape[1]

    # Bilinear interpolation (order=1)
    resampled = zoom(band_20m, (zoom_h, zoom_w), order=1)
    return resampled


def _normalize_band(band: np.ndarray, percentile_low=2, percentile_high=98) -> np.ndarray:
    """
    Normalize band values to 0-1 range using percentile stretch.

    Percentile stretch giúp tăng contrast, loại bỏ outliers
    (ví dụ: pixel mây quá sáng, shadow quá tối).

    Args:
        band: Array 2D raw values
        percentile_low: Percentile dưới (cắt bớt giá trị tối)
        percentile_high: Percentile trên (cắt bớt giá trị sáng)

    Returns:
        Array 2D normalized [0, 1]
    """
    # Lọc bỏ no-data (0 hoặc NaN)
    valid = band[band > 0]
    if len(valid) == 0:
        return np.zeros_like(band)

    low = np.percentile(valid, percentile_low)
    high = np.percentile(valid, percentile_high)

    if high == low:
        return np.zeros_like(band)

    # Clip và normalize
    normalized = (band - low) / (high - low)
    return np.clip(normalized, 0, 1)


def _save_png(rgb_array: np.ndarray, output_path: Path, dpi=150):
    """
    Lưu array RGB (H, W, 3) thành file PNG.

    Args:
        rgb_array: Array 3D (height, width, 3) giá trị [0, 1]
        output_path: Đường dẫn output .png
        dpi: Độ phân giải hình ảnh
    """
    import matplotlib
    matplotlib.use("Agg")  # Backend không cần display
    import matplotlib.pyplot as plt

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(1, 1, figsize=(12, 12))
    ax.imshow(rgb_array)
    ax.axis("off")
    plt.tight_layout(pad=0)
    plt.savefig(str(output_path), dpi=dpi, bbox_inches="tight", pad_inches=0,
                facecolor="black", transparent=False)
    plt.close(fig)

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"     ✅ Đã lưu: {output_path.name} ({size_mb:.1f} MB)")


# ── Các hàm render visualization ──────────────────────────

def render_rgb(file_10m: Path, output_dir: Path) -> str | None:
    """
    Render ảnh RGB True Color (TCI) từ Sentinel-2.

    RGB True Color sử dụng 3 band quang học:
      - B4 (Red, 665nm)   → kênh đỏ
      - B3 (Green, 560nm) → kênh xanh lá
      - B2 (Blue, 490nm)  → kênh xanh dương

    Đây là dạng ảnh giống mắt thường nhìn thấy,
    giúp nhận dạng đất đai, công trình, sông ngòi.

    Args:
        file_10m: Path tới sentinel2_10m_bands.tif
        output_dir: Thư mục output

    Returns:
        Path tới file PNG đã render, hoặc None nếu lỗi
    """
    print("\n  🌈 Render RGB True Color (B4, B3, B2)...")

    try:
        red = _read_band(file_10m, BANDS_10M_INDEX["B4"])    # Band 4 = Red
        green = _read_band(file_10m, BANDS_10M_INDEX["B3"])  # Band 3 = Green
        blue = _read_band(file_10m, BANDS_10M_INDEX["B2"])   # Band 2 = Blue

        # Normalize từng kênh bằng percentile stretch
        red_n = _normalize_band(red)
        green_n = _normalize_band(green)
        blue_n = _normalize_band(blue)

        # Stack thành ảnh RGB (H, W, 3)
        rgb = np.dstack([red_n, green_n, blue_n])

        output_path = output_dir / "rgb_tci.png"
        _save_png(rgb, output_path)
        return str(output_path)

    except Exception as e:
        print(f"     ❌ Lỗi render RGB: {e}")
        return None


def render_ndvi(file_10m: Path, output_dir: Path) -> str | None:
    """
    Render ảnh NDVI (Normalized Difference Vegetation Index).

    Công thức NDVI:
      NDVI = (NIR - Red) / (NIR + Red) = (B8 - B4) / (B8 + B4)

    Ý nghĩa giá trị NDVI:
      - [-1, 0]:   Nước, đất trống, mây
      - [0, 0.2]:  Đất khô, đá, khu đô thị
      - [0.2, 0.4]: Cây bụi, cỏ thưa
      - [0.4, 0.6]: Thảm thực vật trung bình
      - [0.6, 1.0]: Rừng rậm, cây xanh tốt

    Colormap: RdYlGn (Đỏ → Vàng → Xanh lá)
      - Đỏ = giá trị thấp (không có cây)
      - Xanh = giá trị cao (nhiều cây xanh)

    Args:
        file_10m: Path tới sentinel2_10m_bands.tif
        output_dir: Thư mục output

    Returns:
        Path tới file PNG, hoặc None nếu lỗi
    """
    print("\n  🌿 Render NDVI (B8 - B4) / (B8 + B4)...")

    try:
        nir = _read_band(file_10m, BANDS_10M_INDEX["B8"])  # Band 8 = NIR (842nm)
        red = _read_band(file_10m, BANDS_10M_INDEX["B4"])  # Band 4 = Red (665nm)

        # Tính NDVI, xử lý division by zero
        denominator = nir + red
        ndvi = np.where(denominator > 0, (nir - red) / denominator, 0)

        # Clip về [-1, 1]
        ndvi = np.clip(ndvi, -1, 1)

        # Áp dụng colormap RdYlGn
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm

        # Normalize NDVI [-1, 1] → [0, 1] cho colormap
        ndvi_norm = (ndvi + 1) / 2
        colored = cm.RdYlGn(ndvi_norm)[:, :, :3]  # Bỏ alpha channel

        output_path = output_dir / "ndvi.png"
        _save_png(colored, output_path)
        return str(output_path)

    except Exception as e:
        print(f"     ❌ Lỗi render NDVI: {e}")
        return None


def render_infrared(file_10m: Path, file_20m: Path, output_dir: Path) -> str | None:
    """
    Render ảnh Infrared Composite (IRP) — B11, B8, B5.

    False-color infrared composite sử dụng:
      - B11 (SWIR, 1610nm) → kênh đỏ  (phát hiện độ ẩm đất, cháy rừng)
      - B8  (NIR, 842nm)   → kênh xanh lá (phản xạ thực vật)
      - B5  (Red Edge, 705nm) → kênh xanh dương (ranh giới thực vật)

    Ứng dụng:
      - Phân biệt đất khô/ướt (B11 nhạy với nước)
      - Phát hiện cháy rừng, khu vực bị phá
      - Phân loại sử dụng đất

    Lưu ý: B11 và B5 là band 20m, cần resample lên 10m grid.

    Args:
        file_10m: Path tới sentinel2_10m_bands.tif (chứa B8)
        file_20m: Path tới sentinel2_20m_bands.tif (chứa B11, B5)
        output_dir: Thư mục output

    Returns:
        Path tới file PNG, hoặc None nếu lỗi
    """
    print("\n  🔴 Render Infrared Composite (B11, B8, B5)...")

    try:
        # B8 từ file 10m
        nir = _read_band(file_10m, BANDS_10M_INDEX["B8"])
        target_shape = nir.shape

        # B11 và B5 từ file 20m — cần resample lên 10m
        swir = _read_band(file_20m, BANDS_20M_INDEX["B11"])
        red_edge = _read_band(file_20m, BANDS_20M_INDEX["B5"])

        # Resample 20m → 10m bằng bilinear interpolation
        swir_10m = _resample_20m_to_10m(swir, target_shape)
        red_edge_10m = _resample_20m_to_10m(red_edge, target_shape)

        # Normalize từng kênh
        r = _normalize_band(swir_10m)       # Red channel = SWIR
        g = _normalize_band(nir)             # Green channel = NIR
        b = _normalize_band(red_edge_10m)    # Blue channel = Red Edge

        # Stack thành RGB
        irp = np.dstack([r, g, b])

        output_path = output_dir / "infrared_irp.png"
        _save_png(irp, output_path)
        return str(output_path)

    except Exception as e:
        print(f"     ❌ Lỗi render Infrared: {e}")
        return None


def render_false_color(file_10m: Path, output_dir: Path) -> str | None:
    """
    Render ảnh False Color Composite — B8, B4, B3.

    Classic false color composite (CIR):
      - B8  (NIR, 842nm)   → kênh đỏ  (thực vật phản xạ mạnh)
      - B4  (Red, 665nm)   → kênh xanh lá
      - B3  (Green, 560nm) → kênh xanh dương

    Trong ảnh false color:
      - Thực vật khỏe mạnh → màu ĐỎ TƯƠI (NIR phản xạ cao)
      - Nước                → màu XANH ĐEN
      - Đất trống           → màu NÂU/XÁM
      - Khu đô thị          → màu XÁM/TRẮNG

    Args:
        file_10m: Path tới sentinel2_10m_bands.tif
        output_dir: Thư mục output

    Returns:
        Path tới file PNG, hoặc None nếu lỗi
    """
    print("\n  🎨 Render False Color (B8, B4, B3)...")

    try:
        nir = _read_band(file_10m, BANDS_10M_INDEX["B8"])    # NIR → Red
        red = _read_band(file_10m, BANDS_10M_INDEX["B4"])    # Red → Green
        green = _read_band(file_10m, BANDS_10M_INDEX["B3"])  # Green → Blue

        r = _normalize_band(nir)
        g = _normalize_band(red)
        b = _normalize_band(green)

        false_color = np.dstack([r, g, b])

        output_path = output_dir / "false_color.png"
        _save_png(false_color, output_path)
        return str(output_path)

    except Exception as e:
        print(f"     ❌ Lỗi render False Color: {e}")
        return None


# ── Hàm chính ────────────────────────────────────────────

def render_all_visualizations(
    input_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> list[str]:
    """
    Render tất cả visualization từ GeoTIFF bands đã export.

    Quy trình:
      1. Tìm file sentinel2_10m_bands.tif và sentinel2_20m_bands.tif
      2. Render 4 loại ảnh: RGB, NDVI, Infrared, False Color
      3. Lưu PNG vào output directory

    Args:
        input_dir: Thư mục chứa GeoTIFF (mặc định: data/)
        output_dir: Thư mục output PNG (mặc định: output/)

    Returns:
        Danh sách paths tới các file PNG đã render
    """
    from config.settings import DATA_DIR, OUTPUT_DIR

    in_dir = Path(input_dir) if input_dir else DATA_DIR
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    # Tìm file GeoTIFF
    file_10m = in_dir / "sentinel2_10m_bands.tif"
    file_20m = in_dir / "sentinel2_20m_bands.tif"

    if not file_10m.exists():
        print(f"❌ Không tìm thấy file 10m: {file_10m}")
        print("   Chạy 'python scripts/gee_export_bands.py' trước.")
        return []

    print(f"📊 Render visualizations từ GeoTIFF...")
    print(f"   Input:  {in_dir}")
    print(f"   Output: {out_dir}")
    print(f"   File 10m: {'✅' if file_10m.exists() else '❌'} {file_10m.name}")
    print(f"   File 20m: {'✅' if file_20m.exists() else '❌'} {file_20m.name}")

    out_dir.mkdir(parents=True, exist_ok=True)
    rendered = []

    # 1. RGB True Color — luôn render được (chỉ cần 10m bands)
    path = render_rgb(file_10m, out_dir)
    if path:
        rendered.append(path)

    # 2. NDVI — luôn render được (B8, B4 đều ở file 10m)
    path = render_ndvi(file_10m, out_dir)
    if path:
        rendered.append(path)

    # 3. Infrared — cần cả file 20m (B11, B5)
    if file_20m.exists():
        path = render_infrared(file_10m, file_20m, out_dir)
        if path:
            rendered.append(path)
    else:
        print("\n  ⚠️  Bỏ qua Infrared — không có file 20m bands")

    # 4. False Color — chỉ cần 10m bands
    path = render_false_color(file_10m, out_dir)
    if path:
        rendered.append(path)

    print(f"\n{'=' * 50}")
    print(f"✅ Render hoàn tất! {len(rendered)} ảnh visualization")
    for p in rendered:
        print(f"   📷 {Path(p).name}")

    return rendered


def render_sr_visualizations(
    output_dir: str | Path | None = None,
) -> list[str]:
    """
    Render visualization từ SuperResolutionV1 super-resolution output (1m/px).

    SuperResolutionV1 output là file GeoTIFF multi-band (tất cả bands 1m).
    Hàm này tìm file SR trong output dir, đọc bands, và render
    cùng 4 loại ảnh như gốc nhưng với prefix "sr_".

    Output files:
      - sr_rgb_tci.png     (RGB True Color 1m)
      - sr_ndvi.png        (NDVI 1m)
      - sr_infrared_irp.png (Infrared 1m)
      - sr_false_color.png  (False Color 1m)

    SuperResolutionV1 output band order (10 bands, all at 1m):
      B2(0), B3(1), B4(2), B5(3), B6(4), B7(5), B8(6), B8A(7), B11(8), B12(9)

    Args:
        output_dir: Thư mục chứa SR output GeoTIFF (mặc định: output/)

    Returns:
        Danh sách paths tới các file PNG đã render
    """
    from config.settings import OUTPUT_DIR

    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    # ── Tìm file SR GeoTIFF ──
    # SuperResolutionV1 output thường có tên chứa "sr", "super", "1m" hoặc là file .tif
    # mới nhất không phải file gốc (sentinel2_*.tif)
    sr_file = None

    # Ưu tiên tìm theo pattern phổ biến
    sr_patterns = [
        "sr_*.tif", "*_sr.tif", "*super*.tif", "*1m*.tif",
        "*output*.tif", "*result*.tif",
    ]
    for pattern in sr_patterns:
        matches = list(out_dir.glob(pattern))
        if matches:
            sr_file = matches[0]
            break

    # Fallback: tìm tất cả .tif trong output dir, loại bỏ file gốc
    if not sr_file:
        all_tifs = sorted(out_dir.glob("*.tif"), key=lambda f: f.stat().st_mtime, reverse=True)
        for tif in all_tifs:
            if "sentinel2_" not in tif.name:
                sr_file = tif
                break

    if not sr_file:
        print("❌ Không tìm thấy file SR GeoTIFF trong output/")
        print("   SuperResolutionV1 chưa tạo output? Kiểm tra lại quá trình inference.")
        return []

    print(f"\n📊 Render SR visualizations (1m/px)...")
    print(f"   SR file: {sr_file.name}")

    import rasterio
    with rasterio.open(sr_file) as src:
        n_bands = src.count
        print(f"   Bands:   {n_bands}")
        print(f"   Size:    {src.width} x {src.height}")

    rendered = []

    # ── Band mapping cho SR output ──
    # SuperResolutionV1 outputs 10 bands: B2, B3, B4, B5, B6, B7, B8, B8A, B11, B12
    # Index 0-based: B2=0, B3=1, B4=2, B5=3, B6=4, B7=5, B8=6, B8A=7, B11=8, B12=9
    SR_BAND = {"B2": 0, "B3": 1, "B4": 2, "B5": 3, "B6": 4,
               "B7": 5, "B8": 6, "B8A": 7, "B11": 8, "B12": 9}

    # Nếu SR có ít bands hơn 10, dùng cùng mapping như file gốc 10m
    if n_bands <= 4:
        SR_BAND = {"B2": 0, "B3": 1, "B4": 2, "B8": 3}

    try:
        # 1. SR RGB True Color
        print("\n  🌈 SR RGB True Color (B4, B3, B2)...")
        if all(b in SR_BAND for b in ["B4", "B3", "B2"]):
            red = _read_band(sr_file, SR_BAND["B4"])
            green = _read_band(sr_file, SR_BAND["B3"])
            blue = _read_band(sr_file, SR_BAND["B2"])
            rgb = np.dstack([_normalize_band(red), _normalize_band(green), _normalize_band(blue)])
            path = out_dir / "sr_rgb_tci.png"
            _save_png(rgb, path)
            rendered.append(str(path))

        # 2. SR NDVI
        print("\n  🌿 SR NDVI (B8, B4)...")
        if all(b in SR_BAND for b in ["B8", "B4"]):
            nir = _read_band(sr_file, SR_BAND["B8"])
            red = _read_band(sr_file, SR_BAND["B4"])
            denom = nir + red
            ndvi = np.where(denom > 0, (nir - red) / denom, 0)
            ndvi = np.clip(ndvi, -1, 1)

            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.cm as cm
            colored = cm.RdYlGn((ndvi + 1) / 2)[:, :, :3]
            path = out_dir / "sr_ndvi.png"
            _save_png(colored, path)
            rendered.append(str(path))

        # 3. SR Infrared (B11, B8, B5) — all bands tại 1m, ko cần resample
        print("\n  🔴 SR Infrared (B11, B8, B5)...")
        if all(b in SR_BAND for b in ["B11", "B8", "B5"]):
            swir = _read_band(sr_file, SR_BAND["B11"])
            nir = _read_band(sr_file, SR_BAND["B8"])
            re = _read_band(sr_file, SR_BAND["B5"])
            irp = np.dstack([_normalize_band(swir), _normalize_band(nir), _normalize_band(re)])
            path = out_dir / "sr_infrared_irp.png"
            _save_png(irp, path)
            rendered.append(str(path))

        # 4. SR False Color (B8, B4, B3)
        print("\n  🎨 SR False Color (B8, B4, B3)...")
        if all(b in SR_BAND for b in ["B8", "B4", "B3"]):
            nir = _read_band(sr_file, SR_BAND["B8"])
            red = _read_band(sr_file, SR_BAND["B4"])
            green = _read_band(sr_file, SR_BAND["B3"])
            fc = np.dstack([_normalize_band(nir), _normalize_band(red), _normalize_band(green)])
            path = out_dir / "sr_false_color.png"
            _save_png(fc, path)
            rendered.append(str(path))

    except Exception as e:
        print(f"     ❌ Lỗi render SR: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'=' * 50}")
    print(f"✅ SR render hoàn tất! {len(rendered)} ảnh")
    for p in rendered:
        print(f"   📷 {Path(p).name}")

    return rendered


# ── CLI ──────────────────────────────────────────────────

if __name__ == "__main__":
    import click

    @click.command()
    @click.option("--input-dir", type=str, default=None,
                  help="Thư mục chứa GeoTIFF (mặc định: data/)")
    @click.option("--output-dir", type=str, default=None,
                  help="Thư mục output PNG (mặc định: output/)")
    def main(input_dir, output_dir):
        """Render visualization PNG từ Sentinel-2 GeoTIFF bands."""
        render_all_visualizations(input_dir, output_dir)

    main()
