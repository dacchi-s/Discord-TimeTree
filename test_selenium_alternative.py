#!/usr/bin/env python3
"""Selenium with alternative capability setting approach"""
import os
import platform
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

# 設定
chromedriver_path = "/usr/bin/chromedriver"
chromium_binary = "/usr/bin/chromium"

# 環境変数
os.environ['CHROME_BIN'] = chromium_binary
os.environ['CHROME_PATH'] = chromium_binary

# 方法1: binary_locationを使用
print("=== Method 1: binary_location ===")
try:
    options1 = webdriver.ChromeOptions()
    options1.binary_location = chromium_binary
    options1.add_argument("--headless=new")
    options1.add_argument("--no-sandbox")
    options1.add_argument("--disable-dev-shm-usage")
    options1.add_argument("--disable-gpu")

    service1 = Service(chromedriver_path)
    driver1 = webdriver.Chrome(service=service1, options=options1)
    print("SUCCESS with binary_location")
    driver1.quit()
except Exception as e:
    print(f"FAILED: {e}")

# 方法2: capabilitiesでbinaryを指定
print("\n=== Method 2: capabilities with goog:chromeOptions ===")
try:
    options2 = webdriver.ChromeOptions()
    options2.add_argument("--headless=new")
    options2.add_argument("--no-sandbox")
    options2.add_argument("--disable-dev-shm-usage")
    options2.add_argument("--disable-gpu")

    # capabilitiesを直接設定
    options2.set_capability("goog:chromeOptions", {
        "binary": chromium_binary
    })

    service2 = Service(chromedriver_path)
    driver2 = webdriver.Chrome(service=service2, options=options2)
    print("SUCCESS with capabilities")
    driver2.quit()
except Exception as e:
    print(f"FAILED: {e}")

# 方法3: experimental_options
print("\n=== Method 3: experimental_options ===")
try:
    options3 = webdriver.ChromeOptions()
    options3.add_argument("--headless=new")
    options3.add_argument("--no-sandbox")
    options3.add_argument("--disable-dev-shm-usage")
    options3.add_argument("--disable-gpu")

    # experimental_optionsとしてbinaryを設定
    options3._experimental_options["binary"] = chromium_binary

    service3 = Service(chromedriver_path)
    driver3 = webdriver.Chrome(service=service3, options=options3)
    print("SUCCESS with experimental_options")
    driver3.quit()
except Exception as e:
    print(f"FAILED: {e}")

# 方法4: 引数でバイナリを指定
print("\n=== Method 4: No explicit binary (let ChromeDriver find it) ===")
try:
    options4 = webdriver.ChromeOptions()
    options4.add_argument("--headless=new")
    options4.add_argument("--no-sandbox")
    options4.add_argument("--disable-dev-shm-usage")
    options4.add_argument("--disable-gpu")

    service4 = Service(chromedriver_path)
    driver4 = webdriver.Chrome(service=service4, options=options4)
    print("SUCCESS without explicit binary")
    print(f"Browser: {driver4.capabilities.get('browserName')}")
    print(f"Version: {driver4.capabilities.get('browserVersion')}")
    driver4.quit()
except Exception as e:
    print(f"FAILED: {e}")

# 方法5: Desired capabilities (古いAPI)
print("\n=== Method 5: Desired capabilities ===")
try:
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

    caps = DesiredCapabilities.CHROME.copy()
    caps["goog:chromeOptions"] = {
        "binary": chromium_binary,
        "args": ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
    }

    service5 = Service(chromedriver_path)
    driver5 = webdriver.Chrome(service=service5, desired_capabilities=caps)
    print("SUCCESS with desired_capabilities")
    driver5.quit()
except Exception as e:
    print(f"FAILED: {e}")
