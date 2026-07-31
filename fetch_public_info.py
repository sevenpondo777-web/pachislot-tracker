"""
fetch_public_info.py
機種の一般攻略情報（天井G数・ゾーン期待値・狙い目条件など）をDBに保存するツール。

【重要な設計方針】
このスクリプトは有料攻略サイト（すろらぼ等）の自動巡回・スクレイピング・コンテンツ複製は
一切行わない。ネットワークアクセス機能を持たない、完全にオフラインの「手動キュレーション
ツール」として実装している。

ユーザー自身がメーカー公式サイトや無料の一般公開情報（メーカー公式スペック表、公式YouTube、
無料ブログ等）を調べ、その要約と出典（サイト名・URL）を自分の言葉でこのツール経由でDBに
記録する、という使い方を想定している。他サイトの文章をそのまま貼り付けての複製保存は行わないこと。

既知の有料攻略サイトのドメインを簡易ブラックリストで検出し、該当する場合は保存を拒否する
（多重の安全策として。ブラックリストに無い有料サイトも自己責任で入力しないこと）。

使用例:
    python fetch_public_info.py add --machine "北斗の拳" --category 天井 \\
        --title "天井G数（メーカー公式値）" \\
        --summary "公式スペック表によると天井は999G。詳細は自分でメーカーサイトを確認。" \\
        --source-name "メーカー公式サイト" --source-url "https://example-maker.co.jp/hokuto/spec"

    python fetch_public_info.py list --machine "北斗の拳"

【優遇/冷遇・実践値ベースの設定推測情報について】
スマスロ等では、メーカーの正式発表にはないが実践値から明らかになっている「優遇/冷遇」の
挙動（特定設定での演出頻度の偏り、AT当選率の偏りなど）が存在する。これらはコミュニティの
実践値（X投稿・個人ブログ・まとめサイト等の無料公開情報）を出典として記録する
`add-bias` / `list-bias` / `import-bias` サブコマンドで扱う。
公式情報と違い未検証の実践値であるため、必ず `--confidence`（信頼度: 高/中/低）を付与すること。
有料サイトのスクレイピングは引き続き禁止。まとめサイトは有料サイトの内容を無断転載している
場合があるため、収集前に出典が本当に無料公開情報かを自分の目で確認すること。

使用例:
    python fetch_public_info.py add-bias --machine "北斗の拳" --category AT当選率偏り \\
        --treatment 優遇 --target-setting "6" \\
        --summary "設定6は特定モードでのAT当選率が高い傾向、との実践値報告が複数あり。" \\
        --sample-size "有志報告 合計約2000G分" --confidence 中 \\
        --source-type X投稿 --source-name "個人ユーザーの実践値まとめ投稿" \\
        --source-url "https://x.com/example/status/xxxx"

    python fetch_public_info.py list-bias --machine "北斗の拳"

    python fetch_public_info.py import-bias --file entries.json
        # entries.json は下記キーを持つオブジェクトのリスト（必須: machine, category,
        # treatment, summary, source_type, source_name。他は任意）:
        #   machine, category, treatment, target_setting, summary,
        #   sample_size, confidence, source_type, source_name, source_url, notes
"""

import argparse
import json
import os
import sqlite3
import sys
from urllib.parse import urlparse

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "pachislot.db")

# 既知の有料攻略サイト等、収集対象外とするドメインの簡易ブラックリスト。
# 必要に応じて追記すること。ここに無いサイトでも有料サイトへの掲載は禁止。
BLOCKED_DOMAINS = {
    "surolabo.jp",
    "www.surolabo.jp",
    "slorepo.com",
    "www.slorepo.com",
    "p-town.dmm.com",
    "diamond-slot.jp",
}

VALID_CATEGORIES = ("天井", "ゾーン", "設定示唆", "狙い目", "その他")

VALID_BIAS_CATEGORIES = ("演出頻度偏り", "AT当選率偏り", "内部モード示唆", "その他")
VALID_TREATMENTS = ("優遇", "冷遇", "不明")
VALID_CONFIDENCE = ("高", "中", "低")
VALID_SOURCE_TYPES = ("X投稿", "個人ブログ", "まとめサイト", "その他")


def get_connection() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        print("DBが見つかりません。先に `python init_db.py` を実行してください。", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def is_blocked_url(url: str) -> bool:
    if not url:
        return False
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return False
    return host in BLOCKED_DOMAINS


def get_or_create_machine(conn: sqlite3.Connection, machine_name: str) -> int:
    cur = conn.execute("SELECT machine_id FROM machines WHERE name = ?", (machine_name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO machines (name) VALUES (?)", (machine_name,))
    conn.commit()
    print(f"新規機種を登録しました: {machine_name}")
    return cur.lastrowid


def _insert_strategy_entry(conn: sqlite3.Connection, entry: dict) -> int:
    """1件の一般攻略情報をバリデーションのうえDBに保存し、info_idを返す。
    不正な場合は ValueError を送出する。
    """
    machine = (entry.get("machine") or "").strip()
    category = entry.get("category")
    title = (entry.get("title") or "").strip()
    summary = (entry.get("summary") or "").strip()
    source_name = (entry.get("source_name") or "").strip()
    source_url = entry.get("source_url")

    if not machine:
        raise ValueError("machine（機種名）は必須です。")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"category は {VALID_CATEGORIES} のいずれかである必要があります: {category!r}")
    if not title:
        raise ValueError("title（タイトル）は必須です。")
    if not summary:
        raise ValueError("summary（要約）は必須です。原文コピペではなく自分の言葉で。")
    if not source_name:
        raise ValueError("source_name（出典名）は必須です。出典不明の情報は保存しません。")
    if is_blocked_url(source_url):
        raise ValueError(f"'{source_url}' は有料攻略サイトのドメインです。保存できません。")

    machine_id = get_or_create_machine(conn, machine)
    cur = conn.execute(
        """
        INSERT INTO machine_strategy_info (
            machine_id, category, title, summary,
            tenjyo_min, tenjyo_max, source_name, source_url, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            machine_id,
            category,
            title,
            summary,
            entry.get("tenjyo_min"),
            entry.get("tenjyo_max"),
            source_name,
            source_url,
            entry.get("notes"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def cmd_add(args: argparse.Namespace) -> None:
    entry = {
        "machine": args.machine,
        "category": args.category,
        "title": args.title,
        "summary": args.summary,
        "tenjyo_min": args.tenjyo_min,
        "tenjyo_max": args.tenjyo_max,
        "source_name": args.source_name,
        "source_url": args.source_url,
        "notes": args.notes,
    }
    conn = get_connection()
    try:
        try:
            info_id = _insert_strategy_entry(conn, entry)
        except ValueError as e:
            print(f"エラー: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"保存しました (info_id={info_id}): {args.machine} / {args.category} / {args.title}")
    finally:
        conn.close()


def cmd_import(args: argparse.Namespace) -> None:
    if not os.path.exists(args.file):
        print(f"エラー: ファイルが見つかりません: {args.file}", file=sys.stderr)
        sys.exit(1)

    with open(args.file, "r", encoding="utf-8") as f:
        try:
            entries = json.load(f)
        except json.JSONDecodeError as e:
            print(f"エラー: JSONの読み込みに失敗しました: {e}", file=sys.stderr)
            sys.exit(1)

    if not isinstance(entries, list):
        print("エラー: JSONファイルの中身はオブジェクトのリストである必要があります。", file=sys.stderr)
        sys.exit(1)

    conn = get_connection()
    saved, skipped = 0, 0
    try:
        for i, entry in enumerate(entries, start=1):
            try:
                info_id = _insert_strategy_entry(conn, entry)
                print(f"[{i}] 保存しました (info_id={info_id}): "
                      f"{entry.get('machine')} / {entry.get('category')} / {entry.get('title')}")
                saved += 1
            except ValueError as e:
                print(f"[{i}] スキップ: {e}", file=sys.stderr)
                skipped += 1
    finally:
        conn.close()

    print(f"完了: {saved}件保存 / {skipped}件スキップ（全{len(entries)}件中）")


def cmd_list(args: argparse.Namespace) -> None:
    conn = get_connection()
    try:
        if args.machine:
            rows = conn.execute(
                """
                SELECT i.info_id, m.name, i.category, i.title, i.summary,
                       i.tenjyo_min, i.tenjyo_max, i.source_name, i.source_url, i.collected_date
                FROM machine_strategy_info i
                JOIN machines m ON m.machine_id = i.machine_id
                WHERE m.name = ?
                ORDER BY i.collected_date DESC
                """,
                (args.machine,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT i.info_id, m.name, i.category, i.title, i.summary,
                       i.tenjyo_min, i.tenjyo_max, i.source_name, i.source_url, i.collected_date
                FROM machine_strategy_info i
                JOIN machines m ON m.machine_id = i.machine_id
                ORDER BY i.collected_date DESC
                """
            ).fetchall()

        if not rows:
            print("該当する攻略情報はありません。")
            return

        for (info_id, machine, category, title, summary, tmin, tmax, src_name, src_url, collected) in rows:
            print(f"[{info_id}] {collected} | {machine} | {category} | {title}")
            print(f"    要約: {summary}")
            if tmin is not None or tmax is not None:
                print(f"    天井G数: {tmin or '-'} 〜 {tmax or '-'}")
            print(f"    出典: {src_name} {('(' + src_url + ')') if src_url else ''}")
            print()
    finally:
        conn.close()


def _insert_bias_entry(conn: sqlite3.Connection, entry: dict) -> int:
    """1件の優遇/冷遇情報をバリデーションのうえDBに保存し、bias_idを返す。
    不正な場合は ValueError を送出する（呼び出し側でどのエントリか分かるように）。
    """
    machine = (entry.get("machine") or "").strip()
    category = entry.get("category")
    treatment = entry.get("treatment")
    summary = (entry.get("summary") or "").strip()
    source_type = entry.get("source_type")
    source_name = (entry.get("source_name") or "").strip()
    source_url = entry.get("source_url")
    confidence = entry.get("confidence") or "中"

    if not machine:
        raise ValueError("machine（機種名）は必須です。")
    if category not in VALID_BIAS_CATEGORIES:
        raise ValueError(f"category は {VALID_BIAS_CATEGORIES} のいずれかである必要があります: {category!r}")
    if treatment not in VALID_TREATMENTS:
        raise ValueError(f"treatment は {VALID_TREATMENTS} のいずれかである必要があります: {treatment!r}")
    if not summary:
        raise ValueError("summary（要約）は必須です。原文コピペではなく自分の言葉で。")
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(f"source_type は {VALID_SOURCE_TYPES} のいずれかである必要があります: {source_type!r}")
    if not source_name:
        raise ValueError("source_name（出典名）は必須です。出典不明の実践値情報は保存しません。")
    if confidence not in VALID_CONFIDENCE:
        raise ValueError(f"confidence は {VALID_CONFIDENCE} のいずれかである必要があります: {confidence!r}")
    if is_blocked_url(source_url):
        raise ValueError(f"'{source_url}' は有料攻略サイトのドメインです。保存できません。")

    machine_id = get_or_create_machine(conn, machine)
    cur = conn.execute(
        """
        INSERT INTO machine_bias_info (
            machine_id, category, treatment, target_setting, summary,
            sample_size, confidence, source_type, source_name, source_url, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            machine_id,
            category,
            treatment,
            entry.get("target_setting"),
            summary,
            entry.get("sample_size"),
            confidence,
            source_type,
            source_name,
            source_url,
            entry.get("notes"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def cmd_add_bias(args: argparse.Namespace) -> None:
    entry = {
        "machine": args.machine,
        "category": args.category,
        "treatment": args.treatment,
        "target_setting": args.target_setting,
        "summary": args.summary,
        "sample_size": args.sample_size,
        "confidence": args.confidence,
        "source_type": args.source_type,
        "source_name": args.source_name,
        "source_url": args.source_url,
        "notes": args.notes,
    }
    conn = get_connection()
    try:
        try:
            bias_id = _insert_bias_entry(conn, entry)
        except ValueError as e:
            print(f"エラー: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"保存しました (bias_id={bias_id}): {args.machine} / {args.category} / {args.treatment}")
    finally:
        conn.close()


def cmd_import_bias(args: argparse.Namespace) -> None:
    if not os.path.exists(args.file):
        print(f"エラー: ファイルが見つかりません: {args.file}", file=sys.stderr)
        sys.exit(1)

    with open(args.file, "r", encoding="utf-8") as f:
        try:
            entries = json.load(f)
        except json.JSONDecodeError as e:
            print(f"エラー: JSONの読み込みに失敗しました: {e}", file=sys.stderr)
            sys.exit(1)

    if not isinstance(entries, list):
        print("エラー: JSONファイルの中身はオブジェクトのリストである必要があります。", file=sys.stderr)
        sys.exit(1)

    conn = get_connection()
    saved, skipped = 0, 0
    try:
        for i, entry in enumerate(entries, start=1):
            try:
                bias_id = _insert_bias_entry(conn, entry)
                print(f"[{i}] 保存しました (bias_id={bias_id}): "
                      f"{entry.get('machine')} / {entry.get('category')} / {entry.get('treatment')}")
                saved += 1
            except ValueError as e:
                print(f"[{i}] スキップ: {e}", file=sys.stderr)
                skipped += 1
    finally:
        conn.close()

    print(f"完了: {saved}件保存 / {skipped}件スキップ（全{len(entries)}件中）")


def cmd_list_bias(args: argparse.Namespace) -> None:
    conn = get_connection()
    try:
        query = """
            SELECT b.bias_id, m.name, b.category, b.treatment, b.target_setting,
                   b.summary, b.sample_size, b.confidence, b.source_type,
                   b.source_name, b.source_url, b.collected_date
            FROM machine_bias_info b
            JOIN machines m ON m.machine_id = b.machine_id
        """
        params = ()
        if args.machine:
            query += " WHERE m.name = ?"
            params = (args.machine,)
        query += " ORDER BY b.collected_date DESC"
        rows = conn.execute(query, params).fetchall()

        if not rows:
            print("該当する優遇/冷遇情報はありません。")
            return

        for (bias_id, machine, category, treatment, target_setting, summary,
             sample_size, confidence, source_type, source_name, source_url, collected) in rows:
            print(f"[{bias_id}] {collected} | {machine} | {category} | {treatment}"
                  f"{' (設定' + target_setting + ')' if target_setting else ''} | 信頼度:{confidence}")
            print(f"    要約: {summary}")
            if sample_size:
                print(f"    サンプル: {sample_size}")
            print(f"    出典: [{source_type}] {source_name} {('(' + source_url + ')') if source_url else ''}")
            print()
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="機種の一般攻略情報および優遇/冷遇・実践値情報（いずれも無料公開情報のみ）を"
                    "手動/一括インポートでDBに保存・一覧表示する"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="攻略情報を1件追加する")
    add_p.add_argument("--machine", required=True, help="機種名")
    add_p.add_argument("--category", required=True, choices=VALID_CATEGORIES, help="情報カテゴリ")
    add_p.add_argument("--title", required=True, help="情報タイトル")
    add_p.add_argument("--summary", required=True, help="自分の言葉での要約（原文コピペ不可）")
    add_p.add_argument("--tenjyo-min", dest="tenjyo_min", type=int, help="天井G数（下限）")
    add_p.add_argument("--tenjyo-max", dest="tenjyo_max", type=int, help="天井G数（上限）")
    add_p.add_argument("--source-name", dest="source_name", required=True,
                        help="出典名（例: メーカー公式サイト）")
    add_p.add_argument("--source-url", dest="source_url", help="出典URL（無料公開ページのみ）")
    add_p.add_argument("--notes", help="補足メモ")
    add_p.set_defaults(func=cmd_add)

    import_p = sub.add_parser("import", help="一般攻略情報をJSONファイルから一括登録する")
    import_p.add_argument("--file", required=True, help="エントリのリストを含むJSONファイルのパス")
    import_p.set_defaults(func=cmd_import)

    list_p = sub.add_parser("list", help="保存済みの攻略情報を一覧表示する")
    list_p.add_argument("--machine", help="機種名で絞り込み（省略時は全件）")
    list_p.set_defaults(func=cmd_list)

    bias_p = sub.add_parser("add-bias", help="優遇/冷遇・実践値ベースの設定推測情報を1件追加する")
    bias_p.add_argument("--machine", required=True, help="機種名")
    bias_p.add_argument("--category", required=True, choices=VALID_BIAS_CATEGORIES, help="偏りのカテゴリ")
    bias_p.add_argument("--treatment", required=True, choices=VALID_TREATMENTS, help="優遇/冷遇/不明")
    bias_p.add_argument("--target-setting", dest="target_setting", help="対象設定（例: 6, 5-6）")
    bias_p.add_argument("--summary", required=True, help="自分の言葉での要約（原文コピペ不可）")
    bias_p.add_argument("--sample-size", dest="sample_size", help="実践サンプル数の目安（自由記述）")
    bias_p.add_argument("--confidence", choices=VALID_CONFIDENCE, default="中", help="情報の信頼度（デフォルト: 中）")
    bias_p.add_argument("--source-type", dest="source_type", required=True, choices=VALID_SOURCE_TYPES,
                         help="出典の種類")
    bias_p.add_argument("--source-name", dest="source_name", required=True, help="出典名")
    bias_p.add_argument("--source-url", dest="source_url", help="出典URL（無料公開ページのみ）")
    bias_p.add_argument("--notes", help="補足メモ")
    bias_p.set_defaults(func=cmd_add_bias)

    import_p = sub.add_parser("import-bias", help="優遇/冷遇情報をJSONファイルから一括登録する")
    import_p.add_argument("--file", required=True, help="エントリのリストを含むJSONファイルのパス")
    import_p.set_defaults(func=cmd_import_bias)

    list_bias_p = sub.add_parser("list-bias", help="保存済みの優遇/冷遇情報を一覧表示する")
    list_bias_p.add_argument("--machine", help="機種名で絞り込み（省略時は全件）")
    list_bias_p.set_defaults(func=cmd_list_bias)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
