#!/usr/bin/env python3
"""
Visualization — So sánh kết quả Super Resolution
===================================================
So sánh ảnh Sentinel-2 gốc (10m/20m) với kết quả SuperResolutionV1 (1m).

Sử dụng:
    python scripts/visualize_results.py
    python scripts/visualize_results.py --input-dir ./data --output-dir ./output
"""

import sys
from pathlib import Path

import click
import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def load_geotiff(filepath: str | Path):
    """
    Load GeoTIFF file sử dụng rasterio.

    Returns:
        tuple: (data_array, profile) — numpy array và metadata
    """
    import rasterio

    filepath = Path(filepath)
    if not filepath.exists():
        print(f"❌ File không tồn tại: {filepath}")
        return None, None

    with rasterio.open(filepath) as src:
        data = src.read()  # Shape: (bands, height, width)
        profile = src.profile

    print(f"  📂 {filepath.name}: shape={data.shape}, dtype={data.dtype}")
    print(f"     CRS={profile.get('crs')}, Resolution={profile.get('res')}")

    return data, profile


def normalize_band(band_data, percentile_low=2, percentile_high=98):
    """Normalize band data to 0-1 range using percentile stretching."""
    low = np.percentile(band_data, percentile_low)
    high = np.percentile(band_data, percentile_high)

    if high == low:
        return np.zeros_like(band_data, dtype=np.float32)

    normalized = (band_data.astype(np.float32) - low) / (high - low)
    return np.clip(normalized, 0, 1)


def create_rgb_composite(data, band_order=None):
    """
    Tạo RGB composite từ multi-band data.

    Args:
        data: numpy array shape (bands, H, W)
        band_order: [R_idx, G_idx, B_idx] trong data array
                     Mặc định: B4=Red(idx 2), B3=Green(idx 1), B2=Blue(idx 0)
                     cho file 10m bands [B2, B3, B4, B8]
    """
    if band_order is None:
        # Mặc định: B4(Red)=idx2, B3(Green)=idx1, B2(Blue)=idx0
        band_order = [2, 1, 0]

    rgb = np.stack([
        normalize_band(data[band_order[0]]),
        normalize_band(data[band_order[1]]),
        normalize_band(data[band_order[2]]),
    ], axis=-1)

    return rgb


def compute_ndvi(data, nir_idx=3, red_idx=2):
    """
    Tính NDVI (Normalized Difference Vegetation Index).

    NDVI = (NIR - Red) / (NIR + Red)

    Args:
        data: numpy array shape (bands, H, W)
        nir_idx: Index của band NIR (B8) — mặc định 3 cho file 10m
        red_idx: Index của band Red (B4) — mặc định 2 cho file 10m
    """
    nir = data[nir_idx].astype(np.float32)
    red = data[red_idx].astype(np.float32)

    denominator = nir + red
    ndvi = np.where(denominator != 0, (nir - red) / denominator, 0)

    return ndvi


def visualize_comparison(
    input_dir: str | None = None,
    output_dir: str | None = None,
    save_png: bool = True,
):
    """
    Tạo visualization so sánh trước/sau super resolution.

    Args:
        input_dir: Thư mục chứa ảnh gốc (data/)
        output_dir: Thư mục chứa ảnh SuperResolutionV1 (output/)
        save_png: Lưu file PNG
    """
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from config.settings import DATA_DIR, OUTPUT_DIR

    in_dir = Path(input_dir) if input_dir else DATA_DIR
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    print("=" * 60)
    print("🎨 Sentinel-2 Visualization")
    print("=" * 60)

    # ── Tìm ảnh gốc 10m ──
    original_10m = in_dir / "sentinel2_10m_bands.tif"
    sr_files = list(out_dir.glob("*1m*.tif")) + list(out_dir.glob("*sr*.tif"))

    has_original = original_10m.exists()
    has_sr = len(sr_files) > 0

    if not has_original and not has_sr:
        print("❌ Không tìm thấy ảnh!")
        print(f"   Gốc:  {in_dir}/sentinel2_10m_bands.tif")
        print(f"   SuperResolutionV1: {out_dir}/*1m*.tif hoặc *sr*.tif")
        print()
        print("💡 Chạy các bước trước:")
        print("   1. python scripts/gee_export_bands.py")
        print("   2. python scripts/superresolutionv1_process.py")
        return

    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    # ── Visualize ảnh gốc ──
    if has_original:
        print(f"\n📷 Ảnh gốc (10m):")
        data_orig, profile_orig = load_geotiff(original_10m)

        if data_orig is not None:
            fig, axes = plt.subplots(1, 3, figsize=(18, 6))
            fig.suptitle("Sentinel-2 — Ảnh gốc (10m/px)", fontsize=14, fontweight="bold")

            # RGB True Color
            rgb = create_rgb_composite(data_orig)
            axes[0].imshow(rgb)
            axes[0].set_title("RGB True Color\n(B4-B3-B2)")
            axes[0].axis("off")

            # False Color (NIR-R-G)
            if data_orig.shape[0] >= 4:
                false_color = create_rgb_composite(data_orig, [3, 2, 1])
                axes[1].imshow(false_color)
                axes[1].set_title("False Color (NIR)\n(B8-B4-B3)")
                axes[1].axis("off")

                # NDVI
                ndvi = compute_ndvi(data_orig)
                im = axes[2].imshow(ndvi, cmap="RdYlGn", vmin=-0.2, vmax=0.8)
                axes[2].set_title("NDVI\n(B8-B4)/(B8+B4)")
                axes[2].axis("off")
                plt.colorbar(im, ax=axes[2], shrink=0.8, label="NDVI")
            else:
                axes[1].text(0.5, 0.5, "NIR band\nkhông có", ha="center", va="center", fontsize=14)
                axes[1].axis("off")
                axes[2].text(0.5, 0.5, "NDVI\nkhông có", ha="center", va="center", fontsize=14)
                axes[2].axis("off")

            plt.tight_layout()

            if save_png:
                fig_path = figures_dir / "original_10m_overview.png"
                plt.savefig(fig_path, dpi=150, bbox_inches="tight")
                print(f"\n  ✅ Đã lưu: {fig_path}")

            plt.show()

    # ── Visualize ảnh SuperResolutionV1 ──
    if has_sr:
        sr_file = sr_files[0]
        print(f"\n🚀 Ảnh SuperResolutionV1 super resolution (1m):")
        data_sr, profile_sr = load_geotiff(sr_file)

        if data_sr is not None:
            fig2, axes2 = plt.subplots(1, 2, figsize=(14, 6))
            fig2.suptitle("SuperResolutionV1 — Super Resolution (1m/px)", fontsize=14, fontweight="bold")

            # RGB
            if data_sr.shape[0] >= 3:
                rgb_sr = create_rgb_composite(data_sr)
                axes2[0].imshow(rgb_sr)
                axes2[0].set_title("RGB True Color (1m/px)")
                axes2[0].axis("off")

                # NDVI nếu có NIR band
                if data_sr.shape[0] >= 4:
                    ndvi_sr = compute_ndvi(data_sr)
                    im2 = axes2[1].imshow(ndvi_sr, cmap="RdYlGn", vmin=-0.2, vmax=0.8)
                    axes2[1].set_title("NDVI (1m/px)")
                    axes2[1].axis("off")
                    plt.colorbar(im2, ax=axes2[1], shrink=0.8, label="NDVI")
                else:
                    axes2[1].axis("off")

            plt.tight_layout()

            if save_png:
                fig_path = figures_dir / "superresolutionv1_1m_overview.png"
                plt.savefig(fig_path, dpi=150, bbox_inches="tight")
                print(f"\n  ✅ Đã lưu: {fig_path}")

            plt.show()

    # ── So sánh side-by-side ──
    if has_original and has_sr and data_orig is not None and data_sr is not None:
        print(f"\n🔍 So sánh trước/sau:")
        fig3, axes3 = plt.subplots(1, 2, figsize=(16, 7))
        fig3.suptitle("So sánh: Gốc (10m) vs SuperResolutionV1 (1m)", fontsize=14, fontweight="bold")

        rgb_orig = create_rgb_composite(data_orig)
        axes3[0].imshow(rgb_orig)
        axes3[0].set_title(f"Gốc — 10m/px\n({data_orig.shape[1]}×{data_orig.shape[2]} px)")
        axes3[0].axis("off")

        rgb_sr = create_rgb_composite(data_sr)
        axes3[1].imshow(rgb_sr)
        axes3[1].set_title(f"SuperResolutionV1 — 1m/px\n({data_sr.shape[1]}×{data_sr.shape[2]} px)")
        axes3[1].axis("off")

        plt.tight_layout()

        if save_png:
            fig_path = figures_dir / "comparison_10m_vs_1m.png"
            plt.savefig(fig_path, dpi=200, bbox_inches="tight")
            print(f"  ✅ Đã lưu: {fig_path}")

        plt.show()

    print(f"\n{'=' * 60}")
    print(f"✅ Visualization hoàn tất!")
    if save_png:
        print(f"   📁 Figures: {figures_dir}")


@click.command()
@click.option("--input-dir", type=str, help="Thư mục ảnh gốc (data/)")
@click.option("--output-dir", type=str, help="Thư mục ảnh SuperResolutionV1 (output/)")
@click.option("--no-save", is_flag=True, help="Không lưu file PNG")
def main(input_dir, output_dir, no_save):
    """So sánh visualization ảnh gốc vs SuperResolutionV1 super resolution."""
    visualize_comparison(input_dir, output_dir, save_png=not no_save)


if __name__ == "__main__":
    main()
