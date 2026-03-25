from app.models.auth_user import AuthUser


ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"


def is_admin_user(user: AuthUser | None) -> bool:
    return bool(user and bool(getattr(user, "is_admin", False)))


def role_names_for_user(user: AuthUser | None) -> tuple[str, ...]:
    if user is None:
        return tuple()
    roles = [ROLE_OWNER]
    if is_admin_user(user):
        roles.append(ROLE_ADMIN)
    return tuple(roles)
