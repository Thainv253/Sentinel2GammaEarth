#!/usr/bin/env python3
"""
Sentinel-2 Super Resolution — Web UI
=======================================
Giao diện web Flask cho pipeline xử lý ảnh vệ tinh.

Sử dụng:
    python app.py
    Mở http://localhost:5000
"""

import sys
import os
import json
import time
import glob
import threading
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_from_directory, Response, redirect, session

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import (
    WEB_HOST, WEB_PORT, WEB_DEBUG,
    DATA_DIR, OUTPUT_DIR, GCP_PROJECT_ID,
    LATITUDE, LONGITUDE, START_DATE, END_DATE,
    CLOUD_THRESHOLD, BUFFER_METERS, DEVICE, RUNTIME_ENV,
)

app = Flask(__name__)
app.secret_key = "super-secret-key-1234"

@app.before_request
def require_login():
    """Kiểm tra login. Ngoại trừ các route login, static."""
    # Bỏ qua kiểm tra login cho các route phục vụ trang login và static
    if request.endpoint in ('login', 'static'):
        return
    
    # Cho phép thumbnail API load trực tiếp nếu cần
    if request.path.startswith('/api/thumbnail'):
        return

    # Mấu chốt: không login thì chặn
    if not session.get('logged_in'):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Unauthorized", "success": False}), 401
        return redirect('/login')

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "namnh" and password == "a1b2c3d4":
            session['logged_in'] = True
            return redirect("/")
        else:
            error = "Tài khoản hoặc mật khẩu không đúng."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ── Trạng thái pipeline (in-memory) ────────────────────
pipeline_state = {
    "status": "idle",       # idle | searching | exporting | processing | done | error
    "progress": 0,          # 0-100
    "message": "",
    "logs": [],
    "search_results": [],
    "output_files": [],
    "error": None,
}
state_lock = threading.Lock()


def _update_state(**kwargs):
    with state_lock:
        pipeline_state.update(kwargs)
        if "message" in kwargs and kwargs["message"]:
            pipeline_state["logs"].append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "msg": kwargs["message"],
            })


def _reset_state():
    with state_lock:
        pipeline_state.update({
            "status": "idle",
            "progress": 0,
            "message": "",
            "logs": [],
            "search_results": [],
            "output_files": [],
            "error": None,
        })


# ── Helpers ─────────────────────────────────────────────

def _safe_float(val, default):
    """Parse float an toàn — trả default nếu val rỗng/invalid."""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default):
    """Parse int an toàn — trả default nếu val rỗng/invalid."""
    if val is None or val == "":
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


# ── Docker Detection ───────────────────────────────────

def _is_inside_docker():
    """Phát hiện đang chạy trong Docker container."""
    return (
        os.path.exists("/.dockerenv")
        or os.environ.get("RUNTIME_ENV", "").lower() == "docker"
    )


# ── Routes ─────────────────────────────────────────────

@app.route("/")
def index():
    """Trang chính."""
    return render_template("index.html", config={
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "cloud_threshold": CLOUD_THRESHOLD,
        "buffer_meters": BUFFER_METERS,
        "device": DEVICE,
        "runtime_env": RUNTIME_ENV,
        "gcp_project": GCP_PROJECT_ID or "",
    })


@app.route("/api/status")
def api_status():
    """Trả về trạng thái hiện tại của pipeline."""
    with state_lock:
        return jsonify(pipeline_state)


@app.route("/api/search", methods=["POST"])
def api_search():
    """Tìm kiếm ảnh Sentinel-2 cloud-free."""
    data = request.json or {}

    _reset_state()
    _update_state(status="searching", progress=10, message="🔍 Đang tìm ảnh Sentinel-2...")

    try:
        from scripts.gee_search_imagery import search_sentinel2_imagery

        lat = _safe_float(data.get("latitude"), LATITUDE)
        lon = _safe_float(data.get("longitude"), LONGITUDE)
        start_date = data.get("start_date") or START_DATE
        end_date = data.get("end_date") or END_DATE
        cloud_threshold = _safe_int(data.get("cloud_threshold"), CLOUD_THRESHOLD)
        buffer_meters = _safe_int(data.get("buffer_meters"), BUFFER_METERS)

        results = search_sentinel2_imagery(
            lat=lat,
            lon=lon,
            start_date=start_date,
            end_date=end_date,
            cloud_threshold=cloud_threshold,
            buffer_meters=buffer_meters,
            max_results=20,
        )

        _update_state(
            status="idle",
            progress=100,
            message=f"✅ Tìm thấy {len(results)} ảnh",
            search_results=results,
        )
        return jsonify({"success": True, "results": results, "count": len(results)})

    except Exception as e:
        import traceback
        traceback.print_exc()
        _update_state(status="error", message=f"❌ Lỗi: {str(e)}", error=str(e))
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/export", methods=["POST"])
def api_export():
    """Export ảnh Sentinel-2 (chạy async trong background thread)."""
    data = request.json or {}

    def _do_export():
        try:
            _update_state(status="exporting", progress=20, message="📥 Đang export bands GeoTIFF...")

            from scripts.gee_export_bands import export_bands_to_local

            files = export_bands_to_local(
                image_id=data.get("image_id"),
                lat=_safe_float(data.get("latitude"), LATITUDE),
                lon=_safe_float(data.get("longitude"), LONGITUDE),
                start_date=data.get("start_date") or START_DATE,
                end_date=data.get("end_date") or END_DATE,
                cloud_threshold=_safe_int(data.get("cloud_threshold"), CLOUD_THRESHOLD),
                buffer_meters=_safe_int(data.get("buffer_meters"), BUFFER_METERS),
            )

            if files:
                # Auto-render visualizations sau khi export xong
                _update_state(status="rendering", progress=80, message="📊 Đang render visualization (RGB, NDVI, IR)...")
                try:
                    from scripts.render_visualizations import render_all_visualizations
                    rendered = render_all_visualizations()
                    _update_state(
                        status="done",
                        progress=100,
                        message=f"✅ Export hoàn tất: {len(files)} files + {len(rendered)} visualizations",
                    )
                except Exception as ve:
                    # Render lỗi không critical — vẫn báo export thành công
                    _update_state(
                        status="done",
                        progress=100,
                        message=f"✅ Export hoàn tất: {len(files)} files (⚠️ Render lỗi: {ve})",
                    )
            else:
                _update_state(status="error", message="❌ Export thất bại", error="No files exported")

        except Exception as e:
            _update_state(status="error", message=f"❌ Lỗi export: {str(e)}", error=str(e))

    thread = threading.Thread(target=_do_export, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "Export đã bắt đầu..."})


@app.route("/api/process", methods=["POST"])
def api_process():
    """Chạy SuperResolutionV1 super resolution (async)."""
    data = request.json or {}

    def _do_process():
        try:
            _update_state(status="processing", progress=30, message="🚀 Đang chạy SuperResolutionV1 inference...")

            from scripts.superresolutionv1_process import process_with_superresolutionv1

            result = process_with_superresolutionv1(
                lat=_safe_float(data.get("latitude"), LATITUDE),
                lon=_safe_float(data.get("longitude"), LONGITUDE),
                date=data.get("date"),
                device=data.get("device") or DEVICE,
            )

            # ── Kiểm tra kết quả SuperResolutionV1 ──
            # result có thể là: dict (thành công), None (env check fail / lỗi)
            superresolutionv1_success = False
            if isinstance(result, dict):
                superresolutionv1_success = result.get("success", False)
            elif result is not None:
                # inferutils.test() trả về non-None → coi là thành công
                superresolutionv1_success = True

            if not superresolutionv1_success:
                # SuperResolutionV1 không thể chạy hoặc thất bại
                is_docker = _is_inside_docker()
                if not is_docker:
                    _update_state(
                        status="error",
                        progress=100,
                        message=(
                            "❌ SuperResolutionV1 không tạo được file output.\n"
                            "Kiểm tra logs terminal để xem lỗi chi tiết."
                        ),
                    )
                else:
                    _update_state(
                        status="error",
                        progress=100,
                        message=(
                            "❌ SuperResolutionV1 inference thất bại. Kiểm tra logs container.\n"
                            "Thử: docker compose build --no-cache"
                        ),
                    )
                return

            # ── SuperResolutionV1 inference thành công → render SR visualizations ──
            _update_state(status="rendering", progress=80, message="📊 Đang render SR visualizations...")

            try:
                from scripts.render_visualizations import render_sr_visualizations
                sr_rendered = render_sr_visualizations()
            except Exception as ve:
                sr_rendered = []
                print(f"⚠️ Render SR visualization lỗi: {ve}")

            # Scan output files
            output_files = _scan_output_files()

            # Lấy preview URL từ gamayos.github.io (nếu có)
            preview_url = ""
            sr_file_names = []
            if isinstance(result, dict):
                preview_url = result.get("preview_url") or ""
                sr_file_names = result.get("sr_files", [])

            msg = f"✅ SuperResolutionV1 hoàn tất! {len(sr_file_names)} SR files."
            if sr_file_names:
                msg += f"\n📁 Files: {', '.join(sr_file_names)}"
            if preview_url:
                msg += f"\n🔗 Preview: {preview_url}"

            _update_state(
                status="done",
                progress=100,
                message=msg,
                output_files=output_files,
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            _update_state(status="error", message=f"❌ Lỗi SuperResolutionV1: {str(e)}", error=str(e))

    thread = threading.Thread(target=_do_process, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "SuperResolutionV1 đã bắt đầu..."})


@app.route("/api/results")
def api_results():
    """Lấy danh sách ảnh kết quả (output + data)."""
    files = _scan_output_files()
    return jsonify({"success": True, "files": files})


@app.route("/api/generate-colab", methods=["POST"])
def api_generate_colab():
    """Tạo Colab notebook (.ipynb) với parameters pre-filled."""
    data = request.json or {}

    from scripts.generate_colab import generate_colab_notebook

    lat = _safe_float(data.get("latitude"), LATITUDE)
    lon = _safe_float(data.get("longitude"), LONGITUDE)
    date = data.get("date") or ""
    buffer = _safe_int(data.get("buffer_meters"), BUFFER_METERS)

    notebook = generate_colab_notebook(lat=lat, lon=lon, date=date, buffer_meters=buffer)

    # Lưu notebook vào output/
    nb_path = OUTPUT_DIR / "SuperResolutionV1_SuperResolution.ipynb"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

    return jsonify({
        "success": True,
        "download_url": f"/output/SuperResolutionV1_SuperResolution.ipynb",
        "message": "Notebook đã tạo! Tải về rồi upload lên Google Colab.",
    })


@app.route("/api/clear-results", methods=["POST"])
def api_clear_results():
    """Xoá tất cả file output (ảnh PNG, GeoTIFF)."""
    import shutil

    deleted = 0
    for directory in [OUTPUT_DIR, DATA_DIR]:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue
        for ext in ["*.tif", "*.tiff", "*.png", "*.jpg", "*.jpeg", "*.json"]:
            for f in dir_path.glob(ext):
                try:
                    f.unlink()
                    deleted += 1
                except Exception:
                    pass

    _reset_state()
    return jsonify({"success": True, "deleted": deleted})


def _scan_output_files():
    """Quét thư mục output và data để tìm ảnh.

    Phân loại thông minh dựa trên naming convention SuperResolutionV1:
      - S2L2A_*_TCI.tif    → gốc 10m, RGB
      - S2L2Ax10_*_TCI.tif  → super-res 1m, RGB
      - S2L2A_*_NDVI.tif   → gốc 10m, NDVI
      - S2L2Ax10_*_NDVI.tif → super-res 1m, NDVI
      - S2L2A_*_IRP.tif    → gốc 10m, Infrared
      - S2L2Ax10_*_IRP.tif  → super-res 1m, Infrared
    """
    files = []

    for directory, label in [(OUTPUT_DIR, "output"), (DATA_DIR, "data")]:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue

        for ext in ["*.tif", "*.tiff", "*.png", "*.jpg", "*.jpeg"]:
            for f in dir_path.glob(ext):
                size_mb = f.stat().st_size / 1024 / 1024
                name = f.stem
                name_lower = name.lower()
                is_geotiff = f.suffix.lower() in (".tif", ".tiff")

                # ── Phân loại SuperResolutionV1 output (GeoTIFF COG) ──
                is_sr = "s2l2ax10" in name_lower or "x10_" in name_lower
                is_s2_original = name_lower.startswith("s2l2a_") and not is_sr

                # Xác định mode hiển thị
                mode = "other"
                if "tci" in name_lower or "rgb" in name_lower or "color" in name_lower or "true" in name_lower:
                    mode = "rgb"
                elif "ndvi" in name_lower:
                    mode = "ndvi"
                elif "irp" in name_lower or "infrared" in name_lower or "ir" in name_lower or "nir" in name_lower:
                    mode = "infrared"
                elif "false" in name_lower:
                    mode = "false_color"
                elif "10m" in name_lower:
                    mode = "original_10m"
                elif "20m" in name_lower:
                    mode = "original_20m"

                # Nếu là SR GeoTIFF → đánh dấu mode đặc biệt
                if is_sr and is_geotiff:
                    mode = f"sr_{mode}" if mode != "other" else "super_resolution"

                # Label hiển thị
                if is_sr and is_geotiff:
                    display_label = f"🔬 SR 1m — {_mode_display(mode)}"
                elif is_s2_original and is_geotiff:
                    display_label = f"🛰️ Gốc 10m — {_mode_display(mode)}"
                elif is_geotiff:
                    display_label = f"📦 GeoTIFF — {name}"
                else:
                    display_label = f"🖼️ Preview — {_mode_display(mode)}"

                files.append({
                    "name": f.name,
                    "path": f"/{label}/{f.name}",
                    "size_mb": round(size_mb, 2),
                    "mode": mode,
                    "dir": label,
                    "ext": f.suffix.lower(),
                    "is_geotiff": is_geotiff,
                    "is_sr": is_sr,
                    "is_s2_original": is_s2_original,
                    "display_label": display_label,
                })

    # Sắp xếp: SR GeoTIFF trước, rồi original GeoTIFF, rồi PNG
    files.sort(key=lambda f: (0 if f["is_sr"] else 1, 0 if f["is_geotiff"] else 1, f["name"]))
    return files


def _mode_display(mode: str) -> str:
    """Chuyển mode code thành label hiển thị."""
    labels = {
        "rgb": "RGB", "sr_rgb": "RGB 1m",
        "ndvi": "NDVI", "sr_ndvi": "NDVI 1m",
        "infrared": "Infrared", "sr_infrared": "Infrared 1m",
        "false_color": "False Color", "sr_false_color": "False Color 1m",
        "original_10m": "10m Bands", "original_20m": "20m Bands",
        "super_resolution": "Super Res",
    }
    return labels.get(mode, mode)


# ── Thumbnail API (GEE) ──
@app.route("/api/thumbnail")
def api_thumbnail():
    """Tạo thumbnail preview từ GEE image ID."""
    image_id = request.args.get("image_id", "")
    if not image_id:
        return jsonify({"error": "Missing image_id"}), 400

    try:
        import ee
        from config.settings import GCP_PROJECT_ID

        try:
            ee.Initialize(project=GCP_PROJECT_ID)
        except Exception:
            ee.Authenticate()
            ee.Initialize(project=GCP_PROJECT_ID)

        img = ee.Image(image_id)

        # True color RGB thumbnail
        thumb_url = img.getThumbURL({
            "bands": ["B4", "B3", "B2"],
            "min": 0,
            "max": 3000,
            "dimensions": 128,
            "format": "png",
        })

        # Redirect sang GEE thumb URL
        return redirect(thumb_url)

    except Exception as e:
        # Trả 1x1 transparent PNG nếu lỗi
        import base64
        pixel = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIABQABNjN9GQAAAAlwSFlzAAALEwAACxMBAJqcGAAA"
            "AAd0SU1FB+cBGQYFNhP1V+MAAAANSURBVAjXY2BgYPgPAAEEAQB9ssjqAAAAAElFTkSuQmCC"
        )
        return Response(pixel, mimetype="image/png")


# ── Serve static files từ data/ và output/ ──
@app.route("/data/<path:filename>")
def serve_data(filename):
    return send_from_directory(str(DATA_DIR), filename)


@app.route("/output/<path:filename>")
def serve_output(filename):
    return send_from_directory(str(OUTPUT_DIR), filename)


# ── Download GeoTIFF (force download, không preview) ──
@app.route("/api/download/<dir_name>/<path:filename>")
def api_download_file(dir_name, filename):
    """Download file trực tiếp (Content-Disposition: attachment).

    Dùng cho GeoTIFF lớn — browser sẽ download thay vì mở.
    """
    if dir_name == "output":
        directory = str(OUTPUT_DIR)
    elif dir_name == "data":
        directory = str(DATA_DIR)
    else:
        return jsonify({"error": "Invalid directory"}), 400

    return send_from_directory(
        directory, filename,
        as_attachment=True,
        download_name=filename,
    )


@app.route("/api/sr-files")
def api_sr_files():
    """Liệt kê riêng files GeoTIFF super-resolution từ SuperResolutionV1.

    Trả về danh sách files SR (S2L2Ax10_*) để UI hiển thị
    section download GeoTIFF riêng biệt.
    """
    all_files = _scan_output_files()
    sr_files = [f for f in all_files if f["is_sr"] and f["is_geotiff"]]
    original_files = [f for f in all_files if f.get("is_s2_original") and f["is_geotiff"]]
    preview_files = [f for f in all_files if not f["is_geotiff"]]

    return jsonify({
        "success": True,
        "sr_files": sr_files,
        "original_files": original_files,
        "preview_files": preview_files,
        "total_sr": len(sr_files),
        "total_original": len(original_files),
    })


# ── Compare Page ──
@app.route("/compare")
def compare_page():
    """Trang so sánh split-view (10m gốc vs 1m super-resolution)."""
    config_data = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
    }
    return render_template("compare.html", config=config_data)


# ── Render Visualizations API ──
@app.route("/api/visualize", methods=["POST"])
def api_visualize():
    """Trigger render visualization PNG từ GeoTIFF đã export."""
    try:
        from scripts.render_visualizations import render_all_visualizations
        rendered = render_all_visualizations()
        return jsonify({
            "success": True,
            "rendered": rendered,
            "count": len(rendered),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ── Image Bounds API ──
@app.route("/api/image-bounds")
def api_image_bounds():
    """
    Trả bounds (lat/lon) của ảnh GeoTIFF đã export.
    Dùng cho Leaflet map trong compare page.
    """
    try:
        import rasterio
        from rasterio.warp import transform_bounds

        tif_path = DATA_DIR / "sentinel2_10m_bands.tif"
        if not tif_path.exists():
            return jsonify({"bounds": None, "error": "Chưa có file GeoTIFF"})

        with rasterio.open(tif_path) as src:
            # Chuyển bounds từ CRS gốc sang WGS84 (EPSG:4326)
            bounds = transform_bounds(src.crs, "EPSG:4326", *src.bounds)

        return jsonify({
            "bounds": {
                "west": bounds[0],
                "south": bounds[1],
                "east": bounds[2],
                "north": bounds[3],
            }
        })
    except Exception as e:
        return jsonify({"bounds": None, "error": str(e)})


# ── SSE Progress Stream ──
@app.route("/api/progress-stream")
def progress_stream():
    """Server-Sent Events stream cho progress updates."""
    def generate():
        last_msg = ""
        while True:
            with state_lock:
                data = json.dumps({
                    "status": pipeline_state["status"],
                    "progress": pipeline_state["progress"],
                    "message": pipeline_state["message"],
                    "logs": pipeline_state["logs"][-10:],  # Last 10 logs
                })

            if data != last_msg:
                yield f"data: {data}\n\n"
                last_msg = data

            if pipeline_state["status"] in ("done", "error", "idle"):
                yield f"data: {data}\n\n"
                break

            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    print()
    print("╔" + "═" * 52 + "╗")
    print("║  🛰️  Sentinel-2 Super Resolution — Web UI        ║")
    print(f"║  http://{WEB_HOST}:{WEB_PORT}" + " " * (52 - 11 - len(f"{WEB_HOST}:{WEB_PORT}")) + "║")
    print("╚" + "═" * 52 + "╝")
    print()

    from config.settings import print_config
    print_config()
    print()

    app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG, threaded=True)
