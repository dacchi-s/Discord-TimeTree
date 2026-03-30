#!/usr/bin/env python3
"""TimeTreeページを手動でインスペクト"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# ヘッドレスモードでChromeを起動
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

print("Navigating to TimeTree login page...")
driver.get("https://timetreeapp.com/signin")
time.sleep(3)

print("\n=== Page Title ===")
print(driver.title)

print("\n=== All input fields ===")
inputs = driver.find_elements(By.TAG_NAME, "input")
for i, inp in enumerate(inputs):
    print(f"Input {i}:")
    print(f"  type: {inp.get_attribute('type')}")
    print(f"  name: {inp.get_attribute('name')}")
    print(f"  id: {inp.get_attribute('id')}")
    print(f"  class: {inp.get_attribute('class')}")
    print(f"  placeholder: {inp.get_attribute('placeholder')}")

print("\n=== All buttons ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for i, btn in enumerate(buttons):
    print(f"Button {i}:")
    print(f"  text: {btn.text[:50]}")
    print(f"  type: {btn.get_attribute('type')}")
    print(f"  class: {btn.get_attribute('class')}")

print("\n=== Page source snippet (first 2000 chars) ===")
print(driver.page_source[:2000])

# スクリーンショットを保存
driver.save_screenshot("timetree_login_page.png")
print("\nScreenshot saved to timetree_login_page.png")

driver.quit()
