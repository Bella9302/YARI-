"""First-time setup: owner account creation, secret key, and demo login hints."""
from app import _load_secret_key, create_app
from app.db import query
from app.seed import seed
from tests.conftest import login


def fresh_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "s.sqlite"), "UPLOAD_FOLDER": str(tmp_path),
                       "CSRF_ENABLED": False})


def test_create_owner_command_makes_a_working_login(tmp_path):
    app = fresh_app(tmp_path)
    result = app.test_cli_runner().invoke(args=["create-owner", "--name", "Bella Owner", "--email", "bella@example.com",
                                                "--password", "longpassword"])
    assert result.exit_code == 0, result.output
    with app.app_context():
        user = query("SELECT role FROM users WHERE email = 'bella@example.com'", one=True)
        assert user["role"] == "owner"
    r = login(app.test_client(), "bella@example.com", "longpassword")
    assert "Dashboard" in r.get_data(as_text=True)


def test_create_owner_rejects_short_password_and_duplicates(tmp_path):
    app = fresh_app(tmp_path)
    runner = app.test_cli_runner()
    short = runner.invoke(args=["create-owner", "--name", "A", "--email", "a@example.com", "--password", "short"])
    assert short.exit_code != 0 and "at least 8" in short.output
    runner.invoke(args=["create-owner", "--name", "A", "--email", "a@example.com", "--password", "longenough"])
    dup = runner.invoke(args=["create-owner", "--name", "B", "--email", "a@example.com", "--password", "longenough"])
    assert dup.exit_code != 0 and "already exists" in dup.output


def test_secret_key_is_generated_once_and_reused(tmp_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    first = _load_secret_key(tmp_path)
    assert len(first) == 64 and first == _load_secret_key(tmp_path)
    monkeypatch.setenv("SECRET_KEY", "from-environment")
    assert _load_secret_key(tmp_path) == "from-environment"


def test_demo_login_hints_only_show_with_demo_data(tmp_path):
    app = fresh_app(tmp_path)
    client = app.test_client()
    assert "Demo logins" not in client.get("/account/login").get_data(as_text=True)
    with app.app_context():
        seed(force=True)
    assert "Demo logins" in client.get("/account/login").get_data(as_text=True)
