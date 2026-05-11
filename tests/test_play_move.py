import chess
import pytest

from app.service.move import PositionNotInTablebase, play_move


def test_play_move_checkmate():
    board = chess.Board("4k3/8/4K3/8/8/8/8/7R w - - 0 1")
    result = play_move(board, chess.Move.from_uci("h1h8"))
    assert result.outcome == "checkmate"
    assert result.opponent_move is None


def test_play_move_position_not_in_tablebase():
    board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    with pytest.raises(PositionNotInTablebase):
        play_move(board, chess.Move.from_uci("e2e4"))
