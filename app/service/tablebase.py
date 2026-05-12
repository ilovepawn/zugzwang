import os
import sys
import threading
from time import perf_counter

import chess
import chess.syzygy

from app.config import settings
from app.service.metrics import (
    tablebase_lock_wait_seconds,
    tablebase_operation_seconds,
)

if not os.path.isdir(settings.syzygy_path) or not any(
    f.endswith((".rtbw", ".rtbz")) for f in os.listdir(settings.syzygy_path)
):
    print(f"ERROR: Syzygy tablebase files not found in '{settings.syzygy_path}'", file=sys.stderr)
    print("Download from: https://tablebase.lichess.ovh/tables/standard/", file=sys.stderr)
    sys.exit(1)

tablebase = chess.syzygy.open_tablebase(settings.syzygy_path)
# chess.syzygy.Tablebase는 thread-safe하지 않음. sync 라우트가 starlette
# threadpool에서 병렬 호출되므로 모든 probe 호출을 단일 락으로 직렬화.
_tablebase_lock = threading.Lock()


def _acquire_with_wait_timing(operation: str) -> None:
    """락을 잡고 wait 시간을 observe. observe 실패 시 잡은 락을 반드시 해제해
    호출자 finally가 없는 시점의 release 누수를 방지."""
    start = perf_counter()
    _tablebase_lock.acquire()
    try:
        tablebase_lock_wait_seconds.labels(operation=operation).observe(perf_counter() - start)
    except BaseException:
        _tablebase_lock.release()
        raise


def probe_wdl(board: chess.Board) -> int:
    # tablebase_operation_seconds는 "호출자 체감 wall-clock"(락 대기 포함)으로
    # 통일. 락 대기 분해는 tablebase_lock_wait_seconds에서 따로 본다.
    with tablebase_operation_seconds.labels(operation="probe_wdl").time():
        _acquire_with_wait_timing("probe_wdl")
        try:
            return tablebase.probe_wdl(board)
        finally:
            _tablebase_lock.release()


def best_opponent_move(board: chess.Board) -> chess.Move | None:
    """상대(흑) 입장에서 가장 오래 버티는 수를 선택."""
    with tablebase_operation_seconds.labels(operation="best_opponent_move").time():
        best_move = None
        best_dtz = None

        for move in board.legal_moves:
            board.push(move)
            try:
                _acquire_with_wait_timing("best_opponent_move")
                try:
                    dtz = tablebase.probe_dtz(board)
                except KeyError:
                    continue
                finally:
                    _tablebase_lock.release()
            finally:
                board.pop()

            # 흑 입장: DTZ가 가장 큰 수(가장 오래 버티는 수)가 최선
            if best_dtz is None or dtz > best_dtz:
                best_dtz = dtz
                best_move = move

        return best_move
