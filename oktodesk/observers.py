from abc import ABC, abstractmethod

from oktodesk import processing as proc


class TicketObserver(ABC):
    @abstractmethod
    def on_ticket_opened(self, ticket):
        pass

    @abstractmethod
    def on_ticket_closed(self, ticket):
        pass


class KnowledgeBaseRecorder(TicketObserver):
    def __init__(self, entries):
        self.entries = entries

    def on_ticket_opened(self, ticket):
        pass

    def on_ticket_closed(self, ticket):
        keywords = list(ticket.linked_cves)
        if ticket.affected_product:
            keywords.append(ticket.affected_product)
        entry = ticket.to_knowledge_base_entry(self._next_entry_id(), keywords=keywords)
        self.entries.append(entry)

    def _next_entry_id(self):
        return max((entry.entry_id for entry in self.entries), default=0) + 1


class NotificationObserver(TicketObserver):
    def __init__(self, notification_queue, channels):
        self.notification_queue = notification_queue
        self.channels = list(channels)

    def on_ticket_opened(self, ticket):
        message = f"New {ticket.priority.name} ticket opened: {ticket.title}"
        if ticket.linked_cves:
            message += f" (critical vulnerabilities: {', '.join(ticket.linked_cves)})"
        proc.enqueue_notification(self.notification_queue, (ticket, message))

    def on_ticket_closed(self, ticket):
        message = f"Ticket closed with solution: {ticket.solution}"
        proc.enqueue_notification(self.notification_queue, (ticket, message))

    def dispatch(self):
        # FIFO: messages go out in the order the events happened
        sent = 0
        while True:
            notification = proc.dequeue_notification(self.notification_queue)
            if notification is None:
                return sent
            ticket, message = notification
            for channel in self.channels:
                channel.notify(ticket, message)
            sent += 1
