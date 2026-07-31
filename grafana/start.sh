#!/bin/bash
# Grafana Quick Start Script for Egypt Investment Analytics

set -e

echo "=========================================="
echo "Egypt Investment Analytics - Grafana Setup"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "ERROR: docker-compose is not installed. Please install it and try again."
    exit 1
fi

echo "Starting Grafana services..."
echo ""

# Start Grafana and image renderer
docker-compose up -d grafana grafana-image-renderer

echo ""
echo "Waiting for Grafana to start..."
sleep 10

# Check if Grafana is running
if docker ps | grep -q grafana; then
    echo "✓ Grafana is running"
else
    echo "✗ Grafana failed to start"
    echo "Check logs with: docker logs grafana"
    exit 1
fi

# Check if image renderer is running
if docker ps | grep -q grafana-image-renderer; then
    echo "✓ Image renderer is running"
else
    echo "✗ Image renderer failed to start"
    echo "Check logs with: docker logs grafana-image-renderer"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Access Grafana at: http://localhost:3000"
echo "Username: admin"
echo "Password: admin"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:3000 in your browser"
echo "2. Install the Dremio datasource plugin"
echo "3. Configure the Dremio connection"
echo "4. Create your dashboards"
echo ""
echo "To capture screenshots:"
echo "  python grafana/screenshot_utility.py --action list"
echo "  python grafana/screenshot_utility.py --action capture --dashboard <UID>"
echo ""
echo "To stop services:"
echo "  docker-compose stop grafana grafana-image-renderer"
echo ""