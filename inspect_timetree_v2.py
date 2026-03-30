#!/usr/bin/env python3
"""TimeTreeページの詳細インスペクト"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC

# ヘッドレスモードでChromeを起動
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

print("Navigating to TimeTree login page...")
driver.get("https://timetreeapp.com/signin")

# ページが完全に読み込まれるのを待つ
print("Waiting for page to load...")
time.sleep(5)

print("\n=== Page Title ===")
print(driver.title)

print("\n=== All input fields ===")
inputs = driver.find_elements(By.TAG_NAME, "input")
print(f"Found {len(inputs)} input fields")
for i, inp in enumerate(inputs):
    print(f"\nInput {i}:")
    print(f"  type: {inp.get_attribute('type')}")
    print(f"  name: {inp.get_attribute('name')}")
    print(f"  id: {inp.get_attribute('id')}")
    print(f"  class: {inp.get_attribute('class')}")
    print(f"  placeholder: {inp.get_attribute('placeholder')}")
    print(f"  aria-label: {inp.get_attribute('aria-label')}")

print("\n=== All buttons ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
print(f"Found {len(buttons)} buttons")
for i, btn in enumerate(buttons):
    text = btn.text.strip()
    print(f"\nButton {i}:")
    print(f"  text: '{text}'")
    print(f"  type: {btn.get_attribute('type')}")
    print(f"  class: {btn.get_attribute('class')}")
    print(f"  id: {btn.get_attribute('id')}")
    print(f"  data-testid: {btn.get_attribute('data-testid')}")

print("\n=== All forms ===")
forms = driver.find_elements(By.TAG_NAME, "form")
print(f"Found {len(forms)} forms")
for i, form in enumerate(forms):
    print(f"\nForm {i}:")
    print(f"  action: {form.get_attribute('action')}")
    print(f"  class: {form.get_attribute('class')}")
    print(f"  id: {form.get_attribute('id')}")

# 完全なHTMLを保存
with open("timetree_signin.html", "w", encoding="utf-8") as f:
    f.write(driver.page_source)
print("\nFull HTML saved to timetree_signin.html")

# スクリーンショットを保存
driver.save_screenshot("timetree_signin.png")
print("Screenshot saved to timetree_signin.png")

driver.quit()
print("\nDone!")
