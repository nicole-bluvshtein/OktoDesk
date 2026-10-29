import pytest

from oktodesk.context_managers import TicketWorkSession
from oktodesk.models import Priority, Status


# T5
def test_failed_session_restores_every_field_and_reraises(make_ticket):
    ticket = make_ticket(3, Priority.MEDIUM, title="Printer offline")
    before = (ticket.title, ticket.priority, ticket.status, ticket.assigned_to,
              ticket.solution, ticket.closed_at, ticket.updated_at)

    with pytest.raises(RuntimeError, match="disk full"):
        with TicketWorkSession(ticket, performed_by="tech-201") as session_ticket:
            session_ticket.update_details("tech-201", title="Printer on fire",
                                          priority=Priority.CRITICAL)
            session_ticket.close("tech-201", "Replaced the fuser")
            raise RuntimeError("disk full")

    after = (ticket.title, ticket.priority, ticket.status, ticket.assigned_to,
             ticket.solution, ticket.closed_at, ticket.updated_at)
    assert after == before
    assert "rolled back: disk full" in ticket.activity_log[-1]["action"]


def test_successful_session_keeps_the_close(make_ticket):
    ticket = make_ticket()
    with TicketWorkSession(ticket, performed_by="tech-201") as session_ticket:
        session_ticket.close("tech-201", "Replaced the fuser")
    assert ticket.status is Status.CLOSED
    assert ticket.solution == "Replaced the fuser"
    assert ticket.activity_log[-1]["action"] == "ended work session"


def test_session_on_closed_ticket_is_refused(make_ticket):
    ticket = make_ticket(status=Status.CLOSED, solution="Already fixed")
    with pytest.raises(ValueError, match="closed ticket"):
        with TicketWorkSession(ticket, performed_by="tech-201"):
            pass
    assert ticket.status is Status.CLOSED
