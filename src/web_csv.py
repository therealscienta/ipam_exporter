import io
import csv
import json
import time
import random
import asyncio
import threading

from typing import List, Any, Tuple
from flask import Flask, jsonify, Response
from ping3 import ping
import dns.resolver, dns.reversename, dns.exception

from src.common import logger, get_addresses

# --- Global cache (starts as empty list) ---
CACHE: List[dict] = []           # latest snapshot
LAST_UPDATED: float = 0.0        # epoch seconds
_CACHE_LOCK = threading.Lock()   # guard reads/writes


def get_cached_snapshot() -> Tuple[List[dict], float]:
    """Return a copy of the latest cache + timestamp without triggering any rescan."""
    with _CACHE_LOCK:
        data = list(CACHE)
        ts = LAST_UPDATED
    return data, ts


# --- Blocking worker for one host (runs in thread via asyncio.to_thread) ---
def _probe_one(ip) -> dict:
    s = str(ip)
    rev = dns.reversename.from_address(s)

    latency = ping(s, timeout=0.2, unit="ms") or 0
    try:
        ans = dns.resolver.resolve(rev, "PTR", lifetime=0.2)
        dns_addr = str(ans[0])
    except dns.exception.DNSException:
        dns_addr = ""

    return {"ip": s, "dns": dns_addr, "ms": latency}


# --- One async scan pass over all hosts ---
async def scan_once(ips: set[Any], concurrency: int = 200) -> List[dict]:
    sem = asyncio.Semaphore(concurrency)

    async def run_one(ip):
        async with sem:
            return await asyncio.to_thread(_probe_one, ip)

    tasks = [run_one(ip) for ip in ips]
    return await asyncio.gather(*tasks)


# --- Background scanner: runs forever and updates CACHE; endpoints never call it ---
async def run_scanner_forever(networks: set, interval: float = 60.0):
    global CACHE, LAST_UPDATED
    jitter: float = 0.15
    ips = get_addresses(networks)

    while True:
        t0 = time.monotonic()
        try:
            results = await scan_once(ips, concurrency=200)
            with _CACHE_LOCK:
                CACHE = results
                LAST_UPDATED = time.time()
            logger.info(f"[scan] updated {len(results)} hosts")
        except Exception as e:
            logger.error(f"[scan] error: {e}")

        elapsed = time.monotonic() - t0
        wait = max(0.0, interval - elapsed)
        wait *= random.uniform(1 - jitter, 1 + jitter)
        await asyncio.sleep(wait)


def start_scanner_thread(settings):
    """Start the async scanner in a daemon thread; Flask endpoints will NOT trigger scans."""
    def _runner():
        asyncio.run(run_scanner_forever(interval=settings.interval, networks=settings.networks))
    t = threading.Thread(target=_runner, name="scanner", daemon=True)
    t.start()


# --- Flask app: endpoints only read the cache ---
app = Flask(__name__)


@app.route("/health")
def health():
    data, ts = get_cached_snapshot()
    return {"status": "ok", "count": len(data), "last_updated": int(ts)}


@app.route("/data")
def data():
    data, _ = get_cached_snapshot()
    return jsonify(data)


@app.route("/count")
def count():
    data, _ = get_cached_snapshot()
    n = len(data) if isinstance(data, list) else 1
    return {"count": n}


@app.route("/columns")
def columns():
    data, _ = get_cached_snapshot()
    cols = list(data[0].keys()) if isinstance(data, list) and data and isinstance(data[0], dict) else []
    return {"columns": cols}


@app.route("/csv")
def csv_export():
    data, _ = get_cached_snapshot()
    buf = io.StringIO()
    if data:
        writer = csv.DictWriter(buf, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    return Response(buf.getvalue(), mimetype="text/csv")


@app.route("/download.json")
def download_json():
    data, _ = get_cached_snapshot()
    buf = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(
        buf,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=export.json"},
    )


def main(settings):
    start_scanner_thread(settings)
    app.run(
        host=settings.listening_host,
        port=settings.port,
        debug=settings.debug
    )
