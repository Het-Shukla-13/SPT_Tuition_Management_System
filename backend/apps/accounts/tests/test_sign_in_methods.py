"""The login screen asks which sign-in methods exist (no login needed)."""

import pytest
from rest_framework.test import APIClient

URL = "/api/v1/auth/methods/"


@pytest.mark.django_db
def test_phone_only_when_an_sms_provider_is_set(settings):
    settings.SMS_BACKEND = "apps.accounts.services.sms.DisabledSMSBackend"
    settings.GOOGLE_OAUTH_CLIENT_ID = "client.apps.googleusercontent.com"
    data = APIClient().get(URL).json()["data"]
    assert data == {"email": True, "phone": False, "google": True}

    settings.SMS_BACKEND = "apps.accounts.services.sms.ConsoleSMSBackend"
    settings.GOOGLE_OAUTH_CLIENT_ID = ""
    data = APIClient().get(URL).json()["data"]
    assert data == {"email": True, "phone": True, "google": False}
