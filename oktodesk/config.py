import os
from dataclasses import dataclass

NVD_CVE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _env_flag(value):
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class NvdConfig:
    base_url: str = NVD_CVE_URL
    timeout_seconds: float = 10.0
    max_attempts: int = 3
    retry_wait_seconds: float = 2.0
    lookback_days: int = 90
    results_per_page: int = 20
    api_key: str | None = None
    live: bool = False

    @classmethod
    def from_env(cls, environ=None):
        environ = os.environ if environ is None else environ
        defaults = cls()
        return cls(
            base_url=environ.get("OKTODESK_NVD_URL", defaults.base_url),
            timeout_seconds=float(environ.get("OKTODESK_NVD_TIMEOUT", defaults.timeout_seconds)),
            max_attempts=int(environ.get("OKTODESK_NVD_ATTEMPTS", defaults.max_attempts)),
            retry_wait_seconds=float(environ.get("OKTODESK_NVD_RETRY_WAIT", defaults.retry_wait_seconds)),
            lookback_days=int(environ.get("OKTODESK_NVD_LOOKBACK_DAYS", defaults.lookback_days)),
            results_per_page=int(environ.get("OKTODESK_NVD_RESULTS_PER_PAGE", defaults.results_per_page)),
            api_key=environ.get("NVD_API_KEY") or None,
            live=_env_flag(environ.get("OKTODESK_LIVE")),
        )

    def __repr__(self):
        # the key is a secret: never let it reach a log line or a traceback
        key = "set" if self.api_key else None
        return (
            f"NvdConfig(base_url={self.base_url!r}, timeout_seconds={self.timeout_seconds!r}, "
            f"max_attempts={self.max_attempts!r}, retry_wait_seconds={self.retry_wait_seconds!r}, "
            f"lookback_days={self.lookback_days!r}, results_per_page={self.results_per_page!r}, "
            f"api_key={key!r}, live={self.live!r})"
        )
