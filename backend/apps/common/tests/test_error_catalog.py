"""The frontend's error-code catalogue must match the code."""

import re
from pathlib import Path

from django.conf import settings

from apps.common.error_catalog import DOC_PATH, collect, render


def test_committed_catalogue_is_up_to_date():
    assert DOC_PATH.read_text(encoding="utf-8") == render(), (
        "Run `python manage.py error_codes` and commit docs/frontend/error-codes.md"
    )


def test_explicit_codes_in_source_are_catalogued():
    # Codes passed as code="..." (not via an exception class) must be listed too.
    catalogued = {e.code for e in collect()}
    explicit = set()
    for path in (Path(settings.BASE_DIR) / "apps").rglob("*.py"):
        if "tests" in path.parts:
            continue
        explicit |= {
            m.upper()
            for m in re.findall(
                r'code\s*=\s*"([A-Za-z_]+)"', path.read_text(encoding="utf-8")
            )
        }
    assert explicit <= catalogued, explicit - catalogued


def test_every_code_has_guidance():
    for entry in collect():
        assert entry.action and entry.status >= 400, entry
