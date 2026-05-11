from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_invalid_fen_returns_400():
    response = client.post("/move", json={"fen": "garbage", "move": "e2e4"})
    assert response.status_code == 400


def test_invalid_move_format_returns_400():
    response = client.post(
        "/move",
        json={"fen": "4k3/8/4K3/8/8/8/8/7R w - - 0 1", "move": "zz"},
    )
    assert response.status_code == 400


def test_illegal_move_returns_400():
    response = client.post(
        "/move",
        json={"fen": "4k3/8/4K3/8/8/8/8/7R w - - 0 1", "move": "a1a2"},
    )
    assert response.status_code == 400


def test_game_already_over_returns_400():
    response = client.post(
        "/move",
        json={"fen": "7k/7Q/6K1/8/8/8/8/8 b - - 0 1", "move": "h8g8"},
    )
    assert response.status_code == 400


def test_checkmate_outcome():
    response = client.post(
        "/move",
        json={"fen": "4k3/8/4K3/8/8/8/8/7R w - - 0 1", "move": "h1h8"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "checkmate"


def test_position_not_in_tablebase():
    response = client.post(
        "/move",
        json={
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "move": "e2e4",
        },
    )
    assert response.status_code == 400
