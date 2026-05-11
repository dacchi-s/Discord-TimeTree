"""TimeTree UIスキャナー - CSSセレクタを網羅的に収集・解析"""
import json
import logging
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from config import config

logger = logging.getLogger(__name__)

LOG_FORMAT = "[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d-%H:%M:%S"


def _setup_logging() -> Path:
    """スキャナー用ロギングを設定（コンソール＋ファイル）"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_path = log_dir / f"scanner_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    root_logger = logging.getLogger("selector_scanner")
    root_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    return log_path


class SelectorScanner:
    """TimeTreeのUIをスキャンしてCSSセレクタを収集"""

    def __init__(self, headless: bool = False):
        # ディスプレイがない場合は自動的にheadlessモードを使用
        if not headless and not os.environ.get('DISPLAY'):
            logger.warning("No display detected, forcing headless mode")
            headless = True

        self.headless = headless
        self.driver = None
        self.selectors_data = {
            "scan_date": None,
            "selectors": {}
        }

    def _setup_driver(self):
        """Chrome WebDriverを設定"""
        logger.info("Setting up Chrome WebDriver (headless=%s, os=%s, arch=%s)",
                     self.headless, platform.system(), platform.machine())
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")

        # 注意: --remote-debugging-portは設定しない（ChromeDriverが自動で設定する）

        # Linux用Chromiumバイナリ検出
        chromium_binary = None
        if platform.system() == "Linux":
            chromium_paths = [
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium",
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable"
            ]
            for path in chromium_paths:
                if os.path.exists(path):
                    chromium_binary = path
                    logger.info("Using Chromium at: %s", path)
                    break
            else:
                logger.warning("No Chromium binary found on Linux")

        # ARMアーキテクチャの場合、webdriver-managerはスキップ
        is_linux_arm = (
            platform.system() == "Linux" and
            platform.machine() in ("aarch64", "armv7l", "arm64")
        )

        # システムのchromedriverを試す
        driver_chrome_pairs = []
        if platform.system() == "Linux":
            if os.path.exists("/snap/bin/chromium.chromedriver") and os.path.exists("/snap/bin/chromium"):
                driver_chrome_pairs.append(("/snap/bin/chromium.chromedriver", "/snap/bin/chromium"))
            if os.path.exists("/usr/bin/chromedriver") and chromium_binary:
                driver_chrome_pairs.append(("/usr/bin/chromedriver", chromium_binary))
            if os.path.exists("/usr/bin/chromium-driver") and chromium_binary:
                driver_chrome_pairs.append(("/usr/bin/chromium-driver", chromium_binary))

        # 非ARM Linuxならwebdriver-managerを試す
        if not is_linux_arm:
            try:
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
                logger.info("WebDriverManager succeeded")
                return
            except Exception as e:
                logger.warning("WebDriverManager failed: %s", e)

        # システムのchromedriverを試す
        for driver_path, chrome_path in driver_chrome_pairs:
            try:
                os.environ['CHROME_BIN'] = chrome_path
                os.environ['CHROME_PATH'] = chrome_path
                options.binary_location = chrome_path

                service = Service(driver_path)
                logger.info("Attempting: %s with %s", driver_path, chrome_path)
                self.driver = webdriver.Chrome(service=service, options=options)
                logger.info("SUCCESS: Using chromedriver at: %s", driver_path)
                return
            except Exception as e:
                logger.warning("Failed: %s - %s", driver_path, e)
                continue

        # ARM Linuxの場合、Selenium Managerはスキップ
        if is_linux_arm:
            raise Exception(
                "All ChromeDriver attempts failed on ARM64 Linux.\n"
                "Please ensure chromedriver and chromium are installed and compatible."
            )

        # 最後にデフォルトを試す
        try:
            self.driver = webdriver.Chrome(options=options)
        except Exception as e2:
            logger.error("All chromedriver attempts failed: %s", e2)
            raise

    def _teardown_driver(self):
        """WebDriverを終了"""
        if self.driver:
            self.driver.quit()

    def _log_browser_console(self, page_name: str):
        """ブラウザのコンソールログをDEBUGで記録"""
        try:
            logs = self.driver.get_log("browser")
            if logs:
                for entry in logs:
                    logger.debug("[browser:%s] %s: %s", page_name, entry.get("level", "?"), entry.get("message", ""))
            else:
                logger.debug("[browser:%s] No console logs", page_name)
        except Exception as e:
            logger.debug("[browser:%s] Could not retrieve console logs: %s", page_name, e)

    def _get_all_interactive_elements(self) -> List[Dict[str, Any]]:
        """ページ上のすべてのインタラクティブ要素を取得"""
        elements = []

        # 対象とするタグ
        tags = ["button", "input", "textarea", "select", "a"]

        for tag in tags:
            try:
                elems = self.driver.find_elements(By.TAG_NAME, tag)
                for elem in elems:
                    try:
                        data = {
                            "tag": tag,
                            "text": elem.text[:100] if elem.text else "",
                            "id": elem.get_attribute("id"),
                            "name": elem.get_attribute("name"),
                            "class": elem.get_attribute("class"),
                            "type": elem.get_attribute("type"),
                            "placeholder": elem.get_attribute("placeholder"),
                            "aria_label": elem.get_attribute("aria-label"),
                            "data_testid": elem.get_attribute("data-testid"),
                            "role": elem.get_attribute("role"),
                            "href": elem.get_attribute("href") if tag == "a" else None,
                        }

                        # 複数のセレクタパターンを生成
                        data["selectors"] = self._generate_selectors(data)

                        # XPathも生成
                        data["xpath"] = self._generate_xpath(elem)

                        elements.append(data)
                    except Exception:
                        continue
            except Exception:
                continue

        return elements

    def _generate_selectors(self, elem_data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """要素データから複数のセレクタパターンを生成"""
        selectors = {}

        tag = elem_data["tag"]

        # IDセレクタ
        if elem_data["id"]:
            selectors["by_id"] = f"#{elem_data['id']}"

        # Nameセレクタ
        if elem_data["name"]:
            selectors["by_name"] = f"{tag}[name='{elem_data['name']}']"

        # data-testidセレクタ
        if elem_data["data_testid"]:
            selectors["by_testid"] = f"[data-testid='{elem_data['data_testid']}']"

        # Classセレクタ（最初のクラスのみ）
        if elem_data["class"]:
            first_class = elem_data["class"].split()[0]
            selectors["by_class"] = f"{tag}.{first_class}"

        # Placeholderセレクタ
        if elem_data["placeholder"]:
            selectors["by_placeholder"] = f"{tag}[placeholder*='{elem_data['placeholder']}']"

        # ARIA labelセレクタ
        if elem_data["aria_label"]:
            selectors["by_aria_label"] = f"[aria-label*='{elem_data['aria_label']}']"

        # Typeセレクタ
        if elem_data["type"]:
            selectors["by_type"] = f"{tag}[type='{elem_data['type']}']"

        return selectors

    def _generate_xpath(self, element) -> str:
        """要素のXPathを生成"""
        try:
            return self.driver.execute_script(
                """
                function getXPath(element) {
                    if (element.id !== '')
                        return "//*[@id='" + element.id + "']";
                    if (element === document.body)
                        return element.tagName.toLowerCase();

                    var ix = Array.prototype.indexOf.call(element.parentNode.children, element) + 1;
                    return getXPath(element.parentNode) + "/" + element.tagName.toLowerCase() + "[" + ix + "]";
                }
                return getXPath(arguments[0]);
                """,
                element
            )
        except Exception:
            return ""

    def _identify_element_purpose(self, elem: Dict[str, Any]) -> str:
        """要素の用途を推定"""
        text = (elem.get("text") or "").lower()
        placeholder = (elem.get("placeholder") or "").lower()
        aria_label = (elem.get("aria_label") or "").lower()
        data_testid = (elem.get("data_testid") or "").lower()
        elem_type = (elem.get("type") or "").lower()

        combined = f"{text} {placeholder} {aria_label} {data_testid} {elem_type}"

        # ログイン関連
        if "email" in combined or "mail" in combined:
            return "login.email"
        if "password" in combined or "pass" in combined:
            return "login.password"
        if "login" in combined or "sign" in combined or "log" in combined:
            return "login.submit"

        # 予定作成関連
        if "create" in combined and "event" in combined:
            return "event.create_button"
        if "title" in combined:
            return "event.title_input"
        if "start" in combined:
            return "event.start_input"
        if "end" in combined:
            return "event.end_input"
        if "location" in combined or "place" in combined:
            return "event.location_input"
        if "description" in combined or "desc" in combined:
            return "event.description_input"
        if "save" in combined:
            return "event.save_button"
        if "cancel" in combined:
            return "event.cancel_button"
        if "all" in combined and "day" in combined:
            return "event.all_day_toggle"

        # カレンダー選択
        if "calendar" in combined and "selector" in combined:
            return "calendar.selector"
        if "calendar" in combined and "item" in combined:
            return "calendar.item"

        # 日付選択
        if "day" in combined or "date" in combined:
            return "date.day"

        return "unknown"

    def scan_login_page(self) -> Dict[str, Any]:
        """ログインページをスキャン"""
        logger.info("Scanning login page...")
        self.driver.get("https://timetreeapp.com/signin")
        time.sleep(3)
        logger.debug("Login page URL: %s", self.driver.current_url)
        logger.debug("Login page title: %s", self.driver.title)

        elements = self._get_all_interactive_elements()
        logger.debug("Found %d interactive elements on login page", len(elements))
        login_selectors = {
            "email_candidates": [],
            "password_candidates": [],
            "submit_candidates": []
        }

        for elem in elements:
            purpose = self._identify_element_purpose(elem)

            if purpose == "login.email":
                login_selectors["email_candidates"].append(elem)
            elif purpose == "login.password":
                login_selectors["password_candidates"].append(elem)
            elif purpose == "login.submit":
                login_selectors["submit_candidates"].append(elem)

        self.selectors_data["selectors"]["login"] = login_selectors
        self._log_browser_console("login")
        logger.debug("Login selectors: email=%d, password=%d, submit=%d",
                      len(login_selectors["email_candidates"]),
                      len(login_selectors["password_candidates"]),
                      len(login_selectors["submit_candidates"]))
        return login_selectors

    def scan_calendar_page(self) -> Dict[str, Any]:
        """カレンダーページをスキャン（ログイン後）"""
        logger.info("Scanning calendar page...")
        time.sleep(2)
        logger.debug("Calendar page URL: %s", self.driver.current_url)
        logger.debug("Calendar page title: %s", self.driver.title)

        elements = self._get_all_interactive_elements()
        logger.debug("Found %d interactive elements on calendar page", len(elements))
        calendar_selectors = {
            "create_button_candidates": [],
            "calendar_selector_candidates": [],
            "calendar_item_candidates": []
        }

        for elem in elements:
            purpose = self._identify_element_purpose(elem)

            if purpose == "event.create_button":
                calendar_selectors["create_button_candidates"].append(elem)
            elif purpose == "calendar.selector":
                calendar_selectors["calendar_selector_candidates"].append(elem)
            elif purpose == "calendar.item":
                calendar_selectors["calendar_item_candidates"].append(elem)

        self.selectors_data["selectors"]["calendar"] = calendar_selectors
        self._log_browser_console("calendar")
        logger.debug("Calendar selectors: create=%d, selector=%d, item=%d",
                      len(calendar_selectors["create_button_candidates"]),
                      len(calendar_selectors["calendar_selector_candidates"]),
                      len(calendar_selectors["calendar_item_candidates"]))
        return calendar_selectors

    def scan_event_form(self) -> Dict[str, Any]:
        """イベント作成フォームをスキャン"""
        logger.info("Scanning event creation form...")
        logger.debug("Event form page URL: %s", self.driver.current_url)

        # まず作成ボタンを探してクリック
        time.sleep(2)
        try:
            # テキスト内容でボタンを探す
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            logger.debug("Found %d buttons on page", len(buttons))
            for btn in buttons:
                text = btn.text.lower()
                if "create" in text or "new" in text or "+" in text or "予定" in text:
                    logger.debug("Clicking create button: '%s'", btn.text)
                    btn.click()
                    time.sleep(2)
                    break
            else:
                logger.warning("No create button found on page")
        except Exception as e:
            logger.warning("Could not click create button: %s", e)

        elements = self._get_all_interactive_elements()
        logger.debug("Found %d interactive elements in event form", len(elements))
        form_selectors = {
            "title_input_candidates": [],
            "start_input_candidates": [],
            "end_input_candidates": [],
            "location_input_candidates": [],
            "description_input_candidates": [],
            "all_day_toggle_candidates": [],
            "save_button_candidates": [],
            "cancel_button_candidates": []
        }

        for elem in elements:
            purpose = self._identify_element_purpose(elem)

            if purpose == "event.title_input":
                form_selectors["title_input_candidates"].append(elem)
            elif purpose == "event.start_input":
                form_selectors["start_input_candidates"].append(elem)
            elif purpose == "event.end_input":
                form_selectors["end_input_candidates"].append(elem)
            elif purpose == "event.location_input":
                form_selectors["location_input_candidates"].append(elem)
            elif purpose == "event.description_input":
                form_selectors["description_input_candidates"].append(elem)
            elif purpose == "event.all_day_toggle":
                form_selectors["all_day_toggle_candidates"].append(elem)
            elif purpose == "event.save_button":
                form_selectors["save_button_candidates"].append(elem)
            elif purpose == "event.cancel_button":
                form_selectors["cancel_button_candidates"].append(elem)

        self.selectors_data["selectors"]["event_form"] = form_selectors
        self._log_browser_console("event_form")
        logger.debug("Event form selectors: title=%d, start=%d, end=%d, location=%d, "
                      "description=%d, all_day=%d, save=%d, cancel=%d",
                      len(form_selectors["title_input_candidates"]),
                      len(form_selectors["start_input_candidates"]),
                      len(form_selectors["end_input_candidates"]),
                      len(form_selectors["location_input_candidates"]),
                      len(form_selectors["description_input_candidates"]),
                      len(form_selectors["all_day_toggle_candidates"]),
                      len(form_selectors["save_button_candidates"]),
                      len(form_selectors["cancel_button_candidates"]))

        # フォームを閉じる
        try:
            self.driver.find_elements(By.TAG_NAME, "button")[-1].click()
        except Exception:
            pass

        return form_selectors

    def run_full_scan(self, save_path: str = "selectors_data.json") -> Dict[str, Any]:
        """フルスキャンを実行"""
        logger.info("=== Full scan started ===")
        try:
            self._setup_driver()
            self.selectors_data["scan_date"] = datetime.now().isoformat()

            # ログインページスキャン
            self.scan_login_page()

            # ログイン（スキャン目的のため、手動でログインしてもらうか、設定がある場合は自動）
            logger.info("--- Please login manually if needed ---")
            logger.info("Waiting 30 seconds for manual login...")
            time.sleep(30)

            # カレンダーページスキャン
            self.scan_calendar_page()

            # イベントフォームスキャン
            self.scan_event_form()

            # 結果を保存
            self._save_scan_results(save_path)

            logger.info("=== Full scan completed ===")
            return self.selectors_data

        finally:
            self._teardown_driver()
            logger.info("WebDriver closed")

    def _save_scan_results(self, path: str):
        """スキャン結果を保存"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.selectors_data, f, indent=2, ensure_ascii=False)
        logger.info("Scan results saved to %s", path)

    def load_scan_results(self, path: str = "selectors_data.json") -> Dict[str, Any]:
        """スキャン結果を読み込み"""
        if Path(path).exists():
            with open(path, "r", encoding="utf-8") as f:
                self.selectors_data = json.load(f)
            return self.selectors_data
        return None


class SelectorAnalyzer:
    """スキャン結果を解析して最適なセレクタを選択"""

    def __init__(self, scan_data: Dict[str, Any]):
        self.scan_data = scan_data

    def get_best_selector(self, category: str, field: str) -> List[str]:
        """カテゴリとフィールドから最適なセレクタ候補を取得"""
        try:
            candidates = self.scan_data["selectors"][category][f"{field}_candidates"]
            selectors = []

            for cand in candidates:
                # 優先順位: testid > id > name > aria_label > class
                if cand.get("data_testid"):
                    selectors.append(f"[data-testid='{cand['data_testid']}']")
                elif cand.get("id"):
                    selectors.append(f"#{cand['id']}")
                elif cand.get("name"):
                    selectors.append(f"[name='{cand['name']}']")
                elif cand.get("aria_label"):
                    selectors.append(f"[aria-label='{cand['aria_label']}']")
                elif cand.get("class"):
                    first_class = cand["class"].split()[0]
                    selectors.append(f".{first_class}")

                # XPathも追加
                if cand.get("xpath"):
                    selectors.append(f"xpath:{cand['xpath']}")

            return selectors
        except (KeyError, IndexError):
            return []

    def generate_selector_config(self) -> Dict[str, List[str]]:
        """セレクタ設定ファイルを生成"""
        config = {}

        # ログイン用セレクタ
        config["login_email"] = self.get_best_selector("login", "email")
        config["login_password"] = self.get_best_selector("login", "password")
        config["login_submit"] = self.get_best_selector("login", "submit")

        # カレンダー用セレクタ
        config["calendar_selector"] = self.get_best_selector("calendar", "calendar_selector")
        config["calendar_item"] = self.get_best_selector("calendar", "calendar_item")
        config["create_button"] = self.get_best_selector("calendar", "create_button")

        # イベントフォーム用セレクタ
        config["event_title"] = self.get_best_selector("event_form", "title_input")
        config["event_start"] = self.get_best_selector("event_form", "start_input")
        config["event_end"] = self.get_best_selector("event_form", "end_input")
        config["event_location"] = self.get_best_selector("event_form", "location_input")
        config["event_description"] = self.get_best_selector("event_form", "description_input")
        config["event_all_day"] = self.get_best_selector("event_form", "all_day_toggle")
        config["event_save"] = self.get_best_selector("event_form", "save_button")
        config["event_cancel"] = self.get_best_selector("event_form", "cancel_button")

        return config


def main():
    """スキャナーを実行"""
    config.validate()

    log_path = _setup_logging()
    logger.info("=== TimeTree UI Scanner ===")
    logger.info("This will scan TimeTree's UI to find CSS selectors.")
    logger.info("Please login manually when prompted.")
    logger.info("Log file: %s", log_path)

    scanner = SelectorScanner(headless=config.HEADLESS)
    results = scanner.run_full_scan()

    # セレクタ設定を生成
    analyzer = SelectorAnalyzer(results)
    selector_config = analyzer.generate_selector_config()

    # セレクタ設定を保存
    config_path = Path("selectors_config.json")
    if config_path.exists():
        config_path.chmod(0o644)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(selector_config, f, indent=2, ensure_ascii=False)

    logger.info("=== Selector Configuration Generated ===")
    logger.info("Saved to %s", config_path)
    logger.info("Full log: %s", log_path)

    # セレクタ設定のサマリー
    for key, selectors in selector_config.items():
        logger.info("  %s: %d candidates", key, len(selectors))


if __name__ == "__main__":
    main()
