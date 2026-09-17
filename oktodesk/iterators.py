from oktodesk.models import Status


class TicketIterator:
    def __init__(self, tickets):
        self._tickets = tickets
        self._index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._index >= len(self._tickets):
            raise StopIteration
        ticket = self._tickets[self._index]
        self._index += 1
        return ticket


class TicketCollection:
    def __init__(self, tickets):
        self._tickets = list(tickets)

    def __iter__(self):
        return TicketIterator(self._tickets)


def iter_open_tickets(tickets):
    for ticket in tickets:
        if ticket.status != Status.CLOSED:
            yield ticket


def open_ticket_id_pipeline(tickets, priority):
    by_priority = (ticket for ticket in tickets if ticket.priority == priority)
    open_only = (ticket for ticket in by_priority if ticket.status != Status.CLOSED)
    ticket_ids = (ticket.ticket_id for ticket in open_only)
    return ticket_ids
