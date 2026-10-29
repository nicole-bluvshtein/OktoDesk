# AI Usage — synthetic ticket data

## Tool

Claude (via Claude Code) was used to draft the synthetic ticket
records in `data/sample_data.jsonl`. The AI generated the *data* only — every
class, method, and validation rule in `oktodesk/` was written and reviewed
line by line during this session, not generated in bulk and accepted as-is.

## Prompt

Generate 16 realistic IT-support ticket records as JSON, one object per line
(JSONL), matching the `Ticket` schema in `oktodesk/models.py`:

- Fields: `ticket_id` (unique int), `title`, `description`, `category`,
  `priority`, `status`, `opened_by`, and optionally `assigned_to`,
  `created_at`, `updated_at`, `closed_at`, `solution`, `activity_log`.
- `priority` must be one of the `Priority` enum's member names exactly as
  spelled in the code (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) — not the Hebrew
  display text.
- `status` must be one of the `Status` member names (`OPEN`, `IN_PROGRESS`,
  `WAITING_INFO`, `CLOSED`).
- Cover all four priorities and all four statuses more than once, spread
  across several categories (hardware, network, access, software,
  infrastructure, security) and a handful of recurring technician ids, with
  `created_at` timestamps spread over the past several days so sorting and
  SLA-overdue checks produce varied, meaningful results.

## Record structure

```json
{
  "ticket_id": 5,
  "title": "Email client crashing on launch",
  "description": "Outlook crashes immediately after opening on Windows 11.",
  "category": "software",
  "priority": "HIGH",
  "status": "CLOSED",
  "opened_by": "emp-105",
  "assigned_to": "tech-201",
  "created_at": "2026-09-10T09:00:00",
  "updated_at": "2026-09-10T13:00:00",
  "closed_at": "2026-09-10T13:00:00",
  "solution": "Reinstalled Outlook and cleared the local profile cache.",
  "activity_log": [
    {"performed_by": "emp-105", "action": "Ticket opened", "timestamp": "2026-09-10T09:00:00"},
    {"performed_by": "tech-201", "action": "Took ownership", "timestamp": "2026-09-10T09:30:00"},
    {"performed_by": "tech-201", "action": "Closed with solution", "timestamp": "2026-09-10T13:00:00"}
  ]
}
```

## Data errors introduced on purpose to test the loader

The generated data loaded cleanly. To prove that
`oktodesk.repository.load_tickets` really handles bad input — the kind of
mistakes the assignment brief warns to expect from AI-generated data — we
deliberately introduced three errors into the file, loaded it, checked that
each one was caught the way the loader's policy says, and then removed them:

1. **Missing required field.** We removed `category` from ticket `3`.
   `Ticket.from_dict` raised a `KeyError`, which `load_tickets` caught and
   recorded as a skipped row: `(3, "'category'")`. Restored `"category": "access"`.

2. **Bad enum casing.** We changed ticket `11` to `"priority": "high"`
   (lowercase). Enum member lookup (`Priority["high"]`) is case-sensitive and
   raised a `KeyError`, again caught and skipped: `(11, "'high'")`.
   Restored `"HIGH"`.

3. **Duplicate `ticket_id`.** We changed ticket `12` to `"ticket_id": 5`,
   colliding with an earlier record. Per `load_tickets`'s duplicate-id policy
   this is fatal rather than silently overwriting the index — it raised
   `ValueError: Duplicate ticket_id 5 found at line 12` and halted loading.
   Restored the id to `12`.

## Verification

After the fixes, `load_tickets("data/sample_data.jsonl")` was re-run:

```
Loaded: 16
Skipped: []
```

All 16 records loaded with zero skipped rows and no duplicate-id error. A
sample of records was also spot-checked by hand for correct `Status`/`Priority`
mapping and sensible `is_overdue` results (open, non-`LOW`-priority tickets
created more than their SLA window ago correctly report `is_overdue=True`;
closed tickets and fresh `LOW`-priority tickets report `False`).

## Knowledge Base data (Stage 2)

Claude (via Claude Code) drafted the 8 records in `data/knowledge_base.jsonl`.

**Prompt (summary):** write 8 KnowledgeBaseEntry records as JSONL. Three must be
built from the closed tickets 5, 7 and 12 in `sample_data.jsonl` — same solution
text, `source_ticket_id` set, `created_at` equal to the ticket's `closed_at`. The
other five should match problems in the *open* tickets (printer jam, VPN, shared
drive, laptop battery, slow network) so the "suggest solutions" feature has real
matches, while some open tickets deliberately have no match. Categories must be
ones the tickets use; no real personal data.

**What we checked:** loaded the file through `load_knowledge_base` — 8 entries,
0 skipped. Compared entries 1–3 with tickets 5, 7 and 12 by hand (solution text
and dates). Kept as a test: `test_real_knowledge_base_loads_completely`.
