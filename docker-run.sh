#!/bin/bash
# =============================================
# Sentinel-2 Super Resolution — Docker Runner
# =============================================
# Sử dụng:
#   ./docker-run.sh              # Web UI (CPU mode)
#   ./docker-run.sh cpu          # Web UI (CPU mode)
#   ./docker-run.sh gpu          # Web UI (GPU mode)
#   ./docker-run.sh cpu pipeline # Chạy full pipeline
#   ./docker-run.sh cpu s2dr3    # Chỉ chạy S2DR3
#   ./docker-run.sh cpu shell    # Mở bash shell
# =============================================

set -e

MODE="${1:-cpu}"     # Mặc định: cpu
ACTION="${2:-web}"   # Mặc định: web UI

# Validate mode
if [[ "$MODE" != "cpu" && "$MODE" != "gpu" ]]; then
    echo "❌ Mode không hợp lệ: $MODE"
    echo ""
    echo "📋 Sử dụng:"
    echo "   ./docker-run.sh              # Web UI (CPU)"
    echo "   ./docker-run.sh cpu          # Web UI (CPU)"
    echo "   ./docker-run.sh gpu          # Web UI (GPU)"
    echo "   ./docker-run.sh cpu pipeline # Full pipeline"
    echo "   ./docker-run.sh cpu s2dr3    # Chỉ S2DR3"
    echo "   ./docker-run.sh cpu shell    # Bash shell"
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  🛰️  Sentinel-2 Super Resolution — Docker   ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Mode:     $MODE"
echo "  Action:   $ACTION"
echo "  Platform: linux/amd64"
echo ""

SERVICE="sentinel2-$MODE"

# Build image
echo "🔨 Building Docker image ($MODE)..."
docker compose --profile "$MODE" build "$SERVICE"

echo ""

# Chạy theo action
case "$ACTION" in
    web|ui)
        echo "🌐 Khởi động Web UI..."
        echo "   → http://localhost:5050"
        echo ""
        docker compose --profile "$MODE" up "$SERVICE"
        ;;
    shell|bash)
        echo "🐚 Mở shell trong container..."
        docker compose --profile "$MODE" run --rm "$SERVICE" bash
        ;;
    pipeline|all)
        echo "🚀 Chạy pipeline đầy đủ..."
        docker compose --profile "$MODE" run --rm "$SERVICE" python run_pipeline.py
        ;;
    s2dr3)
        echo "🚀 Chạy S2DR3 super resolution..."
        docker compose --profile "$MODE" run --rm "$SERVICE" python run_pipeline.py --step s2dr3
        ;;
    *)
        echo "🚀 Chạy: python run_pipeline.py --step $ACTION"
        docker compose --profile "$MODE" run --rm "$SERVICE" python run_pipeline.py --step "$ACTION"
        ;;
esac
