"""
Chapters become topics of a standard + subject (no board, no number). Chapters
that only differed by board (same standard, subject and name, ignoring case)
are merged into one; tests and notes tagged with a removed one get the kept one.
"""

from collections import defaultdict

from django.db import migrations


def merge(apps, schema_editor):
    Chapter = apps.get_model("academics", "Chapter")
    TestPaper = apps.get_model("learning", "TestPaper")
    Note = apps.get_model("learning", "Note")

    groups = defaultdict(list)
    for chapter in Chapter.objects.order_by("pk"):
        key = (chapter.standard_id, chapter.subject_id, chapter.name.strip().lower())
        groups[key].append(chapter)

    for chapters in groups.values():
        keep, *duplicates = chapters
        if not duplicates:
            continue
        # The merged topic is active if any of its copies was.
        if not keep.is_active and any(c.is_active for c in duplicates):
            keep.is_active = True
            keep.save(update_fields=["is_active"])
        dup_ids = [c.pk for c in duplicates]
        for Model in (TestPaper, Note):
            for item in Model._base_manager.filter(chapters__in=dup_ids).distinct():
                item.chapters.add(keep)
                item.chapters.remove(*dup_ids)
        Chapter.objects.filter(pk__in=dup_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0003_academic_year_per_board"),
        ("learning", "0004_remove_single_board_and_year"),
    ]

    # Merging can't be undone (the board copies are gone); going back keeps one copy.
    operations = [migrations.RunPython(merge, migrations.RunPython.noop)]
