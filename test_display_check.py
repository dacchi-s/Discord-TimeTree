#!/usr/bin/env python3
"""Display environment check"""
import os
import platform

print("=== Environment Check ===")
print(f"Platform: {platform.system()} {platform.machine()}")
print(f"DISPLAY: {os.environ.get('DISPLAY', 'NOT SET')}")
print(f"WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY', 'NOT SET')}")
print(f"XDG_SESSION_TYPE: {os.environ.get('XDG_SESSION_TYPE', 'NOT SET')}")

# Test headless=True (should work without display)
print("\n=== Testing headless=True ===")
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")

service = Service("/usr/bin/chromedriver")
try:
    driver = webdriver.Chrome(service=service, options=options)
    print(f"SUCCESS! Browser: {driver.capabilities.get('browserName')} {driver.capabilities.get('browserVersion')}")
    driver.get("https://www.google.com")
    print(f"Page title: {driver.title}")
    driver.quit()
except Exception as e:
    print(f"FAILED: {e}")

# Test headless=False (requires display)
print("\n=== Testing headless=False ===")
options2 = Options()
# No headless argument
options2.add_argument("--no-sandbox")
options2.add_argument("--disable-dev-shm-usage")

service2 = Service("/usr/bin/chromedriver")
try:
    driver2 = webdriver.Chrome(service=service2, options=options2)
    print(f"SUCCESS! Browser: {driver2.capabilities.get('browserName')}")
    driver2.quit()
except Exception as e:
    print(f"FAILED: {e}")
