"""
Database models package.

WHY: Centralizing model imports ensures Alembic can discover all models
for migration generation and makes it easier to import models elsewhere.
"""

from app.models.base import Base, TimestampMixin, PrimaryKeyMixin
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog, AuditAction

# TODO: Import additional models as they are created
# from app.models.project import Project, ProjectStatus
# from app.models.proposal import Proposal, ProposalStatus
# from app.models.invoice import Invoice, InvoiceStatus, InvoiceType
# from app.models.ticket import Ticket, TicketStatus, TicketPriority
# from app.models.workflow import (
#     WorkflowTemplate,
#     WorkflowInstance,
#     WorkflowInstanceStatus,
#     ExecutionLog,
#     ExecutionStatus,
# )
# from app.models.n8n_environment import N8nEnvironment

__all__ = [
    "Base",
    "TimestampMixin",
    "PrimaryKeyMixin",
    "Organization",
    "User",
    "UserRole",
    "AuditLog",
    "AuditAction",
    # Add additional models here as they are created
]
