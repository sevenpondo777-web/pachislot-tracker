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

# カード左端のアクセント色を切り替えるためのキー
CATEGORY_KEY = {
    "天井": "tenjyo",
    "ゾーン": "zone",
    "設定示唆": "settei",
    "狙い目": "nerai",
    "その他": "other",
}

TREATMENT_KEY = {
    "優遇": "yugu",
    "冷遇": "reigu",
    "不明": "fumei",
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
    acc = CATEGORY_KEY.get(row["category"], "other")
    tenjyo_range = ""
    if row["tenjyo_min"] is not None or row["tenjyo_max"] is not None:
        tmin = row["tenjyo_min"] if row["tenjyo_min"] is not None else "?"
        tmax = row["tenjyo_max"] if row["tenjyo_max"] is not None else "?"
        tenjyo_range = f'<div class="chip chip-tenjyo">🎯 天井目安 {esc(tmin)}–{esc(tmax)}G</div>'
    source_line = esc(row["source_name"])
    if row["source_url"]:
        source_line = f'<a href="{esc(row["source_url"])}" target="_blank" rel="noopener">{source_line}</a>'
    return f"""
    <article class="info-card acc-{acc}">
      <div class="info-card-head">
        <span class="badge {badge_class}">{esc(row['category'])}</span>
        <span class="info-title">{esc(row['title'])}</span>
      </div>
      <p class="info-summary">{esc(row['summary'])}</p>
      {tenjyo_range}
      <div class="info-source">出典 {source_line}<span class="src-dot">·</span>{esc(row['collected_date'])}収集</div>
    </article>
    """


def render_bias_card(row) -> str:
    treat_class = TREATMENT_BADGE_CLASS.get(row["treatment"], "badge-fumei")
    conf_class = CONFIDENCE_BADGE_CLASS.get(row["confidence"], "conf-mid")
    acc = TREATMENT_KEY.get(row["treatment"], "fumei")
    target = f'<span class="target-setting">対象設定 {esc(row["target_setting"])}</span>' if row["target_setting"] else ""
    sample = f'<div class="chip chip-sample">📊 サンプル {esc(row["sample_size"])}</div>' if row["sample_size"] else ""
    source_line = esc(row["source_name"])
    if row["source_url"]:
        source_line = f'<a href="{esc(row["source_url"])}" target="_blank" rel="noopener">{source_line}</a>'
    return f"""
    <article class="info-card bias-card acc-{acc}">
      <div class="info-card-head">
        <span class="badge {treat_class}">{esc(row['treatment'])}</span>
        <span class="badge badge-cat">{esc(row['category'])}</span>
        <span class="conf-badge {conf_class}">信頼度 {esc(row['confidence'])}</span>
        {target}
      </div>
      <p class="info-summary">{esc(row['summary'])}</p>
      {sample}
      <div class="info-source"><span class="src-type">{esc(row['source_type'])}</span>{source_line}<span class="src-dot">·</span>{esc(row['collected_date'])}収集</div>
    </article>
    """


def pick_primary_tenjyo(strategy_rows):
    """天井カードが複数ある場合に、早見ストリップに出す代表1件を選ぶ。
    min/maxが両方揃っている中で最もtenjyo_maxが大きいもの(=短縮版でない通常天井)を優先する。
    """
    tenjyo_rows = [r for r in strategy_rows if r["category"] == "天井"]
    if not tenjyo_rows:
        return None
    both = [r for r in tenjyo_rows if r["tenjyo_min"] is not None and r["tenjyo_max"] is not None]
    if both:
        return max(both, key=lambda r: r["tenjyo_max"])
    any_max = [r for r in tenjyo_rows if r["tenjyo_max"] is not None]
    if any_max:
        return max(any_max, key=lambda r: r["tenjyo_max"])
    any_min = [r for r in tenjyo_rows if r["tenjyo_min"] is not None]
    if any_min:
        return any_min[0]
    return tenjyo_rows[0]


def render_tenjyo_strip(strategy_rows) -> str:
    row = pick_primary_tenjyo(strategy_rows)
    if row is None:
        return ""
    tmin, tmax = row["tenjyo_min"], row["tenjyo_max"]
    if tmin is not None and tmax is not None:
        num = f'{esc(tmin)}<span class="unit">〜</span>{esc(tmax)}<span class="unit">G</span>'
    elif tmax is not None:
        num = f'<span class="unit">〜</span>{esc(tmax)}<span class="unit">G</span>'
    elif tmin is not None:
        num = f'{esc(tmin)}<span class="unit">G〜</span>'
    else:
        return """
    <div class="tenjyo-strip fallback">
      <span class="fallback-pill">🎯 天井情報あり（詳細は下記カード参照）</span>
    </div>
    """
    return f"""
    <div class="tenjyo-strip">
      <span class="tenjyo-strip-cap">🎯 天井目安</span>
      <span class="tenjyo-strip-num">{num}</span>
    </div>
    """


def render_machine_section(name: str, strategy_rows, bias_rows) -> str:
    anchor = html.escape(name, quote=True)
    tenjyo_strip = render_tenjyo_strip(strategy_rows)
    strategy_html = "".join(render_strategy_card(r) for r in strategy_rows) or '<p class="empty">登録なし</p>'
    bias_html = "".join(render_bias_card(r) for r in bias_rows) or '<p class="empty">登録なし（未確認）</p>'
    return f"""
    <section class="machine-section" id="m-{anchor}">
      <h2 class="machine-name">{esc(name)}</h2>
      {tenjyo_strip}
      <h3 class="section-label"><span class="dot dot-info"></span>攻略情報 <span class="label-note">公式・一般</span></h3>
      {strategy_html}
      <h3 class="section-label"><span class="dot dot-warn"></span>優遇/冷遇・実践値 <span class="label-note">未検証・参考</span></h3>
      {bias_html}
    </section>
    """


def render_picker(names) -> str:
    """スマホ向けの機種セレクタ（下部固定ボタン＋全画面ボトムシート）。

    画面下部の親指が届く位置に「機種を選ぶ」ボタンを常駐させ、タップすると
    検索欄付きの一覧シートが立ち上がる。インクリメンタル検索で目的の機種を
    絞り込み、タップでその機種セクションへスクロールする。
    """
    items = "".join(
        f'<button type="button" class="pick-item" data-target="m-{html.escape(n, quote=True)}">'
        f'<span class="pick-name">{esc(n)}</span><span class="pick-go" aria-hidden="true">›</span>'
        f'</button>'
        for n in names
    )
    count = len(names)
    return f"""
    <div class="pick-bar">
      <button type="button" class="pick-top" id="pickTop" aria-label="ページ上部へ戻る">↑</button>
      <button type="button" class="pick-open" id="pickOpen" aria-haspopup="dialog" aria-expanded="false">
        <span class="pick-open-ico">🎰</span>機種を選ぶ<span class="pick-open-count">{count}</span>
      </button>
    </div>
    <div class="sheet" id="sheet" hidden>
      <div class="sheet-backdrop" data-close></div>
      <div class="sheet-panel" role="dialog" aria-modal="true" aria-label="機種を選ぶ">
        <div class="sheet-grip"></div>
        <div class="sheet-head">
          <input type="search" id="pickSearch" class="sheet-search"
                 placeholder="機種名で検索（例: 北斗 / モンキー）"
                 autocomplete="off" enterkeyhint="search" aria-label="機種名で検索">
          <button type="button" class="sheet-close" data-close aria-label="閉じる">✕</button>
        </div>
        <div class="sheet-list" id="sheetList">
          {items}
        </div>
        <p class="sheet-empty" id="sheetEmpty" hidden>該当する機種がありません</p>
      </div>
    </div>
    """


def render_html(sections_data) -> str:
    names = [name for name, _, _ in sections_data]
    picker = render_picker(names) if sections_data else ""
    body = "".join(render_machine_section(name, s, b) for name, s, b in sections_data)
    if not sections_data:
        body = '<p class="empty">登録されている機種情報がありません。fetch_public_info.py で追加してください。</p>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5, viewport-fit=cover">
<title>機種リファレンス</title>
<meta name="theme-color" content="#1c1c1e">
<meta name="description" content="パチスロ機種の攻略情報・優遇冷遇まとめ（無料公開情報ベース）">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="機種メモ">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/svg+xml" href="icons/icon.svg">
<link rel="apple-touch-icon" href="icons/icon-180.png">
<style>
  :root {{
    color-scheme: light dark;
    --bg: #eef1f7;
    --bg-2: #e7ebf4;
    --surface: #ffffff;
    --surface-2: #f7f8fb;
    --border: #e7e9f0;
    --ink: #1a1d29;
    --muted: #666d7d;
    --faint: #9aa1ad;
    --link: #4f46e5;
    --primary: #6366f1;
    --primary-2: #8b5cf6;
    --shadow: 0 1px 2px rgba(16,24,40,.05), 0 10px 28px -14px rgba(16,24,40,.20);
    --tenjyo: #2563eb;
    --zone:   #0f9d75;
    --settei: #7c3aed;
    --nerai:  #d97706;
    --other:  #64748b;
    --cat:    #475569;
    --yugu:   #e11d48;
    --reigu:  #2563eb;
    --fumei:  #64748b;
  }}
  * {{ box-sizing: border-box; }}
  html {{ overflow-x: hidden; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", "Segoe UI", sans-serif;
    margin: 0;
    overflow-x: hidden;
    padding: 0 0 calc(6rem + env(safe-area-inset-bottom)) 0;
    background: linear-gradient(180deg, var(--bg-2), var(--bg) 240px);
    background-attachment: fixed;
    color: var(--ink);
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }}
  header {{
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 55%, #9333ea 100%);
    color: #fff;
    padding: 1rem 1rem 0.7rem 1rem;
    position: sticky;
    top: 0;
    z-index: 10;
    box-shadow: 0 6px 22px -10px rgba(79,70,229,.55);
  }}
  header h1 {{
    font-size: 1.08rem;
    font-weight: 700;
    letter-spacing: .01em;
    margin: 0;
    display: flex;
    align-items: center;
    gap: .45rem;
  }}
  header h1 .logo {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.55rem;
    height: 1.55rem;
    border-radius: 8px;
    background: rgba(255,255,255,.18);
    font-size: .95rem;
  }}
  header .subtitle {{
    margin: .2rem 0 .7rem 0;
    font-size: .72rem;
    color: rgba(255,255,255,.82);
    letter-spacing: .02em;
  }}
  /* ===== 下部固定の機種セレクタ ===== */
  .pick-bar {{
    position: fixed;
    left: 0; right: 0; bottom: 0;
    z-index: 40;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.6rem;
    padding: 0.55rem 0.9rem calc(0.55rem + env(safe-area-inset-bottom));
    background: linear-gradient(180deg, transparent, var(--bg) 45%);
    pointer-events: none;
  }}
  .pick-open {{
    pointer-events: auto;
    flex: 0 1 430px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    height: 3rem;
    padding: 0 1.3rem;
    border: 0;
    border-radius: 999px;
    cursor: pointer;
    font-size: 0.98rem;
    font-weight: 700;
    letter-spacing: .02em;
    color: #fff;
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    box-shadow: 0 12px 28px -8px rgba(79,70,229,.62), 0 2px 6px rgba(0,0,0,.15);
    transition: transform .1s ease;
  }}
  .pick-open:active {{ transform: translateY(1px) scale(.99); }}
  .pick-open-ico {{ font-size: 1.05rem; }}
  .pick-open-count {{
    font-size: .72rem;
    font-weight: 700;
    background: rgba(255,255,255,.22);
    padding: .05rem .5rem;
    border-radius: 999px;
  }}
  .pick-top {{
    pointer-events: none;
    width: 2.7rem; height: 2.7rem;
    flex: 0 0 auto;
    border-radius: 50%;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--ink);
    font-size: 1.15rem;
    cursor: pointer;
    opacity: 0;
    transform: translateY(8px);
    transition: opacity .18s ease, transform .18s ease;
    box-shadow: var(--shadow);
  }}
  .pick-top.show {{ pointer-events: auto; opacity: 1; transform: none; }}

  /* ===== 全画面ボトムシート ===== */
  .sheet {{ position: fixed; inset: 0; z-index: 60; }}
  .sheet[hidden] {{ display: none; }}
  .sheet-backdrop {{
    position: absolute; inset: 0;
    background: rgba(10,12,20,.5);
    opacity: 0;
    transition: opacity .22s ease;
  }}
  .sheet.open .sheet-backdrop {{ opacity: 1; }}
  .sheet-panel {{
    position: absolute;
    left: 0; right: 0; bottom: 0;
    max-width: 720px;
    margin: 0 auto;
    max-height: 82vh;
    display: flex;
    flex-direction: column;
    background: var(--surface);
    border-radius: 20px 20px 0 0;
    box-shadow: 0 -14px 44px -12px rgba(0,0,0,.42);
    transform: translateY(100%);
    transition: transform .26s cubic-bezier(.22,1,.36,1);
    padding-bottom: env(safe-area-inset-bottom);
  }}
  .sheet.open .sheet-panel {{ transform: none; }}
  .sheet-grip {{
    width: 38px; height: 4px;
    border-radius: 999px;
    background: var(--border);
    margin: .55rem auto .1rem;
  }}
  .sheet-head {{
    display: flex;
    align-items: center;
    gap: .5rem;
    padding: .5rem .9rem .7rem;
  }}
  .sheet-search {{
    flex: 1;
    height: 2.85rem;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--surface-2);
    color: var(--ink);
    font-size: 1rem;
    padding: 0 .9rem;
    outline: none;
    transition: border-color .15s ease, box-shadow .15s ease;
  }}
  .sheet-search:focus {{
    border-color: var(--primary);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 20%, transparent);
  }}
  .sheet-close {{
    width: 2.6rem; height: 2.6rem;
    flex: 0 0 auto;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--surface-2);
    color: var(--muted);
    font-size: 1rem;
    cursor: pointer;
  }}
  .sheet-list {{
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    padding: .2rem .7rem 1rem;
  }}
  .pick-item {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: .6rem;
    width: 100%;
    text-align: left;
    cursor: pointer;
    padding: .85rem .9rem;
    margin-bottom: .4rem;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface-2);
    color: var(--ink);
    font-size: .95rem;
    font-weight: 600;
    letter-spacing: .01em;
  }}
  .pick-item:active {{ background: color-mix(in srgb, var(--primary) 10%, var(--surface-2)); }}
  .pick-name {{ min-width: 0; line-height: 1.4; word-break: break-word; }}
  .pick-go {{ font-size: 1.25rem; font-weight: 700; color: var(--primary); flex: 0 0 auto; line-height: 1; }}
  .sheet-empty {{
    text-align: center;
    color: var(--faint);
    padding: 1.4rem;
    font-size: .9rem;
  }}
  body.sheet-lock {{ overflow: hidden; }}
  main {{
    max-width: 720px;
    margin: 0 auto;
    padding: 1rem 0.8rem;
  }}
  .machine-section {{
    position: relative;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 1.15rem 1.15rem 1.25rem;
    margin-bottom: 1.1rem;
    box-shadow: var(--shadow);
    scroll-margin-top: 4.75rem;
    overflow: hidden;
  }}
  .machine-section::before {{
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 4px;
    background: linear-gradient(90deg, var(--primary), var(--primary-2));
  }}
  .machine-name {{
    display: flex;
    align-items: center;
    gap: .55rem;
    font-size: 1.22rem;
    font-weight: 700;
    letter-spacing: .01em;
    margin: 0.25rem 0 1rem 0;
    overflow-wrap: anywhere;
  }}
  .info-title, .pick-name {{ overflow-wrap: anywhere; }}
  .machine-name::before {{
    content: "";
    flex: 0 0 auto;
    width: .28rem;
    height: 1.15em;
    border-radius: 3px;
    background: linear-gradient(180deg, var(--primary), var(--primary-2));
  }}
  .section-label {{
    display: flex;
    align-items: center;
    gap: .5rem;
    font-size: 0.86rem;
    font-weight: 700;
    color: var(--muted);
    margin: 1.25rem 0 0.65rem 0;
  }}
  .section-label .dot {{
    width: .5rem;
    height: .5rem;
    border-radius: 50%;
    flex: 0 0 auto;
  }}
  .dot-info {{ background: var(--primary); }}
  .dot-warn {{ background: var(--nerai); }}
  .label-note {{
    font-size: .68rem;
    font-weight: 600;
    color: var(--faint);
    background: var(--surface-2);
    border: 1px solid var(--border);
    padding: .06rem .45rem;
    border-radius: 999px;
    letter-spacing: .02em;
  }}
  .info-card {{
    position: relative;
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent, #cbd5e1);
    border-radius: 12px;
    padding: 0.75rem 0.85rem;
    margin-bottom: 0.55rem;
    background: var(--surface-2);
    transition: transform .1s ease, box-shadow .15s ease;
  }}
  .info-card:hover {{
    box-shadow: 0 6px 18px -12px rgba(16,24,40,.28);
  }}
  .acc-tenjyo {{ --accent: var(--tenjyo); }}
  .acc-zone   {{ --accent: var(--zone); }}
  .acc-settei {{ --accent: var(--settei); }}
  .acc-nerai  {{ --accent: var(--nerai); }}
  .acc-other  {{ --accent: var(--other); }}
  .acc-yugu   {{ --accent: var(--yugu); }}
  .acc-reigu  {{ --accent: var(--reigu); }}
  .acc-fumei  {{ --accent: var(--fumei); }}
  .bias-card {{
    background: color-mix(in srgb, var(--nerai) 5%, var(--surface-2));
  }}
  .info-card-head {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 0.35rem;
  }}
  .info-title {{
    font-weight: 650;
    font-size: 0.95rem;
    letter-spacing: .01em;
  }}
  .badge {{
    display: inline-block;
    font-size: 0.72rem;
    padding: 0.16rem 0.55rem;
    border-radius: 999px;
    font-weight: 700;
    letter-spacing: .02em;
    color: var(--c, #475569);
    background: color-mix(in srgb, var(--c, #475569) 13%, transparent);
    border: 1px solid color-mix(in srgb, var(--c, #475569) 26%, transparent);
  }}
  .badge-tenjyo {{ --c: var(--tenjyo); }}
  .badge-zone   {{ --c: var(--zone); }}
  .badge-settei {{ --c: var(--settei); }}
  .badge-nerai  {{ --c: var(--nerai); }}
  .badge-other  {{ --c: var(--other); }}
  .badge-cat    {{ --c: var(--cat); }}
  .badge-yugu   {{ --c: var(--yugu); }}
  .badge-reigu  {{ --c: var(--reigu); }}
  .badge-fumei  {{ --c: var(--fumei); }}
  .conf-badge {{
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.14rem 0.5rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    color: var(--muted);
  }}
  .conf-high {{ background: color-mix(in srgb, #0f9d75 12%, transparent); border-color: color-mix(in srgb,#0f9d75 34%,transparent); color: #0b7a5b; }}
  .conf-mid  {{ background: color-mix(in srgb, #d97706 12%, transparent); border-color: color-mix(in srgb,#d97706 34%,transparent); color: #b45309; }}
  .conf-low  {{ background: color-mix(in srgb, #e11d48 12%, transparent); border-color: color-mix(in srgb,#e11d48 34%,transparent); color: #be123c; }}
  .target-setting {{
    font-size: 0.76rem;
    font-weight: 600;
    color: var(--muted);
    background: var(--surface);
    border: 1px solid var(--border);
    padding: .1rem .5rem;
    border-radius: 999px;
  }}
  .info-summary {{
    margin: 0.35rem 0;
    font-size: 0.9rem;
    color: var(--ink);
  }}
  .chip {{
    display: inline-flex;
    align-items: center;
    gap: .3rem;
    font-size: 0.78rem;
    font-weight: 600;
    padding: .2rem .55rem;
    border-radius: 8px;
    margin: .15rem .3rem .15rem 0;
  }}
  .chip-tenjyo {{ color: var(--tenjyo); background: color-mix(in srgb, var(--tenjyo) 11%, transparent); }}
  .chip-sample {{ color: var(--muted); background: var(--surface); border: 1px solid var(--border); }}
  .info-source {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: .3rem;
    font-size: 0.73rem;
    color: var(--faint);
    margin-top: 0.45rem;
    word-break: break-all;
  }}
  .info-source a {{ color: var(--link); text-decoration: none; }}
  .info-source a:hover {{ text-decoration: underline; }}
  .src-dot {{ color: var(--border); }}
  .src-type {{
    font-size: .66rem;
    font-weight: 700;
    color: var(--muted);
    background: var(--surface);
    border: 1px solid var(--border);
    padding: .02rem .38rem;
    border-radius: 5px;
  }}
  .empty {{
    color: var(--faint);
    font-size: 0.85rem;
    padding: .4rem 0;
  }}
  /* ===== 天井早見ストリップ(機種名直下) ===== */
  .tenjyo-strip {{
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: .5rem;
    background: color-mix(in srgb, var(--tenjyo) 7%, var(--surface-2));
    border: 1px solid color-mix(in srgb, var(--tenjyo) 22%, var(--border));
    border-radius: 12px;
    padding: .65rem .85rem;
    margin: 0 0 1.1rem 0;
  }}
  .tenjyo-strip-cap {{
    font-size: .72rem;
    font-weight: 700;
    color: var(--muted);
    letter-spacing: .02em;
    flex: 1 1 100%;
  }}
  .tenjyo-strip-num {{
    font-variant-numeric: tabular-nums;
    font-size: 1.35rem;
    font-weight: 800;
    color: var(--tenjyo);
    line-height: 1;
  }}
  .tenjyo-strip-num .unit {{
    font-size: .78rem;
    font-weight: 600;
    color: var(--muted);
    margin: 0 .1rem;
  }}
  .tenjyo-strip.fallback {{
    background: var(--surface-2);
    border-color: var(--border);
  }}
  .fallback-pill {{
    display: inline-flex;
    align-items: center;
    gap: .35rem;
    font-size: .8rem;
    font-weight: 600;
    color: var(--muted);
  }}
  .site-footer {{
    max-width: 720px;
    margin: 1.5rem auto 0;
    padding: 0 1.2rem;
    font-size: .72rem;
    color: var(--faint);
    text-align: center;
    line-height: 1.7;
  }}

  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0b0c11;
      --bg-2: #12141c;
      --surface: #161822;
      --surface-2: #1c1f2b;
      --border: #272b38;
      --ink: #e8eaf0;
      --muted: #9ba3b4;
      --faint: #727a8b;
      --link: #a5b4fc;
      --shadow: 0 1px 2px rgba(0,0,0,.4), 0 14px 32px -16px rgba(0,0,0,.75);
      --tenjyo: #60a5fa;
      --zone:   #34d399;
      --settei: #a78bfa;
      --nerai:  #fbbf24;
      --other:  #94a3b8;
      --cat:    #94a3b8;
      --yugu:   #fb7185;
      --reigu:  #60a5fa;
      --fumei:  #94a3b8;
    }}
    .conf-high {{ color: #34d399; }}
    .conf-mid  {{ color: #fbbf24; }}
    .conf-low  {{ color: #fb7185; }}
  }}
</style>
</head>
<body>
<header>
  <h1><span class="logo">🎰</span>機種リファレンス</h1>
  <p class="subtitle">攻略情報・優遇/冷遇まとめ（無料公開情報ベース）</p>
</header>
<main>
{body}
</main>
<footer class="site-footer">
  掲載情報は無料公開情報をもとにした参考値です。優遇/冷遇・実践値は未検証情報を含みます。<br>
  最終的な判断はご自身の責任でお願いします。
</footer>
{picker}
<script>
  if ("serviceWorker" in navigator) {{
    window.addEventListener("load", function () {{
      navigator.serviceWorker.register("sw.js").catch(function () {{}});
    }});
  }}

  (function () {{
    var sheet = document.getElementById("sheet");
    if (!sheet) return;
    var openBtn = document.getElementById("pickOpen");
    var topBtn = document.getElementById("pickTop");
    var search = document.getElementById("pickSearch");
    var empty = document.getElementById("sheetEmpty");
    var items = [].slice.call(document.querySelectorAll(".pick-item"));

    function norm(s) {{ return (s || "").toLowerCase().replace(/\\s+/g, ""); }}
    function filter(q) {{
      var nq = norm(q), shown = 0;
      items.forEach(function (it) {{
        var hit = nq === "" || norm(it.textContent).indexOf(nq) >= 0;
        it.style.display = hit ? "" : "none";
        if (hit) shown++;
      }});
      empty.hidden = shown !== 0;
    }}
    function openSheet() {{
      sheet.hidden = false;
      document.body.classList.add("sheet-lock");
      openBtn.setAttribute("aria-expanded", "true");
      search.value = ""; filter("");
      requestAnimationFrame(function () {{
        sheet.classList.add("open");
        setTimeout(function () {{ try {{ search.focus(); }} catch (e) {{}} }}, 90);
      }});
    }}
    function closeSheet() {{
      sheet.classList.remove("open");
      document.body.classList.remove("sheet-lock");
      openBtn.setAttribute("aria-expanded", "false");
      setTimeout(function () {{ sheet.hidden = true; }}, 220);
    }}

    openBtn.addEventListener("click", openSheet);
    topBtn.addEventListener("click", function () {{
      window.scrollTo({{ top: 0, behavior: "smooth" }});
    }});
    search.addEventListener("input", function () {{ filter(search.value); }});
    sheet.addEventListener("click", function (e) {{
      var t = e.target;
      if (t.closest && t.closest("[data-close]")) {{ closeSheet(); return; }}
      var item = t.closest ? t.closest(".pick-item") : null;
      if (item) {{
        var id = item.getAttribute("data-target");
        closeSheet();
        var el = document.getElementById(id);
        if (el) {{ setTimeout(function () {{ el.scrollIntoView({{ behavior: "smooth", block: "start" }}); }}, 240); }}
      }}
    }});
    document.addEventListener("keydown", function (e) {{
      if (e.key === "Escape" && !sheet.hidden) closeSheet();
    }});
    window.addEventListener("scroll", function () {{
      if (window.scrollY > 400) topBtn.classList.add("show");
      else topBtn.classList.remove("show");
    }}, {{ passive: true }});
  }})();
</script>
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
