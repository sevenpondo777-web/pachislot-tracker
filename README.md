# パチスロ・ハイエナ稼働データ管理システム

対象ホール: **相模原プラザ**（神奈川県相模原市）ほか

ローカルSQLiteで動作する、**世の中の無料公開情報を継続的に集めて「台を打つときの判断根拠」を
作るためのツール**です。中心となるのは以下の2種類のデータで、これを蓄積して
`machine_report.py`が生成するスマホ向けページに育てていくのがメインの使い方です。

- **A. 機種の一般攻略情報**（天井G数、ゾーン期待値、狙い目条件など）— 無料公開情報のみ
- **C. 優遇/冷遇・実践値ベースの設定推測情報**（メーカー非公式、コミュニティ実践値）— 無料公開情報のみ

以下は**オプション機能**で、使わなくてもA・Cの情報収集には影響しません。

- **B. 自分が実地で記録するホールデータ**（差枚・G数・設定示唆など）— 使う場合のみ`log_data.py`/`weekly_report.py`を利用

## ⚠️ 重要な制約・設計方針（必ず読んでください）

- **有料攻略サイト（すろらぼ等）のスクレイピング・自動巡回・コンテンツ複製は一切行いません。**
  `fetch_public_info.py` はネットワークアクセス機能を持たない完全オフラインの
  「手動キュレーションツール」です。ユーザー自身（または対話中にClaudeが検索した結果を
  ユーザーが確認したもの）が無料の公開情報（メーカー公式サイト、公式YouTube、無料ブログ、
  X投稿、まとめサイト等）を調べ、**自分の言葉で要約**し、出典（サイト名・URL）とともに
  DBへ記録する、という使い方を想定しています。他サイトの文章をそのままコピペして保存する
  用途には使わないでください。
- 既知の有料サイトドメインを簡易ブラックリストで検出し、該当する場合は保存を拒否します
  （`fetch_public_info.py` 内 `BLOCKED_DOMAINS`）。ただし、これは多重の安全策の一つに過ぎず、
  リストに無い有料サイトであっても入力しないでください。まとめサイトは有料サイトの内容を
  無断転載している場合があるため、収集前に出典が本当に無料公開情報かを自分の目で確認すること。
- 優遇/冷遇情報（C）はメーカー非公式の未検証情報であるため、必ず `confidence`（信頼度:
  高/中/低）を付与し、公式攻略情報（A）とは明確に区別して扱う。
- 実在ホールの運営情報・著作物の無断収集は行いません。ホールに関するデータは、機種構成の
  確認など本人が能動的に調べた範囲と、**（使う場合のみ）自分が実地で記録した稼働データ**
  （B、オプション）のみを対象とします。
- 収集・記録した情報は**個人の稼働判断の参考**として利用することのみを目的とします。
- **無人の自動収集スクリプトは意図的に作っていません。** 優遇/冷遇情報のような「鮮度の良い
  コミュニティ情報」が欲しい場合は、Claudeとの対話の中で「〇〇の優遇冷遇情報を調べて」と
  依頼し、Claudeが無料公開情報を検索・要約したものをユーザーが確認したうえで、
  `add-bias` / `import-bias` コマンドでDBに保存する運用を想定しています（詳細は下記）。

## 動作環境

- Python 3.9以降（標準ライブラリのみ使用、追加インストール不要）
- Windows 10/11（Windowsタスクスケジューラーでの自動実行を想定）

### 文字化けについて

日本語を含む出力がターミナルで文字化けする場合は、以下のいずれかを試してください。

```powershell
# PowerShellの場合
chcp 65001
$env:PYTHONUTF8 = "1"
```

```
# コマンドプロンプトの場合
chcp 65001
set PYTHONUTF8=1
```

これは端末側の表示（コードページ）の問題であり、SQLiteに保存されるデータ自体は
常にUTF-8で正しく保存されます。

## セットアップ

```powershell
cd pachislot-tracker
python init_db.py
```

`db/pachislot.db` が作成され、対象ホール「相模原プラザ」が自動登録されます。
DBを作り直したい場合（既存データは削除されます）:

```powershell
python init_db.py --reset
```

既存のDBに新しいテーブル（例: 後から追加した `machine_bias_info`）だけを追加したい場合は、
`--reset` を付けずに `python init_db.py` を再実行してください。`CREATE TABLE IF NOT EXISTS`
方式のため、既存データを削除せずに不足しているテーブルだけが追加されます。

## ファイル構成

```
pachislot-tracker/
├── init_db.py            # DBスキーマ初期化
├── fetch_public_info.py   # 攻略情報・優遇冷遇情報の手動キュレーションツール【中心機能】
├── machine_report.py       # 機種リファレンス（スマホ向けHTML）生成【中心機能】
├── log_data.py            # 稼働データ入力CLI（オプション、使わなくてもよい）
├── weekly_report.py        # 週次統計レポート生成（オプション、log_data.pyを使う場合のみ意味を持つ）
├── db/
│   └── pachislot.db        # SQLiteファイル（init_db.py実行後に生成）
└── reports/
    ├── machine_reference.html      # 生成された機種リファレンス（スマホ向け、メインの成果物）
    └── weekly_report_*.md / .html  # 生成された週次レポート（オプション機能の成果物）
```

## データベーススキーマ概要

| テーブル | 内容 |
|---|---|
| `halls` | ホールマスタ（相模原プラザ等） |
| `machines` | 機種マスタ |
| `machine_strategy_info` | 機種の一般攻略情報（メーカー公式等の無料公開情報・手動投入）【中心データ】 |
| `machine_bias_info` | 優遇/冷遇・実践値ベースの設定推測情報（コミュニティ実践値・無料公開情報）【中心データ】 |
| `play_sessions` | 実地で記録した稼働データ（オプション機能、使わない場合は空のまま） |

`play_sessions` の主なカラム: `play_date`, `hall_id`, `machine_id`, `unit_number`,
`total_games`, `diff_medals`, `investment_yen`, `payout_yen`, `setting_hint`,
`estimated_setting`, `is_hyena`, `memo`

`machine_bias_info` の主なカラム: `machine_id`, `category`（演出頻度偏り/AT当選率偏り/
内部モード示唆/その他）, `treatment`（優遇/冷遇/不明）, `target_setting`（対象設定、自由記述）,
`summary`, `sample_size`（実践サンプル数の目安）, `confidence`（高/中/低）, `source_type`
（X投稿/個人ブログ/まとめサイト/その他）, `source_name`, `source_url`, `collected_date`

## 使い方

情報収集の中心となるのは「1. 攻略情報」「2. 優遇/冷遇情報」「3. 機種リファレンス生成」の3つです。
「4. 稼働データの記録」「5. 週次統計レポート」はオプション機能で、使わなくても1〜3の運用には影響しません。

### 1. 攻略情報の登録・閲覧（fetch_public_info.py）

追加（自分で調べた無料公開情報を要約して保存）:

```powershell
python fetch_public_info.py add --machine "北斗の拳" --category 天井 `
  --title "天井G数（メーカー公式スペックより）" `
  --summary "自分で確認したメーカー公式スペック表に基づく要約。" `
  --tenjyo-min 950 --tenjyo-max 999 `
  --source-name "メーカー公式サイト" --source-url "https://example.com/spec"
```

`--category` は `天井` / `ゾーン` / `設定示唆` / `狙い目` / `その他` から選択します。

一覧表示:

```powershell
python fetch_public_info.py list --machine "北斗の拳"
python fetch_public_info.py list   # 全件表示
```

複数件をまとめて登録したい場合（Claudeが検索結果を機種分まとめてJSONにしてから一括投入する
運用を想定）:

```powershell
python fetch_public_info.py import --file strategy_entries.json
```

`strategy_entries.json` の形式（オブジェクトのリスト。必須項目: `machine`, `category`,
`title`, `summary`, `source_name`）:

```json
[
  {
    "machine": "スマスロ北斗の拳",
    "category": "天井",
    "title": "天井G数とAT当選条件",
    "summary": "自分の言葉での要約",
    "tenjyo_min": 800,
    "tenjyo_max": 1268,
    "source_name": "解析まとめサイト名",
    "source_url": "https://example.com/..."
  }
]
```

有料サイトのドメインが含まれるエントリは自動的にスキップされます。

### 2. 優遇/冷遇・実践値情報の登録・閲覧（fetch_public_info.py）

スマスロ等における、メーカー非公式だが実践値から示唆される「優遇/冷遇」の挙動
（特定設定での演出頻度の偏り、AT当選率の偏りなど）を記録します。

**推奨ワークフロー**: 自分で毎回探すのは手間がかかるため、Claudeとの対話の中で
「〇〇の優遇冷遇情報を調べて」と依頼してください。Claudeが無料公開情報
（X投稿・個人ブログ・まとめサイト等）を検索し、要約・出典・信頼度付きで提示します。
内容を確認し、保存してよいものだけを以下のコマンドで登録します。

単発追加:

```powershell
python fetch_public_info.py add-bias --machine "北斗の拳" --category AT当選率偏り `
  --treatment 優遇 --target-setting "6" `
  --summary "設定6は特定モードでのAT当選率が高い傾向、との実践値報告が複数あり。" `
  --sample-size "有志報告 合計約2000G分" --confidence 中 `
  --source-type X投稿 --source-name "個人ユーザーの実践値まとめ投稿" `
  --source-url "https://x.com/example/status/xxxx"
```

複数件をまとめて登録したい場合（Claudeが検索結果をJSONファイルにまとめてから一括投入する
運用を想定）:

```powershell
python fetch_public_info.py import-bias --file entries.json
```

`entries.json` の形式（オブジェクトのリスト。必須項目: `machine`, `category`, `treatment`,
`summary`, `source_type`, `source_name`）:

```json
[
  {
    "machine": "北斗の拳",
    "category": "AT当選率偏り",
    "treatment": "優遇",
    "target_setting": "6",
    "summary": "自分の言葉での要約",
    "sample_size": "有志報告 合計約2000G分",
    "confidence": "中",
    "source_type": "X投稿",
    "source_name": "個人ユーザーの実践値まとめ投稿",
    "source_url": "https://x.com/example/status/xxxx",
    "notes": "補足メモ"
  }
]
```

有料サイトのドメインが含まれるエントリは自動的にスキップされ、理由が表示されます。

オプション一覧:

| オプション | 説明 |
|---|---|
| `--category` (必須) | `演出頻度偏り` / `AT当選率偏り` / `内部モード示唆` / `その他` |
| `--treatment` (必須) | `優遇` / `冷遇` / `不明` |
| `--target-setting` | 対象設定（例: `6`, `5-6`） |
| `--summary` (必須) | 自分の言葉での要約（原文コピペ不可） |
| `--sample-size` | 実践サンプル数の目安（自由記述） |
| `--confidence` | 信頼度: `高` / `中` / `低`（デフォルト: 中） |
| `--source-type` (必須) | `X投稿` / `個人ブログ` / `まとめサイト` / `その他` |
| `--source-name` (必須) | 出典名 |
| `--source-url` | 出典URL（無料公開ページのみ） |

一覧表示:

```powershell
python fetch_public_info.py list-bias --machine "北斗の拳"
python fetch_public_info.py list-bias   # 全件表示
```

### 3. 機種リファレンス（スマホ向けHTML）の生成（machine_report.py）

ホールで台選びをする際にスマホで開いて見る用の、機種別まとめページを生成します。
`fetch_public_info.py` で登録した一般攻略情報（A）と優遇/冷遇情報（C）を、機種ごとに
カード形式でまとめ、上部の横スクロールタブから機種にジャンプできるようにしています。
ライト/ダークモード自動対応、テーブルなしのカードレイアウトで、スマホの縦画面でも
横スクロールなしで読めるようにしています。

```powershell
python machine_report.py                      # 登録済み全機種
python machine_report.py --machine "スマスロ北斗の拳"  # 機種を絞り込み
python machine_report.py --output-dir reports # 出力先指定
```

`reports/machine_reference.html` が生成されます。生成後、そのままスマホのブラウザで
ファイルを開くか、OneDrive等で同期して閲覧してください。

### 4.（オプション）稼働データの記録（log_data.py）

自分の実際の稼働（差枚・G数等）を記録したい場合のみ使う機能です。使わなくても1〜3の
情報収集・スマホ向けページ作成には一切影響しません。

```powershell
python log_data.py --machine "北斗の拳" --game 500 --diff -300
```

主なオプション:

| オプション | 説明 |
|---|---|
| `--machine` (必須) | 機種名 |
| `--diff` (必須) | 差枚（例: -300, 850） |
| `--hall` | ホール名（デフォルト: 相模原プラザ） |
| `--date` | 稼働日 YYYY-MM-DD（デフォルト: 今日） |
| `--unit` | 台番号 |
| `--game` | 消化G数 |
| `--start` / `--end` | 開始/終了G数（両方指定でG数を自動計算） |
| `--investment` | 投資額（円） |
| `--payout` | 回収額（円） |
| `--setting-hint` | 設定示唆メモ |
| `--estimated-setting` | 推定設定（1〜6） |
| `--hyena` | ハイエナ狙い台としてマーク |
| `--memo` | 自由メモ |

例（詳細記録）:

```powershell
python log_data.py --machine "ジャグラーガールズSS" --hall "相模原プラザ" `
  --unit 123 --game 3200 --diff 850 --investment 8000 --payout 12000 `
  --setting-hint "設定6示唆演出多数" --estimated-setting 6 --hyena `
  --memo "朝一ゾーン狙い"
```

機種名・ホール名が未登録の場合は自動でマスタに追加されます。

### 5.（オプション）週次統計レポート生成（weekly_report.py）

`log_data.py`で稼働データを記録している場合のみ意味を持つ機能です。

```powershell
python weekly_report.py                      # 直近7日間、Markdown+HTML両方
python weekly_report.py --days 14            # 直近14日間
python weekly_report.py --format md          # Markdownのみ
python weekly_report.py --format html        # HTMLのみ
python weekly_report.py --output-dir reports # 出力先指定
```

`reports/weekly_report_YYYYMMDD.md` / `.html` が生成されます。内容:

- サマリー（稼働回数、合計差枚、平均差枚、投資額、回収額、収支、ハイエナ狙い台実績）
- 機種別集計
- ホール別集計
- ベスト5 / ワースト5（差枚順）

## Windowsタスクスケジューラーでの自動実行設定

※ この章は**オプション機能**である週次稼働レポート（`weekly_report.py`）向けの設定です。
`log_data.py`で稼働データを記録していない場合、このタスクは空のレポートを生成するだけなので
設定する必要はありません。中心機能（攻略情報・優遇冷遇情報の収集、機種リファレンス生成）は
チャットでの都度の依頼がトリガーになるため、そもそも定期実行に向いていません。

毎週月曜 9:00 に週次レポートを自動生成する例です。

### 方法A: GUI（タスクスケジューラー）を使う場合

1. `Win + R` → `taskschd.msc` → Enter でタスクスケジューラーを開く
2. 右側の「基本タスクの作成」をクリック
3. 名前: `パチスロ週次レポート生成`、次へ
4. トリガー: 「毎週」を選択 → 次へ
5. 開始日時と曜日（例: 毎週月曜 09:00）を設定 → 次へ
6. 操作: 「プログラムの開始」を選択 → 次へ
7. 「プログラム/スクリプト」に以下を入力:
   ```
   C:\Windows\System32\cmd.exe
   ```
8. 「引数の追加」に以下を入力（パスは実際の設置場所に合わせて変更）:
   ```
   /c chcp 65001 >nul & python weekly_report.py --days 7 --format both
   ```
9. 「開始（オプション）」に作業ディレクトリを指定:
   ```
   C:\Users\seven\OneDrive\Desktop\pachislot-tracker
   ```
10. 「完了」をクリック。必要に応じてタスクのプロパティから
    「ユーザーがログオンしているかどうかにかかわらず実行する」を有効化してください。

### 方法B: コマンドラインで `schtasks` を使う場合

PowerShellまたはコマンドプロンプトを**管理者権限で**開き、以下を実行します
（パスは実際の設置場所・Pythonパスに合わせて変更してください）。

```powershell
schtasks /create /tn "パチスロ週次レポート生成" `
  /tr "cmd /c chcp 65001 >nul & cd /d C:\Users\seven\OneDrive\Desktop\pachislot-tracker & python weekly_report.py --days 7 --format both" `
  /sc weekly /d MON /st 09:00
```

登録内容の確認:

```powershell
schtasks /query /tn "パチスロ週次レポート生成" /v /fo LIST
```

手動実行してテストする場合:

```powershell
schtasks /run /tn "パチスロ週次レポート生成"
```

削除する場合:

```powershell
schtasks /delete /tn "パチスロ週次レポート生成" /f
```

### 注意事項

- タスクスケジューラーから実行する場合、Pythonの実行ファイルパスが通っていないと
  失敗することがあります。`python` コマンドが見つからない場合は、
  `python.exe` のフルパス（例: `C:\Users\seven\AppData\Local\Programs\Python\Python312\python.exe`）
  を指定してください。
- `db/pachislot.db` は稼働データ・攻略情報を含む個人データです。OneDrive等の
  同期対象に含まれる場合、同期タイミングによる競合に注意してください。

## よくある使い方の流れ

このプロジェクトの主目的は**稼働記録をつけることではなく、世の中の無料公開情報を集めて
台を打つときの判断根拠を育てること**です。基本サイクルは以下の通りです。

1. `python init_db.py` でDBを一度だけ初期化
2. 気になる機種・ホールが出てきたら、Claudeに「〇〇の攻略情報／優遇冷遇情報を調べて」と依頼する
3. Claudeが信頼できる無料の情報源（メーカー公式、note/X/YouTubeの実績ある無料分析者など）を
   優先して検索し、出典・信頼度（confidence）付きで内容を提示する
4. 内容を確認し、問題なければ「保存して」と伝え、`fetch_public_info.py`の
   `add` / `import`（攻略情報）・`add-bias` / `import-bias`（優遇冷遇情報）で登録する
5. `python machine_report.py` を実行して `reports/machine_reference.html` を更新し、
   ホールに行く前や台選びの最中にスマホで開いて参照する
6. 気になる機種が増えるたびに2〜5を繰り返し、リファレンスページを継続的に育てていく

**オプション**: 実際の稼働結果も記録したくなった場合は、`log_data.py`で差枚・G数等を記録し、
`weekly_report.py`で週次集計を確認することもできます（詳細は上記「4.」「5.」参照）。ただし
これは任意の追加機能であり、上記1〜6の基本サイクルには不要です。
