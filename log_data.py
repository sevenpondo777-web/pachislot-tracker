"""
log_data.py
実地で記録するホールデータ（差枚・G数・設定示唆など）をDBに投入するCLI。

使用例:
    python log_data.py --machine "北斗の拳" --game 500 --diff -300
    python log_data.py --machine "ジャグラーガールズSS" --hall "相模原プラザ" \\
        --unit 123 --game 3200 --diff 850 --investment 8000 --payout 12000 \\
        --setting-hint "設定6示唆演出多数" --estimated-setting 6 --hyena --memo "朝一ゾーン狙い"

機種名・ホール名が未登録の場合は自動でマスタに追加する。
"""

import argparse
import os
import sqlite3
import sys
from datetime import date

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "pachislot.db")
DEFAULT_HALL_NAME = "相模原プラザ"


def get_connection() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        print("DBが見つかりません。先に `python init_db.py` を実行してください。", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_or_create_hall(conn: sqlite3.Connection, hall_name: str) -> int:
    cur = conn.execute("SELECT hall_id FROM halls WHERE name = ?", (hall_name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO halls (name) VALUES (?)", (hall_name,))
    conn.commit()
    print(f"新規ホールを登録しました: {hall_name}")
    return cur.lastrowid


def get_or_create_machine(conn: sqlite3.Connection, machine_name: str) -> int:
    cur = conn.execute("SELECT machine_id FROM machines WHERE name = ?", (machine_name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO machines (name) VALUES (?)", (machine_name,))
    conn.commit()
    print(f"新規機種を登録しました: {machine_name}")
    return cur.lastrowid


def insert_session(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    hall_id = get_or_create_hall(conn, args.hall)
    machine_id = get_or_create_machine(conn, args.machine)

    total_games = args.game
    if args.start is not None and args.end is not None and args.game is None:
        total_games = args.end - args.start

    cur = conn.execute(
        """
        INSERT INTO play_sessions (
            play_date, hall_id, machine_id, unit_number,
            start_game, end_game, total_games, diff_medals,
            investment_yen, payout_yen, setting_hint,
            estimated_setting, is_hyena, memo
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            args.date,
            hall_id,
            machine_id,
            args.unit,
            args.start,
            args.end,
            total_games,
            args.diff,
            args.investment,
            args.payout,
            args.setting_hint,
            args.estimated_setting,
            1 if args.hyena else 0,
            args.memo,
        ),
    )
    conn.commit()
    return cur.lastrowid


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="稼働データをDBに記録する")
    parser.add_argument("--machine", required=True, help="機種名（例: 北斗の拳）")
    parser.add_argument("--hall", default=DEFAULT_HALL_NAME, help=f"ホール名（デフォルト: {DEFAULT_HALL_NAME}）")
    parser.add_argument("--date", default=date.today().isoformat(), help="稼働日 YYYY-MM-DD（デフォルト: 今日）")
    parser.add_argument("--unit", help="台番号")
    parser.add_argument("--game", type=int, help="消化G数")
    parser.add_argument("--start", type=int, help="開始G数（--endと併用でG数を自動計算）")
    parser.add_argument("--end", type=int, help="終了G数（--startと併用でG数を自動計算）")
    parser.add_argument("--diff", type=int, required=True, help="差枚（例: -300, 850）")
    parser.add_argument("--investment", type=int, help="投資額（円）")
    parser.add_argument("--payout", type=int, help="回収額（円）")
    parser.add_argument("--setting-hint", dest="setting_hint", help="設定示唆メモ（自由記述）")
    parser.add_argument("--estimated-setting", dest="estimated_setting", type=int, choices=range(1, 7),
                         metavar="1-6", help="推定設定")
    parser.add_argument("--hyena", action="store_true", help="ハイエナ狙い台としてマークする")
    parser.add_argument("--memo", help="自由メモ")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    conn = get_connection()
    try:
        session_id = insert_session(conn, args)
        print(f"記録しました (session_id={session_id}): {args.date} {args.hall} / {args.machine} "
              f"G数={args.game if args.game is not None else '-'} 差枚={args.diff}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
