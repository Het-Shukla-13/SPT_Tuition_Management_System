"""Copy each test/note's single board into its boards list, and its year's name across."""

from django.db import migrations


def copy_forward(apps, schema_editor):
    for model_name in ("TestPaper", "Note"):
        Model = apps.get_model("learning", model_name)
        for item in Model._base_manager.select_related("academic_year").all():
            item.boards.add(item.board_id)
            item.academic_year_name = item.academic_year.name
            item.save(update_fields=["academic_year_name"])


def copy_back(apps, schema_editor):
    """Undo: first board back into the single board, the year from board + name."""
    AcademicYear = apps.get_model("academics", "AcademicYear")
    for model_name in ("TestPaper", "Note"):
        Model = apps.get_model("learning", model_name)
        for item in Model._base_manager.all():
            first = item.boards.order_by("pk").first()
            if first is None:
                continue
            item.board_id = first.pk
            year = AcademicYear.objects.filter(
                board_id=first.pk, name=item.academic_year_name
            ).first()
            if year is not None:
                item.academic_year_id = year.pk
            item.save(update_fields=["board", "academic_year"])


class Migration(migrations.Migration):
    dependencies = [
        ("learning", "0002_boards_year_name_start_time"),
        ("academics", "0003_academic_year_per_board"),
    ]

    operations = [migrations.RunPython(copy_forward, copy_back)]
