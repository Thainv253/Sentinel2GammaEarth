#!/usr/bin/env python3
"""
Google Earth Engine — Tìm kiếm ảnh Sentinel-2 không bị mây
=============================================================
Tìm kiếm ảnh Sentinel-2 trong khu vực và khoảng thời gian cho trước,
lọc theo tỷ lệ mây, hiển thị danh sách ảnh phù hợp.

Sử dụng:
    python scripts/gee_search_imagery.py
    python scripts/gee_search_imagery.py --lat 10.76 --lon 106.66 --start-date 2024-01-01
"""

import sys
import json
from datetime import datetime

import click

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def _init_ee():
    """Khởi tạo Earth Engine."""
    import ee
    from config.settings import GCP_PROJECT_ID

    try:
        ee.Initialize(project=GCP_PROJECT_ID)
    except Exception:
        print("⚠️  Chưa xác thực. Đang thử authenticate...")
        ee.Authenticate()
        ee.Initialize(project=GCP_PROJECT_ID)
    return ee


def create_aoi(ee_module, lat: float, lon: float, buffer_meters: int):
    """
    Tạo Area of Interest (bounding box) từ tọa độ trung tâm.

    Args:
        ee_module: Earth Engine module
        lat: Vĩ độ trung tâm
        lon: Kinh độ trung tâm
        buffer_meters: Bán kính buffer (mét)

    Returns:
        ee.Geometry — bounding box
    """
    point = ee_module.Geometry.Point([lon, lat])
    aoi = point.buffer(buffer_meters).bounds()
    return aoi


def search_sentinel2_imagery(
    lat: float | None = None,
    lon: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    cloud_threshold: int | None = None,
    buffer_meters: int | None = None,
    max_results: int = 20,
):
    """
    Tìm kiếm ảnh Sentinel-2 không bị mây.

    Args:
        lat: Vĩ độ (mặc định từ .env)
        lon: Kinh độ (mặc định từ .env)
        start_date: Ngày bắt đầu YYYY-MM-DD
        end_date: Ngày kết thúc YYYY-MM-DD
        cloud_threshold: Ngưỡng mây tối đa (%)
        buffer_meters: Bán kính buffer (mét)
        max_results: Số kết quả tối đa

    Returns:
        list[dict] — danh sách ảnh với metadata
    """
    from config.settings import (
        LATITUDE, LONGITUDE, START_DATE, END_DATE,
        CLOUD_THRESHOLD, BUFFER_METERS,
        GEE_COLLECTION, GEE_CLOUD_COLLECTION,
    )

    # Sử dụng giá trị từ tham số hoặc config
    lat = lat or LATITUDE
    lon = lon or LONGITUDE
    start = start_date or START_DATE
    end = end_date or END_DATE
    cloud_max = cloud_threshold if cloud_threshold is not None else CLOUD_THRESHOLD
    buffer = buffer_meters or BUFFER_METERS

    ee = _init_ee()

    print(f"🔍 Tìm kiếm ảnh Sentinel-2...")
    print(f"   Tọa độ:    {lat}, {lon}")
    print(f"   Buffer:    {buffer}m")
    print(f"   Thời gian: {start} → {end}")
    print(f"   Cloud max: {cloud_max}%")
    print()

    # Tạo AOI
    aoi = create_aoi(ee, lat, lon, buffer)

    # Lọc Sentinel-2 SR Harmonized
    s2_collection = (
        ee.ImageCollection(GEE_COLLECTION)
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", cloud_max))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
        .limit(max_results)
    )

    # Lấy metadata
    count = s2_collection.size().getInfo()
    print(f"📊 Tìm thấy {count} ảnh phù hợp:")
    print("-" * 80)

    if count == 0:
        print("   ⚠️  Không tìm thấy ảnh nào! Thử:")
        print("      - Tăng CLOUD_THRESHOLD")
        print("      - Mở rộng khoảng thời gian")
        print("      - Kiểm tra lại tọa độ")
        return []

    # Lấy danh sách ảnh
    image_list = s2_collection.toList(max_results)
    results = []

    for i in range(count):
        img = ee.Image(image_list.get(i))
        info = img.getInfo()
        props = info.get("properties", {})

        # Trích xuất metadata
        image_id = info.get("id", "N/A")
        date_ms = props.get("system:time_start", 0)
        date_str = datetime.fromtimestamp(date_ms / 1000).strftime("%Y-%m-%d %H:%M") if date_ms else "N/A"
        cloud_pct = props.get("CLOUDY_PIXEL_PERCENTAGE", "N/A")
        spacecraft = props.get("SPACECRAFT_NAME", "N/A")
        orbit = props.get("SENSING_ORBIT_NUMBER", "N/A")
        tile = props.get("MGRS_TILE", "N/A")

        result = {
            "index": i + 1,
            "image_id": image_id,
            "date": date_str,
            "cloud_percentage": round(cloud_pct, 2) if isinstance(cloud_pct, (int, float)) else cloud_pct,
            "spacecraft": spacecraft,
            "orbit_number": orbit,
            "mgrs_tile": tile,
        }
        results.append(result)

        # In kết quả
        cloud_emoji = "☀️" if isinstance(cloud_pct, (int, float)) and cloud_pct < 5 else "⛅"
        print(f"  {cloud_emoji} [{i+1}] {date_str}")
        print(f"      ID:    {image_id}")
        print(f"      Cloud: {result['cloud_percentage']}%")
        print(f"      Tile:  {tile}  |  {spacecraft}  |  Orbit: {orbit}")
        print()

    print("-" * 80)
    print(f"💡 Để export ảnh, chạy:")
    print(f"   python scripts/gee_export_bands.py --image-id <IMAGE_ID>")

    # Lưu kết quả JSON
    from config.settings import DATA_DIR
    output_file = DATA_DIR / "search_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n📁 Kết quả đã lưu: {output_file}")

    return results


@click.command()
@click.option("--lat", type=float, help="Vĩ độ trung tâm")
@click.option("--lon", type=float, help="Kinh độ trung tâm")
@click.option("--start-date", type=str, help="Ngày bắt đầu (YYYY-MM-DD)")
@click.option("--end-date", type=str, help="Ngày kết thúc (YYYY-MM-DD)")
@click.option("--cloud-threshold", type=int, help="Ngưỡng mây tối đa (%)")
@click.option("--buffer", "buffer_meters", type=int, help="Bán kính buffer (mét)")
@click.option("--max-results", type=int, default=20, help="Số kết quả tối đa")
def main(lat, lon, start_date, end_date, cloud_threshold, buffer_meters, max_results):
    """Tìm kiếm ảnh Sentinel-2 không bị mây che phủ."""
    search_sentinel2_imagery(lat, lon, start_date, end_date, cloud_threshold, buffer_meters, max_results)


if __name__ == "__main__":
    main()
