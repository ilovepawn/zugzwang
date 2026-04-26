import chess
import chess.syzygy

from app.config import settings

tablebase = chess.syzygy.open_tablebase(settings.syzygy_path)


def probe_wdl(board: chess.Board) -> int:
    return tablebase.probe_wdl(board)


def best_opponent_move(board: chess.Board) -> chess.Move:
    """상대(흑) 입장에서 가장 오래 버티는 수를 선택."""
    best_move = None
    best_dtz = None

    for move in board.legal_moves:
        board.push(move)
        try:
            dtz = tablebase.probe_dtz(board)
        except KeyError:
            board.pop()
            continue

        # 흑 입장: DTZ가 가장 큰 수(가장 오래 버티는 수)가 최선
        if best_dtz is None or dtz > best_dtz:
            best_dtz = dtz
            best_move = move

        board.pop()

    return best_move
