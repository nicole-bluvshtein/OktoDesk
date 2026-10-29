from datetime import datetime, timedelta

import pytest

from oktodesk.models import User, Priority, Status, Ticket



# T7
@pytest.mark.parametrize("field, bad_value", [
    ("title", ""),
    ("title", "   "),
    ("description", ""),
    ("category", ""),
    ("opened_by", ""),
])
def test_ticket_rejects_empty_required_text(make_ticket, field, bad_value):
    with pytest.raises(ValueError, match=f"{field} must be a non-empty string"):
        make_ticket(**{field: bad_value})


def test_updating_title_to_empty_is_rejected(make_ticket):
    ticket = make_ticket()
    with pytest.raises(ValueError):
        ticket.title = ""
    assert ticket.title == "Test ticket 1"


def test_ticket_rejects_priority_that_is_not_an_enum(make_ticket):
    with pytest.raises(ValueError, match="Invalid priority"):
        make_ticket(priority="HIGH")
    assert Priority.HIGH.name == "HIGH"


def test_user_rejects_bad_email():
    with pytest.raises(ValueError):
        User("u1", "Dana Cohen", "not-an-email", "Finance")


CLOSE_TIME = datetime(2026, 9, 17, 15, 0)


# T8
def test_close_sets_every_closing_field_and_logs(make_ticket):
    ticket = make_ticket()
    ticket.close("tech-201", "Replaced the cable", now=CLOSE_TIME)
    assert ticket.status is Status.CLOSED
    assert ticket.solution == "Replaced the cable"
    assert ticket.closed_at == CLOSE_TIME
    assert ticket.updated_at == CLOSE_TIME
    assert ticket.activity_log[-1]["action"] == "closed with solution"
    assert ticket.activity_log[-1]["performed_by"] == "tech-201"


# T9
@pytest.mark.parametrize("solution", ["", "   ", None])
def test_close_with_empty_solution_is_refused_and_changes_nothing(make_ticket, solution):
    ticket = make_ticket()
    with pytest.raises(ValueError, match="solution must be a non-empty string"):
        ticket.close("tech-201", solution)
    assert ticket.status is Status.OPEN
    assert ticket.closed_at is None
    assert ticket.activity_log == []


def test_closing_twice_is_refused(make_ticket):
    ticket = make_ticket()
    ticket.close("tech-201", "Fixed", now=CLOSE_TIME)
    with pytest.raises(ValueError, match="already closed"):
        ticket.close("tech-201", "Fixed again")
    assert ticket.solution == "Fixed"


# T10
def test_assign_links_ticket_and_technician_both_ways(make_ticket, technician):
    ticket = make_ticket(5)
    ticket.assign_to(technician)
    assert ticket.assigned_to == "tech-201"
    assert technician.assigned_tickets == [5]
    assert ticket.status is Status.IN_PROGRESS
    assert ticket.activity_log[-1]["action"] == "assigned to tech-201"


def test_assigning_to_a_second_technician_is_refused(make_ticket, technician, manager):
    ticket = make_ticket(5)
    ticket.assign_to(technician)
    with pytest.raises(ValueError, match="already assigned to tech-201"):
        ticket.assign_to(manager)
    assert manager.assigned_tickets == []


# F11 - updates are logged and change updated_at
def test_update_details_changes_fields_logs_and_touches_updated_at(make_ticket):
    ticket = make_ticket()
    created = ticket.updated_at
    ticket.update_details("tech-201", title="Printer jammed", priority=Priority.HIGH)
    assert ticket.title == "Printer jammed"
    assert ticket.priority is Priority.HIGH
    assert ticket.updated_at > created
    assert ticket.activity_log[-1]["action"] == "updated title, priority"


def test_update_details_is_all_or_nothing(make_ticket):
    ticket = make_ticket()
    with pytest.raises(ValueError):
        ticket.update_details("tech-201", title="New title", priority="HIGH")
    assert ticket.title == "Test ticket 1"
    assert ticket.activity_log == []


def test_update_details_cannot_close(make_ticket):
    ticket = make_ticket()
    with pytest.raises(ValueError, match="Use close"):
        ticket.update_details("tech-201", status=Status.CLOSED)


def test_kb_entry_only_from_closed_ticket(make_ticket):
    ticket = make_ticket(9, title="Outlook crashes on launch", category="software")
    with pytest.raises(ValueError, match="must be closed"):
        ticket.to_knowledge_base_entry(1)
    ticket.close("tech-201", "Reinstalled Outlook", now=CLOSE_TIME)
    entry = ticket.to_knowledge_base_entry(1, keywords=["office"])
    assert entry.source_ticket_id == 9
    assert entry.solution_description == "Reinstalled Outlook"
    assert entry.keywords == {"outlook", "crashes", "launch", "office"}


# T11 - expected values defined by Nicole and Amit (assignment section 7.3)
@pytest.mark.parametrize("priority, status, hours_ago, extra, expected_overdue, expected_hours", [
    (Priority.CRITICAL, Status.OPEN, 3, {}, True, 2),
    (Priority.LOW, Status.OPEN, 4, {}, False, -20),
    (Priority.HIGH, Status.OPEN, 8, {}, True, 4),
    (Priority.CRITICAL, Status.CLOSED, 0.5, {"closed_at": "now", "solution": "Fixed"}, False, -0.5),
    (Priority.MEDIUM, Status.WAITING_INFO, 4, {"waiting_since": "now"}, False, -4),
    (Priority.HIGH, Status.OPEN, 4, {}, False, 0),
], ids=["critical-open-3h", "low-open-4h", "high-open-8h",
        "critical-closed-on-time", "medium-waiting", "high-exactly-at-target"])
def test_sla_overdue_and_hours_over(make_ticket, fixed_now, priority, status, hours_ago,
                                    extra, expected_overdue, expected_hours):
    fields = {key: fixed_now if value == "now" else value for key, value in extra.items()}
    ticket = make_ticket(1, priority, status, hours_ago=hours_ago, **fields)
    assert ticket.is_overdue_at(fixed_now) is expected_overdue
    assert ticket.hours_over_sla(fixed_now) == pytest.approx(expected_hours)


def test_waiting_ticket_from_file_starts_waiting_at_last_update():
    ticket = Ticket.from_dict({
        "ticket_id": 1, "title": "VPN drops", "description": "Disconnects hourly",
        "category": "network", "priority": "HIGH", "status": "WAITING_INFO",
        "opened_by": "emp-101",
        "created_at": "2026-09-16T08:00:00", "updated_at": "2026-09-16T10:00:00",
    })
    assert ticket.waiting_since == datetime(2026, 9, 16, 10, 0)


def test_leaving_waiting_adds_the_paused_hours(make_ticket):
    three_hours_ago = datetime.now() - timedelta(hours=3)
    ticket = make_ticket(status=Status.WAITING_INFO, waiting_since=three_hours_ago)
    ticket.update_details("tech-201", status=Status.IN_PROGRESS)
    assert ticket.waiting_since is None
    assert ticket.waiting_hours == pytest.approx(3, abs=0.01)
