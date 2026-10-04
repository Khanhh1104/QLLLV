import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-only-not-for-production-12345678"
os.environ["AUTO_MIGRATE"] = "false"
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        yield db
    engine.dispose()


@pytest.fixture()
def client(session):
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def logged(client):
    client.post(
        "/auth/register",
        json={
            "username": "khanh",
            "email": "khanh@example.com",
            "password": "password123",
        },
    )
    response = client.post(
        "/auth/login", data={"username": "khanh", "password": "password123"}
    )
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    return client
