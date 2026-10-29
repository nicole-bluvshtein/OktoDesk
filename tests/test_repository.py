import json

import pytest

from oktodesk.repository import load_tickets, load_knowledge_base


def _record(ticket_id, **overrides):
    record = {
        "ticket_id": ticket_id,
        "title": f"Ticket {ticket_id}",
        "description": "Something is broken",
        "category": "hardware",
        "priority": "MEDIUM",
        "status": "OPEN",
        "opened_by": "emp-101",
        "created_at": "2026-09-10T09:00:00",
    }
    record.update(overrides)
    return record


@pytest.fixture
def write_jsonl(tmp_path):
    def _write(records):
        path = tmp_path / "tickets.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        return path
    return _write


# T1
def test_loader_reads_every_valid_ticket(write_jsonl):
    path = write_jsonl([_record(1), _record(2), _record(3)])
    tickets_by_id, skipped = load_tickets(path)
    assert sorted(tickets_by_id) == [1, 2, 3]
    assert skipped == []


def test_sample_data_still_loads_completely():
    tickets_by_id, skipped = load_tickets("data/sample_data.jsonl")
    assert len(tickets_by_id) == 16
    assert skipped == []


# T2
def _without_category():
    record = _record(2)
    del record["category"]
    return record


@pytest.mark.parametrize("bad_record, reason_part", [
    (_without_category(), "category"),
    (_record(2, priority="high"), "Invalid priority: 'high'"),
    (_record(2, status="DONE"), "Invalid status: 'DONE'"),
])
def test_loader_skips_bad_row_and_records_line_and_reason(write_jsonl, bad_record, reason_part):
    path = write_jsonl([_record(1), bad_record, _record(3)])
    tickets_by_id, skipped = load_tickets(path)
    assert sorted(tickets_by_id) == [1, 3]
    assert len(skipped) == 1
    line_number, reason = skipped[0]
    assert line_number == 2
    assert reason_part in reason


# T3
def test_duplicate_ticket_id_stops_the_load(write_jsonl):
    path = write_jsonl([_record(1), _record(5), _record(5)])
    with pytest.raises(ValueError, match="Duplicate ticket_id 5 found at line 3"):
        load_tickets(path)


def _kb_record(entry_id, **overrides):
    record = {
        "entry_id": entry_id,
        "title": f"Entry {entry_id}",
        "problem_description": "Something broke",
        "solution_description": "Fixed it",
        "category": "hardware",
        "keywords": ["Printer", "jam"],
    }
    record.update(overrides)
    return record


# T14 - loading
def test_kb_loader_reads_entries_and_normalizes_keywords(write_jsonl):
    path = write_jsonl([_kb_record(1), _kb_record(2)])
    entries_by_id, skipped = load_knowledge_base(path)
    assert sorted(entries_by_id) == [1, 2]
    assert skipped == []
    assert entries_by_id[1].keywords == {"printer", "jam"}


def test_kb_loader_skips_entry_with_empty_solution(write_jsonl):
    path = write_jsonl([_kb_record(1), _kb_record(2, solution_description="  "), _kb_record(3)])
    entries_by_id, skipped = load_knowledge_base(path)
    assert sorted(entries_by_id) == [1, 3]
    assert skipped == [(2, "solution_description must be a non-empty string")]


def test_kb_loader_stops_on_duplicate_entry_id(write_jsonl):
    path = write_jsonl([_kb_record(1), _kb_record(1)])
    with pytest.raises(ValueError, match="Duplicate entry_id 1 found at line 2"):
        load_knowledge_base(path)


def test_real_knowledge_base_loads_completely():
    entries_by_id, skipped = load_knowledge_base("data/knowledge_base.jsonl")
    assert len(entries_by_id) == 8
    assert skipped == []
