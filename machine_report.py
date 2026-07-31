"""
machine_report.py
機種の一般攻略情報（天井・ゾーン・設定示唆等）と優遇/冷遇・実践値情報を、
スマートフォンでの閲覧に最適化したHTMLレポートとして出力する。

ホールで台選びをする際にスマホで開いて参照する用途を想定している。

使用例:
    python machine_report.py
    python machine_report.py --machine "スマスロ北斗の拳"
    python machine_report.py --output-dir reports
"""

import argparse
import html
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "pachislot.db")
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
OUTPUT_FILENAME = "machine_reference.html"

CATEGORY_BADGE_CLASS = {
    "天井": "badge-tenjyo",
    "ゾーン": "badge-zone",
    "設定示唆": "badge-settei",
    "狙い目": "badge-nerai",
    "その他": "badge-other",
}

TREATMENT_BADGE_CLASS = {
    "優遇": "badge-yugu",
    "冷遇": "badge-reigu",
    "不明": "badge-fumei",
}

CONFIDENCE_BADGE_CLASS = {
    "高": "conf-high",
    "中": "conf-mid",
    "低": "conf-low",
}


def get_connection() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        print("DBが見つかりません。先に `python init_db.py` を実行してください。", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def fetch_machines(conn: sqlite3.Connection, machine_filter: str):
    if machine_filter:
        return conn.execute(
            "SELECT machine_id, name FROM machines WHERE name = ? ORDER BY name",
            (machine_filter,),
        ).fetchall()
    return conn.execute(
        """
        SELECT DISTINCT m.machine_id, m.name
        FROM machines m
        WHERE m.machine_id IN (SELECT machine_id FROM machine_strategy_info)
           OR m.machine_id IN (SELECT machine_id FROM machine_bias_info)
        ORDER BY m.name
        """
    ).fetchall()


def fetch_strategy(conn: sqlite3.Connection, machine_id: int):
    return conn.execute(
        """
        SELECT category, title, summary, tenjyo_min, tenjyo_max,
               source_name, source_url, collected_date
        FROM machine_strategy_info
        WHERE machine_id = ?
        ORDER BY CASE category
            WHEN '天井' THEN 0 WHEN 'ゾーン' THEN 1 WHEN '設定示唆' THEN 2
            WHEN '狙い目' THEN 3 ELSE 4 END, info_id
        """,
        (machine_id,),
    ).fetchall()


def fetch_bias(conn: sqlite3.Connection, machine_id: int):
    return conn.execute(
        """
        SELECT category, treatment, target_setting, summary, sample_size,
               confidence, source_type, source_name, source_url, collected_date
        FROM machine_bias_info
        WHERE machine_id = ?
        ORDER BY CASE treatment WHEN '優遇' THEN 0 WHEN '冷遇' THEN 1 ELSE 2 END, bias_id
        """,
        (machine_id,),
    ).fetchall()


def esc(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def render_strategy_card(row) -> str:
    badge_class = CATEGORY_BADGE_CLASS.get(row["category"], "badge-other")
    tenjyo_range = ""
    if row["tenjyo_min"] is not None or row["tenjyo_max"] is not None:
        tmin = row["tenjyo_min"] if row["tenjyo_min"] is not None else "-"
        tmax = row["tenjyo_max"] if row["tenjyo_max"] is not None else "-"
        tenjyo_range = f'<div class="tenjyo-range">天井目安: {esc(tmin)}G 〜 {esc(tmax)}G</div>'
    source_line = esc(row["source_name"])
    if row["source_url"]:
        source_line = f'<a href="{esc(row["source_url"])}" target="_blank" rel="noopener">{source_line}</a>'
    return f"""
    <div class="info-card">
      <div class="info-card-head">
        <span class="badge {badge_class}">{esc(row['category'])}</span>
        <span class="info-title">{esc(row['title'])}</span>
      </div>
      <p class="info-summary">{esc(row['summary'])}</p>
      {tenjyo_range}
      <div class="info-source">出典: {source_line}（{esc(row['collected_date'])}収集）</div>
    </div>
    """


def render_bias_card(row) -> str:
    treat_class = TREATMENT_BADGE_CLASS.get(row["treatment"], "badge-fumei")
    conf_class = CONFIDENCE_BADGE_CLASS.get(row["confidence"], "conf-mid")
    target = f'<span class="target-setting">対象設定: {esc(row["target_setting"])}</span>' if row["target_setting"] else ""
    sample = f'<div class="sample-size">サンプル: {esc(row["sample_size"])}</div>' if row["sample_size"] else ""
    source_line = esc(row["source_name"])
    if row["source_url"]:
        source_line = f'<a href="{esc(row["source_url"])}" target="_blank" rel="noopener">{source_line}</a>'
    return f"""
    <div class="info-card bias-card">
      <div class="info-card-head">
        <span class="badge {treat_class}">{esc(row['treatment'])}</span>
        <span class="badge badge-cat">{esc(row['category'])}</span>
        <span class="conf-badge {conf_class}">信頼度:{esc(row['confidence'])}</span>
        {target}
      </div>
      <p class="info-summary">{esc(row['summary'])}</p>
      {sample}
      <div class="info-source">出典: [{esc(row['source_type'])}] {source_line}（{esc(row['collected_date'])}収集）</div>
    </div>
    """


def render_machine_section(name: str, strategy_rows, bias_rows) -> str:
    anchor = html.escape(name, quote=True)
    strategy_html = "".join(render_strategy_card(r) for r in strategy_rows) or '<p class="empty">登録なし</p>'
    bias_html = "".join(render_bias_card(r) for r in bias_rows) or '<p class="empty">登録なし（未確認）</p>'
    return f"""
    <section class="machine-section" id="m-{anchor}">
      <h2 class="machine-name">{esc(name)}</h2>
      <h3 class="section-label">攻略情報（公式・一般）</h3>
      {strategy_html}
      <h3 class="section-label">優遇/冷遇・実践値情報（未検証・参考情報）</h3>
      {bias_html}
    </section>
    """


def render_toc(names) -> str:
    items = "".join(
        f'<a class="toc-item" href="#m-{html.escape(n, quote=True)}">{esc(n)}</a>' for n in names
    )
    return f'<nav class="toc">{items}</nav>'


def render_html(sections_data) -> str:
    names = [name for name, _, _ in sections_data]
    toc = render_toc(names)
    body = "".join(render_machine_section(name, s, b) for name, s, b in sections_data)
    if not sections_data:
        body = '<p class="empty">登録されている機種情報がありません。fetch_public_info.py で追加してください。</p>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">
<title>機種リファレンス</title>
<style>
  :root {{
    color-scheme: light dark;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif;
    margin: 0;
    padding: 0 0 3rem 0;
    background: #f4f5f7;
    color: #1c1c1e;
    line-height: 1.6;
  }}
  header {{
    background: #1c1c1e;
    color: #fff;
    padding: 1rem 1rem 0.8rem 1rem;
    position: sticky;
    top: 0;
    z-index: 10;
  }}
  header h1 {{
    font-size: 1.1rem;
    margin: 0 0 0.6rem 0;
  }}
  .toc {{
    display: flex;
    gap: 0.5rem;
    overflow-x: auto;
    padding-bottom: 0.6rem;
    -webkit-overflow-scrolling: touch;
  }}
  .toc-item {{
    flex: 0 0 auto;
    background: #2c2c2e;
    color: #fff;
    padding: 0.4rem 0.8rem;
    border-radius: 999px;
    font-size: 0.85rem;
    text-decoration: none;
    white-space: nowrap;
  }}
  main {{
    max-width: 720px;
    margin: 0 auto;
    padding: 0.8rem;
  }}
  .machine-section {{
    background: #fff;
    border-radius: 12px;
    padding: 1rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    scroll-margin-top: 5.5rem;
  }}
  .machine-name {{
    font-size: 1.25rem;
    margin: 0 0 0.6rem 0;
    border-bottom: 2px solid #eee;
    padding-bottom: 0.4rem;
  }}
  .section-label {{
    font-size: 0.95rem;
    color: #555;
    margin: 1rem 0 0.5rem 0;
  }}
  .info-card {{
    border: 1px solid #e5e5e7;
    border-radius: 10px;
    padding: 0.7rem 0.8rem;
    margin-bottom: 0.6rem;
    background: #fafafa;
  }}
  .bias-card {{
    background: #fff8f0;
    border-color: #f0dcc0;
  }}
  .info-card-head {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 0.4rem;
  }}
  .info-title {{
    font-weight: 600;
    font-size: 0.95rem;
  }}
  .badge {{
    display: inline-block;
    font-size: 0.75rem;
    padding: 0.15rem 0.55rem;
    border-radius: 999px;
    color: #fff;
    font-weight: 600;
  }}
  .badge-tenjyo {{ background: #2b6cb0; }}
  .badge-zone   {{ background: #2f855a; }}
  .badge-settei {{ background: #6b46c1; }}
  .badge-nerai  {{ background: #b7791f; }}
  .badge-other  {{ background: #718096; }}
  .badge-cat    {{ background: #4a5568; }}
  .badge-yugu   {{ background: #c53030; }}
  .badge-reigu  {{ background: #2c5282; }}
  .badge-fumei  {{ background: #718096; }}
  .conf-badge {{
    font-size: 0.75rem;
    padding: 0.15rem 0.5rem;
    border-radius: 6px;
    border: 1px solid #ccc;
  }}
  .conf-high {{ background: #e6fffa; border-color: #38b2ac; color: #234e52; }}
  .conf-mid  {{ background: #fffbea; border-color: #d69e2e; color: #744210; }}
  .conf-low  {{ background: #fff5f5; border-color: #e53e3e; color: #742a2a; }}
  .target-setting {{
    font-size: 0.8rem;
    color: #444;
  }}
  .info-summary {{
    margin: 0.3rem 0;
    font-size: 0.9rem;
  }}
  .tenjyo-range, .sample-size {{
    font-size: 0.82rem;
    color: #333;
    margin-bottom: 0.2rem;
  }}
  .info-source {{
    font-size: 0.75rem;
    color: #777;
    margin-top: 0.3rem;
    word-break: break-all;
  }}
  .info-source a {{ color: #2b6cb0; }}
  .empty {{
    color: #999;
    font-size: 0.85rem;
  }}

  @media (prefers-color-scheme: dark) {{
    body {{ background: #000; color: #eee; }}
    .machine-section {{ background: #1c1c1e; box-shadow: none; }}
    .machine-name {{ border-bottom-color: #333; }}
    .info-card {{ background: #2c2c2e; border-color: #3a3a3c; }}
    .bias-card {{ background: #2e2620; border-color: #5a4a30; }}
    .info-source a {{ color: #6cb2eb; }}
    .section-label {{ color: #aaa; }}
  }}
</style>
</head>
<body>
<header>
  <h1>機種リファレンス（攻略情報・優遇冷遇まとめ）</h1>
  {toc}
</header>
<main>
{body}
</main>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="機種攻略情報・優遇冷遇情報のスマホ向けHTMLレポートを生成する")
    parser.add_argument("--machine", help="機種名で絞り込み（省略時は全機種）")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="出力先ディレクトリ")
    args = parser.parse_args()

    conn = get_connection()
    try:
        machines = fetch_machines(conn, args.machine)
        sections_data = []
        for m in machines:
            strategy_rows = fetch_strategy(conn, m["machine_id"])
            bias_rows = fetch_bias(conn, m["machine_id"])
            sections_data.append((m["name"], strategy_rows, bias_rows))
    finally:
        conn.close()

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir, OUTPUT_FILENAME)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render_html(sections_data))

    print(f"機種リファレンス（スマホ向け）を生成しました: {out_path}")
    if not sections_data:
        print("注意: 登録されている機種情報がありませんでした。")


if __name__ == "__main__":
    main()
