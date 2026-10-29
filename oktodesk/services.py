import logging

from oktodesk import processing as proc
from oktodesk.api_client import VulnerabilityServiceError
from oktodesk.context_managers import TicketWorkSession
from oktodesk.models import Ticket, Status, Priority

logger = logging.getLogger(__name__)


class TicketService:
    def __init__(self, tickets_by_id, kb_entries, observers, queue, vulnerability_client=None):
        self.tickets_by_id = tickets_by_id
        self.kb_entries = kb_entries
        self.observers = list(observers)
        self.queue = queue
        self.vulnerability_client = vulnerability_client
        self._vulnerability_reports = {}

    def open_ticket(self, title, description, category, priority, opened_by,
                    affected_product=None, now=None):
        ticket = Ticket(
            ticket_id=self._next_ticket_id(), title=title, description=description,
            category=category, priority=priority, status=Status.OPEN,
            opened_by=opened_by, created_at=now, affected_product=affected_product,
        )
        ticket.add_log_entry(opened_by, "ticket opened", timestamp=ticket.created_at)
        self.check_vulnerabilities(ticket)
        self.tickets_by_id[ticket.ticket_id] = ticket
        self.queue.push(ticket)
        for observer in self.observers:
            observer.on_ticket_opened(ticket)
        return ticket

    def assign_next(self, technician):
        while True:
            ticket = self.queue.pop_most_urgent()
            if ticket is None:
                return None
            if ticket.status == Status.OPEN and ticket.assigned_to is None:
                ticket.assign_to(technician)
                return ticket

    def close_ticket(self, ticket_id, performed_by, solution):
        ticket = self.get_ticket(ticket_id)
        with TicketWorkSession(ticket, performed_by):
            ticket.close(performed_by, solution)
        for observer in self.observers:
            observer.on_ticket_closed(ticket)
        return ticket

    def suggest_solutions(self, ticket_id):
        return proc.suggest_solutions(self.get_ticket(ticket_id), self.kb_entries)

    def check_vulnerabilities(self, ticket):
        product = ticket.affected_product
        if product is None or self.vulnerability_client is None:
            return None
        report = self._vulnerability_reports.get(product.lower())
        if report is None:
            try:
                report = self.vulnerability_client.find_recent_critical(product)
            except VulnerabilityServiceError as error:
                logger.warning("Vulnerability check for %r failed: %s", product, error)
                ticket.vulnerability_check = "unknown"
                ticket.add_log_entry("system", f"vulnerability check unknown for {product}")
                return None
            self._vulnerability_reports[product.lower()] = report
        self._apply_report(ticket, report)
        return report

    def apply_vulnerability_reports(self, reports):
        for report in reports:
            self._vulnerability_reports[report.product.lower()] = report
            for ticket in self.tickets_by_id.values():
                if (ticket.status != Status.CLOSED and ticket.affected_product
                        and ticket.affected_product.lower() == report.product.lower()):
                    self._apply_report(ticket, report)
        self.queue.rebuild()

    def get_ticket(self, ticket_id):
        try:
            return self.tickets_by_id[ticket_id]
        except KeyError:
            raise ValueError(f"No ticket #{ticket_id}") from None

    def _apply_report(self, ticket, report):
        if report.is_vulnerable:
            worst = sorted(report.vulnerabilities, key=lambda cve: cve.score, reverse=True)[:3]
            ticket.linked_cves = [cve.cve_id for cve in worst]
            ticket.vulnerability_check = "vulnerable"
            ticket.raise_priority_to(Priority.HIGH, "system")
            ticket.add_log_entry("system", f"critical vulnerabilities in {report.product}: "
                                           f"{', '.join(ticket.linked_cves)}")
        else:
            ticket.vulnerability_check = "clear"
            ticket.add_log_entry("system", f"no recent critical vulnerabilities in {report.product}")

    def _next_ticket_id(self):
        return max(self.tickets_by_id, default=0) + 1
