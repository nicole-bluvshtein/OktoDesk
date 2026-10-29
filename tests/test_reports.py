import json
from datetime import timedelta

import pytest

from oktodesk import reports
from oktodesk.models import Priority, Status


# T12 - expected values defined by Nicole and Amit (assignment section 7.3)
def test_sla_breach_report_lists_only_overdue_tickets_by_priority(make_ticket, fixed_now):
    tickets = [
        make_ticket(21, Priority.CRITICAL, Status.OPEN, hours_ago=5),
        make_ticket(22, Priority.HIGH, Status.IN_PROGRESS, hours_ago=6),
        make_ticket(23, Priority.MEDIUM, Status.OPEN, hours_ago=3),
        make_ticket(24, Priority.LOW, Status.WAITING_INFO, hours_ago=40,
                    waiting_since=fixed_now - timedelta(hours=30)),
        make_ticket(25, Priority.HIGH, Status.CLOSED, hours_ago=10, solution="Fixed",
                    closed_at=fixed_now - timedelta(hours=8)),
        make_ticket(26, Priority.LOW, Status.OPEN, hours_ago=30),
    ]
    assert reports.sla_breach_report(tickets, fixed_now) == [
        (21, Priority.CRITICAL, 4),
        (22, Priority.HIGH, 2),
        (26, Priority.LOW, 6),
    ]


def test_same_priority_breaches_put_more_hours_over_first(make_ticket, fixed_now):
    tickets = [
        make_ticket(31, Priority.HIGH, Status.OPEN, hours_ago=6),
        make_ticket(32, Priority.HIGH, Status.OPEN, hours_ago=9),
    ]
    assert reports.sla_breach_report(tickets, fixed_now) == [
        (32, Priority.HIGH, 5),
        (31, Priority.HIGH, 2),
    ]


def test_overdue_tickets_keeps_only_overdue_ones(sample_tickets, fixed_now):
    overdue = reports.overdue_tickets(sample_tickets, fixed_now)
    assert [ticket.ticket_id for ticket in overdue] == [1, 2, 3]


def test_workload_counts_only_open_assigned_tickets(sample_tickets):
    assert reports.workload_report(sample_tickets) == {"tech-201": 1}


# T13 - only a manager with export permission may export
@pytest.mark.parametrize("requester_name", ["employee", "technician", "manager_without_permission"])
def test_export_is_refused_without_permission(request, manager, sample_tickets, fixed_now,
                                              tmp_path, requester_name):
    if requester_name == "manager_without_permission":
        manager.can_export_reports = False
        requester = manager
    else:
        requester = request.getfixturevalue(requester_name)
    path = tmp_path / "report.json"
    with pytest.raises(PermissionError, match="not allowed to export reports"):
        reports.export_report(requester, sample_tickets, fixed_now, path)
    assert not path.exists()


def test_manager_exports_report_to_file(manager, sample_tickets, fixed_now, tmp_path):
    path = tmp_path / "report.json"
    reports.export_report(manager, sample_tickets, fixed_now, path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["generated_by"] == "u9"
    assert [breach["ticket_id"] for breach in saved["sla_breaches"]] == [2, 3, 1]
    assert saved["workload"] == {"tech-201": 1}
