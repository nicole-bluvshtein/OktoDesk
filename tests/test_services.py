from unittest.mock import Mock

import pytest

from oktodesk import processing as proc
from oktodesk.models import NotificationChannel, Priority, Status
from oktodesk.observers import KnowledgeBaseRecorder, NotificationObserver, TicketObserver
from oktodesk.services import TicketService


def _service(tickets=(), observers=(), kb_entries=None):
    tickets_by_id = {ticket.ticket_id: ticket for ticket in tickets}
    queue = proc.TicketQueue(t for t in tickets if t.status == Status.OPEN and t.assigned_to is None)
    return TicketService(tickets_by_id, kb_entries if kb_entries is not None else [], observers, queue)


def test_open_ticket_gets_next_id_is_queued_and_observers_hear_once(make_ticket, fixed_now):
    first, second = Mock(spec=TicketObserver), Mock(spec=TicketObserver)
    service = _service([make_ticket(4), make_ticket(9)], observers=[first, second])

    ticket = service.open_ticket("Monitor dead", "No signal", "hardware", Priority.HIGH,
                                 "emp-101", now=fixed_now)

    assert ticket.ticket_id == 10
    assert ticket.status is Status.OPEN
    assert service.tickets_by_id[10] is ticket
    assert len(service.queue) == 3
    assert ticket.activity_log[0]["action"] == "ticket opened"
    first.on_ticket_opened.assert_called_once_with(ticket)
    second.on_ticket_opened.assert_called_once_with(ticket)


def test_assign_next_gives_the_most_urgent_ticket(make_ticket, technician):
    service = _service([make_ticket(1, Priority.LOW), make_ticket(2, Priority.CRITICAL)])
    ticket = service.assign_next(technician)
    assert ticket.ticket_id == 2
    assert ticket.assigned_to == "tech-201"
    assert technician.assigned_tickets == [2]


def test_assign_next_skips_a_ticket_that_was_taken_meanwhile(make_ticket, technician, manager):
    service = _service([make_ticket(1, Priority.LOW), make_ticket(2, Priority.CRITICAL)])
    service.get_ticket(2).assign_to(manager)
    assert service.assign_next(technician).ticket_id == 1


def test_assign_next_on_empty_queue_returns_none(technician):
    assert _service().assign_next(technician) is None


def test_close_ticket_saves_kb_entry_and_queues_a_notification(make_ticket):
    kb_entries = []
    notifications = proc.new_notification_queue()
    channel = Mock(spec=NotificationChannel)
    notifier = NotificationObserver(notifications, [channel])
    service = _service([make_ticket(5, title="Printer offline")],
                       observers=[KnowledgeBaseRecorder(kb_entries), notifier],
                       kb_entries=kb_entries)

    ticket = service.close_ticket(5, "tech-201", "Replaced the cable")

    assert ticket.status is Status.CLOSED
    assert [entry.source_ticket_id for entry in kb_entries] == [5]
    assert notifier.dispatch() == 1
    channel.notify.assert_called_once_with(ticket, "Ticket closed with solution: Replaced the cable")


# T36
def test_failed_close_rolls_back_and_triggers_no_observer(make_ticket):
    kb_entries = []
    watcher = Mock(spec=TicketObserver)
    service = _service([make_ticket(5)], observers=[KnowledgeBaseRecorder(kb_entries), watcher],
                       kb_entries=kb_entries)

    with pytest.raises(ValueError, match="solution must be a non-empty string"):
        service.close_ticket(5, "tech-201", "")

    ticket = service.get_ticket(5)
    assert ticket.status is Status.OPEN
    assert ticket.closed_at is None
    assert kb_entries == []
    watcher.on_ticket_closed.assert_not_called()


def test_closed_ticket_becomes_a_suggestion_for_a_new_one(make_ticket, fixed_now):
    kb_entries = []
    service = _service([make_ticket(5, title="Printer offline")],
                       observers=[KnowledgeBaseRecorder(kb_entries)], kb_entries=kb_entries)
    service.close_ticket(5, "tech-201", "Replaced the cable")
    new_ticket = service.open_ticket("Printer offline again", "Same issue", "hardware",
                                     Priority.MEDIUM, "emp-102", now=fixed_now)
    top_match, _ = service.suggest_solutions(new_ticket.ticket_id)
    assert top_match.source_ticket_id == 5


def test_unknown_ticket_id_gives_a_clear_error():
    with pytest.raises(ValueError, match="No ticket #42"):
        _service().close_ticket(42, "tech-201", "Fixed")


def test_ticket_queue_rebuild_restores_order_after_priority_change(make_ticket):
    low, medium = make_ticket(1, Priority.LOW), make_ticket(2, Priority.MEDIUM)
    queue = proc.TicketQueue([low, medium])
    low.priority = Priority.CRITICAL
    queue.rebuild()
    assert queue.pop_most_urgent() is low
    assert len(queue) == 1
