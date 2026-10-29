import json

import pytest

from oktodesk.factories import create_user
from oktodesk.models import User, Technician, ITManager
from oktodesk.repository import load_tickets, load_users, link_technicians_to_tickets


def _user_record(role, **overrides):
    record = {
        "user_id": "emp-900",
        "name": "Test Person",
        "email": "test.person@example.com",
        "department": "IT",
        "role": role,
        "technician_id": "tech-900",
    }
    record.update(overrides)
    return record


# T16
@pytest.mark.parametrize("role, expected_class", [
    ("employee", User),
    ("technician", Technician),
    ("it_manager", ITManager),
])
def test_factory_returns_the_exact_class_for_each_role(role, expected_class):
    user = create_user(_user_record(role))
    assert type(user) is expected_class
    assert user.role == role


# T17
@pytest.mark.parametrize("role", ["boss", None])
def test_factory_rejects_unknown_or_missing_role(role):
    with pytest.raises(ValueError, match="Unknown role"):
        create_user(_user_record(role))


def test_real_users_file_loads_completely():
    users_by_id, skipped = load_users("data/users.jsonl")
    assert len(users_by_id) == 20
    assert skipped == []


def test_user_loader_skips_a_row_with_unknown_role(tmp_path):
    path = tmp_path / "users.jsonl"
    records = [_user_record("employee", user_id="emp-1"),
               _user_record("boss", user_id="emp-2"),
               _user_record("technician", user_id="emp-3")]
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    users_by_id, skipped = load_users(path)
    assert sorted(users_by_id) == ["emp-1", "emp-3"]
    assert [line_number for line_number, _ in skipped] == [2]


def test_every_ticket_person_exists_in_the_users_file():
    users_by_id, _ = load_users("data/users.jsonl")
    tickets_by_id, _ = load_tickets("data/sample_data.jsonl")
    technician_ids = {getattr(user, "technician_id", None) for user in users_by_id.values()}
    for ticket in tickets_by_id.values():
        assert ticket.opened_by in users_by_id
        assert ticket.assigned_to is None or ticket.assigned_to in technician_ids


def test_linking_fills_each_technicians_tickets_from_the_data():
    users_by_id, _ = load_users("data/users.jsonl")
    tickets_by_id, _ = load_tickets("data/sample_data.jsonl")
    technicians_by_id = link_technicians_to_tickets(users_by_id, tickets_by_id)
    expected = sorted(t.ticket_id for t in tickets_by_id.values() if t.assigned_to == "tech-201")
    assert technicians_by_id["tech-201"].assigned_tickets == expected
    assert technicians_by_id["tech-300"].assigned_tickets == []


def test_linking_to_an_unknown_technician_is_refused(make_ticket, employee):
    ticket = make_ticket(1, assigned_to="tech-999")
    with pytest.raises(ValueError, match="unknown technician 'tech-999'"):
        link_technicians_to_tickets({employee.user_id: employee}, {1: ticket})
