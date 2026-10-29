import asyncio
import json
from datetime import datetime, timezone

import pytest

from oktodesk.api_client import ServiceUnavailableError, VulnerabilityReport
from oktodesk.async_processing import (
    collect_reports_concurrent, collect_reports_sequential, load_simulated_cves,
    make_simulated_fetch,
)

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
PRODUCTS = ["chrome", "outlook", "zoom"]

SIMULATED = {
    "chrome": {"delay_seconds": 0.03, "vulnerabilities": [
        {"cve_id": "CVE-SIM-0001", "severity": "CRITICAL", "score": 9.8,
         "published": "2026-10-02T09:00:00"},
    ]},
    "outlook": {"delay_seconds": 0.01, "vulnerabilities": []},
    "zoom": {"delay_seconds": 0.02, "vulnerabilities": [
        {"cve_id": "CVE-SIM-0003", "severity": "CRITICAL", "score": 9.6,
         "published": "2026-08-20T11:00:00"},
    ]},
    "vpn client": {"delay_seconds": 0.0, "fail": True, "vulnerabilities": []},
}


def tracked_fetch(events):
    inner = make_simulated_fetch(SIMULATED, now=NOW)

    async def fetch(product):
        events.append(("start", product))
        report = await inner(product)
        events.append(("end", product))
        return report
    return fetch


# T29
def test_sequential_and_concurrent_match_in_input_order_though_finish_order_differs():
    sequential_events, concurrent_events = [], []

    sequential = asyncio.run(collect_reports_sequential(PRODUCTS, tracked_fetch(sequential_events)))
    concurrent = asyncio.run(collect_reports_concurrent(PRODUCTS, tracked_fetch(concurrent_events)))

    assert concurrent == sequential
    assert [report.product for report in concurrent] == PRODUCTS
    assert [report.total for report in concurrent] == [1, 0, 1]
    finish_order = [product for kind, product in concurrent_events if kind == "end"]
    assert finish_order == ["outlook", "zoom", "chrome"]


def test_concurrent_schedules_every_check_before_any_finishes():
    events = []
    asyncio.run(collect_reports_concurrent(PRODUCTS, tracked_fetch(events)))
    assert events[:3] == [("start", product) for product in PRODUCTS]


def test_sequential_waits_for_each_check_before_the_next():
    events = []
    asyncio.run(collect_reports_sequential(PRODUCTS, tracked_fetch(events)))
    assert events == [(kind, product) for product in PRODUCTS for kind in ("start", "end")]


# T30
@pytest.mark.parametrize("collect", [collect_reports_sequential, collect_reports_concurrent])
def test_exactly_one_result_per_product(collect):
    products = ["chrome", "outlook", "zoom", "teams"]
    results = asyncio.run(collect(products, make_simulated_fetch(SIMULATED, now=NOW)))
    assert len(results) == len(products)
    assert all(isinstance(result, VulnerabilityReport) for result in results)
    assert results[3].total == 0


@pytest.mark.parametrize("collect", [collect_reports_sequential, collect_reports_concurrent])
def test_one_failed_product_keeps_the_other_reports(collect):
    products = ["chrome", "vpn client", "zoom"]
    results = asyncio.run(collect(products, make_simulated_fetch(SIMULATED, now=NOW)))
    assert isinstance(results[1], ServiceUnavailableError)
    assert "[SIMULATED]" in str(results[1])
    assert [results[0].product, results[2].product] == ["chrome", "zoom"]


def test_unexpected_bug_is_not_hidden_as_unknown():
    async def broken_fetch(product):
        raise KeyError("bug in fetch")
    with pytest.raises(KeyError):
        asyncio.run(collect_reports_concurrent(PRODUCTS, broken_fetch))


def test_simulated_file_loads_and_skips_the_note(tmp_path):
    path = tmp_path / "simulated.json"
    path.write_text(json.dumps({"_note": "simulated", **SIMULATED}), encoding="utf-8")
    loaded = load_simulated_cves(path)
    assert set(loaded) == set(SIMULATED)


def test_shipped_simulated_data_uses_only_fake_ids():
    data = load_simulated_cves("data/simulated_cves.json")
    ids = [item["cve_id"] for record in data.values() for item in record["vulnerabilities"]]
    assert ids
    assert all(cve_id.startswith("CVE-SIM-") for cve_id in ids)
