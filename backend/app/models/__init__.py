# Domain models package- All models must be imported here so Alembic's `autogenerate` can find them via `Base.metadata`.

from app.db.base import Base
from app.models.alert import Alert, Notification, ScheduledReport
from app.models.api_key import ApiKey
from app.models.dashboard import Dashboard, Widget
from app.models.event import Event, IngestionJob
from app.models.organization import Invitation, Organization
from app.models.user import User

__all__ = [
    "Base",
    "Organization",
    "Invitation",
    "User",
    "ApiKey",
    "Event",
    "IngestionJob",
    "Dashboard",
    "Widget",
    "Alert",
    "Notification",
    "ScheduledReport",
]
