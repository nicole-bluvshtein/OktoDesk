import heapq
from collections import deque

from oktodesk.models import Status


def tickets_by_id(tickets):
    return {ticket.ticket_id: ticket for ticket in tickets}


def category_set(tickets):
    return {ticket.category for ticket in tickets}


def open_ticket_count_by_technician(tickets):
    counts = {}
    for ticket in tickets:
        if ticket.assigned_to is None or ticket.status == Status.CLOSED:
            continue
        counts[ticket.assigned_to] = counts.get(ticket.assigned_to, 0) + 1
    return counts


def add_expertise_area(technician, area):
    technician.expertise_areas.add(area)


def remove_expertise_area(technician, area):
    technician.expertise_areas.remove(area)


def discard_expertise_area(technician, area):
    technician.expertise_areas.discard(area)


def has_expertise_area(technician, area):
    return area in technician.expertise_areas


def shared_expertise_areas(technician_a, technician_b):
    return technician_a.expertise_areas & technician_b.expertise_areas


def combined_expertise_areas(technicians):
    areas = set()
    for technician in technicians:
        areas |= technician.expertise_areas
    return areas


def busiest_technician(counts):
    busiest_id, busiest_count = None, -1
    for technician_id, count in counts.items():
        if count > busiest_count:
            busiest_id, busiest_count = technician_id, count
    return busiest_id, busiest_count


def insert_ticket(index, ticket):
    if ticket.ticket_id in index:
        raise ValueError(f"duplicate ticket id: {ticket.ticket_id}")
    index[ticket.ticket_id] = ticket


def new_notification_queue():
    return deque()


def enqueue_notification(queue, message):
    queue.append(message)


def dequeue_notification(queue):
    if not queue:
        return None
    return queue.popleft()


def new_priority_queue():
    return []


def push_ticket(queue, ticket):
    heapq.heappush(queue, ticket)


def pop_most_urgent_ticket(queue):
    # min-heap: Ticket.__lt__ ranks lower priority_rank as more urgent
    if not queue:
        return None
    return heapq.heappop(queue)


def ticket_urgency_score(ticket):
    return ticket.priority_rank * 10**12 + ticket.created_at.timestamp()


def sort_by_urgency_score(tickets):
    return sorted(tickets, key=ticket_urgency_score)


def sort_by_created_at(tickets):
    return sorted(tickets, key=lambda t: t.created_at)


def sort_by_priority_then_created_at(tickets):
    return sorted(tickets, key=lambda t: (t.priority_rank, t.created_at))

def search_knowledge_base(entries, keyword, category=None):
    if not keyword or not keyword.strip():
        raise ValueError("keyword must be a non-empty string")
    return [
        entry for entry in entries
        if entry.matches_keyword(keyword.strip())
        and (category is None or entry.category == category)
    ]

def _match_score(entry, ticket_words, ticket_category):
    matching_keywords = len(entry.keywords & ticket_words)
    same_category = entry.category == ticket_category
    return matching_keywords, same_category, entry.created_at


def suggest_solutions(ticket, entries):
    if ticket.status == Status.CLOSED:
        raise ValueError(f"Ticket #{ticket.ticket_id} is closed; no suggestions needed")
    ticket_words = ticket.search_words
    candidates = [
        entry for entry in entries
        if entry.source_ticket_id != ticket.ticket_id and entry.keywords & ticket_words
    ]
    ranked = sorted(
        candidates,
        key=lambda entry: _match_score(entry, ticket_words, ticket.category),
        reverse=True,
    )
    if not ranked:
        return None, []
    top_match, *other_matches = ranked
    return top_match, other_matches


class TicketQueue:
    def __init__(self, tickets=None):
        self._heap = new_priority_queue()
        for ticket in tickets or []:
            self.push(ticket)

    def push(self, ticket):
        push_ticket(self._heap, ticket)

    def pop_most_urgent(self):
        return pop_most_urgent_ticket(self._heap)

    def rebuild(self):
        heapq.heapify(self._heap)

    def __len__(self):
        return len(self._heap)
