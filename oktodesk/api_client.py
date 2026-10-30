import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

_NVD_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.000"


class VulnerabilityServiceError(Exception):
    def __init__(self, message, product=None):
        super().__init__(message)
        self.product = product


class ServiceUnavailableError(VulnerabilityServiceError):
    pass


class ServiceHTTPError(VulnerabilityServiceError):
    def __init__(self, message, status_code, product=None):
        super().__init__(message, product)
        self.status_code = status_code


class InvalidServiceDataError(VulnerabilityServiceError):
    pass


@dataclass(frozen=True)
class Vulnerability:
    cve_id: str
    severity: str
    score: float
    published: datetime


@dataclass(frozen=True)
class VulnerabilityReport:
    product: str
    total: int
    vulnerabilities: tuple
    checked_at: datetime

    @property
    def is_vulnerable(self):
        return self.total > 0


class NvdClient:
    def __init__(self, session, sleep, config):
        self.session = session
        self.sleep = sleep
        self.config = config

    def find_recent_critical(self, product, now=None):
        now = now if now is not None else datetime.now(timezone.utc)
        try:
            response = self._get_with_retry(product, self._query_params(product, now))
            return self._parse_report(product, self._decode_json(response), now)
        except VulnerabilityServiceError as error:
            # every failure names its product, so a sweep can mark the right tickets "unknown"
            error.product = product
            raise

    def _query_params(self, product, now):
        start = now - timedelta(days=self.config.lookback_days)
        return {
            "keywordSearch": product,
            "cvssV3Severity": "CRITICAL",
            "pubStartDate": start.strftime(_NVD_DATE_FORMAT),
            "pubEndDate": now.strftime(_NVD_DATE_FORMAT),
            "resultsPerPage": self.config.results_per_page,
        }

    def _headers(self):
        return {"apiKey": self.config.api_key} if self.config.api_key else {}

    def _get_with_retry(self, product, params):
        attempts = self.config.max_attempts
        for attempt in range(1, attempts + 1):
            logger.info("NVD request for %r, attempt %d of %d", product, attempt, attempts)
            try:
                response = self.session.get(
                    self.config.base_url, params=params, headers=self._headers(),
                    timeout=self.config.timeout_seconds,
                )
                response.raise_for_status()
                return response
            except requests.HTTPError as error:
                # 401/403 (NVD also uses 403 for a bad key or a rate limit) and 5xx: not retried
                status = error.response.status_code if error.response is not None else None
                logger.error("NVD returned HTTP %s for %r, not retrying", status, product)
                raise ServiceHTTPError(f"NVD returned HTTP {status} for {product!r}", status) from error
            except (requests.Timeout, requests.ConnectionError) as error:
                logger.warning("NVD attempt %d of %d for %r failed: %s",
                               attempt, attempts, product, type(error).__name__)
                if attempt == attempts:
                    raise ServiceUnavailableError(
                        f"NVD unreachable for {product!r} after {attempts} attempts"
                    ) from error
                self.sleep(self.config.retry_wait_seconds)

    @staticmethod
    def _decode_json(response):
        try:
            return response.json()
        except ValueError as error:
            logger.error("NVD response was not valid JSON")
            raise InvalidServiceDataError("NVD response was not valid JSON") from error

    def _parse_report(self, product, payload, now):
        if not isinstance(payload, dict):
            raise InvalidServiceDataError("NVD response is not a JSON object")
        total = payload.get("totalResults")
        items = payload.get("vulnerabilities")
        if not isinstance(total, int) or total < 0:
            raise InvalidServiceDataError("NVD response has no valid 'totalResults'")
        if not isinstance(items, list):
            raise InvalidServiceDataError("NVD response has no 'vulnerabilities' list")
        vulnerabilities = tuple(self._parse_vulnerability(item) for item in items)
        logger.info("NVD found %d critical CVE(s) for %r", total, product)
        return VulnerabilityReport(product, total, vulnerabilities, now)

    @staticmethod
    def _parse_vulnerability(item):
        try:
            cve = item["cve"]
            cve_id = cve["id"]
            metrics = cve["metrics"]
            cvss = (metrics.get("cvssMetricV31") or metrics.get("cvssMetricV30"))[0]["cvssData"]
            severity = cvss["baseSeverity"]
            score = float(cvss["baseScore"])
            published = datetime.fromisoformat(cve["published"])
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise InvalidServiceDataError(f"NVD CVE record is missing a required field: {error}") from error
        if not isinstance(cve_id, str) or not cve_id.startswith("CVE-"):
            raise InvalidServiceDataError(f"NVD CVE record has an invalid id: {cve_id!r}")
        if not 0.0 <= score <= 10.0:
            raise InvalidServiceDataError(f"{cve_id} has an out-of-range score: {score}")
        return Vulnerability(cve_id, severity, score, published)
