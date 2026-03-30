"""セレクタ管理 - 複数の候補を試行して動作するものを見つける"""
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException


class SelectorManager:
    """CSSセレクタの管理と試行"""

    # デフォルトセレクタ（フォールバック用）
    DEFAULT_SELECTORS = {
        "login_email": [
            "input[name='email']",
            "input[type='email']",
            "input[placeholder*='mail']",
            "input[placeholder*='Mail']",
            "#email",
        ],
        "login_password": [
            "input[name='password']",
            "input[type='password']",
            "input[placeholder*='pass']",
            "input[placeholder*='Pass']",
            "#password",
        ],
        "login_submit": [
            "button[type='submit']",
            "button[type='submit']",
            "form button",
            "button",
        ],
        "calendar_selector": [
            "[data-testid='calendar-selector']",
            ".calendar-selector",
            "button[aria-label*='Calendar']",
            "button[aria-label*='カレンダー']",
        ],
        "calendar_item": [
            "[data-testid='calendar-item']",
            ".calendar-item",
            ".calendar-name",
        ],
        "create_button": [
            "[data-testid='create-event-button']",
            "button[aria-label*='Create']",
            "button[aria-label*='予定']",
            ".create-event-btn",
        ],
        "event_title": [
            "[data-testid='event-title-input']",
            "input[placeholder*='タイトル']",
            "input[placeholder*='Title']",
            "input[name='title']",
            "#event-title",
        ],
        "event_start": [
            "[data-testid='event-start-input']",
            "input[placeholder*='開始']",
            "input[placeholder*='Start']",
            "input[name='start']",
            "#event-start",
        ],
        "event_end": [
            "[data-testid='event-end-input']",
            "input[placeholder*='終了']",
            "input[placeholder*='End']",
            "input[name='end']",
            "#event-end",
        ],
        "event_location": [
            "[data-testid='event-location-input']",
            "input[placeholder*='場所']",
            "input[placeholder*='Location']",
            "input[name='location']",
            "#event-location",
        ],
        "event_description": [
            "[data-testid='event-description-input']",
            "textarea[placeholder*='説明']",
            "textarea[placeholder*='Description']",
            "textarea[name='description']",
            "#event-description",
        ],
        "event_all_day": [
            "[data-testid='all-day-toggle']",
            "input[type='checkbox']",
            "input[role='switch']",
        ],
        "event_save": [
            "[data-testid='save-event-button']",
            "button[type='submit']",
            ".save-event-btn",
        ],
        "event_cancel": [
            "button[aria-label*='Cancel']",
            "button[aria-label*='キャンセル']",
        ],
    }

    def __init__(self, config_path: str = "selectors_config.json"):
        self.config_path = config_path
        self.selectors = self._load_selectors()

    def _load_selectors(self) -> Dict[str, List[str]]:
        """セレクタ設定を読み込み"""
        if Path(self.config_path).exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # デフォルトセレクタとマージ
                merged = self.DEFAULT_SELECTORS.copy()
                for key, value in loaded.items():
                    if value:  # 空でない場合のみ上書き
                        merged[key] = value
                return merged
            except (json.JSONDecodeError, IOError):
                pass
        return self.DEFAULT_SELECTORS.copy()

    def find_element(self, driver: webdriver.Chrome, key: str,
                     timeout: int = 5) -> Optional[Any]:
        """セレクタ候補を順に試行して要素を見つける"""
        candidates = self.selectors.get(key, [])

        for selector in candidates:
            try:
                # XPathの場合
                if selector.startswith("xpath:"):
                    element = driver.find_element(By.XPATH, selector[6:])
                else:
                    element = driver.find_element(By.CSS_SELECTOR, selector)

                if element and element.is_displayed():
                    print(f"  ✓ Found element with selector: {selector}")
                    return element
            except (NoSuchElementException, Exception):
                continue

        print(f"  ✗ No element found for key: {key}")
        return None

    def wait_for_element(self, driver: webdriver.Chrome, key: str,
                         timeout: int = 10) -> Optional[Any]:
        """要素が現れるまで待機（複数セレクタ試行）"""
        candidates = self.selectors.get(key, [])

        for selector in candidates:
            try:
                if selector.startswith("xpath:"):
                    element = WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.XPATH, selector[6:]))
                    )
                else:
                    element = WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )

                if element:
                    print(f"  ✓ Waited for element: {selector}")
                    return element
            except TimeoutException:
                continue

        print(f"  ✗ Timeout waiting for key: {key}")
        return None

    def find_elements(self, driver: webdriver.Chrome, key: str) -> List[Any]:
        """セレクタ候補を順に試行して要素リストを見つける"""
        candidates = self.selectors.get(key, [])

        for selector in candidates:
            try:
                if selector.startswith("xpath:"):
                    elements = driver.find_elements(By.XPATH, selector[6:])
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)

                if elements:
                    print(f"  ✓ Found {len(elements)} elements with: {selector}")
                    return elements
            except (NoSuchElementException, Exception):
                continue

        return []

    def find_element_by_text(self, driver: webdriver.Chrome, text: str,
                             tag: str = "button") -> Optional[Any]:
        """テキスト内容で要素を探す"""
        try:
            elements = driver.find_elements(By.TAG_NAME, tag)
            for elem in elements:
                if text in elem.text:
                    print(f"  ✓ Found element by text: {text}")
                    return elem
        except Exception:
            pass
        return None

    def add_selector(self, key: str, selector: str):
        """新しいセレクタを追加（学習機能）"""
        if key not in self.selectors:
            self.selectors[key] = []
        if selector not in self.selectors[key]:
            self.selectors[key].insert(0, selector)  # 優先度を高くする
            self._save_selectors()

    def _save_selectors(self):
        """セレクタ設定を保存"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.selectors, f, indent=2, ensure_ascii=False)
        except IOError:
            pass
