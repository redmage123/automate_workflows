"""
Data Access Object (DAO) package.

WHY: DAOs provide a clean separation between database operations and business logic,
making the codebase more testable and maintainable.
"""

from app.dao.base import BaseDAO
from app.dao.user import UserDAO
from app.dao.audit_log import AuditLogDAO

__all__ = ["BaseDAO", "UserDAO", "AuditLogDAO"]
