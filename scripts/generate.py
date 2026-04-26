import argparse
import random
import sys
import os
import time
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import chess.syzygy
import pymysql

from app.config import settings

PIECE_MAP = {"Q": chess.QUEEN, "R": chess.ROOK, "B": chess.BISHOP, "N": chess.KNIGHT, "P": chess.PAWN}


def parse_combination(combo):
    if len(combo) < 3 or combo[0] != "K" or "K" not in combo[1:]:
        print(f"Invalid combination format: {combo}")
        print("Expected format: K[pieces]K[pieces] (e.g. KQK, KQKR, KBNK)")
        sys.exit(1)

    inner = combo[1:]
    k_index = inner.index("K")
    white_chars = inner[:k_index]
    black_chars = inner[k_index + 1:]

    for c in white_chars + black_chars:
        if c not in PIECE_MAP:
            print(f"Unknown piece '{c}' in combination: {combo}")
            print(f"Valid pieces: {', '.join(PIECE_MAP.keys())}")
            sys.exit(1)

    white = [PIECE_MAP[c] for c in white_chars]
    black = [PIECE_MAP[c] for c in black_chars]
    return white, black


def make_random_board(white_pieces, black_pieces):
    board = chess.Board.empty()
    used = set()

    wk = random.randint(0, 63)
    board.set_piece_at(wk, chess.Piece(chess.KING, chess.WHITE))
    used.add(wk)

    while True:
        bk = random.randint(0, 63)
        if bk not in used and not (chess.BB_KING_ATTACKS[wk] & chess.BB_SQUARES[bk]):
            board.set_piece_at(bk, chess.Piece(chess.KING, chess.BLACK))
            used.add(bk)
            break

    for pt in white_pieces:
        while True:
            sq = random.randint(8, 55) if pt == chess.PAWN else random.randint(0, 63)
            if sq not in used:
                board.set_piece_at(sq, chess.Piece(pt, chess.WHITE))
                used.add(sq)
                break

    for pt in black_pieces:
        while True:
            sq = random.randint(8, 55) if pt == chess.PAWN else random.randint(0, 63)
            if sq not in used:
                board.set_piece_at(sq, chess.Piece(pt, chess.BLACK))
                used.add(sq)
                break

    board.turn = chess.WHITE
    return board


def connect_db():
    parsed = urlparse(settings.database_url.replace("mysql+pymysql://", "mysql://"))
    return pymysql.connect(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path.lstrip("/"),
        autocommit=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("combination")
    parser.add_argument("count", type=int)
    args = parser.parse_args()

    if args.count <= 0:
        print("Count must be a positive integer")
        sys.exit(1)

    combo = args.combination.upper()
    white_pieces, black_pieces = parse_combination(combo)

    tb = None
    conn = None
    cursor = None

    try:
        tb = chess.syzygy.open_tablebase(settings.syzygy_path)
        conn = connect_db()
        cursor = conn.cursor()

        start = time.time()
        generated = 0
        attempts = 0
        invalid = 0
        not_win = 0
        fen_dup = 0

        while generated < args.count:
            attempts += 1
            board = make_random_board(white_pieces, black_pieces)

            if not board.is_valid():
                invalid += 1
                continue

            try:
                wdl = tb.probe_wdl(board)
            except KeyError:
                invalid += 1
                continue

            if wdl != 2:
                not_win += 1
                continue

            fen = board.fen()

            cursor.execute("SELECT 1 FROM endgame_position WHERE fen = %s", (fen,))
            if cursor.fetchone():
                fen_dup += 1
                continue

            cursor.execute(
                "INSERT INTO endgame_position (combination, fen, difficulty, created_at) VALUES (%s, %s, 0, NOW())",
                (combo, fen),
            )
            generated += 1

            if generated % 100 == 0:
                print(f"  {generated}/{args.count}")

        elapsed = time.time() - start
        rate = generated / attempts * 100
        print(f"[{combo}] +{generated} | {elapsed:.2f}s | attempts: {attempts} | rate: {rate:.1f}% | invalid: {invalid} | not_win: {not_win} | fen_dup: {fen_dup}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        if tb:
            tb.close()


if __name__ == "__main__":
    main()
