import pytest

from oktodesk.models import User, Priority


# T7
@pytest.mark.parametrize("field, bad_value", [
    ("title", ""),
    ("title", "   "),
    ("description", ""),
    ("category", ""),
    ("opened_by", ""),
])
def test_ticket_rejects_empty_required_text(make_ticket, field, bad_value):
    with pytest.raises(ValueError, match=f"{field} must be a non-empty string"):
        make_ticket(**{field: bad_value})


def test_updating_title_to_empty_is_rejected(make_ticket):
    ticket = make_ticket()
    with pytest.raises(ValueError):
        ticket.title = ""
    assert ticket.title == "Test ticket 1"


def test_ticket_rejects_priority_that_is_not_an_enum(make_ticket):
    with pytest.raises(ValueError, match="Invalid priority"):
        make_ticket(priority="HIGH")
    assert Priority.HIGH.name == "HIGH"


def test_user_rejects_bad_email():
    with pytest.raises(ValueError):
        User("u1", "Dana Cohen", "not-an-email", "Finance")
