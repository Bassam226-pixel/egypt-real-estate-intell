# Grafana Dashboard Setup

This directory contains the Grafana configuration for the Egypt Investment Analytics project.

## Overview

Grafana visualizes Gold/Silver layer data through a dedicated `postgres-grafana` Postgres
instance — **not** through Dremio. `scripts/export_to_postgres.py` (run via the `exporter`
service) does a direct Spark JDBC write from Nessie/Iceberg into that Postgres instance;
Grafana then queries it through the auto-provisioned `PostgreSQL` datasource. See
[PIPELINE.md](../PIPELINE.md) for the full data flow.

## Directory Structure

```
grafana/
├── provisioning/
│   ├── datasources/
│   │   └── postgres.yml        # Postgres data source configuration (auto-provisioned)
│   └── dashboards/
│       └── dashboards.yml      # Dashboard provisioning configuration
├── dashboards/
│   ├── home.json                    # Home dashboard
│   ├── equities-dashboard.json
│   ├── commodities-dashboard.json
│   ├── currencies-dashboard.json
│   ├── real-estate-dashboard.json
│   └── portfolio-dashboard.json
├── plugins/                    # Grafana plugins directory
├── screenshot_utility.py       # Python script for capturing screenshots
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Quick Start

### 1. Export Gold layer data to Postgres, then start Grafana

```bash
docker compose --profile export up exporter
docker compose up -d postgres-grafana grafana grafana-image-renderer
```

### 2. Access Grafana

- URL: http://localhost:3001 (host port 3001 — 3000 is reserved for the `frontend` service under `--profile app`)
- Username: `admin` (`GF_SECURITY_ADMIN_USER`)
- Password: `admin` (`GF_SECURITY_ADMIN_PASSWORD`)

The `PostgreSQL` datasource is provisioned automatically from `provisioning/datasources/postgres.yml`
— no manual data source setup is needed. Its credentials come from the `GRAFANA_PG_USER` /
`GRAFANA_PG_PASSWORD` env vars (see `env.example`), which must match `postgres-grafana`'s own
credentials.

## Screenshot Capabilities

Grafana is configured with the image renderer for capturing dashboard screenshots.

### Using the Screenshot Utility

```bash
# Install dependencies
pip install -r requirements.txt

# List all dashboards
python screenshot_utility.py --url http://localhost:3001 --action list

# Capture a specific dashboard
python screenshot_utility.py --url http://localhost:3001 --action capture --dashboard <UID> --output screenshots/

# Capture all dashboards
python screenshot_utility.py --url http://localhost:3001 --action capture-all --output screenshots/

# Capture individual panels
python screenshot_utility.py --url http://localhost:3001 --action capture-panels --dashboard <UID> --output screenshots/

# Export dashboard JSON
python screenshot_utility.py --url http://localhost:3001 --action export --dashboard <UID> --output dashboards/
```

### Command Line Options

- `--url`: Grafana URL (default: http://localhost:3000 — pass `http://localhost:3001` for this project's mapping)
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
curl -u admin:admin "http://localhost:3001/render/d/<DASHBOARD_UID>?orgId=1&from=now-1h&to=now&width=1920&height=1080" -o dashboard.png

# Capture specific panel
curl -u admin:admin "http://localhost:3001/render/d/<DASHBOARD_UID>?orgId=1&panelId=<PANEL_ID>&width=800&height=400" -o panel.png
```

## Environment Variables

The Grafana container can be configured using environment variables in `docker-compose.yml`:

- `GF_SECURITY_ADMIN_USER`: Admin username (default: admin)
- `GF_SECURITY_ADMIN_PASSWORD`: Admin password (default: admin)
- `GF_RENDERING_SERVER_URL`: Image renderer URL
- `GF_RENDERING_CALLBACK_URL`: Grafana callback URL for rendering
- `POSTGRES_USER` / `POSTGRES_PASSWORD`: substituted into `postgres.yml`'s datasource config via `$__env{}` — set via `GRAFANA_PG_USER` / `GRAFANA_PG_PASSWORD` in `.env`

## Resource Limits

- **Grafana**: 512MB memory, 0.5 CPU
- **Image Renderer**: 2GB memory, 1.0 CPU

## Troubleshooting

### Grafana won't start

1. Check if port 3001 is available: `netstat -an | findstr :3001`
2. Check Docker logs: `docker logs grafana`
3. Verify provisioning files are correct

### Screenshots not working

1. Ensure image renderer is running: `docker ps | findstr grafana-image-renderer`
2. Check renderer logs: `docker logs grafana-image-renderer`
3. Verify environment variables in docker-compose.yml

### Data source connection issues / empty dashboards

1. Ensure `postgres-grafana` is running: `docker ps | findstr postgres-grafana`
2. Check that the export job has actually run: `docker compose --profile export up exporter` populates the tables Grafana queries — dashboards will be empty until this has run at least once
3. Check Postgres logs: `docker logs postgres-grafana`

## Dashboard Design Reference

[DASHBOARD_DESIGN.md](DASHBOARD_DESIGN.md) predates the current schema and no longer matches
the tables `scripts/export_to_postgres.py` actually produces or the queries the dashboard JSON
files actually run — treat the dashboard JSON files themselves as the source of truth, not that doc.
