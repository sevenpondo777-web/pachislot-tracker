"""
weekly_report.py
直近N日間（デフォルト7日）の稼働データを集計し、Markdown / HTMLレポートを生成する。

使用例:
    python weekly_report.py
    python weekly_report.py --days 14 --format html
    python weekly_report.py --format both --output-dir reports

Windowsタスクスケジューラーからの自動実行を想定（README.md参照）。
"""

import argparse
import os
import sqlite3
import sys
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "pachislot.db")
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def get_connection() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        print("DBが見つかりません。先に `python init_db.py` を実行してください。", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def fetch_sessions(conn: sqlite3.Connection, start_date: str, end_date: str):
    return conn.execute(
        """
        SELECT s.*, h.name AS hall_name, m.name AS machine_name
        FROM play_sessions s
        JOIN halls h ON h.hall_id = s.hall_id
        JOIN machines m ON m.machine_id = s.machine_id
        WHERE s.play_date BETWEEN ? AND ?
        ORDER BY s.play_date ASC, s.session_id ASC
        """,
        (start_date, end_date),
    ).fetchall()


def summarize(rows):
    total_sessions = len(rows)
    total_diff = sum(r["diff_medals"] or 0 for r in rows)
    total_investment = sum(r["investment_yen"] or 0 for r in rows)
    total_payout = sum(r["payout_yen"] or 0 for r in rows)
    net_yen = total_payout - total_investment
    avg_diff = round(total_diff / total_sessions, 1) if total_sessions else 0
    hyena_rows = [r for r in rows if r["is_hyena"]]

    by_machine = {}
    for r in rows:
        key = r["machine_name"]
        agg = by_machine.setdefault(key, {"count": 0, "diff": 0, "investment": 0, "payout": 0})
        agg["count"] += 1
        agg["diff"] += r["diff_medals"] or 0
        agg["investment"] += r["investment_yen"] or 0
        agg["payout"] += r["payout_yen"] or 0

    by_hall = {}
    for r in rows:
        key = r["hall_name"]
        agg = by_hall.setdefault(key, {"count": 0, "diff": 0, "investment": 0, "payout": 0})
        agg["count"] += 1
        agg["diff"] += r["diff_medals"] or 0
        agg["investment"] += r["investment_yen"] or 0
        agg["payout"] += r["payout_yen"] or 0

    sorted_by_diff = sorted(rows, key=lambda r: (r["diff_medals"] or 0), reverse=True)
    top5 = sorted_by_diff[:5]
    worst5 = list(reversed(sorted_by_diff[-5:])) if len(sorted_by_diff) >= 1 else []

    return {
        "total_sessions": total_sessions,
        "total_diff": total_diff,
        "total_investment": total_investment,
        "total_payout": total_payout,
        "net_yen": net_yen,
        "avg_diff": avg_diff,
        "hyena_count": len(hyena_rows),
        "hyena_diff": sum(r["diff_medals"] or 0 for r in hyena_rows),
        "by_machine": by_machine,
        "by_hall": by_hall,
        "top5": top5,
        "worst5": worst5,
    }


def render_markdown(start_date: str, end_date: str, stats: dict) -> str:
    lines = []
    lines.append(f"# 週次稼働レポート ({start_date} 〜 {end_date})")
    lines.append("")
    lines.append("## サマリー")
    lines.append("")
    lines.append(f"- 稼働回数: {stats['total_sessions']} 回")
    lines.append(f"- 合計差枚: {stats['total_diff']:+} 枚")
    lines.append(f"- 平均差枚: {stats['avg_diff']:+} 枚/回")
    lines.append(f"- 合計投資額: {stats['total_investment']:,} 円")
    lines.append(f"- 合計回収額: {stats['total_payout']:,} 円")
    lines.append(f"- 収支: {stats['net_yen']:+,} 円")
    lines.append(f"- ハイエナ狙い台: {stats['hyena_count']} 回（差枚合計 {stats['hyena_diff']:+} 枚）")
    lines.append("")

    lines.append("## 機種別集計")
    lines.append("")
    lines.append("| 機種 | 回数 | 差枚合計 | 投資額 | 回収額 |")
    lines.append("|---|---:|---:|---:|---:|")
    for name, agg in sorted(stats["by_machine"].items(), key=lambda kv: kv[1]["diff"], reverse=True):
        lines.append(f"| {name} | {agg['count']} | {agg['diff']:+} | {agg['investment']:,} | {agg['payout']:,} |")
    lines.append("")

    lines.append("## ホール別集計")
    lines.append("")
    lines.append("| ホール | 回数 | 差枚合計 | 投資額 | 回収額 |")
    lines.append("|---|---:|---:|---:|---:|")
    for name, agg in sorted(stats["by_hall"].items(), key=lambda kv: kv[1]["diff"], reverse=True):
        lines.append(f"| {name} | {agg['count']} | {agg['diff']:+} | {agg['investment']:,} | {agg['payout']:,} |")
    lines.append("")

    lines.append("## ベスト5")
    lines.append("")
    lines.append("| 日付 | ホール | 機種 | 台番号 | G数 | 差枚 |")
    lines.append("|---|---|---|---|---:|---:|")
    for r in stats["top5"]:
        lines.append(
            f"| {r['play_date']} | {r['hall_name']} | {r['machine_name']} | "
            f"{r['unit_number'] or '-'} | {r['total_games'] or '-'} | {(r['diff_medals'] or 0):+} |"
        )
    lines.append("")

    lines.append("## ワースト5")
    lines.append("")
    lines.append("| 日付 | ホール | 機種 | 台番号 | G数 | 差枚 |")
    lines.append("|---|---|---|---|---:|---:|")
    for r in stats["worst5"]:
        lines.append(
            f"| {r['play_date']} | {r['hall_name']} | {r['machine_name']} | "
            f"{r['unit_number'] or '-'} | {r['total_games'] or '-'} | {(r['diff_medals'] or 0):+} |"
        )
    lines.append("")

    return "\n".join(lines)


def render_html(start_date: str, end_date: str, stats: dict) -> str:
    def table_rows(agg_dict):
        rows = ""
        for name, agg in sorted(agg_dict.items(), key=lambda kv: kv[1]["diff"], reverse=True):
            rows += (
                f"<tr><td>{name}</td><td>{agg['count']}</td>"
                f"<td>{agg['diff']:+}</td><td>{agg['investment']:,}</td><td>{agg['payout']:,}</td></tr>\n"
            )
        return rows

    def session_rows(rows):
        out = ""
        for r in rows:
            out += (
                f"<tr><td>{r['play_date']}</td><td>{r['hall_name']}</td><td>{r['machine_name']}</td>"
                f"<td>{r['unit_number'] or '-'}</td><td>{r['total_games'] or '-'}</td>"
                f"<td>{(r['diff_medals'] or 0):+}</td></tr>\n"
            )
        return out

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">
<title>週次稼働レポート ({start_date} 〜 {end_date})</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif;
    margin: 0;
    padding: 1rem;
    color: #1c1c1e;
    background: #f4f5f7;
    max-width: 720px;
    margin-left: auto;
    margin-right: auto;
  }}
  h1 {{ font-size: 1.2rem; }}
  h2 {{ font-size: 1.05rem; margin-top: 1.8rem; border-bottom: 1px solid #ccc; padding-bottom: 0.3rem; }}
  .table-scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; margin-top: 0.5rem; }}
  table {{ border-collapse: collapse; width: 100%; min-width: 480px; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: right; font-size: 0.85rem; white-space: nowrap; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ background: #eaeaea; }}
  ul.summary {{ line-height: 1.8; padding-left: 1.2rem; font-size: 0.95rem; }}

  @media (prefers-color-scheme: dark) {{
    body {{ background: #000; color: #eee; }}
    h2 {{ border-bottom-color: #333; }}
    th, td {{ border-color: #3a3a3c; }}
    th {{ background: #2c2c2e; }}
  }}
</style>
</head>
<body>
<h1>週次稼働レポート ({start_date} 〜 {end_date})</h1>

<h2>サマリー</h2>
<ul class="summary">
  <li>稼働回数: {stats['total_sessions']} 回</li>
  <li>合計差枚: {stats['total_diff']:+} 枚</li>
  <li>平均差枚: {stats['avg_diff']:+} 枚/回</li>
  <li>合計投資額: {stats['total_investment']:,} 円</li>
  <li>合計回収額: {stats['total_payout']:,} 円</li>
  <li>収支: {stats['net_yen']:+,} 円</li>
  <li>ハイエナ狙い台: {stats['hyena_count']} 回（差枚合計 {stats['hyena_diff']:+} 枚）</li>
</ul>

<h2>機種別集計</h2>
<div class="table-scroll"><table>
<tr><th>機種</th><th>回数</th><th>差枚合計</th><th>投資額</th><th>回収額</th></tr>
{table_rows(stats['by_machine'])}
</table></div>

<h2>ホール別集計</h2>
<div class="table-scroll"><table>
<tr><th>ホール</th><th>回数</th><th>差枚合計</th><th>投資額</th><th>回収額</th></tr>
{table_rows(stats['by_hall'])}
</table></div>

<h2>ベスト5</h2>
<div class="table-scroll"><table>
<tr><th>日付</th><th>ホール</th><th>機種</th><th>台番号</th><th>G数</th><th>差枚</th></tr>
{session_rows(stats['top5'])}
</table></div>

<h2>ワースト5</h2>
<div class="table-scroll"><table>
<tr><th>日付</th><th>ホール</th><th>機種</th><th>台番号</th><th>G数</th><th>差枚</th></tr>
{session_rows(stats['worst5'])}
</table></div>

</body>
</html>
"""
    return html


def main():
    parser = argparse.ArgumentParser(description="週次稼働統計レポートを生成する")
    parser.add_argument("--days", type=int, default=7, help="集計対象期間（日数、デフォルト7）")
    parser.add_argument("--format", choices=["md", "html", "both"], default="both", help="出力形式")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="出力先ディレクトリ")
    args = parser.parse_args()

    end_date = date.today()
    start_date = end_date - timedelta(days=args.days - 1)
    start_str, end_str = start_date.isoformat(), end_date.isoformat()

    conn = get_connection()
    try:
        rows = fetch_sessions(conn, start_str, end_str)
    finally:
        conn.close()

    stats = summarize(rows)
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = end_date.strftime("%Y%m%d")

    if args.format in ("md", "both"):
        md_path = os.path.join(args.output_dir, f"weekly_report_{stamp}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(render_markdown(start_str, end_str, stats))
        print(f"Markdownレポートを生成しました: {md_path}")

    if args.format in ("html", "both"):
        html_path = os.path.join(args.output_dir, f"weekly_report_{stamp}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(render_html(start_str, end_str, stats))
        print(f"HTMLレポートを生成しました: {html_path}")

    if stats["total_sessions"] == 0:
        print("注意: 対象期間の稼働データがありませんでした。")


if __name__ == "__main__":
    main()
