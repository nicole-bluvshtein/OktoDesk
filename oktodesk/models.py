import re
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _parse_timestamp(value):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _hours_between(start, end):
    return (end - start).total_seconds() / 3600


class Status(Enum):
    OPEN = "פתוח"
    IN_PROGRESS = "בטיפול"
    WAITING_INFO = "ממתין למידע"
    CLOSED = "סגור"


class Priority(Enum):
    CRITICAL = "קריטי"
    HIGH = "גבוה"
    MEDIUM = "בינוני"
    LOW = "נמוך"


_PRIORITY_RANK = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}

_PRIORITY_SLA_HOURS = {
    Priority.CRITICAL: 1,
    Priority.HIGH: 4,
    Priority.MEDIUM: 8,
    Priority.LOW: 24,
}


class User:
    def __init__(self, user_id, name, email, department, role="employee"):
        self.user_id = user_id
        self.name = name
        self.email = email
        self.department = department
        self.role = role

    @property
    def email(self):
        return self._email

    @email.setter
    def email(self, value):
        if not _EMAIL_PATTERN.match(value):
            raise ValueError(f"Invalid email address: {value!r}")
        self._email = value

    @classmethod
    def from_dict(cls, data):
        return cls(
            user_id=data["user_id"],
            name=data["name"],
            email=data["email"],
            department=data["department"],
            role=data.get("role", "employee"),
        )

    def describe_capabilities(self):
        return f"{self.name} can open tickets and view their own tickets."

    def __str__(self):
        return f"User({self.name}, {self.role}, {self.department})"

    def __repr__(self):
        return (
            f"User(user_id={self.user_id!r}, name={self.name!r}, email={self.email!r}, "
            f"department={self.department!r}, role={self.role!r})"
        )


class Technician(User):
    def __init__(self, user_id, name, email, department, technician_id,
                 expertise_areas=None, assigned_tickets=None, role="technician"):
        super().__init__(user_id, name, email, department, role)
        self.technician_id = technician_id
        self.expertise_areas = set(expertise_areas) if expertise_areas else set()
        self.assigned_tickets = list(assigned_tickets) if assigned_tickets else []

    @classmethod
    def from_dict(cls, data):
        return cls(
            user_id=data["user_id"],
            name=data["name"],
            email=data["email"],
            department=data["department"],
            technician_id=data["technician_id"],
            expertise_areas=data.get("expertise_areas", []),
            assigned_tickets=data.get("assigned_tickets", []),
            role=data.get("role", "technician"),
        )

    def describe_capabilities(self):
        base = super().describe_capabilities()
        areas = ", ".join(sorted(self.expertise_areas)) if self.expertise_areas else "no listed specialties"
        return f"{base} As a technician, {self.name} can also view, edit and close tickets, and document solutions (expertise: {areas})."

    def __str__(self):
        return f"Technician({self.name}, {self.technician_id}, {sorted(self.expertise_areas)})"

    def __repr__(self):
        return (
            f"Technician(user_id={self.user_id!r}, name={self.name!r}, email={self.email!r}, "
            f"department={self.department!r}, technician_id={self.technician_id!r}, "
            f"expertise_areas={self.expertise_areas!r}, assigned_tickets={self.assigned_tickets!r})"
        )


class ITManager(Technician):
    def __init__(self, user_id, name, email, department, technician_id,
                 expertise_areas=None, assigned_tickets=None,
                 managed_technicians=None, can_export_reports=True, role="it_manager"):
        super().__init__(user_id, name, email, department, technician_id,
                          expertise_areas, assigned_tickets, role)
        self.managed_technicians = list(managed_technicians) if managed_technicians else []
        self.can_export_reports = can_export_reports

    @classmethod
    def from_dict(cls, data):
        return cls(
            user_id=data["user_id"],
            name=data["name"],
            email=data["email"],
            department=data["department"],
            technician_id=data["technician_id"],
            expertise_areas=data.get("expertise_areas", []),
            assigned_tickets=data.get("assigned_tickets", []),
            managed_technicians=data.get("managed_technicians", []),
            can_export_reports=data.get("can_export_reports", True),
            role=data.get("role", "it_manager"),
        )

    def describe_capabilities(self):
        base = super().describe_capabilities()
        count = len(self.managed_technicians)
        export = "can" if self.can_export_reports else "cannot"
        return f"{base} As an IT manager, {self.name} also oversees {count} technician(s), tracks SLA compliance, and {export} export reports."

    def __str__(self):
        return f"ITManager({self.name}, manages {len(self.managed_technicians)} technician(s))"

    def __repr__(self):
        return (
            f"ITManager(user_id={self.user_id!r}, name={self.name!r}, email={self.email!r}, "
            f"department={self.department!r}, technician_id={self.technician_id!r}, "
            f"expertise_areas={self.expertise_areas!r}, assigned_tickets={self.assigned_tickets!r}, "
            f"managed_technicians={self.managed_technicians!r}, can_export_reports={self.can_export_reports!r})"
        )


class Ticket:
    def __init__(self, ticket_id, title, description, category, priority, status,
                 opened_by, assigned_to=None, created_at=None, updated_at=None,
                 closed_at=None, solution=None, activity_log=None,
                 waiting_since=None, waiting_hours=0.0):
        self.ticket_id = ticket_id
        self.title = title
        self.description = description
        self.category = self._required_text(category, "category")
        self.priority = priority
        self.waiting_since = waiting_since
        self.waiting_hours = waiting_hours
        self._status = None
        self.status = status
        self.opened_by = self._required_text(opened_by, "opened_by")
        self.assigned_to = assigned_to
        self.created_at = created_at if created_at is not None else datetime.now()
        self.updated_at = updated_at if updated_at is not None else self.created_at
        self.closed_at = closed_at
        self.solution = solution
        self.activity_log = list(activity_log) if activity_log else []

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = self._required_text(value, "title")

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value):
        self._description = self._required_text(value, "description")

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, value):
        self._priority = self._validated_enum_value(value, Priority, "priority")

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        new_status = self._validated_enum_value(value, Status, "status")
        if self._status is not None and new_status != self._status:
            self._update_waiting_clock(new_status, datetime.now())
        self._status = new_status

    def _update_waiting_clock(self, new_status, now):
        if new_status == Status.WAITING_INFO:
            self.waiting_since = now
        elif self._status == Status.WAITING_INFO and self.waiting_since is not None:
            self.waiting_hours += _hours_between(self.waiting_since, now)
            self.waiting_since = None

    @staticmethod
    def _validated_enum_value(value, enum_cls, field_name):
        if isinstance(value, enum_cls):
            return value
        raise ValueError(f"Invalid {field_name}: {value!r} is not a valid {enum_cls.__name__}")

    @staticmethod
    def _enum_from_name(name, enum_cls, field_name):
        try:
            return enum_cls[name]
        except KeyError:
            allowed = ", ".join(member.name for member in enum_cls)
            raise ValueError(
                f"Invalid {field_name}: {name!r} (expected one of {allowed})"
            ) from None

    @staticmethod
    def _required_text(value, field_name):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value

    @classmethod
    def from_dict(cls, data):
        status = cls._enum_from_name(data["status"], Status, "status")
        created_at = _parse_timestamp(data.get("created_at"))
        updated_at = _parse_timestamp(data.get("updated_at"))
        waiting_since = _parse_timestamp(data.get("waiting_since"))
        if status == Status.WAITING_INFO and waiting_since is None:
            waiting_since = updated_at or created_at
        return cls(
            ticket_id=data["ticket_id"],
            title=data["title"],
            description=data["description"],
            category=data["category"],
            priority=cls._enum_from_name(data["priority"], Priority, "priority"),
            status=status,
            opened_by=data["opened_by"],
            assigned_to=data.get("assigned_to"),
            created_at=created_at,
            updated_at=updated_at,
            closed_at=_parse_timestamp(data.get("closed_at")),
            solution=data.get("solution"),
            activity_log=data.get("activity_log", []),
            waiting_since=waiting_since,
            waiting_hours=data.get("waiting_hours", 0.0),
        )

    def __str__(self):
        return f"Ticket(#{self.ticket_id}, {self.title}, {self.status.value}, {self.priority.value})"

    def __repr__(self):
        return (
            f"Ticket(ticket_id={self.ticket_id!r}, title={self.title!r}, category={self.category!r}, "
            f"priority={self.priority!r}, status={self.status!r}, opened_by={self.opened_by!r}, "
            f"assigned_to={self.assigned_to!r}, created_at={self.created_at!r})"
        )

    def add_log_entry(self, performed_by, action, timestamp=None):
        entry = {
            "timestamp": timestamp if timestamp is not None else datetime.now(),
            "performed_by": performed_by,
            "action": action,
        }
        self.activity_log.append(entry)

    def _record_change(self, performed_by, action, now=None):
        now = now if now is not None else datetime.now()
        self.updated_at = now
        self.add_log_entry(performed_by, action, timestamp=now)

    def _require_not_closed(self, action):
        if self.status == Status.CLOSED:
            raise ValueError(f"Cannot {action} ticket #{self.ticket_id}: it is already closed")

    def assign_to(self, technician):
        self._require_not_closed("assign")
        if self.assigned_to not in (None, technician.technician_id):
            raise ValueError(f"Ticket #{self.ticket_id} is already assigned to {self.assigned_to}")
        self.assigned_to = technician.technician_id
        if self.ticket_id not in technician.assigned_tickets:
            technician.assigned_tickets.append(self.ticket_id)
        self.status = Status.IN_PROGRESS
        self._record_change(technician.technician_id, f"assigned to {technician.technician_id}")

    def update_details(self, performed_by, *, title=None, description=None,
                       priority=None, status=None):
        self._require_not_closed("update")
        if status == Status.CLOSED:
            raise ValueError("Use close() to close a ticket, so a solution is recorded")
        requested = {"title": title, "description": description,
                     "priority": priority, "status": status}
        changes = {field: value for field, value in requested.items() if value is not None}
        if not changes:
            raise ValueError("update_details needs at least one field to change")
        previous = {field: getattr(self, field) for field in changes}
        try:
            for field, value in changes.items():
                setattr(self, field, value)
        except ValueError:
            for field, value in previous.items():
                setattr(self, field, value)
            raise
        self._record_change(performed_by, "updated " + ", ".join(changes))

    def close(self, performed_by, solution, now=None):
        self._require_not_closed("close")
        self.solution = self._required_text(solution, "solution")
        now = now if now is not None else datetime.now()
        self.status = Status.CLOSED
        self.closed_at = now
        self._record_change(performed_by, "closed with solution", now)

    def to_knowledge_base_entry(self, entry_id, keywords=None):
        if self.status != Status.CLOSED:
            raise ValueError(f"Ticket #{self.ticket_id} must be closed before it becomes a KB entry")
        title_words = {word.strip(".,:;!?()").lower() for word in self.title.split()
                       if len(word) > 2}
        return KnowledgeBaseEntry(
            entry_id=entry_id,
            title=self.title,
            problem_description=self.description,
            solution_description=self.solution,
            category=self.category,
            keywords=title_words | set(keywords or []),
            source_ticket_id=self.ticket_id,
            created_at=self.closed_at,
        )

    def activity_summary(self):
        counts = {}
        for entry in self.activity_log:
            performed_by = entry["performed_by"]
            counts[performed_by] = counts.get(performed_by, 0) + 1
        return counts

    @staticmethod
    def sla_target_hours(priority):
        return _PRIORITY_SLA_HOURS[priority]

    @property
    def priority_rank(self):
        return _PRIORITY_RANK[self.priority]

    def hours_over_sla(self, now=None):
        now = now if now is not None else datetime.now()
        end = self.closed_at if self.status == Status.CLOSED and self.closed_at else now
        paused_hours = self.waiting_hours
        if self.status == Status.WAITING_INFO and self.waiting_since is not None:
            paused_hours += _hours_between(self.waiting_since, now)
        clock_hours = _hours_between(self.created_at, end) - paused_hours
        return clock_hours - self.sla_target_hours(self.priority)

    def is_overdue_at(self, now):
        return self.status != Status.CLOSED and self.hours_over_sla(now) > 0

    @property
    def is_overdue(self):
        return self.is_overdue_at(datetime.now())

    def __lt__(self, other):
        return (self.priority_rank, self.created_at) < (other.priority_rank, other.created_at)


class KnowledgeBaseEntry:
    def __init__(self, entry_id, title, problem_description, solution_description,
                 category, keywords=None, source_ticket_id=None, created_at=None):
        self.entry_id = entry_id
        self.title = title
        self.problem_description = problem_description
        self.solution_description = solution_description
        self.category = category
        self.keywords = set(keywords) if keywords else set()
        self.source_ticket_id = source_ticket_id
        self.created_at = created_at if created_at is not None else datetime.now()

    @classmethod
    def from_dict(cls, data):
        return cls(
            entry_id=data["entry_id"],
            title=data["title"],
            problem_description=data["problem_description"],
            solution_description=data["solution_description"],
            category=data["category"],
            keywords=data.get("keywords", []),
            source_ticket_id=data.get("source_ticket_id"),
            created_at=_parse_timestamp(data.get("created_at")),
        )

    def matches_keyword(self, keyword):
        return keyword.lower() in {k.lower() for k in self.keywords}

    def __str__(self):
        return f"KnowledgeBaseEntry(#{self.entry_id}, {self.title}, {self.category})"

    def __repr__(self):
        return (
            f"KnowledgeBaseEntry(entry_id={self.entry_id!r}, title={self.title!r}, "
            f"category={self.category!r}, keywords={self.keywords!r}, "
            f"source_ticket_id={self.source_ticket_id!r})"
        )


class NotificationChannel(ABC):
    @abstractmethod
    def notify(self, ticket, message):
        pass


class EmailNotificationChannel(NotificationChannel):
    def notify(self, ticket, message):
        print(f"[Email] Ticket #{ticket.ticket_id}: {message}")


class SlackNotificationChannel(NotificationChannel):
    def notify(self, ticket, message):
        print(f"[Slack] Ticket #{ticket.ticket_id}: {message}")
