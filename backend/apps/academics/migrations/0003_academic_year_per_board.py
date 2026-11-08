"""
Academic years become per board (boards start/end on different dates).

The single institute-wide year is copied to one year per board (same name and
dates, editable afterwards), and everything that referred to it (student
history, test papers, notes) is re-pointed to its own board's copy.
"""

import django.db.models.deletion
from django.db import migrations, models


def split_years_per_board(apps, schema_editor):
    AcademicYear = apps.get_model("academics", "AcademicYear")
    Board = apps.get_model("academics", "Board")
    History = apps.get_model("students", "StudentAcademicHistory")
    TestPaper = apps.get_model("learning", "TestPaper")
    Note = apps.get_model("learning", "Note")

    boards = list(Board.objects.order_by("pk"))
    for year in list(AcademicYear.objects.filter(board__isnull=True)):
        copies = {}
        for i, board in enumerate(boards):
            if i == 0:
                year.board = board
                year.save(update_fields=["board"])
                copies[board.pk] = year
            else:
                copies[board.pk] = AcademicYear.objects.create(
                    board=board,
                    name=year.name,
                    start_date=year.start_date,
                    end_date=year.end_date,
                    is_current=year.is_current,
                    is_active=year.is_active,
                )
        for model in (History, TestPaper, Note):
            for row in model.objects.filter(academic_year=year):
                row.academic_year = copies[row.board_id]
                row.save(update_fields=["academic_year"])


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0002_seed_reference_data"),
        ("students", "0001_initial"),
        ("learning", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="academicyear", name="academic_years_single_current"
        ),
        migrations.AlterField(
            model_name="academicyear",
            name="name",
            field=models.CharField(help_text='e.g. "2026-27"', max_length=20),
        ),
        migrations.AddField(
            model_name="academicyear",
            name="board",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="academic_years",
                to="academics.board",
            ),
        ),
        migrations.RunPython(split_years_per_board, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="academicyear",
            name="board",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="academic_years",
                to="academics.board",
            ),
        ),
        migrations.AlterModelOptions(
            name="academicyear", options={"ordering": ["board__code", "-start_date"]}
        ),
        migrations.AddConstraint(
            model_name="academicyear",
            constraint=models.UniqueConstraint(
                fields=("board", "name"), name="academic_years_unique_name_per_board"
            ),
        ),
        migrations.AddConstraint(
            model_name="academicyear",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_current", True)),
                fields=("board",),
                name="academic_years_one_current_per_board",
            ),
        ),
    ]
