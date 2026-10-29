from oktodesk import processing as proc
from oktodesk.models import Priority


# T4
def test_heap_pops_critical_first_and_older_first_on_a_tie(make_ticket):
    newer_high = make_ticket(1, Priority.HIGH, hours_ago=1)
    critical = make_ticket(2, Priority.CRITICAL, hours_ago=1)
    older_high = make_ticket(3, Priority.HIGH, hours_ago=5)
    low = make_ticket(4, Priority.LOW, hours_ago=50)

    queue = proc.new_priority_queue()
    for ticket in [newer_high, critical, older_high, low]:
        proc.push_ticket(queue, ticket)

    popped = [proc.pop_most_urgent_ticket(queue).ticket_id for _ in range(4)]
    assert popped == [2, 3, 1, 4]
    assert proc.pop_most_urgent_ticket(queue) is None


# T6
def test_capabilities_build_up_through_the_hierarchy(employee, technician, manager):
    employee_text = employee.describe_capabilities()
    technician_text = technician.describe_capabilities()
    manager_text = manager.describe_capabilities()

    assert employee_text == "Dana Cohen can open tickets and view their own tickets."
    assert technician_text.startswith("Roi Katz can open tickets")
    assert "can also view, edit and close tickets" in technician_text
    assert "As a technician" in manager_text
    assert "can export reports" in manager_text
