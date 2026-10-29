import heapq
import threading
import time

import pytest

from oktodesk import processing as proc
from oktodesk.models import Priority, Technician
from oktodesk.services import TicketService
from oktodesk.threaded_processing import ThreadSafeTicketQueue, run_assignment_race


def _technicians(count):
    return [Technician(f"emp-{200 + i}", f"Tech {i}", f"tech{i}@example.com", "IT",
                       technician_id=f"tech-{200 + i}") for i in range(count)]


def _service(tickets, queue_class=ThreadSafeTicketQueue):
    return TicketService({t.ticket_id: t for t in tickets}, [], [], queue_class(tickets))


# T31 - one ticket left, five technicians ask at the same moment
@pytest.mark.parametrize("attempt", range(20))
def test_last_ticket_goes_to_exactly_one_technician(make_ticket, attempt):
    ticket = make_ticket(1, Priority.HIGH)
    service = _service([ticket])
    technicians = _technicians(5)

    results = run_assignment_race(service, technicians)

    winners = [tech_id for tech_id, got in results.items() if got is not None]
    assert len(results) == 5
    assert len(winners) == 1
    assert ticket.assigned_to == winners[0]
    assert [t.assigned_tickets for t in technicians].count([1]) == 1
    assert len(service.queue) == 0


@pytest.mark.parametrize("attempt", range(20))
def test_three_tickets_five_technicians_no_ticket_twice(make_ticket, attempt):
    tickets = [make_ticket(i, Priority.MEDIUM, hours_ago=i) for i in (1, 2, 3)]
    service = _service(tickets)

    results = run_assignment_race(service, _technicians(5))

    handed_out = [got.ticket_id for got in results.values() if got is not None]
    assert sorted(handed_out) == [1, 2, 3]
    assert list(results.values()).count(None) == 2


class _SlowUnsafeQueue(proc.TicketQueue):
    def pop_most_urgent(self):
        if not self._heap:
            return None
        time.sleep(0.05)
        return heapq.heappop(self._heap)


class _SlowSafeQueue(ThreadSafeTicketQueue):
    def pop_most_urgent(self):
        with self._lock:
            if not self._heap:
                return None
            time.sleep(0.05)
            return heapq.heappop(self._heap)


def _race_collecting_errors(service, technicians):
    errors = []
    start_together = threading.Barrier(len(technicians))

    def ask(technician):
        start_together.wait()
        try:
            service.assign_next(technician)
        except IndexError as error:
            errors.append(error)

    threads = [threading.Thread(target=ask, args=(t,)) for t in technicians]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors


def test_without_the_lock_the_race_really_breaks(make_ticket):
    service = _service([make_ticket(1)], queue_class=_SlowUnsafeQueue)
    errors = _race_collecting_errors(service, _technicians(5))
    assert len(errors) == 4


def test_with_the_lock_the_same_slow_race_is_safe(make_ticket):
    service = _service([make_ticket(1)], queue_class=_SlowSafeQueue)
    assert _race_collecting_errors(service, _technicians(5)) == []
