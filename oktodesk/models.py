import re
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _parse_timestamp(value):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


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
                 closed_at=None, solution=None, activity_log=None):
        self.ticket_id = ticket_id
        self.title = title
        self.description = description
        self.category = self._required_text(category, "category")
        self.priority = priority
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
        self._status = self._validated_enum_value(value, Status, "status")

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
        return cls(
            ticket_id=data["ticket_id"],
            title=data["title"],
            description=data["description"],
            category=data["category"],
            priority=cls._enum_from_name(data["priority"], Priority, "priority"),
            status=cls._enum_from_name(data["status"], Status, "status"),
            opened_by=data["opened_by"],
            assigned_to=data.get("assigned_to"),
            created_at=_parse_timestamp(data.get("created_at")),
            updated_at=_parse_timestamp(data.get("updated_at")),
            closed_at=_parse_timestamp(data.get("closed_at")),
            solution=data.get("solution"),
            activity_log=data.get("activity_log", []),
        )

    def __str__(self):
        return f"Ticket(#{self.ticket_id}, {self.title}, {self.status.value}, {self.priority.value})"

    def __repr__(self):
        return (
            f"Ticket(ticket_id={self.ticket_id!r}, title={self.title!r}, category={self.category!r}, "
            f"priority={self.priority!r}, status={self.status!r}, opened_by={self.opened_by!r}, "
            f"assigned_to={self.assigned_to!r}, created_at={self.created_at!r})"
        )

    def add_log_entry(self, performed_by, action):
        entry = {"timestamp": datetime.now(), "performed_by": performed_by, "action": action}
        self.activity_log.append(entry)

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

    @property
    def is_overdue(self):
        if self.status == Status.CLOSED:
            return False
        elapsed_hours = (datetime.now() - self.created_at).total_seconds() / 3600
        return elapsed_hours > self.sla_target_hours(self.priority)

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
