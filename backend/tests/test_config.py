import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("frontend_url", ["http://localhost:3000", "http://127.0.0.1:3000", "http://example.com"])
def test_production_rejects_non_public_or_insecure_frontend_url(frontend_url: str) -> None:
    with pytest.raises(ValidationError, match="FRONTEND_URL must be a public HTTPS URL"):
        Settings(app_env="production", frontend_url=frontend_url)


def test_production_accepts_public_https_frontend_url() -> None:
    settings = Settings(app_env="production", frontend_url="https://voltscopes.com")

    assert str(settings.frontend_url) == "https://voltscopes.com/"
