from oktodesk.models import Status


class TicketWorkSession:
    def __init__(self, ticket, actor):
        self.ticket = ticket
        self.actor = actor
        self._previous_status = None

    def __enter__(self):
        self._previous_status = self.ticket.status
        self.ticket.status = Status.IN_PROGRESS
        self.ticket.add_log_entry(self.actor, "started work session")
        return self.ticket

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            self.ticket.status = self._previous_status
            self.ticket.add_log_entry(self.actor, f"work session failed: {exc_value}")
            return False
        self.ticket.add_log_entry(self.actor, "ended work session")
        return False


if __name__ == "__main__":
    from oktodesk.models import Priority, Ticket

    ticket = Ticket(
        ticket_id=1,
        title="Printer offline",
        description="Office printer not responding",
        category="hardware",
        priority=Priority.MEDIUM,
        status=Status.OPEN,
        opened_by="alice",
    )

    print("before normal session:", ticket.status)
    with TicketWorkSession(ticket, actor="tech1") as session_ticket:
        session_ticket.solution = "Replaced network cable"
        session_ticket.status = Status.CLOSED
    print("after normal session:", ticket.status)

    print("before failing session:", ticket.status)
    try:
        with TicketWorkSession(ticket, actor="tech1"):
            raise RuntimeError("could not reach the printer")
    except RuntimeError as exc:
        print("caught:", exc)
    print("after failing session:", ticket.status)
