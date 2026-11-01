import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from oktodesk.api_client import (
    ServiceUnavailableError, Vulnerability, VulnerabilityReport, VulnerabilityServiceError,
)


@dataclass(frozen=True)
class SweepResult:
    # one slot per product: report when the check succeeded, error when it failed
    product: str
    report: VulnerabilityReport = None
    error: VulnerabilityServiceError = None


def load_simulated_cves(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {product: record for product, record in data.items() if not product.startswith("_")}


def _simulated_record(simulated, product):
    record = simulated.get(product.lower())
    if record is None:
        # no simulated data is "we don't know", never "no vulnerabilities"
        raise ServiceUnavailableError(f"[SIMULATED] no simulated data for {product!r}",
                                      product=product)
    return record


def _simulated_report(record, product, now):
    if record.get("fail"):
        raise ServiceUnavailableError(f"[SIMULATED] service unavailable for {product!r}",
                                      product=product)
    vulnerabilities = tuple(
        Vulnerability(item["cve_id"], item["severity"], float(item["score"]),
                      datetime.fromisoformat(item["published"]))
        for item in record["vulnerabilities"]
    )
    checked_at = now if now is not None else datetime.now(timezone.utc)
    return VulnerabilityReport(product, len(vulnerabilities), vulnerabilities, checked_at)


def make_simulated_fetch(simulated, delay_scale=1.0, now=None):
    # SIMULATED: local data and asyncio.sleep stand in for the network; this does not replace NvdClient
    async def fetch(product):
        record = _simulated_record(simulated, product)
        await asyncio.sleep(record["delay_seconds"] * delay_scale)
        return _simulated_report(record, product, now)
    return fetch


class SimulatedVulnerabilityClient:
    # SIMULATED: the same data and rules as the sweep, for the check made when a ticket opens;
    # it answers like NvdClient so the service doesn't know which one it got. No event loop
    # and no waiting: it is a regular call, safe to use from sync or async code
    def __init__(self, simulated, now=None):
        self._simulated = simulated
        self._now = now

    def find_recent_critical(self, product, now=None):
        record = _simulated_record(self._simulated, product)
        return _simulated_report(record, product, now if now is not None else self._now)


async def _check_product(product, fetch):
    # one failed product becomes an "unknown" result in its own slot; the others still count
    try:
        return SweepResult(product, report=await fetch(product))
    except VulnerabilityServiceError as error:
        return SweepResult(product, error=error)


async def collect_reports_sequential(products, fetch):
    results = []
    for product in products:
        results.append(await _check_product(product, fetch))
    return results


async def collect_reports_concurrent(products, fetch):
    tasks = [asyncio.create_task(_check_product(product, fetch)) for product in products]
    # gather returns results in the order the tasks were given, not the order they finish
    return list(await asyncio.gather(*tasks))
