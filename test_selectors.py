#!/usr/bin/env python3
"""セレクタテスト"""
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# ヘッドレスモードでChromeを起動
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)

print("Loading TimeTree signin page...")
driver.get("https://timetreeapp.com/signin")
time.sleep(5)

# セレクタをテスト
test_selectors = [
    # Email input
    ("input[name='email']", "email with name (single quotes)"),
    ("input[name=\"email\"]", "email with name (double quotes)"),
    ("input[type='email']", "email with type"),
    ("[data-test-id='signin-form-email']", "email with data-test-id (single)"),
    ("[data-test-id=\"signin-form-email\"]", "email with data-test-id (double)"),
    # Password input
    ("input[name='password']", "password with name"),
    ("input[type='password']", "password with type"),
    ("[data-test-id='signin-form-password']", "password with data-test-id"),
    # Submit button
    ("button[type='submit']", "submit button"),
    ("[data-test-id='signin-form-submit']", "submit with data-test-id"),
]

print("\n=== Testing selectors ===")
found_count = 0
for selector, description in test_selectors:
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            print(f"✓ FOUND: {description}")
            print(f"  Selector: {selector}")
            print(f"  Elements: {len(elements)}")
            found_count += 1
        else:
            print(f"✗ NOT FOUND: {description}")
            print(f"  Selector: {selector}")
    except Exception as e:
        print(f"✗ ERROR: {description}")
        print(f"  Selector: {selector}")
        print(f"  Error: {e}")

print(f"\n=== Summary: {found_count}/{len(test_selectors)} selectors found ===")

# 現在の設定ファイルを確認
print("\n=== Current selectors_config.json ===")
try:
    with open("selectors_config.json", "r") as f:
        config = json.load(f)
    print(json.dumps(config.get("login_email", []), indent=2))
except Exception as e:
    print(f"Error loading config: {e}")

driver.quit()
