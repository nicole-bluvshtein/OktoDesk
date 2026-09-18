from oktodesk.repository import load_tickets
from oktodesk.models import User, Technician, ITManager
from oktodesk import processing as proc

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
        "u9", "TalAvrahan", "tal@company.com", "IT",
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
    print("Top 3 named-functon urgency score:")
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
        
if __name__ == "__main__":
    main()