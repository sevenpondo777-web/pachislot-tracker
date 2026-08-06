#!/usr/bin/env python3
"""公開用サイト一式(site/)を組み立てる。

手順:
  1. (--rebuild-db 指定時) reports/*.json から DB を作り直す（build_db.py）
  2. PWAアイコンを生成（web/make_icons.py）
  3. machine_report.py でスマホ向けHTMLを生成
  4. site/ に index.html（＝生成HTML）と PWA静的ファイル
     （manifest.webmanifest / sw.js / icons/）をまとめる

出力された site/ をそのまま GitHub Pages 等で配信すると、PWAとして
ホーム画面に追加でき、オフライン閲覧も可能になる。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
SITE_DIR = os.path.join(BASE_DIR, "site")
GENERATED_HTML = os.path.join(REPORTS_DIR, "machine_reference.html")


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=BASE_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(description="公開用サイト(site/)を組み立てる")
    parser.add_argument("--rebuild-db", action="store_true",
                        help="reports/*.json からDBを作り直してから生成する")
    args = parser.parse_args()

    py = sys.executable

    if args.rebuild_db:
        run([py, os.path.join(BASE_DIR, "build_db.py")])

    # PWAアイコン生成
    run([py, os.path.join(WEB_DIR, "make_icons.py")])

    # スマホ向けHTML生成
    run([py, os.path.join(BASE_DIR, "machine_report.py"),
         "--output-dir", REPORTS_DIR])

    if not os.path.exists(GENERATED_HTML):
        print("エラー: HTMLが生成されませんでした。", file=sys.stderr)
        return 1

    # site/ を作り直す
    if os.path.exists(SITE_DIR):
        shutil.rmtree(SITE_DIR)
    os.makedirs(SITE_DIR)

    # index.html
    shutil.copyfile(GENERATED_HTML, os.path.join(SITE_DIR, "index.html"))
    # PWA静的ファイル
    shutil.copyfile(os.path.join(WEB_DIR, "manifest.webmanifest"),
                    os.path.join(SITE_DIR, "manifest.webmanifest"))
    shutil.copyfile(os.path.join(WEB_DIR, "sw.js"), os.path.join(SITE_DIR, "sw.js"))
    shutil.copytree(os.path.join(WEB_DIR, "icons"), os.path.join(SITE_DIR, "icons"))
    # Pages が Jekyll 処理をしないように
    open(os.path.join(SITE_DIR, ".nojekyll"), "w").close()

    print(f"サイトを生成しました: {SITE_DIR}/ (index.html + PWA一式)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
