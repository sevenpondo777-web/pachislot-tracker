"""
init_db.py
パチスロ・ハイエナ稼働データ管理システム - DB初期化スクリプト

ローカルSQLite (db/pachislot.db) にスキーマを作成する。
既にDBが存在する場合はテーブル作成をスキップ（CREATE TABLE IF NOT EXISTS）し、
対象ホール（相模原プラザ）のマスタレコードのみ存在確認の上で投入する。

実行方法:
    python init_db.py
    python init_db.py --reset   # DBファイルを削除して作り直す（要確認プロンプト）
"""

import argparse
import os
import sqlite3
import sys

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db")
DB_PATH = os.path.join(DB_DIR, "pachislot.db")

DEFAULT_HALL_NAME = "相模原プラザ"
DEFAULT_HALL_PREF = "神奈川県"
DEFAULT_HALL_CITY = "相模原市"

SCHEMA_SQL = """
-- ホール（店舗）マスタ
CREATE TABLE IF NOT EXISTS halls (
    hall_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    prefecture  TEXT,
    city        TEXT,
    address     TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 機種マスタ
CREATE TABLE IF NOT EXISTS machines (
    machine_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    maker        TEXT,
    machine_type TEXT,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 機種の一般攻略情報（無料公開情報のみ・ユーザーが出典付きで手動投入）
CREATE TABLE IF NOT EXISTS machine_strategy_info (
    info_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id     INTEGER NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    category       TEXT NOT NULL CHECK (category IN ('天井', 'ゾーン', '設定示唆', '狙い目', 'その他')),
    title          TEXT NOT NULL,
    summary        TEXT NOT NULL,
    tenjyo_min     INTEGER,
    tenjyo_max     INTEGER,
    source_name    TEXT NOT NULL,
    source_url     TEXT,
    collected_date TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 機種の優遇/冷遇・実践値ベースの設定推測情報（メーカー非公式・コミュニティ実践値）
-- スマスロ等でメーカーの正式発表にはないが、実践値から明らかになっている挙動の偏りを記録する。
-- 有料サイトは対象外。X投稿・個人ブログ・まとめサイト等の無料公開情報のみを、
-- 出典・信頼度付きで手動（またはユーザー確認済みの一括import）で記録する。
CREATE TABLE IF NOT EXISTS machine_bias_info (
    bias_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id     INTEGER NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    category       TEXT NOT NULL CHECK (category IN ('演出頻度偏り', 'AT当選率偏り', '内部モード示唆', 'その他')),
    treatment      TEXT NOT NULL CHECK (treatment IN ('優遇', '冷遇', '不明')),
    target_setting TEXT,
    summary        TEXT NOT NULL,
    sample_size    TEXT,
    confidence     TEXT NOT NULL DEFAULT '中' CHECK (confidence IN ('高', '中', '低')),
    source_type    TEXT NOT NULL CHECK (source_type IN ('X投稿', '個人ブログ', 'まとめサイト', 'その他')),
    source_name    TEXT NOT NULL,
    source_url     TEXT,
    collected_date TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 実地で記録するホールデータ（自分の稼働記録）
CREATE TABLE IF NOT EXISTS play_sessions (
    session_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    play_date          TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    hall_id            INTEGER NOT NULL REFERENCES halls(hall_id),
    machine_id         INTEGER NOT NULL REFERENCES machines(machine_id),
    unit_number        TEXT,
    start_game         INTEGER,
    end_game           INTEGER,
    total_games        INTEGER,
    diff_medals        INTEGER,
    investment_yen     INTEGER,
    payout_yen         INTEGER,
    setting_hint       TEXT,
    estimated_setting  INTEGER CHECK (estimated_setting BETWEEN 1 AND 6),
    is_hyena           INTEGER NOT NULL DEFAULT 0 CHECK (is_hyena IN (0, 1)),
    memo               TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_date    ON play_sessions(play_date);
CREATE INDEX IF NOT EXISTS idx_sessions_machine ON play_sessions(machine_id);
CREATE INDEX IF NOT EXISTS idx_sessions_hall    ON play_sessions(hall_id);
CREATE INDEX IF NOT EXISTS idx_info_machine     ON machine_strategy_info(machine_id);
CREATE INDEX IF NOT EXISTS idx_bias_machine      ON machine_bias_info(machine_id);
"""


def init_db(reset: bool = False, assume_yes: bool = False) -> None:
    os.makedirs(DB_DIR, exist_ok=True)

    if reset and os.path.exists(DB_PATH):
        if not assume_yes:
            answer = input(f"'{DB_PATH}' を削除して初期化し直します。よろしいですか？ (yes/no): ")
            if answer.strip().lower() != "yes":
                print("中止しました。")
                sys.exit(0)
        os.remove(DB_PATH)
        print("既存DBを削除しました。")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(SCHEMA_SQL)

        # 対象ホールのマスタレコードを投入（未登録の場合のみ）
        conn.execute(
            """
            INSERT OR IGNORE INTO halls (name, prefecture, city)
            VALUES (?, ?, ?)
            """,
            (DEFAULT_HALL_NAME, DEFAULT_HALL_PREF, DEFAULT_HALL_CITY),
        )
        conn.commit()
        print(f"DBを初期化しました: {DB_PATH}")
        print(f"デフォルトホールを登録済み: {DEFAULT_HALL_NAME}（{DEFAULT_HALL_PREF}{DEFAULT_HALL_CITY}）")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="パチスロ稼働データDBの初期化")
    parser.add_argument("--reset", action="store_true", help="既存DBを削除して作り直す")
    parser.add_argument("--yes", action="store_true",
                        help="--reset時の確認プロンプトを省略する（自動化・CI用）")
    args = parser.parse_args()
    init_db(reset=args.reset, assume_yes=args.yes)


if __name__ == "__main__":
    main()
