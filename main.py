import itertools

from oktodesk.repository import load_tickets
from oktodesk.models import User, Technician, ITManager, Priority, Status
from oktodesk import processing as proc
from oktodesk.iterators import TicketCollection, iter_open_tickets, open_ticket_id_pipeline
from oktodesk.context_managers import TicketWorkSession

def main():
    tickets_by_id, skipped = load_tickets("data/sample_data.jsonl")
    print(f"Loaded {len(tickets_by_id)} tickets, skipped {len(skipped)} rows")
    for line_number, reason in skipped:
        print(f"  - line {line_number}: {reason}")

    print()
    print("=== OOP demo ===")
    employee = User("u1", "Dana Cohen", "dana@company.com", "Finance")
    technician = Technician(
        "u5", "Roi Katz", "roi@company.com", "IT",
        technician_id="tech-201", expertise_areas=["network", "hardware"]
    )
    manager = ITManager(
        "u9", "Tal Avrahan", "tal@company.com", "IT",
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
    with TicketWorkSession(normal_ticket, actor="tech-201") as session_ticket:
        session_ticket.solution = "Replaced the jammed paper tray"
        session_ticket.status = Status.CLOSED
    print("after normal session:", normal_ticket.status)

    failing_ticket = tickets_by_id[4]
    print("before failing session:", failing_ticket.status)
    try:
        with TicketWorkSession(failing_ticket, actor="tech-201"):
            raise RuntimeError("technician had to leave mid-repair")
    except RuntimeError as exc:
        print("caught:", exc)
    print("after failing session (rolled back):", failing_ticket.status)

if __name__ == "__main__":
    main()