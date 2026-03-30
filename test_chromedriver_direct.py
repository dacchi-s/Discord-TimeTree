#!/usr/bin/env python3
"""ChromeDriverセッション作成テスト - 完全なログ取得"""
import subprocess
import json
import os
import time
import threading
from urllib.request import urlopen, Request
from urllib.error import URLError

# テストするChromeDriverパス
chromedriver_path = "/usr/bin/chromedriver"
chromium_binary = "/usr/bin/chromium"

print(f"Chromium binary: {chromium_binary}")
print(f"ChromeDriver: {chromedriver_path}")
print()

# 環境変数を設定
env = os.environ.copy()
env['CHROME_BIN'] = chromium_binary
env['CHROME_PATH'] = chromium_binary

# ChromeDriverを起動
print("Starting ChromeDriver...")
process = subprocess.Popen(
    [chromedriver_path, '--port=9515', '--verbose'],
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

# 出力をキャプチャする関数
output_lines = []
def read_output():
    """プロセス出力をリアルタイムで読み取る"""
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                output_lines.append(line.rstrip())
                print(f"[ChromeDriver] {line.rstrip()}")
    except:
        pass

# 読み取りスレッドを開始
import threading
reader_thread = threading.Thread(target=read_output)
reader_thread.daemon = True
reader_thread.start()

# ChromeDriverが起動するのを待つ
time.sleep(2)

# セッション作成リクエスト（Chromiumを起動）
session_request = {
    "capabilities": {
        "firstMatch": [{}],
        "alwaysMatch": {
            "browserName": "chrome",
            "goog:chromeOptions": {
                "binary": chromium_binary,
                "args": [
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            }
        }
    }
}

print("\n" + "="*60)
print("Sending session creation request via HTTP...")
print("="*60)

try:
    request_json = json.dumps(session_request)
    url = "http://localhost:9515/session"
    req = Request(url, data=request_json.encode('utf-8'), headers={
        'Content-Type': 'application/json'
    })

    response = urlopen(req, timeout=10)
    response_data = json.loads(response.read().decode('utf-8'))

    print("\n" + "="*60)
    print("SUCCESS! Session created!")
    print("="*60)
    print(json.dumps(response_data, indent=2))

    # セッションを閉じる
    session_id = response_data.get('value', {}).get('sessionId')
    if session_id:
        try:
            delete_req = Request(f"http://localhost:9515/session/{session_id}", method='DELETE')
            urlopen(delete_req, timeout=5)
            print("Session closed successfully")
        except:
            pass

except URLError as e:
    print(f"\nHTTP Error: {e}")
    # エラーレスポンスを読み取る
    if hasattr(e, 'read'):
        try:
            error_data = json.loads(e.read().decode('utf-8'))
            print(f"Error details: {json.dumps(error_data, indent=2)}")
        except:
            pass
except Exception as e:
    print(f"\nError: {e}")

# さらに数秒間出力をキャプチャ
print("\n" + "="*60)
print("Capturing additional output...")
print("="*60)
time.sleep(2)

# プロセスを終了
process.terminate()
try:
    process.wait(timeout=2)
except:
    process.kill()

print("\n" + "="*60)
print("Complete ChromeDriver output:")
print("="*60)
for line in output_lines:
    print(line)
