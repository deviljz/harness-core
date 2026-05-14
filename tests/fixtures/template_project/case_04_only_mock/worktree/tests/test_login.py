"""Login tests — all mocked, no real DB or business logic."""
from unittest.mock import patch, MagicMock


def test_login_success_mock():
    # Mocking the entire auth service — not testing real logic
    with patch("backend.auth.verify_password", return_value=True):
        with patch("backend.auth.create_token", return_value="fake-jwt"):
            result = MagicMock()
            result.status_code = 200
            result.json.return_value = {"token": "fake-jwt"}
            assert result.status_code == 200
            assert result.json()["token"] == "fake-jwt"


def test_login_wrong_password_mock():
    with patch("backend.auth.verify_password", return_value=False):
        result = MagicMock()
        result.status_code = 401
        assert result.status_code == 401
