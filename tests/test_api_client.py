from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
import requests

from oktodesk.api_client import (
    InvalidServiceDataError, MalformedJSONError, NvdClient, UnexpectedStructureError, ServiceHTTPError, ServiceUnavailableError,
    Vulnerability, VulnerabilityReport, VulnerabilityServiceError,
)
from oktodesk.config import NVD_CVE_URL, NvdConfig

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def nvd_cve(cve_id="CVE-2026-1111", score=9.8, severity="CRITICAL",
            published="2026-10-01T10:15:00.000"):
    return {"cve": {
        "id": cve_id,
        "published": published,
        "metrics": {"cvssMetricV31": [
            {"cvssData": {"baseScore": score, "baseSeverity": severity}},
        ]},
    }}


def nvd_payload(*cves):
    return {"resultsPerPage": len(cves), "startIndex": 0, "totalResults": len(cves),
            "vulnerabilities": list(cves)}


def ok_response(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def http_error_response(status_code):
    response = Mock(status_code=status_code)
    response.raise_for_status.side_effect = requests.HTTPError(
        f"{status_code} error", response=response)
    return response


@pytest.fixture
def config():
    return NvdConfig()


@pytest.fixture
def sleep():
    return Mock()


def make_client(session, sleep, config):
    return NvdClient(session=session, sleep=sleep, config=config)


# T20
def test_valid_response_becomes_report_and_request_has_params_and_timeout(config, sleep):
    session = Mock()
    session.get.return_value = ok_response(nvd_payload(
        nvd_cve("CVE-2026-1111", 9.8), nvd_cve("CVE-2026-2222", 9.1)))

    report = make_client(session, sleep, config).find_recent_critical("chrome", now=NOW)

    assert report == VulnerabilityReport(
        product="chrome", total=2, checked_at=NOW, vulnerabilities=(
            Vulnerability("CVE-2026-1111", "CRITICAL", 9.8, datetime(2026, 10, 1, 10, 15)),
            Vulnerability("CVE-2026-2222", "CRITICAL", 9.1, datetime(2026, 10, 1, 10, 15)),
        ))
    assert report.is_vulnerable
    session.get.assert_called_once_with(
        NVD_CVE_URL,
        params={
            "keywordSearch": "chrome",
            "cvssV3Severity": "CRITICAL",
            "pubStartDate": "2026-07-31T12:00:00.000",
            "pubEndDate": "2026-10-29T12:00:00.000",
            "resultsPerPage": 20,
        },
        headers={},
        timeout=10.0,
    )
    sleep.assert_not_called()


def test_no_results_is_a_clear_report(config, sleep):
    session = Mock()
    session.get.return_value = ok_response(nvd_payload())
    report = make_client(session, sleep, config).find_recent_critical("zoom", now=NOW)
    assert report.total == 0
    assert report.vulnerabilities == ()
    assert not report.is_vulnerable


def test_api_key_is_sent_as_header_only_when_set(sleep):
    session = Mock()
    session.get.return_value = ok_response(nvd_payload())
    make_client(session, sleep, NvdConfig(api_key="secret-123")).find_recent_critical("zoom", now=NOW)
    assert session.get.call_args.kwargs["headers"] == {"apiKey": "secret-123"}


# T21
def test_timeout_on_every_attempt_ends_in_service_unavailable(config, sleep):
    session = Mock()
    session.get.side_effect = requests.Timeout("read timed out")
    with pytest.raises(ServiceUnavailableError, match="after 3 attempts"):
        make_client(session, sleep, config).find_recent_critical("chrome", now=NOW)
    assert session.get.call_count == 3


# T22
@pytest.mark.parametrize("status_code", [500, 503, 401, 403])
def test_http_error_raises_service_http_error_and_is_tried_once(config, sleep, status_code):
    session = Mock()
    session.get.return_value = http_error_response(status_code)
    with pytest.raises(ServiceHTTPError) as raised:
        make_client(session, sleep, config).find_recent_critical("chrome", now=NOW)
    assert raised.value.status_code == status_code
    assert session.get.call_count == 1
    sleep.assert_not_called()


# T23
@pytest.mark.parametrize("payload", [
    {"vulnerabilities": []},                                  # no totalResults
    {"totalResults": 1},                                      # no vulnerabilities list
    {"totalResults": "many", "vulnerabilities": []},          # wrong type
    nvd_payload({"cve": {"published": "2026-10-01T10:15:00.000", "metrics": {}}}),  # no id
    nvd_payload({"cve": {"id": "CVE-2026-1", "published": "2026-10-01T10:15:00.000",
                         "metrics": {}}}),                    # no CVSS score
    nvd_payload(nvd_cve(score=42)),                           # impossible score
    [],                                                       # not an object
])
def test_bad_structure_raises_invalid_data_and_is_not_retried(config, sleep, payload):
    session = Mock()
    session.get.return_value = ok_response(payload)
    with pytest.raises(UnexpectedStructureError):
        make_client(session, sleep, config).find_recent_critical("chrome", now=NOW)
    assert session.get.call_count == 1
    sleep.assert_not_called()


# T24
def test_malformed_json_raises_invalid_data(config, sleep):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)
    session = Mock()
    session.get.return_value = response
    with pytest.raises(MalformedJSONError, match="not valid JSON"):
        make_client(session, sleep, config).find_recent_critical("chrome", now=NOW)
    assert session.get.call_count == 1


# T25
def test_timeout_timeout_then_success_returns_data_after_3_calls_and_2_waits(config, sleep):
    session = Mock()
    session.get.side_effect = [
        requests.Timeout("slow"),
        requests.Timeout("slow"),
        ok_response(nvd_payload(nvd_cve("CVE-2026-1111"))),
    ]
    report = make_client(session, sleep, config).find_recent_critical("chrome", now=NOW)
    assert report.total == 1
    assert session.get.call_count == 3
    assert sleep.call_count == 2
    sleep.assert_called_with(config.retry_wait_seconds)


# T26
def test_three_connection_errors_stop_after_exactly_three_calls(config, sleep):
    session = Mock()
    session.get.side_effect = requests.ConnectionError("no route to host")
    with pytest.raises(ServiceUnavailableError):
        make_client(session, sleep, config).find_recent_critical("chrome", now=NOW)
    assert session.get.call_count == 3
    assert sleep.call_count == 2


@pytest.mark.parametrize("session_result, error_cls", [
    (requests.Timeout("slow"), ServiceUnavailableError),
    (http_error_response(503), ServiceHTTPError),
    (ok_response({"totalResults": 1}), UnexpectedStructureError),
])
def test_every_failure_names_its_product(config, sleep, session_result, error_cls):
    session = Mock()
    if isinstance(session_result, Exception):
        session.get.side_effect = session_result
    else:
        session.get.return_value = session_result
    with pytest.raises(error_cls) as raised:
        make_client(session, sleep, config).find_recent_critical("zoom", now=NOW)
    assert raised.value.product == "zoom"


def test_every_service_error_shares_one_base_class():
    for error_cls in (ServiceUnavailableError, ServiceHTTPError, InvalidServiceDataError):
        assert issubclass(error_cls, VulnerabilityServiceError)


def test_malformed_json_and_wrong_structure_are_different_errors():
    assert issubclass(MalformedJSONError, InvalidServiceDataError)
    assert issubclass(UnexpectedStructureError, InvalidServiceDataError)
    assert not issubclass(MalformedJSONError, UnexpectedStructureError)
    assert not issubclass(UnexpectedStructureError, MalformedJSONError)


def test_api_key_never_appears_in_logs(sleep, caplog):
    session = Mock()
    session.get.side_effect = requests.Timeout("slow")
    config = NvdConfig(api_key="secret-123")
    with caplog.at_level("DEBUG"), pytest.raises(ServiceUnavailableError):
        make_client(session, sleep, config).find_recent_critical("chrome", now=NOW)
    assert caplog.records
    assert "secret-123" not in caplog.text
    assert "secret-123" not in repr(config)


def test_config_reads_environment_and_defaults():
    config = NvdConfig.from_env({
        "NVD_API_KEY": "abc", "OKTODESK_LIVE": "true",
        "OKTODESK_NVD_TIMEOUT": "5", "OKTODESK_NVD_ATTEMPTS": "2",
    })
    assert config.api_key == "abc"
    assert config.live is True
    assert config.timeout_seconds == 5.0
    assert config.max_attempts == 2
    assert config.lookback_days == 90
    assert NvdConfig.from_env({}) == NvdConfig()
