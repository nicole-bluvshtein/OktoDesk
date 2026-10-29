from datetime import datetime, timedelta

import pytest

from oktodesk.models import User, Technician, ITManager, Ticket, Priority, Status


@pytest.fixture
def fixed_now():
    return datetime(2026, 9, 17, 12, 0)


@pytest.fixture
def employee():
    return User("u1", "Dana Cohen", "dana@example.com", "Finance")


@pytest.fixture
def technician():
    return Technician(
        "u5", "Roi Katz", "roi@example.com", "IT",
        technician_id="tech-201", expertise_areas=["network", "hardware"]
    )


@pytest.fixture
def manager():
    return ITManager(
        "u9", "Tal Avraham", "tal@example.com", "IT",
        technician_id="tech-mgr", expertise_areas=["security"],
        managed_technicians=["tech-201"]
    )


@pytest.fixture
def make_ticket(fixed_now):
    def _make_ticket(ticket_id=1, priority=Priority.MEDIUM, status=Status.OPEN,
                     hours_ago=1, **overrides):
        fields = {
            "title": f"Test ticket {ticket_id}",
            "description": "Something is broken",
            "category": "hardware",
            "opened_by": "u1",
        }
        fields.update(overrides)
        return Ticket(
            ticket_id=ticket_id, priority=priority, status=status,
            created_at=fixed_now - timedelta(hours=hours_ago), **fields
        )
    return _make_ticket


@pytest.fixture
def sample_tickets(make_ticket):
    return [
        make_ticket(1, Priority.LOW, Status.OPEN, hours_ago=30),
        make_ticket(2, Priority.CRITICAL, Status.OPEN, hours_ago=2),
        make_ticket(3, Priority.HIGH, Status.IN_PROGRESS, hours_ago=5, assigned_to="tech-201"),
        make_ticket(4, Priority.MEDIUM, Status.CLOSED, hours_ago=10,
                    assigned_to="tech-201", solution="Restarted the router"),
    ]
