from unittest.mock import Mock, call

import pytest

from oktodesk import processing as proc
from oktodesk.models import KnowledgeBaseEntry, NotificationChannel, Priority, Status
from oktodesk.observers import KnowledgeBaseRecorder, NotificationObserver, TicketObserver


@pytest.fixture
def closed_ticket(make_ticket):
    ticket = make_ticket(5, Priority.HIGH, title="VPN client fails to connect",
                         category="network")
    ticket.close("tech-201", "Reinstalled the VPN client")
    return ticket


@pytest.fixture
def channels():
    return [Mock(spec=NotificationChannel), Mock(spec=NotificationChannel)]


def test_ticket_observer_cannot_be_instantiated():
    with pytest.raises(TypeError):
        TicketObserver()


# T18 (unit part; the end-to-end version through TicketService.close_ticket is in 3.3)
def test_both_observers_react_once_to_one_closed_ticket(closed_ticket, channels):
    entries = []
    queue = proc.new_notification_queue()
    observers = [KnowledgeBaseRecorder(entries), NotificationObserver(queue, channels)]

    for observer in observers:
        observer.on_ticket_closed(closed_ticket)

    assert len(entries) == 1
    assert len(queue) == 1


# T19
def test_closing_saves_kb_entry_from_solution_and_category(closed_ticket):
    entries = []
    KnowledgeBaseRecorder(entries).on_ticket_closed(closed_ticket)

    entry = entries[0]
    assert entry.solution_description == "Reinstalled the VPN client"
    assert entry.category == "network"
    assert entry.problem_description == closed_ticket.description
    assert entry.source_ticket_id == 5
    assert entry.matches_keyword("vpn")


def test_new_kb_entry_id_is_highest_existing_plus_one(closed_ticket):
    entries = [
        KnowledgeBaseEntry(3, "Old fix", "Problem", "Solution", "network"),
        KnowledgeBaseEntry(7, "Other fix", "Problem", "Solution", "hardware"),
    ]
    KnowledgeBaseRecorder(entries).on_ticket_closed(closed_ticket)
    assert entries[-1].entry_id == 8


def test_first_kb_entry_gets_id_one(closed_ticket):
    entries = []
    KnowledgeBaseRecorder(entries).on_ticket_closed(closed_ticket)
    assert entries[0].entry_id == 1


def test_recorder_ignores_opened_tickets(make_ticket):
    entries = []
    KnowledgeBaseRecorder(entries).on_ticket_opened(make_ticket())
    assert entries == []


def test_recorder_refuses_a_ticket_that_is_not_closed(make_ticket):
    entries = []
    with pytest.raises(ValueError, match="must be closed"):
        KnowledgeBaseRecorder(entries).on_ticket_closed(make_ticket(status=Status.OPEN))
    assert entries == []


def test_events_wait_in_the_queue_until_dispatch(make_ticket, channels):
    observer = NotificationObserver(proc.new_notification_queue(), channels)
    observer.on_ticket_opened(make_ticket())
    for channel in channels:
        channel.notify.assert_not_called()


def test_dispatch_sends_every_message_to_every_channel_in_arrival_order(
        make_ticket, closed_ticket, channels):
    opened_ticket = make_ticket(9, Priority.CRITICAL, title="Server room AC failure")
    observer = NotificationObserver(proc.new_notification_queue(), channels)

    observer.on_ticket_opened(opened_ticket)
    observer.on_ticket_closed(closed_ticket)
    sent = observer.dispatch()

    expected = [
        call(opened_ticket, "New CRITICAL ticket opened: Server room AC failure"),
        call(closed_ticket, "Ticket closed with solution: Reinstalled the VPN client"),
    ]
    assert sent == 2
    for channel in channels:
        assert channel.notify.call_args_list == expected


def test_dispatch_on_empty_queue_sends_nothing(channels):
    observer = NotificationObserver(proc.new_notification_queue(), channels)
    assert observer.dispatch() == 0
    for channel in channels:
        channel.notify.assert_not_called()
