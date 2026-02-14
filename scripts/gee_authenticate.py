#!/usr/bin/env python3
"""
Google Earth Engine — Xác thực
================================
Xác thực tài khoản Google và khởi tạo Earth Engine API.

Sử dụng:
    python scripts/gee_authenticate.py
    python scripts/gee_authenticate.py --project your-project-id
"""

import sys
import click

# Thêm project root vào path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def authenticate_gee(project_id: str | None = None, service_account_key: str | None = None):
    """
    Xác thực và khởi tạo Google Earth Engine.

    Args:
        project_id: Google Cloud Project ID
        service_account_key: Đường dẫn tới Service Account JSON key (tùy chọn)

    Returns:
        True nếu xác thực thành công
    """
    try:
        import ee
    except ImportError:
        print("❌ Chưa cài đặt earthengine-api!")
        print("   Chạy: pip install earthengine-api")
        return False

    from config.settings import GCP_PROJECT_ID, GEE_SERVICE_ACCOUNT_KEY

    # Ưu tiên tham số truyền vào, sau đó .env
    project = project_id or GCP_PROJECT_ID
    sa_key = service_account_key or GEE_SERVICE_ACCOUNT_KEY

    if not project:
        print("❌ Thiếu GCP Project ID!")
        print("   Cách 1: python scripts/gee_authenticate.py --project YOUR_PROJECT_ID")
        print("   Cách 2: Điền GCP_PROJECT_ID trong file .env")
        return False

    print(f"🔐 Xác thực Google Earth Engine...")
    print(f"   Project: {project}")

    try:
        if sa_key:
            # Xác thực bằng Service Account
            print(f"   Phương thức: Service Account ({sa_key})")
            credentials = ee.ServiceAccountCredentials(
                email=None,  # Tự lấy từ JSON key
                key_file=sa_key,
            )
            ee.Initialize(credentials=credentials, project=project)
        else:
            # Xác thực bằng tài khoản cá nhân (interactive)
            print("   Phương thức: Tài khoản cá nhân (browser)")
            ee.Authenticate()
            ee.Initialize(project=project)

        # Kiểm tra kết nối
        test = ee.Number(1).getInfo()
        if test == 1:
            print("✅ Xác thực thành công!")
            print(f"   Earth Engine API đã sẵn sàng (project: {project})")
            return True
        else:
            print("❌ Xác thực thất bại — không thể kết nối Earth Engine")
            return False

    except ee.EEException as e:
        print(f"❌ Lỗi Earth Engine: {e}")
        print("\n💡 Gợi ý:")
        print("   1. Kiểm tra GCP Project ID có đúng không")
        print("   2. Đảm bảo Earth Engine API đã được enable:")
        print("      https://console.cloud.google.com/apis/library/earthengine.googleapis.com")
        print("   3. Đảm bảo đã đăng ký Earth Engine:")
        print("      https://code.earthengine.google.com/register")
        return False

    except Exception as e:
        print(f"❌ Lỗi không xác định: {e}")
        return False


@click.command()
@click.option("--project", "-p", help="Google Cloud Project ID")
@click.option("--service-account", "-sa", help="Đường dẫn Service Account JSON key")
def main(project: str | None, service_account: str | None):
    """Xác thực Google Earth Engine."""
    success = authenticate_gee(project, service_account)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
