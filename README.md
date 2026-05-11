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
├── nlp_parser.py               # LLMで自然言語解析
├── timetree_automation.py      # SeleniumでTimeTree操作
├── selector_manager.py         # セレクタ管理・試行
├── ui_diagnostic.py            # UI変更自動検知・修復
├── selector_scanner.py         # UIセレクタスキャナー
├── config.py                   # 設定管理
├── test_scanner.py             # テスト・対話モードスクリプト
├── selectors_config.json       # TimeTree UIセレクタ設定
├── discord-timetree.service    # systemdサービスファイル
├── .env                        # 環境変数（gitには含まれません）
├── .env.example                # 環境変数のテンプレート
├── .gitignore                  # Git除外設定
├── requirements.txt            # 依存ライブラリ
├── logs/                       # スキャナー・診断ログ出力先
│
### 検査・デバッグユーティリティ
├── inspect_timetree.py         # TimeTree要素検査
├── inspect_timetree_v2.py      # TimeTree要素検査 v2
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

TimeTreeのUI要素は `selectors_config.json` で管理しています。
各セレクタは複数のフォールバック候補を持ち、`data-test-id` > `id` > `name` > `aria-label` > `class` の優先順位で試行します。

### 自動修復（Self-Healing）

TimeTreeのUI変更でセレクタが壊れた場合、`ui_diagnostic.py` が自動的に検知・修復します:

1. 要素が見つからない場合、現在のページをスキャン
2. LLM（OpenAI/Anthropic）がHTML構造を解析して新しいセレクタを提案
3. `selectors_config.json` に自動保存してリトライ

主な適用箇所: `create_button`, `event_start`, `event_save`

ログでの確認:
```
Element 'create_button' not found, running self-heal diagnostic...
Self-heal succeeded for 'create_button': button[aria-label="予定を作成"]
```

### 手動スキャン

自動修復で解決しない場合、手動でセレクタを再スキャンできます:

```bash
python test_scanner.py scan
```

スキャン結果とログは `logs/` ディレクトリに保存されます。

---

## トラブルシューティング

### ボットが予定を登録できない

1. ログで self-heal が動いたか確認: `sudo journalctl -u discord-timetree.service -n 50 --no-pager | grep "self-heal"`
2. `.env` の設定を確認
3. テストスクリプトで動作確認: `python test_scanner.py full`
4. スクリーンショット（`*_not_found_*.png`）を確認
5. 手動スキャンでセレクタを更新: `python test_scanner.py scan`

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
- UI変更時は自動修復（self-heal）が試行されますが、解決しない場合は手動スキャンが必要です
- ヘッドレスモードで動作します
- LLM APIの利用には別途料金がかかる場合があります（自然言語解析＋セレクタ自動修復）
- TimeTreeの利用規約を遵守してください
- 他のボットからのメッセージは自動的に無視されます

---

## 参考リンク

- [Discord Developer Documentation](https://discord.com/developers/docs/quick-start/getting-started)
- [discord.py Documentation](https://discordpy.readthedocs.io/)
