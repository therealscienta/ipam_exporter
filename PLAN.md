# Implementation Plan

## Outstanding TODOs from code

### `main.py`
- **Build version placeholder** (`"XXXXXXXX"`): The `ipam_build_version` Prometheus Info metric has a hardcoded build string. This should be injected by the CI/CD pipeline (e.g., via a `BUILD` environment variable or a generated `_version.py` file at build time).

---

## Planned Features

### 1. Active-hosts-only filter (`--active-only`)

Only report/expose hosts that responded to ping (i.e., `ms > 0`). Hosts that are down still consume a Prometheus label set indefinitely once they've been seen, which can bloat metrics. This option would suppress zero-latency entries.

**Scope of changes:**

- **`src/settings.py`** — Add `active_only: bool = False` field.
- **`main.py`** — Add `--active-only` CLI arg and `ACTIVE_ONLY` env var; wire into `Settings`.
- **`src/web_csv.py`** — In `get_cached_snapshot()` (or at the call sites in each endpoint), filter out results where `ms == 0` when `settings.active_only` is `True`. Because `CACHE` is global and settings aren't passed into the Flask app at request time, the cleanest approach is to store `active_only` as a module-level flag set during `start_scanner_thread()`.
- **`src/prom.py`** — In `PromIP.probe()`, skip calling `_ip_ping_ms.labels(...).set(latency)` when `latency == 0` and `active_only` is enabled. Note: existing label sets that were previously set will persist in the Prometheus registry; to fully remove them, call `_ip_ping_ms.remove(ip, dns_addr)` for stale entries.
- **`tests/test_ipam.py`** — Add tests for the filtered endpoints.

**Open question:** Should `active_only` also affect `/count`? Probably yes — count should reflect live hosts only.

---

### 2. Grafana dashboards

Provide pre-built Grafana dashboard JSON files for both operating modes, suitable for import into Grafana or provisioning via Grafana Alloy.

**Scope of changes:**

- **`dashboards/`** — New directory to hold dashboard JSON files.
  - `dashboards/ipam_web.json` — Dashboard for `web` mode, using the JSON/CSV data source (e.g., via the Infinity plugin or a custom Grafana data source pointed at `/data`).
  - `dashboards/ipam_prom.json` — Dashboard for `prom` mode, querying `ip_ping_ms` from Prometheus.

**Suggested panels for `ipam_prom.json`:**
- Table: all hosts with IP, DNS name, and current ping latency
- Stat: total hosts scanned / total active hosts
- Time series: ping latency over time per host (filtered by IP or DNS label)
- Gauge: percentage of hosts currently reachable

**Suggested panels for `ipam_web.json`:**
- Table: all hosts from `/data` endpoint
- Stat: host count from `/count`
- Last updated timestamp from `/health`

**Provisioning:**
- Add a `grafana/provisioning/dashboards/` directory with a provisioning YAML if Alloy-based deployment is used.
- Document import steps in the README.

---

### 3. Docker support

Containerise the app for easy deployment alongside Prometheus and Grafana.

**Scope of changes:**

- **`Dockerfile`** — Multi-stage build: install dependencies, copy source, set entrypoint to `python main.py`. Ensure the container runs as a non-root user (required for raw ICMP on some systems; may need `NET_RAW` capability or use `ping3`'s UDP fallback).
- **`docker-compose.yml`** — Compose stack with `ipam-exporter`, `prometheus`, and `grafana` services pre-wired. Mount `grafana/provisioning/` for automatic dashboard and datasource setup.
- **`.dockerignore`** — Exclude `venv/`, `.env`, `__pycache__/`, etc.
- **README** — Add a Docker usage section.

**Note:** `ping3` requires either root or `NET_RAW` capability for ICMP. The Dockerfile should document this and set `CAP_ADD: NET_RAW` in the compose file.

---

### 4. State change detection and webhook notifications

Track when a host transitions between up and down, log the event, and optionally fire a webhook.

**Scope of changes:**

- **`src/web_csv.py`** — Maintain a `STATE: dict[str, bool]` map alongside `CACHE`. After each `scan_once()`, compare new results to previous state. Emit `logger.info()` events for any transitions. Store first-seen and last-seen timestamps per host.
- **`src/settings.py`** — Add optional `webhook_url: str = ""` field.
- **`main.py`** — Add `--webhook` CLI arg and `WEBHOOK_URL` env var.
- **`src/web_csv.py`** (webhook) — On state change, POST a JSON payload to `webhook_url` in a fire-and-forget thread (use `requests` or `urllib`). Payload should include `ip`, `dns`, `state` (`up`/`down`), and `timestamp`.
- **`requirements.txt`** — Add `requests` if using it for webhook delivery.

**Webhook payload example:**
```json
{"ip": "192.168.1.10", "dns": "host.local.", "state": "down", "timestamp": 1710000000}
```

---

### 5. Forward DNS lookup and consistency checking

Currently only reverse PTR lookups are performed. Adding forward A/AAAA lookups enables DNS consistency validation.

**Scope of changes:**

- **`src/web_csv.py`** and **`src/prom.py`** — In the probe function, after resolving the PTR record, perform a forward A lookup on the returned hostname and compare the result to the original IP. Add a `dns_consistent: bool` field to the result dict.
- **`src/prom.py`** — Add a `ip_dns_consistent{ip, dns}` Gauge (1 = consistent, 0 = inconsistent or unresolvable).
- **`src/web_csv.py`** — Include `dns_consistent` in JSON, CSV, and download responses.

**Failure cases to handle:**
- PTR resolves but forward A does not resolve → inconsistent
- PTR resolves and forward A resolves but to a different IP → inconsistent
- No PTR record → skip consistency check (already recorded as `dns = ""`)

---

### 6. MAC address / ARP resolution

For hosts on directly connected subnets, resolve MAC addresses via ARP to enable vendor identification and rogue device detection.

**Scope of changes:**

- **`requirements.txt`** — Add `scapy` (for ARP) or use the system ARP cache via `subprocess` (no extra dependency, but less portable).
- **`src/web_csv.py`** / **`src/prom.py`** — Add `mac` and `vendor` fields to probe results. Use the ARP cache (`arp -n` output or `scapy`'s `ARP` layer) to resolve MAC. Look up OUI prefix against an IEEE OUI database for vendor name.
- **`src/prom.py`** — Add `ip_mac_info{ip, mac, vendor}` Info metric.

**Limitations:** ARP only works for hosts on the same Layer 2 segment. Hosts behind a router will show the router's MAC. This should be documented.

---

### 7. External IPAM source integration

Pull network ranges dynamically from an external IPAM system instead of requiring static CLI args. Networks would refresh periodically without restarting the exporter.

**Scope of changes:**

- **`src/settings.py`** — Add `ipam_source: str = ""` (e.g., `netbox`, `phpipam`) and `ipam_url`, `ipam_token` fields.
- **`src/ipam_sources/`** — New directory with a plugin per source:
  - `netbox.py` — Query NetBox `/api/ipam/prefixes/` for active prefixes.
  - `phpipam.py` — Query phpIPAM API for subnets.
- **`src/web_csv.py`** / **`src/prom.py`** — Refresh the IP list from the source at each scan interval instead of computing it once at startup from `settings.networks`.
- **`main.py`** — Add `--ipam-source`, `--ipam-url`, `--ipam-token` args.
- **`requirements.txt`** — Add `requests`.

---

### 8. Web endpoint authentication

Protect the web endpoints with a static API key to prevent exposing network topology data.

**Scope of changes:**

- **`src/settings.py`** — Add `api_key: str = ""` field.
- **`main.py`** — Add `--api-key` CLI arg and `API_KEY` env var.
- **`src/web_csv.py`** — Add a Flask `before_request` hook that checks for an `Authorization: Bearer <key>` header (or `X-API-Key`) when `api_key` is set. Return `401` if missing or incorrect. The `/health` endpoint could be exempted to allow liveness probes.
- **`tests/test_ipam.py`** — Add tests for authenticated and unauthenticated requests.

---

### 9. CI/CD pipeline (GitHub Actions)

Automate testing, linting, Docker image builds, and releases via GitHub Actions.

**Workflows:**

#### `.github/workflows/test.yml` — Run on every push and pull request
- Trigger: `push` and `pull_request` on all branches.
- Steps:
  1. Checkout code.
  2. Set up Python (matrix over supported versions, e.g. 3.11, 3.12, 3.13).
  3. Install dependencies: `pip install -r requirements.txt pytest`.
  4. Run tests: `pytest tests/ -v`.

#### `.github/workflows/lint.yml` — Run on every push and pull request
- Trigger: `push` and `pull_request` on all branches.
- Steps:
  1. Checkout code.
  2. Set up Python.
  3. Install linting tools: `pip install ruff`.
  4. Run linter: `ruff check src/ tests/ main.py`.

#### `.github/workflows/docker.yml` — Build and push Docker image on release
- Trigger: `push` to `main` branch and on published GitHub Releases.
- Steps:
  1. Checkout code.
  2. Log in to GitHub Container Registry (`ghcr.io`) using `GITHUB_TOKEN`.
  3. Extract metadata (tags, labels) using `docker/metadata-action`.
     - Tag `latest` on `main` branch pushes.
     - Tag `vX.Y.Z` on release publishes.
  4. Build and push image using `docker/build-push-action`.
  5. Inject build version: pass `--build-arg BUILD=${{ github.sha }}` (or release tag) into the Dockerfile so `ipam_build_version` metric reflects the actual build.

#### `.github/workflows/release.yml` — Create GitHub Release on version tag
- Trigger: `push` of tags matching `v*.*.*`.
- Steps:
  1. Checkout code.
  2. Run tests (reuse test workflow).
  3. Create a GitHub Release using `softprops/action-gh-release` with auto-generated changelog from commit messages.

**Supporting changes:**

- **`Dockerfile`** — Accept `BUILD` as a build arg (`ARG BUILD=dev`) and pass it as an environment variable so `main.py` can read `os.environ.get("BUILD", "dev")` instead of the hardcoded `"XXXXXXXX"`.
- **`README.md`** — Add badges: build status, latest Docker image tag, Python version support.
- **`.github/`** — Add `dependabot.yml` to keep Actions versions and `pip` dependencies up to date automatically.
