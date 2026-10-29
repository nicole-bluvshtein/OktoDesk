from oktodesk.models import User, Technician, ITManager

_USER_CLASSES_BY_ROLE = {
    "employee": User,
    "technician": Technician,
    "it_manager": ITManager,
}


def create_user(record):
    role = record.get("role")
    user_class = _USER_CLASSES_BY_ROLE.get(role)
    if user_class is None:
        allowed = ", ".join(_USER_CLASSES_BY_ROLE)
        raise ValueError(
            f"Unknown role {role!r} for user {record.get('user_id')!r} (expected one of {allowed})"
        )
    return user_class.from_dict(record)
