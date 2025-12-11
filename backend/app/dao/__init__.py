"""
Data Access Object (DAO) package.

WHY: DAOs provide a clean separation between database operations and business logic,
making the codebase more testable and maintainable.
"""

from app.dao.base import BaseDAO
from app.dao.user import UserDAO
from app.dao.audit_log import AuditLogDAO
from app.dao.project import ProjectDAO
from app.dao.proposal import ProposalDAO
from app.dao.invoice import InvoiceDAO
from app.dao.n8n_environment import N8nEnvironmentDAO
from app.dao.workflow_template import WorkflowTemplateDAO
from app.dao.workflow_instance import WorkflowInstanceDAO
from app.dao.execution_log import ExecutionLogDAO
from app.dao.ticket import TicketDAO, TicketCommentDAO, TicketAttachmentDAO

__all__ = [
    "BaseDAO",
    "UserDAO",
    "AuditLogDAO",
    "ProjectDAO",
    "ProposalDAO",
    "InvoiceDAO",
    "N8nEnvironmentDAO",
    "WorkflowTemplateDAO",
    "WorkflowInstanceDAO",
    "ExecutionLogDAO",
    "TicketDAO",
    "TicketCommentDAO",
    "TicketAttachmentDAO",
]
