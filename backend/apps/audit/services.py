from django.db import models

from apps.audit.models import AuditLog
from apps.common.request_context import request_id_var


def record(
    action: str,
    *,
    actor,
    target: models.Model,
    changes: dict | None = None,
    ip: str | None = None,
) -> AuditLog:
    """
    Write one audit entry. Call it inside the same transaction as the change
    it describes, so the change and its record commit (or roll back) together.
    """
    return AuditLog.objects.create(
        action=action,
        actor=actor if getattr(actor, "pk", None) else None,
        target_type=target._meta.label,
        target_id=str(target.pk),
        changes=changes or {},
        ip_address=ip,
        request_id=request_id_var.get() if request_id_var.get() != "-" else "",
    )
