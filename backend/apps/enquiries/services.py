import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.enquiries.models import AdmissionEnquiry

logger = logging.getLogger(__name__)


def _notify_admins(enquiry: AdmissionEnquiry) -> None:
    """Best effort email to active admins. A failure never loses the enquiry."""
    recipients = list(
        User.objects.filter(
            role=User.Role.ADMIN, is_active=True, email__isnull=False
        ).values_list("email", flat=True)
    )
    if not recipients:
        return
    try:
        send_mail(
            subject=f"New admission enquiry: {enquiry.student_name}",
            message=render_to_string(
                "enquiries/email/new_enquiry.txt",
                {"enquiry": enquiry, "institute_name": settings.INSTITUTE_NAME},
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Could not email admins about enquiry %s", enquiry.pk)


def submit_enquiry(*, data: dict, ip: str | None) -> AdmissionEnquiry:
    with transaction.atomic():
        enquiry = AdmissionEnquiry.objects.create(**data, ip_address=ip)
        transaction.on_commit(lambda: _notify_admins(enquiry))
    logger.info("Admission enquiry received: id=%s", enquiry.pk)
    return enquiry


@transaction.atomic
def record_enquiry(*, actor: User, data: dict, ip=None) -> AdmissionEnquiry:
    """Staff record a walk-in / phone enquiry. No admin email: they're already here."""
    enquiry = AdmissionEnquiry.objects.create(
        **data, created_by=actor, handled_by=actor, ip_address=None
    )
    record(
        AuditLog.Action.ENQUIRY_CREATED,
        actor=actor,
        target=enquiry,
        changes={"source": enquiry.source, "status": enquiry.status},
        ip=ip,
    )
    return enquiry


@transaction.atomic
def update_enquiry(*, actor: User, enquiry: AdmissionEnquiry, changes: dict, ip=None):
    locked = AdmissionEnquiry.objects.select_for_update().get(pk=enquiry.pk)
    diff = {}
    for field, value in changes.items():
        if getattr(locked, field) != value:
            diff[field] = [str(getattr(locked, field)), str(value)]
            setattr(locked, field, value)
    if not diff:
        return locked
    locked.handled_by = actor
    locked.save(update_fields=[*diff, "handled_by", "updated_at"])
    record(
        AuditLog.Action.ENQUIRY_UPDATED, actor=actor, target=locked, changes=diff, ip=ip
    )
    return locked
