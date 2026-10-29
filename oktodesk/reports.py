import json

from oktodesk import processing as proc


def overdue_tickets(tickets, now):
    return [ticket for ticket in tickets if ticket.is_overdue_at(now)]


def sla_breach_report(tickets, now):
    overdue = sorted(
        overdue_tickets(tickets, now),
        key=lambda ticket: (ticket.priority_rank, -ticket.hours_over_sla(now)),
    )
    return [(ticket.ticket_id, ticket.priority, round(ticket.hours_over_sla(now), 2))
            for ticket in overdue]


def workload_report(tickets):
    return proc.open_ticket_count_by_technician(tickets)


def export_report(requested_by, tickets, now, path):
    if not requested_by.can_export():
        raise PermissionError(f"{requested_by.name} is not allowed to export reports")
    report = {
        "generated_at": now.isoformat(),
        "generated_by": requested_by.user_id,
        "sla_breaches": [
            {"ticket_id": ticket_id, "priority": priority.name, "hours_over": hours_over}
            for ticket_id, priority, hours_over in sla_breach_report(tickets, now)
        ],
        "workload": workload_report(tickets),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report
