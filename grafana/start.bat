@echo off
REM Grafana Quick Start Script for Egypt Investment Analytics

echo ==========================================
echo Egypt Investment Analytics - Grafana Setup
echo ==========================================
echo.

REM Check if Docker is running
docker info > nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running. Please start Docker and try again.
    pause
    exit /b 1
)

echo Exporting Gold layer data to Postgres (skip if already exported)...
echo.
docker-compose --profile export up exporter

echo Starting Grafana services...
echo.

REM Start Grafana and image renderer (postgres-grafana starts automatically as a dependency)
docker-compose up -d grafana grafana-image-renderer

echo.
echo Waiting for Grafana to start...
timeout /t 10 /nobreak > nul

REM Check if Grafana is running
docker ps | findstr /i "grafana" > nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Grafana is running
) else (
    echo ✗ Grafana failed to start
    echo Check logs with: docker logs grafana
    pause
    exit /b 1
)

REM Check if image renderer is running
docker ps | findstr /i "grafana-image-renderer" > nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Image renderer is running
) else (
    echo ✗ Image renderer failed to start
    echo Check logs with: docker logs grafana-image-renderer
)

echo.
echo ==========================================
echo Setup Complete!
echo ==========================================
echo.
echo Access Grafana at: http://localhost:3001
echo Username: admin
echo Password: admin
echo.
echo The PostgreSQL datasource and dashboards are already provisioned automatically.
echo.
echo To capture screenshots:
echo   python grafana\screenshot_utility.py --action list
echo   python grafana\screenshot_utility.py --action capture --dashboard ^<UID^>
echo.
echo To stop services:
echo   docker-compose stop grafana grafana-image-renderer
echo.
pause