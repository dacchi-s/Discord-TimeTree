#!/usr/bin/env python3
"""Debug login test - mimics actual automation flow"""
import time
import platform
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

print("=== Debug Login Test ===")

# Setup same as automation
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 10)

try:
    print("Loading signin page...")
    driver.get("https://timetreeapp.com/signin")

    print(f"Current URL: {driver.current_url}")
    print(f"Page title: {driver.title}")

    # Same sleep as automation
    print("Sleeping 2 seconds...")
    time.sleep(2)

    # Try the selectors from config
    selectors = [
        '[data-test-id="signin-form-email"]',
        'input[name="email"]',
        'input[type="email"]'
    ]

    for i, selector in enumerate(selectors, 1):
        print(f"\n[{i}/{len(selectors)}] Trying: {selector}")
        try:
            element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            if element:
                print(f"  ✓ FOUND by presence_of_element_located")
                # Check if visible
                if element.is_displayed():
                    print(f"  ✓ Element is displayed")
                else:
                    print(f"  ✗ Element NOT displayed")
                break
        except Exception as e:
            print(f"  ✗ Failed: {type(e).__name__}")

    # Debug: dump page source
    print("\n=== Page source snippet ===")
    page_source = driver.page_source
    if 'data-test-id="signin-form-email"' in page_source:
        print("✓ Found 'data-test-id=\"signin-form-email\"' in page source")
    else:
        print("✗ 'data-test-id=\"signin-form-email\"' NOT in page source")

    if 'name="email"' in page_source:
        print("✓ Found 'name=\"email\"' in page source")
    else:
        print("✗ 'name=\"email\"' NOT in page source")

    if 'type="email"' in page_source:
        print("✓ Found 'type=\"email\"' in page source")
    else:
        print("✗ 'type=\"email\"' NOT in page source")

    # Show input tags found
    inputs = page_source.count('<input')
    print(f"\nFound {inputs} <input> tags in page source")

finally:
    driver.quit()
    print("\n=== Test complete ===")
