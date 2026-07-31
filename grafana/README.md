# Grafana Dashboard Setup

This directory contains the Grafana configuration for the Egypt Investment Analytics project.

## Overview

Grafana is used for creating interactive dashboards to visualize the gold layer data from the Dremio lakehouse.

## Directory Structure

```
grafana/
├── provisioning/
│   ├── datasources/
│   │   └── dremio.yml          # Dremio data source configuration
│   └── dashboards/
│       └── dashboards.yml      # Dashboard provisioning configuration
├── dashboards/
│   └── home.json               # Home dashboard
├── plugins/                    # Grafana plugins directory
├── screenshot_utility.py       # Python script for capturing screenshots
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Quick Start

### 1. Start Grafana

```bash
docker-compose up -d grafana grafana-image-renderer
```

### 2. Access Grafana

- URL: http://localhost:3000
- Username: admin
- Password: admin

### 3. Install Dremio Plugin

After starting Grafana, install the Dremio datasource plugin:

1. Go to **Configuration** → **Data Sources** → **Add data source**
2. Search for "Dremio"
3. Install the plugin
4. Configure the connection:
   - URL: `http://dremio2:9047`
   - Path: `/dremio`

## Screenshot Capabilities

Grafana is configured with the image renderer for capturing dashboard screenshots.

### Using the Screenshot Utility

```bash
# Install dependencies
pip install -r requirements.txt

# List all dashboards
python screenshot_utility.py --action list

# Capture a specific dashboard
python screenshot_utility.py --action capture --dashboard <UID> --output screenshots/

# Capture all dashboards
python screenshot_utility.py --action capture-all --output screenshots/

# Capture individual panels
python screenshot_utility.py --action capture-panels --dashboard <UID> --output screenshots/

# Export dashboard JSON
python screenshot_utility.py --action export --dashboard <UID> --output dashboards/
```

### Command Line Options

- `--url`: Grafana URL (default: http://localhost:3000)
- `--username`: Grafana username (default: admin)
- `--password`: Grafana password (default: admin)
- `--action`: Action to perform (list, capture, capture-all, capture-panels, export)
- `--dashboard`: Dashboard UID (required for capture, capture-panels, export)
- `--output`: Output directory or file path
- `--time-range`: Time range for screenshots (e.g., now-1h, now-24h, now-7d)
- `--width`: Screenshot width (default: 1920)
- `--height`: Screenshot height (default: 1080)

## API-Based Screenshots

You can also capture screenshots directly using the Grafana API:

```bash
# Capture dashboard screenshot
curl -u admin:admin "http://localhost:3000/render/d/<DASHBOARD_UID>?orgId=1&from=now-1h&to=now&width=1920&height=1080" -o dashboard.png

# Capture specific panel
curl -u admin:admin "http://localhost:3000/render/d/<DASHBOARD_UID>?orgId=1&panelId=<PANEL_ID>&width=800&height=400" -o panel.png
```

## Environment Variables

The Grafana container can be configured using environment variables in `docker-compose.yml`:

- `GF_SECURITY_ADMIN_USER`: Admin username (default: admin)
- `GF_SECURITY_ADMIN_PASSWORD`: Admin password (default: admin)
- `GF_INSTALL_PLUGINS`: Comma-separated list of plugins to install
- `GF_RENDERING_SERVER_URL`: Image renderer URL
- `GF_RENDERING_CALLBACK_URL`: Grafana callback URL for rendering

## Resource Limits

Grafana is configured with lightweight resource limits:

- **Grafana**: 512MB memory, 0.5 CPU
- **Image Renderer**: 256MB memory, 0.25 CPU

## Troubleshooting

### Grafana won't start

1. Check if ports are available: `netstat -an | findstr :3000`
2. Check Docker logs: `docker logs grafana`
3. Verify provisioning files are correct

### Screenshots not working

1. Ensure image renderer is running: `docker ps | findstr grafana-image-renderer`
2. Check renderer logs: `docker logs grafana-image-renderer`
3. Verify environment variables in docker-compose.yml

### Data source connection issues

1. Ensure Dremio is running: `docker ps | findstr dremio2`
2. Check Dremio logs: `docker logs dremio2`
3. Verify the Dremio plugin is installed and configured

## Dashboard Design Reference

For comprehensive dashboard structures, visualizations, and KPIs, see:
- **[DASHBOARD_DESIGN.md](DASHBOARD_DESIGN.md)** - Complete guide to all dashboards, visualizations, and implementation details

## Next Steps

1. Create dashboard JSON files for each domain:
   - Equities Dashboard
   - Commodities Dashboard
   - Currencies Dashboard
   - Real Estate Dashboard
   - Portfolio Dashboard

2. Configure data source queries for each dashboard

3. Set up automated screenshot capture for reporting

4. Integrate with Power BI for additional visualization options