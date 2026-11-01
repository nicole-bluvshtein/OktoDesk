from datetime import datetime, timezone
from pathlib import Path

import pytest

import main
from oktodesk.api_client import VulnerabilityReport

REPO_ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def demo(monkeypatch):
    # the demo reads data/ and writes output/ relative to the repository root
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.delenv("OKTODESK_LIVE", raising=False)
    requested = []

    class FakeNvdClient:
        def __init__(self, session, sleep, config):
            pass

        def find_recent_critical(self, product, now=None):
            requested.append(product)
            return VulnerabilityReport(product, 0, (), NOW)

    monkeypatch.setattr(main, "NvdClient", FakeNvdClient)
    return requested


def vulnerability_lines(output):
    section = output.split("=== Stage 2: vulnerability check")[1].split("\n=== ")[0]
    return section.strip().splitlines()[1:]


# R7.2, R7.4
def test_default_run_is_simulated_and_never_builds_the_real_client(demo, capsys):
    main.main([])
    output = capsys.readouterr().out
    assert demo == []
    assert "[LIVE]" not in output
    lines = vulnerability_lines(output)
    assert lines
    assert all(line.startswith("[SIMULATED]") for line in lines)


# R7.3, R7.4
@pytest.mark.parametrize("argv, env", [(["--live"], None), ([], "true")])
def test_live_run_labels_the_check_live_and_keeps_the_sweep_simulated(demo, capsys, monkeypatch,
                                                                     argv, env):
    if env is not None:
        monkeypatch.setenv("OKTODESK_LIVE", env)
    main.main(argv)
    output = capsys.readouterr().out
    assert all(line.startswith("[LIVE]") for line in vulnerability_lines(output))
    sweep = output.split("sequential vs gather [SIMULATED] ===")[1].split("\n=== ")[0]
    assert all(line.startswith("[SIMULATED]") for line in sweep.strip().splitlines())
    # one request per product; the new Chrome ticket reuses this run's result
    assert sorted(demo) == ["Chrome", "FortiClient", "Outlook", "Zoom"]
