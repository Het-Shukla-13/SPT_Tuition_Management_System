"""
Initial reference data for the institute (owner, 2026-11-07):
boards CBSE / GSEB / ICSE, standards 1st-10th, six subjects (English medium),
and the 2026-27 academic year as the current one. Admins can edit or extend
all of it through the API afterwards. Re-running is safe (get_or_create).
"""

import datetime

from django.db import migrations

BOARDS = [
    ("CBSE", "Central Board of Secondary Education"),
    ("GSEB", "Gujarat Secondary and Higher Secondary Education Board"),
    ("ICSE", "Indian Certificate of Secondary Education"),
]

ORDINALS = {1: "1st", 2: "2nd", 3: "3rd"}

SUBJECTS = [
    ("English", "ENG"),
    ("Mathematics", "MATH"),
    ("Science", "SCI"),
    ("Social Studies", "SST"),
    ("Gujarati", "GUJ"),
    ("Hindi", "HIN"),
]


def seed(apps, schema_editor):
    Board = apps.get_model("academics", "Board")
    Standard = apps.get_model("academics", "Standard")
    Subject = apps.get_model("academics", "Subject")
    AcademicYear = apps.get_model("academics", "AcademicYear")

    for code, name in BOARDS:
        Board.objects.get_or_create(code=code, defaults={"name": name})
    for level in range(1, 11):
        Standard.objects.get_or_create(
            level=level, defaults={"name": ORDINALS.get(level, f"{level}th")}
        )
    for name, code in SUBJECTS:
        Subject.objects.get_or_create(code=code, defaults={"name": name})
    if not AcademicYear.objects.exists():
        AcademicYear.objects.create(
            name="2026-27",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True,
        )


class Migration(migrations.Migration):
    dependencies = [("academics", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
