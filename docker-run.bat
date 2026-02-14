@echo off
REM =============================================
REM Sentinel-2 Super Resolution — Docker Runner (Windows)
REM =============================================
REM Sử dụng:
REM   docker-run.bat gpu          - Chạy pipeline với GPU
REM   docker-run.bat cpu          - Chạy pipeline với CPU
REM   docker-run.bat gpu search   - Chỉ chạy bước search (GPU)
REM   docker-run.bat cpu shell    - Mở shell trong container CPU
REM =============================================

SET MODE=%1
SET ACTION=%2

IF "%MODE%"=="" SET MODE=cpu

IF NOT "%MODE%"=="cpu" IF NOT "%MODE%"=="gpu" (
    echo [ERROR] Mode khong hop le: %MODE%
    echo    Su dung: docker-run.bat [cpu^|gpu] [command]
    exit /b 1
)

echo.
echo ================================================
echo   Sentinel-2 Super Resolution — Docker
echo ================================================
echo   Mode:   %MODE%
echo   Action: %ACTION%
echo.

SET SERVICE=sentinel2-%MODE%

echo [BUILD] Building Docker image (%MODE%)...
docker compose --profile %MODE% build %SERVICE%

IF "%ACTION%"=="shell" (
    echo [SHELL] Mo shell trong container...
    docker compose --profile %MODE% run --rm %SERVICE% bash
) ELSE IF NOT "%ACTION%"=="" (
    echo [RUN] Chay: python run_pipeline.py --step %ACTION%
    docker compose --profile %MODE% run --rm %SERVICE% python run_pipeline.py --step %ACTION%
) ELSE (
    echo [RUN] Chay pipeline day du...
    docker compose --profile %MODE% run --rm %SERVICE% python run_pipeline.py
)
