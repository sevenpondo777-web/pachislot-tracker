#!/usr/bin/env python3
"""reports/*.json を「正」として DB を決定論的に作り直す。

JSON を source of truth とし、`init_db.py --reset` で空DBを作ってから
reports 配下の全JSONを取り込む。各ファイルは中身に `treatment` キーが
含まれるかで「優遇冷遇(bias)」か「一般攻略(strategy)」かを自動判別し、
それぞれ `import` / `import-bias` サブコマンドで投入する。

手元でもCI(GitHub Actions)でも同じDBが再現できることを保証するための
ビルドスクリプト。`fetch_public_info.py` の重複排除は無いため、必ず
reset 済みの空DBに対して1回ずつ取り込む前提で使う。
"""
from __future__ import annotations

import glob
import json
import os
import sqlite3
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
DB_PATH = os.path.join(BASE_DIR, "db", "pachislot.db")

# 機種マスタ（メーカー・タイプ・導入日メモ）の正データ。
# 攻略/優遇冷遇のJSONとは形が違うので、取り込み対象から除外して個別に適用する。
MACHINES_MASTER = os.path.join(REPORTS_DIR, "machines_master.json")


def _classify(path: str) -> str | None:
    """JSONファイルを 'bias' / 'strategy' に分類。空・非リストは None。"""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, list) or not data:
        return None
    if any(isinstance(x, dict) and "treatment" in x for x in data):
        return "bias"
    return "strategy"


def apply_machines_master() -> None:
    """machines_master.json のメーカー・タイプ・導入日メモをDBに反映する。

    攻略情報の取り込みでは機種名しか登録されないため、カタログ情報は
    このファイルを正として後から上書きする。
    """
    if not os.path.exists(MACHINES_MASTER):
        return
    with open(MACHINES_MASTER, encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        print(f"警告: {MACHINES_MASTER} がリストではないためスキップします。", file=sys.stderr)
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        for row in rows:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            conn.execute("INSERT OR IGNORE INTO machines (name) VALUES (?)", (name,))
            conn.execute(
                "UPDATE machines SET maker = ?, machine_type = ?, notes = ? WHERE name = ?",
                (row.get("maker"), row.get("machine_type"), row.get("notes"), name),
            )
        conn.commit()
    finally:
        conn.close()
    print(f"機種マスタを反映しました: {len(rows)}件")


def main() -> int:
    py = sys.executable
    # 1. 空DBを作成（既存データは破棄）
    subprocess.run([py, os.path.join(BASE_DIR, "init_db.py"), "--reset", "--yes"],
                   check=True, cwd=BASE_DIR)

    strategy_files, bias_files = [], []
    for path in sorted(glob.glob(os.path.join(REPORTS_DIR, "*.json"))):
        if os.path.abspath(path) == os.path.abspath(MACHINES_MASTER):
            continue
        kind = _classify(path)
        if kind == "strategy":
            strategy_files.append(path)
        elif kind == "bias":
            bias_files.append(path)

    print(f"取り込み対象: 攻略 {len(strategy_files)}ファイル / 優遇冷遇 {len(bias_files)}ファイル")

    apply_machines_master()

    for path in strategy_files:
        subprocess.run([py, os.path.join(BASE_DIR, "fetch_public_info.py"),
                        "import", "--file", path], check=True, cwd=BASE_DIR)
    for path in bias_files:
        subprocess.run([py, os.path.join(BASE_DIR, "fetch_public_info.py"),
                        "import-bias", "--file", path], check=True, cwd=BASE_DIR)

    print("DBの再構築が完了しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
