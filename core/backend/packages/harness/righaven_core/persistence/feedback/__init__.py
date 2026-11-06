"""Feedback persistence — ORM and SQL repository."""

from righaven_core.persistence.feedback.model import FeedbackRow
from righaven_core.persistence.feedback.sql import FeedbackRepository

__all__ = ["FeedbackRepository", "FeedbackRow"]
