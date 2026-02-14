#!/usr/bin/env python3
"""
Sentinel-2 Super Resolution Pipeline — Orchestrator
======================================================
Chạy toàn bộ pipeline end-to-end:
  1. Xác thực Google Earth Engine
  2. Tìm ảnh Sentinel-2 cloud-free
  3. Export bands B2-B12 GeoTIFF
  4. Chạy S2DR3 super resolution (nếu có GPU)
  5. Visualize kết quả

Sử dụng:
    python run_pipeline.py
    python run_pipeline.py --step search
    python run_pipeline.py --step export --image-id <ID>
"""

import sys
import click

from config.settings import print_config


@click.command()
@click.option(
    "--step",
    type=click.Choice(["all", "auth", "search", "export", "s2dr3", "visualize"]),
    default="all",
    help="Chạy bước cụ thể hoặc tất cả",
)
@click.option("--image-id", type=str, help="ID ảnh Sentinel-2 (cho bước export)")
@click.option("--date", type=str, help="Ngày chụp (cho S2DR3 online mode)")
@click.option("--lat", type=float, help="Vĩ độ")
@click.option("--lon", type=float, help="Kinh độ")
def main(step: str, image_id: str | None, date: str | None, lat: float | None, lon: float | None):
    """
    🛰️ Sentinel-2 Super Resolution Pipeline

    Chạy toàn bộ quy trình xử lý ảnh vệ tinh Sentinel-2.
    """
    print()
    print("╔" + "═" * 58 + "╗")
    print("║   🛰️  Sentinel-2 Super Resolution Pipeline                ║")
    print("║   Powered by S2DR3 (Gamma Earth / Yosef Akhtman)         ║")
    print("╚" + "═" * 58 + "╝")
    print()

    print_config()
    print()

    steps = {
        "all": ["auth", "search", "export", "s2dr3", "visualize"],
        "auth": ["auth"],
        "search": ["auth", "search"],
        "export": ["auth", "export"],
        "s2dr3": ["s2dr3"],
        "visualize": ["visualize"],
    }

    to_run = steps[step]

    # ── Step 1: Authenticate ──
    if "auth" in to_run:
        print("\n" + "━" * 50)
        print("📌 BƯỚC 1: Xác thực Google Earth Engine")
        print("━" * 50)

        from scripts.gee_authenticate import authenticate_gee
        success = authenticate_gee()

        if not success:
            print("\n❌ Xác thực thất bại. Dừng pipeline.")
            sys.exit(1)

    # ── Step 2: Search ──
    if "search" in to_run:
        print("\n" + "━" * 50)
        print("📌 BƯỚC 2: Tìm ảnh Sentinel-2 cloud-free")
        print("━" * 50)

        from scripts.gee_search_imagery import search_sentinel2_imagery
        results = search_sentinel2_imagery(lat=lat, lon=lon)

        if not results:
            print("\n⚠️  Không tìm thấy ảnh nào. Thử điều chỉnh tham số.")
            if step == "all":
                sys.exit(1)

        # Tự động chọn ảnh đầu tiên nếu không có image_id
        if not image_id and results:
            image_id = results[0]["image_id"]
            print(f"\n🎯 Tự động chọn ảnh ít mây nhất: {image_id}")

    # ── Step 3: Export ──
    if "export" in to_run:
        print("\n" + "━" * 50)
        print("📌 BƯỚC 3: Export bands B2-B12 GeoTIFF")
        print("━" * 50)

        from scripts.gee_export_bands import export_bands_to_local
        files = export_bands_to_local(image_id=image_id, lat=lat, lon=lon)

        if not files:
            print("\n⚠️  Export không thành công.")
            if step == "all":
                sys.exit(1)

    # ── Step 4: S2DR3 ──
    if "s2dr3" in to_run:
        print("\n" + "━" * 50)
        print("📌 BƯỚC 4: S2DR3 Super Resolution")
        print("━" * 50)

        from scripts.s2dr3_process import process_with_s2dr3
        process_with_s2dr3(lat=lat, lon=lon, date=date)

    # ── Step 5: Visualize ──
    if "visualize" in to_run:
        print("\n" + "━" * 50)
        print("📌 BƯỚC 5: Visualization")
        print("━" * 50)

        from scripts.visualize_results import visualize_comparison
        visualize_comparison()

    # ── Done ──
    print("\n" + "━" * 50)
    print("🏁 Pipeline hoàn tất!")
    print("━" * 50)


if __name__ == "__main__":
    main()
