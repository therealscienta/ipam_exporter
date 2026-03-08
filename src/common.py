import logging
import ipaddress

# Set up a logger
logger = logging.getLogger("matey_exporter")

# Set up a stream handler to log to the console
stream_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
stream_handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(stream_handler)


def get_addresses(networks: list[str]) -> set:
    def _validate_network(network: str) -> bool:
        """Validate a list of network/host strings."""
        try:
            ipaddress.ip_network(network, strict=False)
        except ValueError:
            logger.error(f"Invalid network/host: {network}")
            return False
        return True

    ips = set()
    for net in networks:
        if not _validate_network(net): continue

        network = ipaddress.ip_network(net, strict=False)
        if network.prefixlen == 32: 
            ips.add(network.network_address)
        else:
            for ip in network.hosts(): ips.add(ip)
    return ips