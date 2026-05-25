from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from signal_api.app import create_app
from signal_api.deps import get_db


@pytest.fixture()
def mock_conn():
    return MagicMock(spec=["cursor", "commit", "transaction"])


@pytest.fixture()
def client(mock_conn):
    app = create_app()

    def override_db():
        yield mock_conn

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)
