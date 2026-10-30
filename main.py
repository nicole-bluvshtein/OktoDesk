import itertools
from datetime import datetime
from pathlib import Path

from oktodesk import processing as proc
from oktodesk import reports
from oktodesk.context_managers import TicketWorkSession
from oktodesk.iterators import TicketCollection, iter_open_tickets, open_ticket_id_pipeline
from oktodesk.models import (
    User, Technician, ITManager, Priority, Status,
    EmailNotificationChannel, SlackNotificationChannel,
)
from oktodesk.observers import KnowledgeBaseRecorder, NotificationObserver
from oktodesk.repository import (
    load_tickets, load_knowledge_base, load_users, link_technicians_to_tickets,
)
from oktodesk.services import TicketService
from oktodesk.threaded_processing import ThreadSafeTicketQueue

DEMO_NOW = datetime(2026, 9, 17, 18, 0)


def stage1_demos():
    tickets_by_id, skipped = load_tickets("data/sample_data.jsonl")
    print(f"Loaded {len(tickets_by_id)} tickets, skipped {len(skipped)} rows")
    for line_number, reason in skipped:
        print(f"  - line {line_number}: {reason}")

    print()
    print("=== OOP demo ===")
    employee = User("u1", "Dana Cohen", "dana@example.com", "Finance")
    technician = Technician(
        "u5", "Roi Katz", "roi@example.com", "IT",
        technician_id="tech-201", expertise_areas=["network", "hardware"]
    )
    manager = ITManager(
        "u9", "Tal Avraham", "tal@example.com", "IT",
        technician_id="tech-mgr", expertise_areas=["security"],
        managed_technicians=["tech-201", "tech-202"]
    )

    print(employee)
    print(repr(employee))
    print(technician)
    print(repr(technician))
    print(manager)
    print(repr(manager))

    print()
    print("Polymorphic describe_capabilities() over a mixed list:")
    people = [employee, technician, manager]
    for person in people :
        print("-", person.describe_capabilities())

    print()
    print("=== Data structures & sorting demo ===")
    tickets = list(tickets_by_id.values())

    rebuilt_index = proc.tickets_by_id(tickets)
    categories = proc.category_set(tickets)
    counts_by_technician = proc.open_ticket_count_by_technician(tickets)

    print("Rebuilt index size:", len(rebuilt_index))
    print("Categories:", categories)
    print("Open ticket count by technician:", counts_by_technician)

    print()
    print("Top 3 named-function urgency score:")
    for t in proc.sort_by_urgency_score(tickets)[:3]:
        print(" -",t)

    print("Top 3 by tuple key (priority_rank, created_at):")
    for t in proc.sort_by_priority_then_created_at(tickets)[:3]:
        print(" -",t)

    print("Top 3 oldest first (sort_by_created_at):")
    for t in proc.sort_by_created_at(tickets)[:3]:
        print(" -", t)

    print()
    print("=== FIFO notification ===")
    queue = proc.new_notification_queue()
    for t in tickets[:3]:
        proc.enqueue_notification(queue, f"New ticket opened: #{t.ticket_id} - {t.title}")

    while True:
        notification = proc.dequeue_notification(queue)
        if notification is None:
            break
        print(notification)

    print()
    print("=== Priority queue (heapq) demo ===")
    priority_queue = proc.new_priority_queue()
    for t in tickets:
        proc.push_ticket(priority_queue, t)

    print("Tickets popped in priority order (most urgent first):")
    while True:
        ticket = proc.pop_most_urgent_ticket(priority_queue)
        if ticket is None:
            break
        print(f" - {ticket.priority.name:<8} {ticket}")

    print()
    print("=== TicketCollection / independent iterators demo ===")
    collection = TicketCollection(tickets)
    iterator_a = iter(collection)
    iterator_b = iter(collection)

    print("iterator_a first two:", next(iterator_a).ticket_id, next(iterator_a).ticket_id)
    print("iterator_b first one:", next(iterator_b).ticket_id)
    print("iterators are independent objects:", iterator_a is not iterator_b)

    print()
    print("=== iter_open_tickets generator demo ===")
    open_tickets_gen = iter_open_tickets(tickets)
    first = next(open_tickets_gen)
    print("first ticket (manual next()):", first.ticket_id)
    print("rest of open tickets (for loop):")
    for ticket in open_tickets_gen:
        print(" -", ticket.ticket_id)

    print("second full pass needs a brand-new generator:")
    for ticket in iter_open_tickets(tickets):
        print(" -", ticket.ticket_id)

    print()
    print("=== Lazy three-stage pipeline demo ===")
    visited_ids = []

    def _tracked_tickets():
        for ticket in tickets:
            visited_ids.append(ticket.ticket_id)
            yield ticket

    pipeline = open_ticket_id_pipeline(_tracked_tickets(), Priority.HIGH)
    first_two_ids = list(itertools.islice(pipeline, 2))
    never_touched_ids = [t.ticket_id for t in tickets if t.ticket_id not in visited_ids]

    print("first two open HIGH-priority ticket ids:", first_two_ids)
    print("tickets never even inspected by the pipeline:", never_touched_ids)

    print()
    print("=== TicketWorkSession context manager demo ===")
    normal_ticket = tickets_by_id[1]
    print("before normal session:", normal_ticket.status)
    with TicketWorkSession(normal_ticket, performed_by="tech-201") as session_ticket:
        session_ticket.close("tech-201", "Replaced the jammed paper tray")
    print("after normal session:", normal_ticket.status, "| closed at:", normal_ticket.closed_at)

    failing_ticket = tickets_by_id[4]
    print("before failing session:", failing_ticket.status)
    try:
        with TicketWorkSession(failing_ticket, performed_by="tech-201") as session_ticket:
            session_ticket.close("tech-201", "Swapped the network switch")
            raise RuntimeError("could not save the solution to the knowledge base")
    except RuntimeError as exc:
        print("caught:", exc)
    print("after failing session (rolled back):", failing_ticket.status,
          "| solution:", failing_ticket.solution, "| closed at:", failing_ticket.closed_at)

def build_service(vulnerability_client=None):
    tickets_by_id, _ = load_tickets("data/sample_data.jsonl")
    kb_by_id, _ = load_knowledge_base("data/knowledge_base.jsonl")
    users_by_id, _ = load_users("data/users.jsonl")
    technicians_by_id = link_technicians_to_tickets(users_by_id, tickets_by_id)

    kb_entries = list(kb_by_id.values())
    notifier = NotificationObserver(proc.new_notification_queue(),
                                    [EmailNotificationChannel(), SlackNotificationChannel()])
    waiting = [t for t in tickets_by_id.values() if t.status == Status.OPEN and t.assigned_to is None]
    service = TicketService(
        tickets_by_id, kb_entries,
        observers=[KnowledgeBaseRecorder(kb_entries), notifier],
        queue=ThreadSafeTicketQueue(waiting),
        vulnerability_client=vulnerability_client,
    )
    return service, users_by_id, technicians_by_id, notifier


def service_demo():
    print()
    print("=== Stage 2: the ticket lifecycle through TicketService ===")
    service, users_by_id, technicians_by_id, notifier = build_service()
    print(f"Queue: {len(service.queue)} waiting tickets | KB: {len(service.kb_entries)} entries")

    ticket = service.open_ticket("Printer jammed again", "Paper stuck in tray 2", "hardware",
                                 Priority.MEDIUM, opened_by="emp-104", now=DEMO_NOW)
    print("Opened:", ticket, "| queue now", len(service.queue))

    top_match, see_also = service.suggest_solutions(ticket.ticket_id)
    if top_match is not None:
        print("Suggested solution:", top_match.title, "->", top_match.solution_description)
        print("See also:", [entry.title for entry in see_also])

    technician = technicians_by_id["tech-201"]
    assigned = service.assign_next(technician)
    print(f"{technician.name} takes the most urgent ticket:", assigned)

    try:
        service.close_ticket(assigned.ticket_id, technician.technician_id, "")
    except ValueError as error:
        print("Close refused:", error, "| KB entries still", len(service.kb_entries))

    service.close_ticket(assigned.ticket_id, technician.technician_id,
                         "Restarted the AC unit and booked the vendor to replace the compressor")
    print("Closed:", assigned, "| KB entries now", len(service.kb_entries))
    print("New KB entry:", service.kb_entries[-1])

    print("Queued notifications, sent in order (FIFO):")
    print(notifier.dispatch(), "notifications sent")
    return service, users_by_id, technicians_by_id


def reports_demo(service, users_by_id, technicians_by_id):
    print()
    print("=== SLA and workload reports ===")
    tickets = list(service.tickets_by_id.values())
    print(f"SLA breaches at {DEMO_NOW:%d %b %Y %H:%M} (by priority, then hours over):")
    for ticket_id, priority, hours_over in reports.sla_breach_report(tickets, DEMO_NOW):
        print(f" - #{ticket_id:<3} {priority.name:<8} {hours_over:>6} h over")
    print("Open tickets per technician:", reports.workload_report(tickets))

    manager = users_by_id["emp-300"]
    path = Path("output") / "sla_report.json"
    path.parent.mkdir(exist_ok=True)
    reports.export_report(manager, tickets, DEMO_NOW, path)
    print(f"{manager.name} exported the report to {path}")
    try:
        reports.export_report(technicians_by_id["tech-202"], tickets, DEMO_NOW, path)
    except PermissionError as error:
        print("Export refused:", error)

def main():
    stage1_demos()
    service, users_by_id, technicians_by_id = service_demo()
    reports_demo(service, users_by_id, technicians_by_id)

if __name__ == "__main__":
    main()