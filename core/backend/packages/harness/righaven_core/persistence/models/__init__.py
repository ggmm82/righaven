"""ORM model registration entry point.

Importing this module ensures all ORM models are registered with
``Base.metadata`` so Alembic autogenerate detects every table.

The actual ORM classes have moved to entity-specific subpackages:
- ``righaven_core.persistence.thread_meta``
- ``righaven_core.persistence.run``
- ``righaven_core.persistence.feedback``
- ``righaven_core.persistence.user``

``RunEventRow`` remains in ``righaven_core.persistence.models.run_event`` because
its storage implementation lives in ``righaven_core.runtime.events.store.db`` and
there is no matching entity directory.
"""

from righaven_core.persistence.agents.model import AgentRow
from righaven_core.persistence.channel_connections.model import (
    ChannelConnectionRow,
    ChannelConversationRow,
    ChannelCredentialRow,
    ChannelOAuthStateRow,
)
from righaven_core.persistence.channel_leases.model import ChannelLeaseRow
from righaven_core.persistence.channel_thread_bindings.model import ChannelThreadBindingRow
from righaven_core.persistence.feedback.model import FeedbackRow
from righaven_core.persistence.login_throttle.model import LoginThrottleRow
from righaven_core.persistence.managed_subagents.model import ManagedSubagentRow
from righaven_core.persistence.mcp_tasks.model import McpTaskRow
from righaven_core.persistence.models.run_event import RunEventRow, RunEventThreadSeqRow
from righaven_core.persistence.notification_deliveries.model import NotificationDeliveryRow
from righaven_core.persistence.personal_access_tokens.model import PersonalAccessTokenRow
from righaven_core.persistence.projects.model import ProjectDocumentRow, ProjectRow
from righaven_core.persistence.run.model import RunChangeClockRow, RunRow
from righaven_core.persistence.scheduled_task_events.model import ScheduledTaskEventRow
from righaven_core.persistence.scheduled_task_runs.model import ScheduledTaskRunRow
from righaven_core.persistence.scheduled_tasks.model import ScheduledTaskRow
from righaven_core.persistence.subagent_batches.model import SubagentBatchItemRow, SubagentBatchRow
from righaven_core.persistence.thread_meta.model import ThreadMetaRow
from righaven_core.persistence.thread_reads.model import ThreadReadMarkerRow, ThreadReadVersionRow
from righaven_core.persistence.user.im_notifications import ImNotificationPreferenceRow
from righaven_core.persistence.user.model import UserPreferenceRow, UserRow
from righaven_core.persistence.webhook_delivery.model import WebhookDeliveryRow

__all__ = [
    "AgentRow",
    "ChannelConnectionRow",
    "ChannelConversationRow",
    "ChannelCredentialRow",
    "ChannelLeaseRow",
    "ChannelOAuthStateRow",
    "ChannelThreadBindingRow",
    "FeedbackRow",
    "LoginThrottleRow",
    "McpTaskRow",
    "ManagedSubagentRow",
    "NotificationDeliveryRow",
    "PersonalAccessTokenRow",
    "ProjectDocumentRow",
    "ProjectRow",
    "RunEventRow",
    "RunEventThreadSeqRow",
    "RunChangeClockRow",
    "RunRow",
    "ScheduledTaskEventRow",
    "ScheduledTaskRow",
    "ScheduledTaskRunRow",
    "SubagentBatchRow",
    "SubagentBatchItemRow",
    "ThreadMetaRow",
    "ThreadReadMarkerRow",
    "ThreadReadVersionRow",
    "UserPreferenceRow",
    "ImNotificationPreferenceRow",
    "UserRow",
    "WebhookDeliveryRow",
]
