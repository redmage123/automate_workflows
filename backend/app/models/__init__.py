"""
Database models package.

WHY: Centralizing model imports ensures Alembic can discover all models
for migration generation and makes it easier to import models elsewhere.
"""

from app.models.base import Base, TimestampMixin, PrimaryKeyMixin
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog, AuditAction
from app.models.verification_token import VerificationToken, TokenType
from app.models.project import Project, ProjectStatus, ProjectPriority
from app.models.proposal import Proposal, ProposalStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.workflow import (
    N8nEnvironment,
    WorkflowTemplate,
    WorkflowInstance,
    WorkflowStatus,
    ExecutionLog,
    ExecutionStatus,
)
from app.models.ticket import (
    Ticket,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    TicketComment,
    TicketAttachment,
    SLA_CONFIG,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "PrimaryKeyMixin",
    "Organization",
    "User",
    "UserRole",
    "AuditLog",
    "AuditAction",
    "VerificationToken",
    "TokenType",
    "Project",
    "ProjectStatus",
    "ProjectPriority",
    "Proposal",
    "ProposalStatus",
    "Invoice",
    "InvoiceStatus",
    "N8nEnvironment",
    "WorkflowTemplate",
    "WorkflowInstance",
    "WorkflowStatus",
    "ExecutionLog",
    "ExecutionStatus",
    "Ticket",
    "TicketStatus",
    "TicketPriority",
    "TicketCategory",
    "TicketComment",
    "TicketAttachment",
    "SLA_CONFIG",
]
