"""Shared pytest fixtures."""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.services.sms import LocmemSMSBackend


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def _isolate_state():
    """Rate-limit counters and the SMS outbox must not leak between tests."""
    cache.clear()
    LocmemSMSBackend.outbox.clear()
    yield
    cache.clear()
    LocmemSMSBackend.outbox.clear()
