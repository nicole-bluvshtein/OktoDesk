from datetime import datetime

import pytest

from oktodesk import processing as proc
from oktodesk.models import KnowledgeBaseEntry, Priority, Status
from oktodesk.repository import load_knowledge_base, load_tickets


# T4
def test_heap_pops_critical_first_and_older_first_on_a_tie(make_ticket):
    newer_high = make_ticket(1, Priority.HIGH, hours_ago=1)
    critical = make_ticket(2, Priority.CRITICAL, hours_ago=1)
    older_high = make_ticket(3, Priority.HIGH, hours_ago=5)
    low = make_ticket(4, Priority.LOW, hours_ago=50)

    queue = proc.new_priority_queue()
    for ticket in [newer_high, critical, older_high, low]:
        proc.push_ticket(queue, ticket)

    popped = [proc.pop_most_urgent_ticket(queue).ticket_id for _ in range(4)]
    assert popped == [2, 3, 1, 4]
    assert proc.pop_most_urgent_ticket(queue) is None


# T6
def test_capabilities_build_up_through_the_hierarchy(employee, technician, manager):
    employee_text = employee.describe_capabilities()
    technician_text = technician.describe_capabilities()
    manager_text = manager.describe_capabilities()

    assert employee_text == "Dana Cohen can open tickets and view their own tickets."
    assert technician_text.startswith("Roi Katz can open tickets")
    assert "can also view, edit and close tickets" in technician_text
    assert "As a technician" in manager_text
    assert "can export reports" in manager_text

@pytest.fixture
def kb_entries():
    entries_by_id, _ = load_knowledge_base("data/knowledge_base.jsonl")
    return list(entries_by_id.values())


# T14 - search
@pytest.mark.parametrize("keyword, category, expected_ids", [
    ("printer", None, [3, 4]),
    ("PRINTER", None, [3, 4]),
    (" vpn ", None, [5]),
    ("printer", "hardware", [3, 4]),
    ("printer", "network", []),
    ("projector", None, []),
])
def test_search_knowledge_base(kb_entries, keyword, category, expected_ids):
    results = proc.search_knowledge_base(kb_entries, keyword, category)
    assert [entry.entry_id for entry in results] == expected_ids


@pytest.mark.parametrize("bad_keyword", ["", "   "])
def test_search_with_empty_keyword_is_refused(kb_entries, bad_keyword):
    with pytest.raises(ValueError, match="keyword must be a non-empty string"):
        proc.search_knowledge_base(kb_entries, bad_keyword)

def _entry(entry_id, keywords, category="hardware",
           created_at=datetime(2026, 9, 1), source_ticket_id=None):
    return KnowledgeBaseEntry(
        entry_id, f"Entry {entry_id}", "Problem", "Solution", category,
        keywords=keywords, source_ticket_id=source_ticket_id, created_at=created_at,
    )


# T15a - most matching keywords first, the rest in order
def test_suggestions_put_the_best_match_first_and_keep_the_rest(make_ticket):
    ticket = make_ticket(1, title="Office printer jammed on 3rd floor")
    entries = [
        _entry(1, ["printer", "toner"]),
        _entry(2, ["printer", "jammed", "paper"]),
        _entry(3, ["vpn"]),
        _entry(4, ["office", "printer", "jammed"]),
    ]
    top_match, other_matches = proc.suggest_solutions(ticket, entries)
    assert top_match.entry_id == 4
    assert [entry.entry_id for entry in other_matches] == [2, 1]


# T15b - no keyword match, even in the same category, gives no suggestion
def test_no_matching_keyword_gives_no_suggestion(make_ticket):
    ticket = make_ticket(1, title="Server room AC failure", category="infrastructure")
    entries = [_entry(1, ["printer"]), _entry(2, ["vpn"], category="infrastructure")]
    assert proc.suggest_solutions(ticket, entries) == (None, [])


# T15c - on a keyword tie, the same category wins (even against a newer entry)
def test_keyword_tie_is_broken_by_same_category(make_ticket):
    ticket = make_ticket(1, title="Slow internet", category="network")
    entries = [
        _entry(1, ["slow"], category="hardware", created_at=datetime(2026, 9, 5)),
        _entry(2, ["slow"], category="network", created_at=datetime(2026, 9, 1)),
    ]
    top_match, other_matches = proc.suggest_solutions(ticket, entries)
    assert top_match.entry_id == 2
    assert [entry.entry_id for entry in other_matches] == [1]


# T15d - on a full tie, the newer entry wins
def test_full_tie_is_broken_by_newer_entry(make_ticket):
    ticket = make_ticket(1, title="Printer offline")
    entries = [
        _entry(1, ["printer"], created_at=datetime(2026, 9, 1)),
        _entry(2, ["printer"], created_at=datetime(2026, 9, 8)),
    ]
    top_match, other_matches = proc.suggest_solutions(ticket, entries)
    assert top_match.entry_id == 2
    assert [entry.entry_id for entry in other_matches] == [1]


# T15e - a closed ticket is refused
def test_suggestions_for_closed_ticket_are_refused(make_ticket):
    ticket = make_ticket(1, status=Status.CLOSED, solution="Done")
    with pytest.raises(ValueError, match="closed"):
        proc.suggest_solutions(ticket, [_entry(1, ["ticket"])])


# T15f - an entry made from this same ticket is never suggested to it
def test_entry_from_the_same_ticket_is_not_suggested(make_ticket):
    ticket = make_ticket(7, title="Printer offline")
    entries = [_entry(1, ["printer"], source_ticket_id=7), _entry(2, ["printer"])]
    top_match, other_matches = proc.suggest_solutions(ticket, entries)
    assert top_match.entry_id == 2
    assert other_matches == []


# T15g - real data: ticket #1 (printer jammed)
def test_real_ticket_gets_real_suggestions():
    tickets_by_id, _ = load_tickets("data/sample_data.jsonl")
    entries_by_id, _ = load_knowledge_base("data/knowledge_base.jsonl")
    top_match, other_matches = proc.suggest_solutions(tickets_by_id[1], entries_by_id.values())
    assert top_match.entry_id == 4
    assert [entry.entry_id for entry in other_matches] == [3]
