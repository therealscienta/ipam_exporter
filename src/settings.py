import logging

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class Settings:
    def __init__(self):
        self._networks: set = set()
        self._loglevel: str = 'INFO'
        self._port: int = 8000
        self._interval: int = 30
        self.listening_host: str = '0.0.0.0'
        self.debug: bool = False
        self.mode: str = 'web'

    @property
    def networks(self):
        return self._networks

    @networks.setter
    def networks(self, value):
        if not value:
            return
        self._networks = set(item.strip() for item in value.split(','))

    @property
    def loglevel(self):
        return self._loglevel

    @loglevel.setter
    def loglevel(self, value):
        upper = value.upper()
        if upper not in VALID_LOG_LEVELS:
            raise ValueError(f"Invalid log level: {value!r}. Must be one of {sorted(VALID_LOG_LEVELS)}")
        self._loglevel = upper

    @property
    def port(self):
        return self._port

    @port.setter
    def port(self, port):
        try:
            self._port = int(port)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid port: {port!r}")

    @property
    def interval(self):
        return self._interval

    @interval.setter
    def interval(self, interval):
        try:
            self._interval = int(interval)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid interval: {interval!r}")
