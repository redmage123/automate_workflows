"""
Base model class for all SQLAlchemy models.

WHY: Centralizing common model functionality (timestamps, ID) in a base class
ensures consistency across all models and reduces code duplication.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    WHY: DeclarativeBase provides the foundation for SQLAlchemy 2.0 models
    with improved type hints and async support.
    """

    pass


class TimestampMixin:
    """
    Mixin to add created_at and updated_at timestamps to models.

    WHY: Most models need timestamp tracking for audit trails and debugging.
    Using a mixin ensures consistent timestamp behavior across all models.
    """

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PrimaryKeyMixin:
    """
    Mixin to add an integer primary key to models.

    WHY: Most models use an auto-incrementing integer primary key.
    This mixin ensures consistency and reduces boilerplate.
    """

    id = Column(Integer, primary_key=True, index=True)
