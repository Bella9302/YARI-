import pytest

from app import create_app
from app.seed import seed


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.sqlite"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "SECRET_KEY": "test",
        "CSRF_ENABLED": False,
    })
    with app.app_context():
        seed(force=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email, password="password123"):
    return client.post("/account/login", data={"email": email, "password": password}, follow_redirects=True)


@pytest.fixture
def owner(client):
    login(client, "owner@yari.co.za")
    return client


@pytest.fixture
def seller(client):
    login(client, "naledi@yari.co.za")
    return client


@pytest.fixture
def rep(client):
    login(client, "lerato@yari.co.za")
    return client
