"""Copy each student's single guardian into the new guardians list (as the main contact)."""

from django.db import migrations


def copy_forward(apps, schema_editor):
    StudentProfile = apps.get_model("students", "StudentProfile")
    StudentGuardian = apps.get_model("students", "StudentGuardian")
    rows = []
    # _base_manager: every row, including any soft-deleted ones.
    for s in StudentProfile._base_manager.all():
        if not (s.guardian_name or s.guardian_phone or s.guardian_email):
            continue
        rows.append(
            StudentGuardian(
                student_id=s.pk,
                name=s.guardian_name or s.guardian_relation or "Guardian",
                relation=s.guardian_relation,
                phone=s.guardian_phone,
                email=s.guardian_email,
                position=0,
            )
        )
    StudentGuardian.objects.bulk_create(rows)


def copy_back(apps, schema_editor):
    """Put the main contact back into the old single-guardian columns."""
    StudentProfile = apps.get_model("students", "StudentProfile")
    StudentGuardian = apps.get_model("students", "StudentGuardian")
    for g in StudentGuardian.objects.order_by("student_id", "position", "id"):
        student = StudentProfile._base_manager.filter(pk=g.student_id).first()
        if student is None or student.guardian_name:
            continue
        student.guardian_name = g.name
        student.guardian_relation = g.relation
        student.guardian_phone = g.phone
        student.guardian_email = g.email
        student.save(
            update_fields=[
                "guardian_name",
                "guardian_relation",
                "guardian_phone",
                "guardian_email",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [("students", "0004_student_guardians")]

    operations = [migrations.RunPython(copy_forward, copy_back)]
