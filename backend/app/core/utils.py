"""
Small shared utilities with no business-logic dependencies of their own,
safe to import from any layer (models, services, API).
"""
import re
import uuid


def slugify(name: str) -> str:
    """Lowercase, hyphenated slug. Falls back to a short random id if the
    input has no alphanumeric characters at all."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or str(uuid.uuid4())[:8]
