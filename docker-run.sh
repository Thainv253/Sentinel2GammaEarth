#!/bin/bash
# =============================================
# Sentinel-2 Super Resolution — Docker Runner
# =============================================
# Sử dụng:
#   ./docker-run.sh gpu          # Chạy pipeline với GPU
#   ./docker-run.sh cpu          # Chạy pipeline với CPU
#   ./docker-run.sh gpu search   # Chỉ chạy bước search (GPU)
#   ./docker-run.sh cpu shell    # Mở shell trong container CPU
# =============================================

set -e

MODE="${1:-cpu}"     # Mặc định: cpu
ACTION="${2:-}"      # Mặc định: chạy pipeline

# Validate mode
if [[ "$MODE" != "cpu" && "$MODE" != "gpu" ]]; then
    echo "❌ Mode không hợp lệ: $MODE"
    echo "   Sử dụng: ./docker-run.sh [cpu|gpu] [command]"
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  🛰️  Sentinel-2 Super Resolution — Docker   ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Mode:   $MODE"
echo "  Action: ${ACTION:-pipeline (full)}"
echo ""

SERVICE="sentinel2-$MODE"

# Build nếu chưa có image
echo "🔨 Building Docker image ($MODE)..."
docker compose --profile "$MODE" build "$SERVICE"

# Chạy
if [[ "$ACTION" == "shell" ]]; then
    echo "🐚 Mở shell trong container..."
    docker compose --profile "$MODE" run --rm "$SERVICE" bash
elif [[ -n "$ACTION" ]]; then
    echo "🚀 Chạy: python run_pipeline.py --step $ACTION"
    docker compose --profile "$MODE" run --rm "$SERVICE" python run_pipeline.py --step "$ACTION"
else
    echo "🚀 Chạy pipeline đầy đủ..."
    docker compose --profile "$MODE" run --rm "$SERVICE" python run_pipeline.py
fi
