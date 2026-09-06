import pytest
from backend.app.config import Settings, validate_environment

def test_settings_validation_required():
    settings = Settings()
    report = validate_environment(settings)
    assert report["valid"] is True
    assert "mongodb" in report["required"]
    assert "jwt" in report["required"]

def test_fernet_encryption_key_auto_generation():
    settings = Settings(ENCRYPTION_KEY="")
    fernet = settings.get_fernet()
    test_token = "secret_oauth_refresh_token_12345"
    encrypted = fernet.encrypt(test_token.encode()).decode()
    assert encrypted != test_token
    decrypted = fernet.decrypt(encrypted.encode()).decode()
    assert decrypted == test_token

def test_optional_features_status():
    settings = Settings(PEXELS_API_KEY="", GOOGLE_CLIENT_ID="")
    report = validate_environment(settings)
    assert report["features"]["google_oauth"]["status"] == "disabled"
    assert report["optional"]["pexels"]["status"] == "disabled"
