import json

from oktodesk.models import Ticket


def load_tickets(path):
    tickets_by_id = {}
    skipped = []

    with open(path, encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                ticket = Ticket.from_dict(data)
            except (KeyError, ValueError, json.JSONDecodeError) as error:
                skipped.append((line_number, str(error)))
                continue

            if ticket.ticket_id in tickets_by_id:
                raise ValueError(f"Duplicate ticket_id {ticket.ticket_id!r} found at line {line_number}")

            tickets_by_id[ticket.ticket_id] = ticket

    return tickets_by_id, skipped
