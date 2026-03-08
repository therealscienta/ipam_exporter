import time
import random
import asyncio

from ping3 import ping
import dns.resolver
import dns.reversename
import dns.exception
from prometheus_client import Gauge, Summary, start_http_server

from src.common import logger, get_addresses


_ip_ping_ms = Gauge(
    "ip_ping_ms",
    "IP ping latency",
    labelnames=["ip", "dns"]
)


class PromIP:
    def __init__(self, ip) -> None:
        self.ip = ip

    def probe(self) -> None:
        ip = str(self.ip)
        rev = dns.reversename.from_address(ip)

        latency = ping(ip, timeout=0.2, unit="ms") or 0
        try:
            ans = dns.resolver.resolve(rev, "PTR", lifetime=0.2)
            dns_addr = str(ans[0])
        except dns.exception.DNSException:
            dns_addr = ""

        _ip_ping_ms.labels(ip, dns_addr).set(latency)


async def async_start_ipam_exporter(prom_ips: set, interval: int) -> None:
    """Main async loop: probe all hosts concurrently on each interval."""

    jitter = 0.15
    ipam_exporter_time_seconds = Summary(
        "ipam_exporter_time_seconds",
        "Latency for ipam exporter to complete query",
        labelnames=["job"],
    )
    while True:
        try:
            start_time = time.time()
            await_tasks = set()

            for ip in prom_ips:
                await_tasks.add(asyncio.to_thread(ip.probe))

            await asyncio.gather(*await_tasks)

            ipam_exporter_time_seconds.labels("ipam_exporter").observe(
                time.time() - start_time
            )
        except Exception as e:
            logger.error(e)

        wait = interval * random.uniform(1 - jitter, 1 + jitter)
        await asyncio.sleep(wait)


def start_ipam_exporter(settings) -> None:
    """Start ipam exporter main data collection loop"""

    ips = get_addresses(settings.networks)
    prom_ips = set(PromIP(ip) for ip in ips)

    logger.info(f"Loaded sources: {len(prom_ips)}")
    start_http_server(settings.port)
    asyncio.run(async_start_ipam_exporter(prom_ips=prom_ips, interval=settings.interval))
