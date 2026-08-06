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
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")


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


def main() -> int:
    py = sys.executable
    # 1. 空DBを作成（既存データは破棄）
    subprocess.run([py, os.path.join(BASE_DIR, "init_db.py"), "--reset", "--yes"],
                   check=True, cwd=BASE_DIR)

    strategy_files, bias_files = [], []
    for path in sorted(glob.glob(os.path.join(REPORTS_DIR, "*.json"))):
        kind = _classify(path)
        if kind == "strategy":
            strategy_files.append(path)
        elif kind == "bias":
            bias_files.append(path)

    print(f"取り込み対象: 攻略 {len(strategy_files)}ファイル / 優遇冷遇 {len(bias_files)}ファイル")

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
