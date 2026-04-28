import os
import sys

import chess
import chess.syzygy

from app.config import settings
from app.service.metrics import tablebase_operation_seconds

if not os.path.isdir(settings.syzygy_path) or not any(
    f.endswith((".rtbw", ".rtbz")) for f in os.listdir(settings.syzygy_path)
):
    print(f"ERROR: Syzygy tablebase files not found in '{settings.syzygy_path}'", file=sys.stderr)
    print("Download from: https://tablebase.lichess.ovh/tables/standard/", file=sys.stderr)
    sys.exit(1)

tablebase = chess.syzygy.open_tablebase(settings.syzygy_path)


def probe_wdl(board: chess.Board) -> int:
    with tablebase_operation_seconds.labels(operation="probe_wdl").time():
        return tablebase.probe_wdl(board)


def best_opponent_move(board: chess.Board) -> chess.Move | None:
    """상대(흑) 입장에서 가장 오래 버티는 수를 선택."""
    with tablebase_operation_seconds.labels(operation="best_opponent_move").time():
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
