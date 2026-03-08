import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

from prometheus_client import Info
from src import __version__, Settings, logger, ipam_prom, ipam_web

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        add_help=True,
        description="IPAM Exporter is a Prometheus Exporter for IPAM data.",
    )

    parser.add_argument("--networks", type=str, help="Comma-separated list of networks to scan.")
    parser.add_argument("--debug", action="store_true", help="Activate debug mode.")
    parser.add_argument("--host", type=str, help="Interface address to listen on.")
    parser.add_argument("--port", type=int, help="Port to listen for HTTP traffic.")
    parser.add_argument(
        "--interval", type=int, help="Interval between data collection jobs."
    )
    parser.add_argument(
        "--log_level", type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level, default: INFO.",
    )
    parser.add_argument(
        "--mode", type=str,
        choices=["prom", "web"],
        help="Mode of operation, default: web.",
    )

    args = parser.parse_args()
    load_dotenv()

    settings = Settings()
    settings.networks = args.networks or os.environ.get("NETWORKS")
    settings.loglevel = args.log_level or os.environ.get("LOGLEVEL") or settings.loglevel
    settings.port = args.port or os.environ.get("PORT") or settings.port
    settings.interval = args.interval or os.environ.get("INTERVAL") or settings.interval
    settings.listening_host = args.host or os.environ.get("HOST", settings.listening_host)
    settings.debug = bool(args.debug) or bool(os.environ.get("DEBUG")) or settings.debug
    settings.mode = args.mode or os.environ.get("MODE") or settings.mode

    if not settings.networks:
        logger.error("No networks specified. Use --networks or set the NETWORKS environment variable.")
        sys.exit(1)

    logger.setLevel(settings.loglevel.upper())

    # Set the version of the exporter. Build version supplied by CI pipeline.
    i = Info("ipam_build_version", "Prometheus IPAM Exporter build version")
    i.info({"version": __version__, "build": "XXXXXXXX"})

    logger.info("IPAM Exporter starting.")
    exit_code = 0
    try:
        if settings.mode == "prom":
            ipam_prom(settings)
        elif settings.mode == "web":
            ipam_web(settings)
        else:
            raise Exception("No mode selected.")
    except (OSError, PermissionError) as e:
        logger.error(f"Failed to start server: {e}")
        exit_code = 1
    except KeyboardInterrupt:
        logger.info("IPAM exporter was interrupted.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        exit_code = 1
    finally:
        sys.exit(exit_code)
