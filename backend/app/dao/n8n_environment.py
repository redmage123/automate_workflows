"""
N8n Environment Data Access Object (DAO).

WHAT: Database operations for the N8nEnvironment model.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for n8n environment operations
3. Enforces org-scoping for multi-tenancy security
4. Handles encryption/decryption of API keys

HOW: Extends BaseDAO with environment-specific queries:
- API key encryption on create/update
- Environment health status tracking
- Active environment filtering

Security Considerations (OWASP):
- A01: Org-scoping on all queries
- A02: API key encryption via EncryptionService
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.models.workflow import N8nEnvironment
from app.services.encryption_service import get_encryption_service


class N8nEnvironmentDAO(BaseDAO[N8nEnvironment]):
    """
    Data Access Object for N8nEnvironment model.

    WHAT: Provides CRUD and query operations for n8n environments.

    WHY: Centralizes all n8n environment database operations:
    - Enforces org_id scoping for security
    - Handles API key encryption automatically
    - Provides environment-specific queries

    HOW: Extends BaseDAO with specialized methods.
    API keys are encrypted on create/update and can be decrypted on demand.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize N8nEnvironmentDAO.

        Args:
            session: Async database session
        """
        super().__init__(N8nEnvironment, session)
        self._encryption_service = get_encryption_service()

    async def create_environment(
        self,
        org_id: int,
        name: str,
        base_url: str,
        api_key: str,
        webhook_url: Optional[str] = None,
        is_active: bool = True,
    ) -> N8nEnvironment:
        """
        Create a new n8n environment with encrypted API key.

        WHAT: Creates an n8n environment configuration.

        WHY: Centralized creation ensures:
        - API key is always encrypted before storage
        - Org-scoping is enforced
        - Unique name constraint is respected

        HOW: Encrypts API key using Fernet, then stores environment.

        Args:
            org_id: Organization ID that owns this environment
            name: Display name for the environment
            base_url: Base URL of n8n instance
            api_key: Plain text API key (will be encrypted)
            webhook_url: Optional webhook URL for callbacks
            is_active: Whether environment is active (default True)

        Returns:
            Created N8nEnvironment instance

        Raises:
            IntegrityError: If name already exists for org
            EncryptionError: If encryption fails
        """
        encrypted_key = self._encryption_service.encrypt(api_key)

        return await self.create(
            org_id=org_id,
            name=name,
            base_url=base_url,
            api_key_encrypted=encrypted_key,
            webhook_url=webhook_url,
            is_active=is_active,
        )

    async def update_environment(
        self,
        environment_id: int,
        org_id: int,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        webhook_url: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[N8nEnvironment]:
        """
        Update an n8n environment.

        WHAT: Updates environment configuration.

        WHY: Centralized update ensures:
        - API key is encrypted if changed
        - Org-scoping is enforced
        - Only provided fields are updated

        Args:
            environment_id: Environment ID to update
            org_id: Organization ID for security check
            name: New name (if changing)
            base_url: New base URL (if changing)
            api_key: New API key in plain text (if changing)
            webhook_url: New webhook URL (if changing)
            is_active: New active status (if changing)

        Returns:
            Updated environment or None if not found
        """
        environment = await self.get_by_id_and_org(environment_id, org_id)
        if not environment:
            return None

        if name is not None:
            environment.name = name
        if base_url is not None:
            environment.base_url = base_url
        if api_key is not None:
            environment.api_key_encrypted = self._encryption_service.encrypt(api_key)
        if webhook_url is not None:
            environment.webhook_url = webhook_url
        if is_active is not None:
            environment.is_active = is_active

        environment.updated_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(environment)
        return environment

    async def get_active_environments(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[N8nEnvironment]:
        """
        Get all active n8n environments for an organization.

        WHAT: Filters environments by active status.

        WHY: Inactive environments should not be used for
        new workflow deployments.

        Args:
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of active environments
        """
        result = await self.session.execute(
            select(N8nEnvironment)
            .where(
                N8nEnvironment.org_id == org_id,
                N8nEnvironment.is_active == True,
            )
            .order_by(N8nEnvironment.name)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_name(
        self,
        org_id: int,
        name: str,
    ) -> Optional[N8nEnvironment]:
        """
        Get an environment by name within an organization.

        WHAT: Lookup environment by unique name.

        WHY: Names must be unique within an org, so this
        provides an alternative lookup method.

        Args:
            org_id: Organization ID
            name: Environment name

        Returns:
            Environment if found, None otherwise
        """
        result = await self.session.execute(
            select(N8nEnvironment)
            .where(
                N8nEnvironment.org_id == org_id,
                N8nEnvironment.name == name,
            )
        )
        return result.scalar_one_or_none()

    def get_decrypted_api_key(self, environment: N8nEnvironment) -> str:
        """
        Decrypt the API key for an environment.

        WHAT: Decrypts the stored API key.

        WHY: API keys are stored encrypted (OWASP A02) and
        only decrypted when needed for API calls.

        Args:
            environment: N8nEnvironment instance

        Returns:
            Decrypted API key

        Raises:
            EncryptionError: If decryption fails
        """
        return self._encryption_service.decrypt(environment.api_key_encrypted)

    async def deactivate(
        self,
        environment_id: int,
        org_id: int,
    ) -> Optional[N8nEnvironment]:
        """
        Deactivate an n8n environment.

        WHAT: Sets is_active to False.

        WHY: Soft-disable environment without deleting.
        Preserves historical data and workflow associations.

        Args:
            environment_id: Environment ID
            org_id: Organization ID for security

        Returns:
            Updated environment or None if not found
        """
        return await self.update_environment(
            environment_id=environment_id,
            org_id=org_id,
            is_active=False,
        )

    async def activate(
        self,
        environment_id: int,
        org_id: int,
    ) -> Optional[N8nEnvironment]:
        """
        Activate an n8n environment.

        WHAT: Sets is_active to True.

        WHY: Re-enable a previously deactivated environment.

        Args:
            environment_id: Environment ID
            org_id: Organization ID for security

        Returns:
            Updated environment or None if not found
        """
        return await self.update_environment(
            environment_id=environment_id,
            org_id=org_id,
            is_active=True,
        )

    async def count_by_org(self, org_id: int) -> int:
        """
        Count environments for an organization.

        WHAT: Returns total number of environments.

        WHY: Useful for limits/quotas and dashboard stats.

        Args:
            org_id: Organization ID

        Returns:
            Number of environments
        """
        return await self.count(org_id=org_id)

    async def count_active_by_org(self, org_id: int) -> int:
        """
        Count active environments for an organization.

        WHAT: Returns number of active environments.

        WHY: Dashboard statistics.

        Args:
            org_id: Organization ID

        Returns:
            Number of active environments
        """
        return await self.count(org_id=org_id, is_active=True)
