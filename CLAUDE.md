# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run (web mode, default)
python main.py --networks 192.168.1.0/24 --mode web

# Run (prometheus mode)
python main.py --networks 192.168.1.0/24 --mode prom

# Run tests
pytest tests/

# Run a single test
pytest tests/test_ipam.py::test_health_endpoint
```

## Configuration

Settings can be provided via CLI args or environment variables (`.env` file supported via `python-dotenv`):

| CLI arg | Env var | Default | Description |
|---|---|---|---|
| `--networks` | `NETWORKS` | required | Comma-separated CIDR networks/hosts |
| `--mode` | `MODE` | `web` | `web` (Flask) or `prom` (Prometheus) |
| `--port` | `PORT` | `8000` | HTTP listen port |
| `--host` | `HOST` | `0.0.0.0` | Listen interface |
| `--interval` | `INTERVAL` | `30` | Scan interval in seconds |
| `--log_level` | `LOGLEVEL` | `INFO` | Log level |
| `--debug` | `DEBUG` | `false` | Flask debug mode |

## Architecture

The app has two independent operating modes, selected at startup via `--mode`:

**`web` mode** (`src/web_csv.py`): A Flask HTTP server that exposes host data as JSON/CSV. A background daemon thread runs `run_scanner_forever()` (asyncio event loop) that probes all hosts concurrently via `scan_once()`, writing results to a thread-safe global `CACHE`. Flask endpoints (`/health`, `/data`, `/count`, `/columns`, `/csv`, `/download.json`) only read from the cache — they never trigger scans.

**`prom` mode** (`src/prom.py`): A Prometheus exporter using `prometheus_client`. Exposes `ip_ping_ms` gauge (with `ip` and `dns` labels) and `ipam_exporter_time_seconds` summary. Uses asyncio with `asyncio.to_thread` for concurrent probing of all hosts. Metrics served via `start_http_server()` at `/metrics`.

**Shared components** (`src/common.py`):
- `get_addresses(networks)`: expands CIDR networks into individual IP objects, handles /32 hosts vs subnets
- `logger`: named `matey_exporter`, streams to console

**Entry point** (`main.py`): Parses CLI args, loads `.env`, validates that `--networks` was provided, builds `Settings`, then delegates to either `ipam_prom()` or `ipam_web()`.

Each host probe (both modes): ICMP ping via `ping3` (200ms timeout) + reverse DNS PTR lookup via `dnspython` (200ms timeout). Missing DNS resolves to empty string; no ping resolves to 0ms.

## Planned features

See [PLAN.md](PLAN.md) for implementation details:
- **Active-hosts-only filter** (`--active-only`) — suppress hosts with `ms == 0` from all outputs
- **Grafana dashboards** — pre-built dashboard JSON for both modes
