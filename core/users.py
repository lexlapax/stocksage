"""User resolution for CLI and future web request attribution."""

import getpass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from core.models import User


class UserResolutionError(ValueError):
    pass


def resolve_request_user(
    db: Session,
    *,
    username: str | None = None,
    user_id: int | None = None,
) -> User:
    if username is not None and user_id is not None:
        raise UserResolutionError("Pass either --user or --userid, not both.")

    now = datetime.now(UTC)
    if user_id is not None:
        user = db.get(User, user_id)
        if user is None:
            raise UserResolutionError(f"Unknown user id {user_id}.")
        user.last_seen_at = now
        db.commit()
        db.refresh(user)
        return user

    selected_username = _normalize_username(username or getpass.getuser())
    user = db.query(User).filter(User.username == selected_username).first()
    if user is None:
        user = User(username=selected_username, created_at=now, last_seen_at=now)
        db.add(user)
    else:
        user.last_seen_at = now
    db.commit()
    db.refresh(user)
    return user


def _normalize_username(username: str) -> str:
    normalized = username.strip()
    if not normalized:
        raise UserResolutionError("Username cannot be blank.")
    return normalized
