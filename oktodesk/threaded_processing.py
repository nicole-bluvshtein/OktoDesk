import threading

from oktodesk.processing import TicketQueue


class ThreadSafeTicketQueue(TicketQueue):
    def __init__(self, tickets=None):
        self._lock = threading.Lock()
        super().__init__(tickets)

    def push(self, ticket):
        with self._lock:
            super().push(ticket)

    def pop_most_urgent(self):
        with self._lock:
            return super().pop_most_urgent()

    def rebuild(self):
        with self._lock:
            super().rebuild()

    def __len__(self):
        with self._lock:
            return super().__len__()


def run_assignment_race(service, technicians):
    results = {}
    start_together = threading.Barrier(len(technicians))

    def ask_for_next_ticket(technician):
        start_together.wait()
        results[technician.technician_id] = service.assign_next(technician)

    threads = [threading.Thread(target=ask_for_next_ticket, args=(technician,))
               for technician in technicians]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results
