from oktodesk import processing as proc
from oktodesk.context_managers import TicketWorkSession
from oktodesk.models import Ticket, Status


class TicketService:
    def __init__(self, tickets_by_id, kb_entries, observers, queue):
        self.tickets_by_id = tickets_by_id
        self.kb_entries = kb_entries
        self.observers = list(observers)
        self.queue = queue

    def open_ticket(self, title, description, category, priority, opened_by, now=None):
        ticket = Ticket(
            ticket_id=self._next_ticket_id(), title=title, description=description,
            category=category, priority=priority, status=Status.OPEN,
            opened_by=opened_by, created_at=now,
        )
        ticket.add_log_entry(opened_by, "ticket opened", timestamp=ticket.created_at)
        self.tickets_by_id[ticket.ticket_id] = ticket
        self.queue.push(ticket)
        for observer in self.observers:
            observer.on_ticket_opened(ticket)
        return ticket

    def assign_next(self, technician):
        while True:
            ticket = self.queue.pop_most_urgent()
            if ticket is None:
                return None
            if ticket.status == Status.OPEN and ticket.assigned_to is None:
                ticket.assign_to(technician)
                return ticket

    def close_ticket(self, ticket_id, performed_by, solution):
        ticket = self.get_ticket(ticket_id)
        with TicketWorkSession(ticket, performed_by):
            ticket.close(performed_by, solution)
        for observer in self.observers:
            observer.on_ticket_closed(ticket)
        return ticket

    def suggest_solutions(self, ticket_id):
        return proc.suggest_solutions(self.get_ticket(ticket_id), self.kb_entries)

    def get_ticket(self, ticket_id):
        try:
            return self.tickets_by_id[ticket_id]
        except KeyError:
            raise ValueError(f"No ticket #{ticket_id}") from None

    def _next_ticket_id(self):
        return max(self.tickets_by_id, default=0) + 1
