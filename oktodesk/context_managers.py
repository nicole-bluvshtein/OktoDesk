from oktodesk.models import Status

_RESTORED_FIELDS = ("title", "description", "priority", "status",
                    "assigned_to", "solution", "closed_at", "updated_at",
                    "waiting_since", "waiting_hours")


class TicketWorkSession:
    def __init__(self, ticket, performed_by):
        self.ticket = ticket
        self.performed_by = performed_by
        self._snapshot = {}

    def __enter__(self):
        if self.ticket.status == Status.CLOSED:
            raise ValueError(f"Cannot start a work session on closed ticket #{self.ticket.ticket_id}")
        self._snapshot = {field: getattr(self.ticket, field) for field in _RESTORED_FIELDS}
        self.ticket.status = Status.IN_PROGRESS
        self.ticket.add_log_entry(self.performed_by, "started work session")
        return self.ticket

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            for field, value in self._snapshot.items():
                setattr(self.ticket, field, value)
            self.ticket.add_log_entry(
                self.performed_by, f"work session failed, changes rolled back: {exc_value}"
            )
            return False
        self.ticket.add_log_entry(self.performed_by, "ended work session")
        return False


if __name__ == "__main__":
    from oktodesk.models import Priority, Ticket

    printer_ticket = Ticket(
        ticket_id=1,
        title="Printer offline",
        description="Office printer not responding",
        category="hardware",
        priority=Priority.MEDIUM,
        status=Status.OPEN,
        opened_by="alice",
    )
    switch_ticket = Ticket(
        ticket_id=2,
        title="Network switch down",
        description="Second floor has no network",
        category="network",
        priority=Priority.HIGH,
        status=Status.OPEN,
        opened_by="bob",
    )

    print("before normal session:", printer_ticket.status)
    with TicketWorkSession(printer_ticket, performed_by="tech1") as session_ticket:
        session_ticket.close("tech1", "Replaced network cable")
    print("after normal session:", printer_ticket.status, "| closed at:", printer_ticket.closed_at)

    print("before failing session:", switch_ticket.status)
    try:
        with TicketWorkSession(switch_ticket, performed_by="tech1") as session_ticket:
            session_ticket.close("tech1", "Swapped the switch")
            raise RuntimeError("could not save the solution to the knowledge base")
    except RuntimeError as exc:
        print("caught:", exc)
    print("after failing session:", switch_ticket.status,
          "| solution:", switch_ticket.solution, "| closed at:", switch_ticket.closed_at)
