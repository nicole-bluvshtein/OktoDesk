import json

from oktodesk.models import Ticket, KnowledgeBaseEntry


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
