import chess
import pytest

from app.service import move as move_module
from app.service.move import OpponentMoveNotFound, PositionNotInTablebase, play_move


def test_play_move_checkmate():
    board = chess.Board("4k3/8/4K3/8/8/8/8/7R w - - 0 1")
    result = play_move(board, chess.Move.from_uci("h1h8"))
    assert result.outcome == "checkmate"
    assert result.opponent_move is None


def test_play_move_position_not_in_tablebase():
    board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    with pytest.raises(PositionNotInTablebase):
        play_move(board, chess.Move.from_uci("e2e4"))


def test_play_move_continue_returns_opponent_response():
    board = chess.Board("8/8/8/8/4k3/8/4K3/4Q3 w - - 0 1")
    result = play_move(board, chess.Move.from_uci("e1a1"))
    assert result.outcome == "continue"
    assert result.opponent_move is not None
    # 상대 응수는 흑킹의 유효한 UCI 이동 (4 chars, e4에서 출발)
    assert len(result.opponent_move) == 4
    assert result.opponent_move.startswith("e4")


def test_play_move_stalemate_after_white_move():
    # KQK 표준 스테일메이트 트랩: Qd7-c7으로 흑킹 a8를 묶음.
    board = chess.Board("k7/3Q4/2K5/8/8/8/8/8 w - - 0 1")
    result = play_move(board, chess.Move.from_uci("d7c7"))
    assert result.outcome == "stalemate"
    assert result.opponent_move is None


def test_play_move_opponent_move_not_found(monkeypatch):
    monkeypatch.setattr(move_module, "best_opponent_move", lambda _: None)
    board = chess.Board("8/8/8/8/4k3/8/4K3/4Q3 w - - 0 1")
    with pytest.raises(OpponentMoveNotFound):
        play_move(board, chess.Move.from_uci("e1a1"))
