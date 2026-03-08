# IPAM Exporter

A Prometheus exporter for IP Address Management (IPAM) data, designed for use with Grafana Alloy and Grafana dashboards.

## Features

- Network host discovery and monitoring
- DNS resolution and ping latency checks
- Prometheus metrics exporter (`prom` mode)
- Web-based JSON/CSV export interface (`web` mode)
- Compatible with Grafana Alloy

## Installation

1. Create virtual environment: `python -m venv venv`
2. Activate: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Unix)
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python main.py --networks 192.168.1.0/24 --mode web`

## Usage

### Web mode

```bash
python main.py --networks 192.168.1.0/24 --mode web
```

Serves on `http://localhost:8000` by default.

| Endpoint | URL | Description |
|---|---|---|
| `/health` | `http://localhost:8000/health` | Status, host count, and last scan timestamp |
| `/data` | `http://localhost:8000/data` | All hosts as a JSON array |
| `/count` | `http://localhost:8000/count` | Number of hosts in the current scan |
| `/columns` | `http://localhost:8000/columns` | Field names of the host records |
| `/csv` | `http://localhost:8000/csv` | All hosts as CSV |
| `/download.json` | `http://localhost:8000/download.json` | All hosts as a downloadable JSON file |

Each host record contains:

```json
{"ip": "192.168.1.1", "dns": "router.local.", "ms": 1.23}
```

### Prometheus mode

```bash
python main.py --networks 192.168.1.0/24 --mode prom
```

Exposes metrics at `http://localhost:8000/metrics`:
- `ip_ping_ms{ip, dns}` — ICMP ping latency per host in milliseconds (0 = no response)
- `ipam_exporter_time_seconds{job}` — time taken to complete a full scan

## Configuration

Settings can be provided via CLI args or environment variables (`.env` file supported):

| CLI arg | Env var | Default | Description |
|---|---|---|---|
| `--networks` | `NETWORKS` | required | Comma-separated CIDR networks or /32 hosts |
| `--mode` | `MODE` | `web` | `web` (Flask) or `prom` (Prometheus) |
| `--port` | `PORT` | `8000` | HTTP listen port |
| `--host` | `HOST` | `0.0.0.0` | Listen interface |
| `--interval` | `INTERVAL` | `30` | Scan interval in seconds |
| `--log_level` | `LOGLEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `--debug` | `DEBUG` | `false` | Flask debug mode (web only) |

## Planned features

See [PLAN.md](PLAN.md) for the full implementation plan, including:
- **Active-hosts-only filter** — suppress hosts with zero ping latency (offline hosts) from all outputs
- **Grafana dashboards** — pre-built dashboard JSON for both `web` and `prom` modes
- **Docker support** — Dockerfile and docker-compose with Prometheus and Grafana
- **State change detection and webhooks** — notifications when hosts go up or down
- **Forward DNS consistency checking** — validate that forward and reverse DNS records agree
- **MAC address / ARP resolution** — vendor identification for local subnet hosts
- **External IPAM source integration** — pull networks dynamically from NetBox or phpIPAM
- **Web endpoint authentication** — API key protection for all endpoints
- **CI/CD pipeline** — GitHub Actions for testing, linting, Docker builds, and releases
