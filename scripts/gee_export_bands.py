#!/usr/bin/env python3
"""
Google Earth Engine — Export ảnh Sentinel-2 GeoTIFF
=====================================================
Export các band B2-B12 của ảnh Sentinel-2 thành file GeoTIFF local.

Sử dụng:
    python scripts/gee_export_bands.py
    python scripts/gee_export_bands.py --image-id COPERNICUS/S2_SR_HARMONIZED/20240115T031059_20240115T031054_T48PXS
"""

import sys
import time
import json
from pathlib import Path

import click

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def _init_ee():
    """Khởi tạo Earth Engine."""
    import ee
    from config.settings import GCP_PROJECT_ID

    try:
        ee.Initialize(project=GCP_PROJECT_ID)
    except Exception:
        print("⚠️  Chưa xác thực. Chạy scripts/gee_authenticate.py trước.")
        sys.exit(1)
    return ee


def get_best_image(ee_module, lat: float, lon: float, start_date: str,
                   end_date: str, cloud_max: int, buffer_meters: int):
    """Lấy ảnh Sentinel-2 tốt nhất (ít mây nhất) trong khu vực."""
    from scripts.gee_search_imagery import create_aoi
    from config.settings import GEE_COLLECTION

    aoi = create_aoi(ee_module, lat, lon, buffer_meters)

    collection = (
        ee_module.ImageCollection(GEE_COLLECTION)
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee_module.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", cloud_max))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )

    count = collection.size().getInfo()
    if count == 0:
        return None, aoi

    best = collection.first()
    return best, aoi


def export_bands_to_local(
    image_id: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    cloud_threshold: int | None = None,
    buffer_meters: int | None = None,
    scale: int | None = None,
    output_dir: str | None = None,
):
    """
    Export ảnh Sentinel-2 bands B2-B12 thành GeoTIFF files.

    Nếu image_id được cung cấp, sử dụng ảnh đó.
    Nếu không, tìm ảnh tốt nhất trong khu vực và thời gian.

    Args:
        image_id: ID ảnh cụ thể (từ search results)
        lat, lon: Tọa độ (nếu không có image_id)
        start_date, end_date: Khoảng thời gian
        cloud_threshold: Ngưỡng mây
        buffer_meters: Bán kính buffer
        scale: Export scale (meters)
        output_dir: Thư mục output
    """
    from config.settings import (
        LATITUDE, LONGITUDE, START_DATE, END_DATE,
        CLOUD_THRESHOLD, BUFFER_METERS, GEE_SCALE,
        S2DR3_BANDS, DATA_DIR, BAND_RESOLUTION,
    )

    lat = lat or LATITUDE
    lon = lon or LONGITUDE
    start = start_date or START_DATE
    end = end_date or END_DATE
    cloud_max = cloud_threshold if cloud_threshold is not None else CLOUD_THRESHOLD
    buffer = buffer_meters or BUFFER_METERS
    export_scale = scale or GEE_SCALE
    out_dir = Path(output_dir) if output_dir else DATA_DIR

    ee = _init_ee()

    # ── Chọn ảnh ──
    if image_id:
        print(f"📷 Sử dụng ảnh: {image_id}")
        image = ee.Image(image_id)
        from scripts.gee_search_imagery import create_aoi
        aoi = create_aoi(ee, lat, lon, buffer)
    else:
        print(f"🔍 Tìm ảnh tốt nhất tại ({lat}, {lon})...")
        image, aoi = get_best_image(ee, lat, lon, start, end, cloud_max, buffer)
        if image is None:
            print("❌ Không tìm thấy ảnh phù hợp!")
            return None

    # Lấy metadata ảnh
    info = image.getInfo()
    props = info.get("properties", {})
    img_date = props.get("GENERATION_TIME", "unknown")
    cloud_pct = props.get("CLOUDY_PIXEL_PERCENTAGE", "N/A")
    actual_id = info.get("id", image_id or "unknown")

    print(f"\n📋 Thông tin ảnh:")
    print(f"   ID:    {actual_id}")
    print(f"   Date:  {img_date}")
    print(f"   Cloud: {cloud_pct}%")
    print()

    # ── Export từng nhóm band theo resolution ──
    print(f"📥 Export {len(S2DR3_BANDS)} bands → GeoTIFF...")

    # Nhóm bands theo resolution để export hiệu quả
    band_groups = {
        "10m": [b for b in S2DR3_BANDS if BAND_RESOLUTION.get(b) == 10],
        "20m": [b for b in S2DR3_BANDS if BAND_RESOLUTION.get(b) == 20],
        "60m": [b for b in S2DR3_BANDS if BAND_RESOLUTION.get(b) == 60],
    }

    exported_files = []

    for res_label, bands in band_groups.items():
        if not bands:
            continue

        res_value = int(res_label.replace("m", ""))
        out_file = out_dir / f"sentinel2_{res_label}_bands.tif"

        print(f"\n  📦 Nhóm {res_label}: {', '.join(bands)}")

        # Chọn bands và clip theo AOI
        selected = image.select(bands).clip(aoi)

        # Export sử dụng getDownloadURL
        try:
            url = selected.getDownloadURL({
                "name": f"sentinel2_{res_label}",
                "bands": bands,
                "region": aoi,
                "scale": res_value,  # Sử dụng resolution gốc của band
                "filePerBand": False,
                "format": "GEO_TIFF",
            })

            print(f"     ⬇️  Đang tải ({res_label})...")

            import requests
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()

            # Lưu file
            out_file.parent.mkdir(parents=True, exist_ok=True)
            total_size = int(response.headers.get("content-length", 0))

            with open(out_file, "wb") as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        print(f"\r     ⬇️  {pct:.0f}% ({downloaded / 1024 / 1024:.1f} MB)", end="")

            print(f"\n     ✅ Đã lưu: {out_file} ({out_file.stat().st_size / 1024 / 1024:.1f} MB)")
            exported_files.append(str(out_file))

        except Exception as e:
            print(f"     ❌ Lỗi export {res_label}: {e}")

            # Fallback: export từng band riêng
            print(f"     🔄 Thử export từng band...")
            for band in bands:
                try:
                    band_file = out_dir / f"sentinel2_{band}.tif"
                    single = image.select([band]).clip(aoi)

                    url = single.getDownloadURL({
                        "name": f"sentinel2_{band}",
                        "bands": [band],
                        "region": aoi,
                        "scale": res_value,
                        "format": "GEO_TIFF",
                    })

                    resp = requests.get(url, timeout=300)
                    resp.raise_for_status()

                    with open(band_file, "wb") as f:
                        f.write(resp.content)

                    print(f"        ✅ {band}: {band_file}")
                    exported_files.append(str(band_file))

                except Exception as e2:
                    print(f"        ❌ {band}: {e2}")

    # ── Lưu metadata ──
    meta_file = out_dir / "image_metadata.json"
    metadata = {
        "image_id": actual_id,
        "date": img_date,
        "cloud_percentage": cloud_pct,
        "center": {"lat": lat, "lon": lon},
        "buffer_meters": buffer,
        "exported_files": exported_files,
        "bands": S2DR3_BANDS,
        "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 50}")
    print(f"✅ Export hoàn tất!")
    print(f"   Files: {len(exported_files)}")
    print(f"   Dir:   {out_dir}")
    print(f"   Meta:  {meta_file}")
    print(f"\n💡 Tiếp theo:")
    print(f"   python scripts/s2dr3_process.py")

    return exported_files


@click.command()
@click.option("--image-id", type=str, help="ID ảnh Sentinel-2 cụ thể")
@click.option("--lat", type=float, help="Vĩ độ trung tâm")
@click.option("--lon", type=float, help="Kinh độ trung tâm")
@click.option("--start-date", type=str, help="Ngày bắt đầu (YYYY-MM-DD)")
@click.option("--end-date", type=str, help="Ngày kết thúc (YYYY-MM-DD)")
@click.option("--cloud-threshold", type=int, help="Ngưỡng mây tối đa (%)")
@click.option("--buffer", "buffer_meters", type=int, help="Bán kính buffer (mét)")
@click.option("--scale", type=int, help="Export scale (mét)")
@click.option("--output-dir", type=str, help="Thư mục output")
def main(image_id, lat, lon, start_date, end_date, cloud_threshold, buffer_meters, scale, output_dir):
    """Export ảnh Sentinel-2 (bands B2-B12) thành GeoTIFF."""
    export_bands_to_local(image_id, lat, lon, start_date, end_date,
                          cloud_threshold, buffer_meters, scale, output_dir)


if __name__ == "__main__":
    main()
