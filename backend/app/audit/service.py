"""
Audit logging service.

Call write_audit_log(...) from any endpoint/service that performs a
sensitive mutation. This does NOT commit — callers should commit as part of
their existing transaction so the audit row is atomic with the change it
describes.
"""
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def write_audit_log(
    db: Session,
    *,
    organization_id: uuid.UUID,
    action: str,
    actor_user_id: Optional[uuid.UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> AuditLog:
    entry = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        metadata_json=metadata,
    )
    db.add(entry)
    db.flush()
    return entry
