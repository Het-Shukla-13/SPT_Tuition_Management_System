"""
Existing fee structures cover the main subjects (Subject.is_main). A subject
that is already an optional extra (add-on) on a structure stays optional and
is not also included. Fees and add-ons are left as they are.
"""

from django.db import migrations


def include_main(apps, schema_editor):
    Subject = apps.get_model("academics", "Subject")
    FeeStructure = apps.get_model("fees", "FeeStructure")
    FeeStructureAddOn = apps.get_model("fees", "FeeStructureAddOn")
    main_ids = list(Subject.objects.filter(is_main=True).values_list("pk", flat=True))
    for structure in FeeStructure.objects.all():
        optional = set(
            FeeStructureAddOn.objects.filter(structure=structure).values_list(
                "subject_id", flat=True
            )
        )
        structure.included_subjects.add(*[pk for pk in main_ids if pk not in optional])


def clear(apps, schema_editor):
    FeeStructure = apps.get_model("fees", "FeeStructure")
    for structure in FeeStructure.objects.all():
        structure.included_subjects.clear()


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0007_mark_main_subjects"),
        ("fees", "0003_structure_included_subjects"),
    ]

    operations = [
        migrations.RunPython(include_main, clear),
    ]
