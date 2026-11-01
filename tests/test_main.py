import asyncio
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
            inside_event_loop.append(_event_loop_running())
            return VulnerabilityReport(product, 0, (), NOW)

    monkeypatch.setattr(main, "NvdClient", FakeNvdClient)
    return requested


def _event_loop_running():
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


inside_event_loop = []


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


# R5.1 - the gather results reach the service: ticket #16 (Chrome, LOW) becomes HIGH and moves up
def test_async_sweep_updates_tickets_and_reorders_the_queue(demo, capsys):
    main.main([])
    sweep = capsys.readouterr().out.split("sequential vs gather [SIMULATED] ===")[1]
    before = sweep.split("Queue before the sweep: ")[1].splitlines()[0]
    after = sweep.split("Queue after the sweep: ")[1].splitlines()[0]
    assert before.endswith("'#16 LOW']")
    assert "'#1 HIGH', '#16 HIGH', '#10 MEDIUM'" in after
    assert "#2   FortiClient  unknown" in sweep


# R5.5 - the real client blocks on HTTP and retry waits, so it never runs inside an event loop
def test_live_client_is_never_called_inside_an_event_loop(demo, capsys):
    inside_event_loop.clear()
    main.main(["--live"])
    assert len(inside_event_loop) == 4
    assert not any(inside_event_loop)
