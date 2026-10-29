from oktodesk.models import Priority, Status


def test_fixtures_build(sample_tickets, fixed_now, manager):
    assert len(sample_tickets) == 4
    assert all(ticket.created_at < fixed_now for ticket in sample_tickets)
    assert manager.can_export_reports is True


def test_make_ticket_applies_overrides(make_ticket):
    ticket = make_ticket(7, Priority.CRITICAL, Status.OPEN, title="Printer on fire")
    assert ticket.ticket_id == 7
    assert ticket.title == "Printer on fire"
    assert ticket.priority is Priority.CRITICAL
