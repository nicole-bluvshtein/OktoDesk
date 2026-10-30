# AI Usage

## Tool

Claude (via Claude Code) was used to draft the synthetic ticket records in
`data/sample_data.jsonl`, and to plan, write and review code. The code in
`oktodesk/` was written together with the AI: it proposed and wrote code
alongside us, and every piece was reviewed both by the AI and by us before it was
committed.

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

## User data (Stage 2)

Claude (via Claude Code) drafted the 20 records in `data/users.jsonl`: 16
employees, 3 technicians and 1 IT manager.

**Prompt (summary):** one record per person referenced by the tickets — every
`opened_by` (`emp-101`–`emp-116`) and every `assigned_to` (`tech-201`–`tech-203`)
— plus one manager. Invented names, `example.com` emails, no real personal data.
No `assigned_tickets` in the file: they are derived from the tickets.

**What we checked:** every record builds through `create_user` (16 `User`, 3
`Technician`, 1 `ITManager`); loaded through `load_users` with 0 skipped. Kept as
tests: `test_real_users_file_loads_completely` and
`test_every_ticket_person_exists_in_the_users_file`.

## Amit's track (Stage 2: steps 3.2, 4.1, 5.1 and README parts)

Claude (via Claude Code) wrote the code and tests for the observers
(`observers.py`), the NVD client (`api_client.py`, `config.py`,
`.env.example`), the async security sweep (`async_processing.py`,
`data/simulated_cves.json`) and README Stage 2 parts 2–4.

**Plan first, no code.** Before any change, the AI read the whole repository
and the approved Stage 2 plan, then asked questions instead of assuming. Every
open design choice was put to Amit as a question with options, and Amit
decided:

| Question | Decision |
|---|---|
| Which id does a new KB entry get when a ticket closes? | Highest existing id + 1 (no collision if an entry was removed) |
| The ticket fields for product and CVEs don't exist until step 4.2 | Leave them out of 3.2; Nicole adds the keywords in 4.2 |
| T18 needs `TicketService`, which is Nicole's step 3.3 | Unit tests on the observers now; the end-to-end test in 3.3 |
| Load a `.env` file automatically (extra package `python-dotenv`)? | No: variables are set in the shell, no extra dependency, because NVD needs no key |
| If one product fails during the sweep, does the whole sweep fail? | No: that product's result is the error ("unknown"), the others still count |
| Real-looking or clearly fake CVE ids in the simulated data? | Clearly fake (`CVE-SIM-0001`), so simulated data can't pass as real |

**What we checked**
- Every step: the full test suite, `pyflakes` and `main.py`, not only the new
  tests.
- **Real response shape.** The NVD client was tested with mocked sessions,
  so one real request (`chrome`, 29 Oct 2026) was made to confirm the parser
  matches the real API, not just our own fakes. It returned 5 critical CVEs.
  This was a check, not the live proof for the README.
- **Install command.** After adding the package setting to `pyproject.toml`,
  `pip install -e ".[dev]"` was re-run to confirm it now succeeds.
- **Facts in the README.** Statements in the README parts were checked against
  the code (for example, that the vulnerability report really lists failed
  checks) before being written.

**What we fixed**
- `.env.example` first said "Copy to .env", which became wrong once we decided
  not to load `.env`. Corrected in a follow-up commit.
- **Integration bug between 5.1 and 4.2.** Each side's tests passed alone, but
  feeding the *real* sweep output into `apply_vulnerability_reports` crashed
  (`AttributeError: 'ServiceUnavailableError' object has no attribute
  'product'`): a failed product's slot held an error that didn't say which
  product failed. Fixed on both sides: service errors now carry the product,
  and `apply_vulnerability_reports` marks only that product's tickets
  "unknown". The two new service tests were run against the **old**
  `services.py` first and failed, which proves they catch the bug; they pass
  with the fix. No expected result was changed to make a test pass.

**Simulated data.** `data/simulated_cves.json` was drafted by the AI to our
rules: three products that finish in a different order from the input, one
product that always fails, and only `CVE-SIM-` ids. A test
(`test_shipped_simulated_data_uses_only_fake_ids`) keeps it that way.

## Nicole's track (Stage 2: Phases 0–2 with Amit, then 3.1, 3.3, 4.2, 5.2, 6.1 and README parts)

Claude (via Claude Code) proposed the design and code for each step, and Nicole
approved every step before it was written. Nicole typed a large part of the code
herself — for example `factories.py`, `services.py`, `threaded_processing.py`,
`reports.py` and `main.py` — and committed and merged each step herself.

**Plan first, no code.** Before any change, we asked for an audit of the Stage 1
feedback against the instructions, then one plan for the fixes and every Stage 2
requirement, with test cases T1–T36. We reviewed and approved it before any code
changed.

**Expected results we defined ourselves (section 7.3)**

*T11 — SLA hours.* Our rules: inside the SLA the value is negative (hours left);
overdue means strictly more than the target; a closed ticket is measured up to
`closed_at` and is never overdue; the clock stops while waiting for the employee.
At a fixed "now" of 17 Sep 2026 12:00:

| Ticket | Overdue | Hours over SLA |
|---|---|---|
| CRITICAL, open, opened 3 h ago | yes | 2 |
| LOW, open, opened 4 h ago | no | −20 |
| HIGH, open, opened 8 h ago | yes | 4 |
| CRITICAL, opened 0.5 h ago, closed now | no | −0.5 |
| MEDIUM, waiting since now, opened 4 h ago | no | −4 |
| HIGH, open, opened exactly 4 h ago | no | 0 |

Row 3 was first written as 0.1; when the AI pointed out that row 1 counted in
hours, we clarified it to 4 hours.

*T12 — SLA breach report.* For six tickets, we decided which appear, their hours
over and their order: #21 CRITICAL 4 h, #22 HIGH 2 h, #26 LOW 6 h. We ordered them
by priority, then by more hours over — not "most overdue first" as the plan first
said. The plan, the code and a tie-break test follow our rule.

**Decisions**

| Question | Decision |
|---|---|
| Factory: `if/elif` or a role→class dict? | Dict: a new role is one line |
| Can a technician update status? (the README says yes, the contract didn't) | Yes, but never to CLOSED; closing goes through `close()` |
| How many CVEs to link? | The top 3 by score |
| A vulnerable product and a CRITICAL ticket? | At least HIGH; CRITICAL stays CRITICAL |
| A later sweep says "clear"? | Never lower automatically; a person decides |
| How to notify? | CVE ids in the "ticket opened" message |
| Sweep results that mix reports and errors needed `isinstance` | Replaced with `SweepResult(product, report, error)` |
| Bad JSON and wrong structure shared one error class | Split into `MalformedJSONError` and `UnexpectedStructureError` |
| Review before merging solo branches? | Not required; we read each other's merged code |

**What we checked**
- After every step: the full test suite, `pyflakes` and `main.py`, not only the new tests.
- The new tests failed first, for the right reason (TDD Red in 2.3, and T11 before `hours_over_sla` existed).
- Amit's branches were merged into a separate copy first and the full suite run there before merging into `main`.
- KB entries 1–3 compared by hand with tickets 5, 7 and 12.
- Every statement in our README parts checked against the code; then an audit of every requirement in the plan, with a file and line for each.

**What we fixed after review**
- Waiting tickets loaded from the file had no `waiting_since` when `updated_at` was missing, so the SLA clock never paused. Found by a manual check; fixed and covered by a test.
- Mistakes while typing code, caught by `pyflakes` and the tests: duplicated imports, a function pasted into the wrong module, and imports in `main.py` replaced instead of added.
- The simulated data used "vpn client" while the tickets use "FortiClient", so the offline failure case never appeared. A product without simulated data was reported "clear"; it is now "unknown".
- The README still promised a dashboard in one table; corrected to the export report.

**An expected result changed on purpose.** Amit's test T30 expected a product with
no simulated data to give an empty report. We decided that no data means "unknown",
never "clear", so the rule changed first and the test follows the new rule. No
expected result was changed only to make a test pass.
