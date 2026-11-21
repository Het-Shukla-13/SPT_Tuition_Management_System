"""
Mark the main subjects (owner, 2026-11-21): Maths, Science, English and
Social Science. Matched by the seeded codes or common names, ignoring case,
so renamed or re-added rows are still found. Undo leaves every subject
unmarked.
"""

from django.db import migrations
from django.db.models import Q

MAIN_CODES = ["ENG", "MATH", "MATHS", "SCI", "SST", "SS"]
MAIN_NAMES = [
    "English",
    "Maths",
    "Mathematics",
    "Math",
    "Science",
    "Social Science",
    "Social Studies",
]


def main_subjects_q() -> Q:
    q = Q()
    for code in MAIN_CODES:
        q |= Q(code__iexact=code)
    for name in MAIN_NAMES:
        q |= Q(name__iexact=name)
    return q


def mark(apps, schema_editor):
    Subject = apps.get_model("academics", "Subject")
    Subject.objects.filter(main_subjects_q()).update(is_main=True)


def unmark(apps, schema_editor):
    Subject = apps.get_model("academics", "Subject")
    Subject.objects.update(is_main=False)


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0006_subject_is_main"),
    ]

    operations = [
        migrations.RunPython(mark, unmark),
    ]
