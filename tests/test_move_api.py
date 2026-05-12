from fastapi.testclient import TestClient

from app.main import app
from app.service import move as move_module

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


def test_continue_outcome_returns_opponent_move():
    response = client.post(
        "/move",
        json={"fen": "8/8/8/8/4k3/8/4K3/4Q3 w - - 0 1", "move": "e1a1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "continue"
    assert body["fen"] != "8/8/8/8/4k3/8/4K3/4Q3 w - - 0 1"
    assert "opponentMove" in body
    assert len(body["opponentMove"]) == 4


def test_stalemate_outcome_returns_failed():
    response = client.post(
        "/move",
        json={"fen": "k7/3Q4/2K5/8/8/8/8/8 w - - 0 1", "move": "d7c7"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["reason"] == "stalemate"
    assert body.get("opponentMove") is None


def test_promotion_move_continues():
    response = client.post(
        "/move",
        json={"fen": "8/4P3/8/8/4k3/8/8/4K3 w - - 0 1", "move": "e7e8q"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "continue"
    assert "opponentMove" in body


def test_request_missing_fen_returns_422():
    response = client.post("/move", json={"move": "e2e4"})
    assert response.status_code == 422


def test_request_fen_too_long_returns_422():
    response = client.post(
        "/move",
        json={"fen": "8/8/8/8/8/8/8/8 w - - 0 " + "9" * 100, "move": "e2e4"},
    )
    assert response.status_code == 422


def test_request_move_too_long_returns_422():
    response = client.post(
        "/move",
        json={"fen": "4k3/8/4K3/8/8/8/8/7R w - - 0 1", "move": "e2e4q!"},
    )
    assert response.status_code == 422


def test_draw_outcome_returns_failed(monkeypatch):
    monkeypatch.setattr(move_module, "probe_wdl", lambda _: 0)
    response = client.post(
        "/move",
        json={"fen": "8/8/8/8/4k3/8/4K3/4Q3 w - - 0 1", "move": "e1a1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["reason"] == "draw"
    assert body.get("opponentMove") is None


def test_lost_outcome_returns_failed(monkeypatch):
    monkeypatch.setattr(move_module, "probe_wdl", lambda _: -1)
    response = client.post(
        "/move",
        json={"fen": "8/8/8/8/4k3/8/4K3/4Q3 w - - 0 1", "move": "e1a1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["reason"] == "lost"
    assert body.get("opponentMove") is None
