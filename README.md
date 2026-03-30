# Discord TimeTree Bot

Discordの特定チャンネルに投稿された自然言語から、TimeTreeに予定を登録するボットです。

## 機能

- Discordの指定チャンネルでメッセージを受信
- LLM（OpenAI/Anthropic）で自然言語を解析して日時・予定を抽出
- Seleniumでブラウザ操作しTimeTreeに予定を登録
- ターミナルを閉じても動作し続ける（systemdサービス）

---

## セットアップ

### 1. 依存関係のインストール

#### macOS

```bash
pip install -r requirements.txt
```

#### Raspberry Pi OS / Ubuntu / Debian

```bash
# Pythonパッケージ
pip install -r requirements.txt

# ChromiumとChromeDriverのインストール
sudo apt update
sudo apt install -y chromium-browser chromium-chromedriver

# 確認
chromedriver --version
chromium-browser --version
```

### 2. Discord Botの作成とサーバーへの追加（2025年最新方法）

#### ステップ1: Discord Developer Portal でアプリケーションを作成

1. [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
2. 右上の「New Application」をクリック
3. アプリケーション名を入力（例: `TimeTree Bot`）
4. 「Create」をクリック

#### ステップ2: Botを作成してTokenを取得

1. 左側のメニューから「Bot」を選択
2. 「Reset Token」をクリックしてトークンを生成
3. **⚠️ トークンは一度しか表示されないので、必ずコピーして `.env` に保存**
4. 「MESSAGE CONTENT INTENT」を**ON**にする（メッセージ内容を読み取るために必須）
5. 保存ボタン（「Save Changes」）をクリック

#### ステップ3: Botをサーバーに招待（OAuth2 URL生成）

1. 左側のメニューから「OAuth2」→「URL Generator」を選択
2. **SCOPES** で以下にチェック:
   - ✅ `bot`
3. **BOT PERMISSIONS** で以下にチェック（必要な権限のみ）:
   - ✅ `Read Messages/View Channels`
   - ✅ `Send Messages`
   - ✅ `Add Reactions`
4. 画面下の「Generated URL」をコピー
5. ブラウザでコピーしたURLを開く
6. サーバーを選択して「承認」をクリック

#### ステップ4: チャンネルIDを取得

1. Discordでボットが追加されたサーバーを開く
2. チャンネルを右クリック
3. 「リンクをコピー」を選択
4. URLからチャンネルIDを抽出:
   ```
   https://discord.com/channels/サーバーID/チャンネルID
   ```
   - 最後の数字がチャンネルIDです

または、Discordの設定で「詳細設定」→「開発者モード」をONにして、チャンネルを右クリック→「IDをコピー」でも取得できます。

### 3. 環境変数の設定

`.env.example` を `.env` にコピー:

```bash
cp .env.example .env
```

`.env` を編集:

```env
# Discord Bot Settings
DISCORD_BOT_TOKEN=手順2でコピーしたトークン
DISCORD_CHANNEL_ID=手順4で取得したチャンネルID

# LLM API (使用する方を設定)
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
LLM_PROVIDER=anthropic

# TimeTree
TIMETREE_EMAIL=your_email@example.com
TIMETREE_PASSWORD=your_password
TIMETREE_CALENDAR_NAME=My Calendar

HEADLESS=true
```

---

## テスト

Botを起動する前に、単体テストで動作確認できます。

### NLPパーサーのテスト

```bash
python test_scanner.py nlp
```

### フルAutomationテスト

```bash
python test_scanner.py full
```

### UIセレクタのスキャン

```bash
python test_scanner.py scan
```

TimeTreeのUIが変更された場合に、セレクタを再スキャンして `selectors_config.json` を更新します。

### 対話モード

```bash
python test_scanner.py
```

プロンプトが表示されるので、自然言語で予定を入力してください:

```
> 明日の15時から会議

Parsing event(s)...
  Found 1 event(s):
  [1] Title: 会議
      Start: 2026-02-02T15:00:00+09:00
      End: None
      All Day: False
      Location: None

Create these event(s)? (y/n): y
```

---

## 実行

### 手動実行（開発用）

```bash
python bot.py
```

### バックグラウンド実行（Raspberry Pi推奨）

systemdサービスとして登録します。ターミナルを閉じても動作し続け、システム起動時に自動開始します。

```bash
# 1. サービスファイルをコピー
sudo cp discord-timetree.service /etc/systemd/system/

# 2. WorkingDirectory を実際のパスに修正
sudo nano /etc/systemd/system/discord-timetree.service
# 例: WorkingDirectory=/home/pi/Discord-Timetree
# 例: ExecStart=/home/pi/Discord-Timetree/venv/bin/python bot.py

# 3. サービスを有効化・開始
sudo systemctl daemon-reload
sudo systemctl enable discord-timetree.service
sudo systemctl start discord-timetree.service

# 4. 状態確認
sudo systemctl status discord-timetree.service
```

#### サービス管理コマンド

```bash
# 状態確認
sudo systemctl status discord-timetree.service

# ログを表示（リアルタイム）
sudo journalctl -u discord-timetree.service -f

# ログを表示（最近50行）
sudo journalctl -u discord-timetree.service -n 50

# サービス停止
sudo systemctl stop discord-timetree.service

# サービス再起動
sudo systemctl restart discord-timetree.service

# サービス無効化（自動起動解除）
sudo systemctl disable discord-timetree.service
```

---

## 使用例

Discordの指定チャンネルで以下のように投稿:

```
明日の15時から会議
```

```
来週の水曜日に終日で休み
```

```
2026年2月14日の13時から2時間でバレンタインデー@東京タワー
```

```
明後日の10時から18時までチーム外出@渋谷
```

### 対応している表現

- 相対日時: `明日`、`明後日`、`来週の月曜日`、`来月`
- 絶対日時: `2026年2月14日`、`2/14`
- 時刻: `15時`、`3PM`、`15:30`
- 終日予定: `終日で`、`all-day`
- 場所: `@東京タワー`、`場所:渋谷`
- 時間範囲: `2時間`、`13時から15時まで`

---

## ファイル構成

```
├── bot.py                      # Discordボットのメイン処理
├── nlp_parser.py              # LLMで自然言語解析
├── timetree_automation.py     # SeleniumでTimeTree操作
├── selector_manager.py        # セレクタ管理・試行
├── selector_scanner.py        # UIセレクタスキャナー
├── config.py                  # 設定管理
├── test_scanner.py            # テスト・対話モードスクリプト
├── selectors_config.json      # TimeTree UIセレクタ設定
├── discord-timetree.service   # systemdサービスファイル
├── .env                       # 環境変数（gitには含まれません）
├── .env.example               # 環境変数のテンプレート
├── .gitignore                 # Git除外設定
├── requirements.txt           # 依存ライブラリ
├── CLAUDE.md                  # AIアシスタント用ガイドライン
│
### 検査・デバッグユーティリティ
├── inspect_timetree.py        # TimeTree要素検査
├── inspect_timetree_v2.py     # TimeTree要素検査 v2
│
### 個別テストスクリプト
├── test_chromedriver_direct.py  # ChromeDriver直接テスト
├── test_selenium_alternative.py # Selenium代替手法テスト
├── test_display_check.py        # ディスプレイ確認テスト
├── test_debug_login.py          # ログインデバッグテスト
└── test_selectors.py            # セレクタ検証テスト
```

---

## セレクタ設定

TimeTreeのUIが変更された場合、`selectors_config.json` を更新する必要があります。
`selector_manager.py` が複数のフォールバック候補を順に試行し、`selector_scanner.py` でUI要素の再スキャンが可能です。

各セレクタは複数のフォールバック候補を持ち、`data-test-id` ベースのセレクタを優先的に使用します:

```json
{
  "login_email": [
    "[data-test-id=\"signin-form-email\"]",
    "input[name=\"email\"]",
    "input[type=\"email\"]"
  ],
  "login_password": [
    "[data-test-id=\"signin-form-password\"]",
    "input[name=\"password\"]",
    "input[type=\"password\"]"
  ],
  "login_submit": [
    "[data-test-id=\"signin-form-submit\"]",
    "button[type=\"submit\"]"
  ],
  "calendar_selector": [
    "[data-test-id=\"calendar-selector\"]",
    "button[aria-label*=\"calendar\"]",
    "button[aria-label*=\"カレンダー\"]"
  ],
  "calendar_item": [
    "[data-test-id=\"calendar-item\"]",
    "a[href*=\"/calendar\"]"
  ],
  "create_button": [
    ".fcsm7z0 > div:nth-child(2) > button:nth-child(1)",
    "[data-test-id=\"create-button\"]",
    "button[aria-label*=\"create\"]",
    "button[aria-label*=\"作成\"]",
    "button:has(svg)"
  ],
  "event_title": [
    ".css-1yhz41h",
    "div[contenteditable=\"true\"]",
    "[data-test-id=\"event-title\"]",
    "input[name=\"title\"]",
    "input[placeholder*=\"title\"]",
    "input[placeholder*=\"タイトル\"]",
    "input[placeholder*=\"Title\"]",
    "input[aria-label*=\"title\"]",
    "input[aria-label*=\"タイトル\"]",
    "textarea[placeholder*=\"title\"]",
    "input[type=\"text\"]"
  ],
  "event_start": [
    "[data-test-id=\"start-date-picker\"]",
    "div.css-1vptl7o:nth-child(1)",
    "[data-test-id=\"event-start\"]",
    "input[name=\"startDate\"]",
    "input[placeholder*=\"start\"]",
    "input[placeholder*=\"開始\"]",
    "input[placeholder*=\"Start\"]",
    "input[name=\"start\"]",
    "input[aria-label*=\"start\"]"
  ],
  "event_start_time": [
    "[data-test-id=\"start-time-picker\"]",
    "input[name=\"startTime\"]",
    "input[placeholder*=\"time\"]",
    "input[placeholder*=\"時刻\"]"
  ],
  "event_end_time": [
    "[data-test-id=\"end-time-picker\"]",
    "input[name=\"endTime\"]",
    "input[placeholder*=\"end time\"]",
    "input[placeholder*=\"終了時刻\"]"
  ],
  "event_end": [
    "[data-test-id=\"end-date-picker\"]",
    "input[name=\"endDate\"]",
    "div.css-1vptl7o:nth-child(2)",
    "[data-test-id=\"event-end\"]",
    "input[placeholder*=\"end\"]",
    "input[placeholder*=\"終了\"]",
    "input[placeholder*=\"End\"]",
    "input[name=\"end\"]",
    "input[aria-label*=\"end\"]"
  ],
  "event_location": [
    "[data-test-id=\"event-location\"]",
    "input[placeholder*=\"location\"]",
    "input[placeholder*=\"場所\"]",
    "input[placeholder*=\"Location\"]",
    "input[name=\"location\"]",
    "input[aria-label*=\"location\"]"
  ],
  "event_description": [
    "[data-test-id=\"event-description\"]",
    "textarea[placeholder*=\"description\"]",
    "textarea[placeholder*=\"説明\"]",
    "textarea[placeholder*=\"Description\"]",
    "textarea[name=\"description\"]",
    "div[contenteditable=\"true\"]"
  ],
  "event_all_day": [
    "#allday-checkbox",
    "div[role=\"checkbox\"]",
    ".ttfont-check_box",
    "[data-test-id=\"event-all-day\"]",
    "input[type=\"checkbox\"]"
  ],
  "event_save": [
    "._1e0xpu30",
    "[data-test-id=\"event-save\"]",
    "button[type=\"submit\"]",
    "button[class*=\"save\"]",
    "button[class*=\"Save\"]",
    "button[class*=\"submit\"]"
  ],
  "event_cancel": [
    "[data-test-id=\"event-cancel\"]",
    "button[class*=\"cancel\"]",
    "button[class*=\"Cancel\"]"
  ]
}
```

これらのセレクタ（特にCSSクラス名ベースのもの）はTimeTreeのアップデートで変更される可能性があります。
UIが変更された場合は `selector_scanner.py` を使用してセレクタを再スキャンできます:

```bash
python test_scanner.py scan
```

---

## トラブルシューティング

### ボットが予定を登録できない

1. `.env` の設定を確認
2. テストスクリプトで動作確認: `python test_scanner.py full`
3. スクリーンショット（`*_not_found_*.png`）を確認

### ボットがオフラインになる

1. MESSAGE CONTENT INTENTがONになっているか確認
2. Bot権限が正しく設定されているか確認
3. サービスの状態を確認: `sudo systemctl status discord-timetree.service`

### サービスが起動しない

```bash
# 詳細なログを確認
sudo journalctl -u discord-timetree.service -n 100 --no-pager

# パーミッションを確認
ls -la /etc/systemd/system/discord-timetree.service
```

### ChromeDriverのエラー

```bash
# バージョン確認
chromedriver --version
chromium-browser --version

# 再インストール
sudo apt install --reinstall chromium-chromedriver
```

### LLM APIのエラー

- APIキーが正しく設定されているか確認
- 残高/クォータを確認
- `LLM_PROVIDER` の設定を確認

---

## 開発モード

テスト中は非ヘッドレスモードがおすすめです:

```env
HEADLESS=false
```

ブラウザの動作が見えるため、デバッグが容易になります。

---

## セキュリティ

- `.env` ファイルはGitに含まれません
- 認証情報は環境変数で管理してください
- Bot Tokenは絶対に共有しないでください
- TimeTreeのパスワードは安全な場所に保管してください

---

## 注意事項

- Seleniumによるブラウザ操作はTimeTreeのUI変更に依存します
- ヘッドレスモードで動作します
- LLM APIの利用には別途料金がかかる場合があります
- TimeTreeの利用規約を遵守してください
- 他のボットからのメッセージは自動的に無視されます

---

## 参考リンク

- [Discord Developer Documentation](https://discord.com/developers/docs/quick-start/getting-started)
- [discord.py Documentation](https://discordpy.readthedocs.io/)
