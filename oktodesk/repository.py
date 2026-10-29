import json

from oktodesk.models import Ticket, KnowledgeBaseEntry
from oktodesk.factories import create_user


def _load_jsonl(path, from_dict, id_field):
    items_by_id = {}
    skipped = []

    with open(path, encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                item = from_dict(data)
            except (KeyError, ValueError, json.JSONDecodeError) as error:
                skipped.append((line_number, str(error)))
                continue

            item_id = getattr(item, id_field)
            if item_id in items_by_id:
                raise ValueError(f"Duplicate {id_field} {item_id!r} found at line {line_number}")

            items_by_id[item_id] = item

    return items_by_id, skipped


def load_tickets(path):
    return _load_jsonl(path, Ticket.from_dict, "ticket_id")


def load_knowledge_base(path):
    return _load_jsonl(path, KnowledgeBaseEntry.from_dict, "entry_id")


def load_users(path):
    return _load_jsonl(path, create_user, "user_id")


def link_technicians_to_tickets(users_by_id, tickets_by_id):
    technicians_by_id = {
        user.technician_id: user for user in users_by_id.values()
        if getattr(user, "technician_id", None) is not None
    }
    for ticket in tickets_by_id.values():
        if ticket.assigned_to is None:
            continue
        technician = technicians_by_id.get(ticket.assigned_to)
        if technician is None:
            raise ValueError(
                f"Ticket #{ticket.ticket_id} is assigned to unknown technician {ticket.assigned_to!r}"
            )
        if ticket.ticket_id not in technician.assigned_tickets:
            technician.assigned_tickets.append(ticket.ticket_id)
    return technicians_by_id

