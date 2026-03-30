"""TimeTree操作自動化 - Selenium + SelectorManagerを使用"""
import os
import platform
import re
import time
import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from config import config
from selector_manager import SelectorManager

if TYPE_CHECKING:
    from nlp_parser import Event

logger = logging.getLogger(__name__)


class TimeTreeAutomation:
    """Selenium + SelectorManagerを使用してTimeTreeを操作"""

    def __init__(self, headless: bool = None, selector_config: str = "selectors_config.json"):
        # headlessが明示的に指定されていない場合、自動判定
        if headless is None:
            headless = config.HEADLESS

        # ディスプレイがない場合は自動的にheadlessモードを使用
        if not headless and not os.environ.get('DISPLAY'):
            logger.info("No display detected, forcing headless mode")
            headless = True

        self.headless = headless
        self.driver = None
        self.wait = None
        self.selector_manager = SelectorManager(selector_config)

    def _setup_driver(self):
        """Chrome WebDriverを設定"""
        # ARMアーキテクチャの場合、webdriver-managerはスキップ
        is_linux_arm = (
            platform.system() == "Linux" and
            platform.machine() in ("aarch64", "armv7l", "arm64")
        )

        # システムのchromedriverを試す
        driver_chrome_pairs = []
        if platform.system() == "Linux":
            if os.path.exists("/usr/bin/chromedriver"):
                driver_chrome_pairs.append("/usr/bin/chromedriver")
            if os.path.exists("/usr/bin/chromium-driver"):
                driver_chrome_pairs.append("/usr/bin/chromium-driver")
            if os.path.exists("/snap/bin/chromium.chromedriver"):
                driver_chrome_pairs.append("/snap/bin/chromium.chromedriver")

        # 非ARM Linuxならwebdriver-managerを試す
        if not is_linux_arm:
            try:
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service)
                self.wait = WebDriverWait(self.driver, 10)
                return
            except Exception as e:
                logger.warning(f"WebDriverManager failed: {e}")

        # システムのchromedriverを試す
        for driver_path in driver_chrome_pairs:
            try:
                # 最小限の設定（テストで動作確認済み）
                options = Options()
                if self.headless:
                    options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")

                service = Service(driver_path)
                logger.info(f"Attempting: {driver_path}")
                self.driver = webdriver.Chrome(service=service, options=options)
                logger.info(f"SUCCESS: Using chromedriver at: {driver_path}")
                self.wait = WebDriverWait(self.driver, 10)
                return
            except Exception as e:
                logger.warning(f"Failed: {driver_path} - {str(e)[:200]}")
                continue

        # ARM Linuxの場合、Selenium Managerはスキップ
        if is_linux_arm:
            raise Exception(
                "All ChromeDriver attempts failed on ARM64 Linux.\n"
                "Please ensure chromedriver and chromium are installed and compatible.\n"
                f"Tried: {driver_chrome_pairs}"
            )

        # 最後にデフォルトを試す
        try:
            self.driver = webdriver.Chrome()
        except Exception as e2:
            logger.error(f"All chromedriver attempts failed: {e2}")
            raise

        self.wait = WebDriverWait(self.driver, 10)

    def _teardown_driver(self):
        """WebDriverを終了"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error while tearing down driver: {e}")
            finally:
                self.driver = None

    def login(self) -> bool:
        """TimeTreeにログイン"""
        try:
            self._setup_driver()
            self.driver.get("https://timetreeapp.com/signin")
            time.sleep(2)

            logger.info("Logging in to TimeTree...")

            # メールアドレス入力
            email_input = self.selector_manager.wait_for_element(self.driver, "login_email", timeout=10)
            if not email_input:
                logger.error("Email input not found")
                return False
            email_input.send_keys(config.TIMETREE_EMAIL)

            # パスワード入力
            password_input = self.selector_manager.find_element(self.driver, "login_password")
            if not password_input:
                logger.error("Password input not found")
                return False
            password_input.send_keys(config.TIMETREE_PASSWORD)

            # ログインボタンクリック
            login_button = self.selector_manager.find_element(self.driver, "login_submit")
            if not login_button:
                logger.error("Login button not found")
                return False
            login_button.click()

            # ログイン完了を待機
            time.sleep(5)

            # ログイン成功を確認（URLが変わったか）
            if "login" not in self.driver.current_url:
                logger.info("✓ Login successful")
                return True
            else:
                logger.error("✗ Login failed (still on login page)")
                return False

        except Exception as e:
            logger.error(f"Login failed: {e}", exc_info=True)
            return False

    def _select_calendar(self, calendar_name: str) -> bool:
        """カレンダーを選択"""
        try:
            logger.info(f"Selecting calendar: {calendar_name}")
            time.sleep(2)

            # カレンダーセレクタをクリック
            calendar_selector = self.selector_manager.find_element(self.driver, "calendar_selector")
            if calendar_selector:
                try:
                    calendar_selector.click()
                except Exception:
                    # JavaScriptクリックを試す
                    self.driver.execute_script("arguments[0].click();", calendar_selector)
                time.sleep(1)
            else:
                # テキスト検索のフォールバック
                calendar_selector = self.selector_manager.find_element_by_text(
                    self.driver, "Calendar", "button"
                )
                if calendar_selector:
                    try:
                        calendar_selector.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", calendar_selector)
                    time.sleep(1)

            # カレンダー項目を取得
            calendar_items = self.selector_manager.find_elements(self.driver, "calendar_item")

            # カレンダー項目が見つからない場合はリンクを探す
            if not calendar_items:
                try:
                    calendar_items = self.driver.find_elements(By.CSS_SELECTOR, "a")
                    calendar_items = [item for item in calendar_items if item.text and "calendar" in item.text.lower()]
                except Exception:
                    pass

            for item in calendar_items:
                if calendar_name in item.text:
                    try:
                        item.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", item)
                    time.sleep(1)
                    logger.info(f"✓ Selected calendar: {calendar_name}")
                    return True

            # 見つからない場合は最初のカレンダーを選択
            if calendar_items:
                try:
                    calendar_items[0].click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", calendar_items[0])
                time.sleep(1)
                logger.info("✓ Selected first available calendar")
                return True

            logger.error("✗ No calendar found")
            return False

        except Exception as e:
            logger.error(f"Calendar selection failed: {e}", exc_info=True)
            return False

    def _format_datetime(self, iso_time: str, is_all_day: bool) -> str:
        """ISO 8601形式の時間をTimeTreeの入力形式に変換"""
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))

        if is_all_day:
            return dt.strftime("%Y-%m-%d")
        else:
            return dt.strftime("%Y-%m-%d %H:%M")

    def add_event(self, title: str, start_time: str, end_time: Optional[str] = None,
                  all_day: bool = False, location: Optional[str] = None,
                  description: Optional[str] = None) -> bool:
        """予定を追加"""
        try:
            logger.info(f"Adding event: title={title}, start_time={start_time}, end_time={end_time}, all_day={all_day}")

            # 予定作成ボタンを探す（複数の候補を試す）
            create_button = self.selector_manager.find_element(self.driver, "create_button")
            if not create_button:
                # テキストで探すフォールバック
                create_button = self.selector_manager.find_element_by_text(self.driver, "Create", "button")
                if not create_button:
                    create_button = self.selector_manager.find_element_by_text(self.driver, "+", "button")

            if not create_button:
                logger.error("✗ Create button not found")
                self._save_screenshot("create_button_not_found")
                return False

            logger.debug("✓ Found create button")
            # スクロールして見えるようにする
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", create_button)
                time.sleep(0.5)
            except Exception:
                pass

            # まずクリックしてダイアログを開く
            try:
                create_button.click()
                logger.debug("✓ Clicked create button")
            except Exception as e:
                logger.debug(f"Click failed: {e}, trying JavaScript...")
                self.driver.execute_script("arguments[0].click();", create_button)
                logger.debug("✓ Clicked create button (JavaScript)")

            # ダイアログが開くのを待機
            time.sleep(3)

            # URLの日付パラメータを変更して再読み込み
            current_url = self.driver.current_url
            dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            date_param = dt.strftime("%Y-%m-%d")

            # URLの日付パラメータを置換
            new_url = re.sub(r'date=\d{4}-\d{2}-\d{2}', f'date={date_param}', current_url)
            if 'date=' not in new_url:
                # 日付パラメータがない場合は追加
                separator = '&' if '?' in new_url else '?'
                new_url = f"{new_url}{separator}date={date_param}"

            if new_url != current_url:
                logger.info(f"  Updating date in URL: {new_url}")
                self.driver.get(new_url)
                time.sleep(3)

            # デバッグ: ページの状態を確認
            logger.debug(f"  Current URL: {self.driver.current_url}")

            # iframeがあればチェック
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                logger.debug(f"  Found {len(iframes)} iframes")
                for i, iframe in enumerate(iframes):
                    logger.debug(f"    iframe {i}: {iframe.get_attribute('src') or 'no src'}")
            except Exception:
                pass

            # contenteditableなdivを探す
            try:
                editables = self.driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
                logger.debug(f"  Found {len(editables)} contenteditable elements")
                if editables:
                    for i, elem in enumerate(editables[:3]):
                        logger.debug(f"    - {elem.get_attribute('outerHTML')[:150]}")
            except Exception:
                pass

            # タイトル入力 (タイムアウトを長めに設定)
            title_input = self.selector_manager.wait_for_element(self.driver, "event_title", timeout=15)
            if not title_input:
                logger.error("✗ Title input not found")
                self._save_screenshot("title_input_not_found")
                # デバッグ: ページ上のinput要素をダンプ
                try:
                    inputs = self.driver.find_elements(By.TAG_NAME, "input")
                    logger.debug(f"  Found {len(inputs)} input elements:")
                    for i, inp in enumerate(inputs[:5]):  # 最初の5つだけ表示
                        attrs = inp.get_attribute('outerHTML')[:200]
                        logger.debug(f"    - {attrs}")
                except Exception:
                    pass
                return False

            # contenteditable divの場合の処理
            tag_name = title_input.tag_name.lower()
            if tag_name == "div" or title_input.get_attribute("contenteditable") == "true":
                # contenteditable divの場合
                self.driver.execute_script("arguments[0].innerHTML = '';", title_input)
                title_input.click()
                title_input.send_keys(title)
                logger.info(f"  ✓ Title entered (contenteditable): {title}")
            else:
                # 通常のinputの場合
                title_input.clear()
                title_input.send_keys(title)
                logger.info(f"  ✓ Title entered: {title}")

            # 終日チェックボックスの処理（時刻指定の場合はチェックを外す）
            if not all_day:
                all_day_toggle = self.selector_manager.find_element(self.driver, "event_all_day")
                if all_day_toggle:
                    try:
                        # .ttfont-check_boxの場合は親要素をクリック
                        if all_day_toggle.tag_name.lower() == "span":
                            # 親要素を取得してクリック
                            parent = all_day_toggle.find_element(By.XPATH, "..")
                            logger.info(f"  Clicking all-day toggle parent: {parent.tag_name}")
                            parent.click()
                            time.sleep(1)  # UI更新を待つ
                        elif all_day_toggle.tag_name.lower() == "input":
                            if all_day_toggle.is_selected():
                                logger.info("  Unchecking all-day checkbox")
                                all_day_toggle.click()
                                time.sleep(1)
                        else:
                            # その他の要素の場合は直接クリック
                            logger.info(f"  Clicking all-day toggle: {all_day_toggle.tag_name}")
                            all_day_toggle.click()
                            time.sleep(1)
                    except Exception as e:
                        logger.warning(f"  ✗ All-day toggle failed: {e}, trying JavaScript")
                        try:
                            # JavaScriptで親要素をクリック
                            if all_day_toggle.tag_name.lower() == "span":
                                parent = self.driver.execute_script("return arguments[0].parentNode;", all_day_toggle)
                                self.driver.execute_script("arguments[0].click();", parent)
                            else:
                                self.driver.execute_script("arguments[0].click();", all_day_toggle)
                            time.sleep(1)
                        except Exception as e2:
                            logger.error(f"  ✗ All-day toggle JS failed: {e2}")

            # 日時入力（日付と時刻を別々に処理）
            dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = None
            if end_time:
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

            weekday_names = ["月", "火", "水", "木", "金", "土", "日"]

            # ===== 正しい順序で入力: 開始日 → 開始時刻 → 終了日 → 終了時刻 =====

            # 1. 開始日入力
            date_input = self.selector_manager.find_element(self.driver, "event_start")
            if date_input and date_input.tag_name.lower() == "input":
                try:
                    self.driver.execute_script("arguments[0].focus();", date_input)
                    time.sleep(0.2)
                    self.driver.execute_script("arguments[0].value = '';", date_input)
                    time.sleep(0.2)
                    date_str = f"{dt.year}年{dt.month}月{dt.day}日({weekday_names[dt.weekday()]})"
                    self.driver.execute_script("arguments[0].value = arguments[1];", date_input, date_str)
                    self.driver.execute_script("""
                        const element = arguments[0];
                        element.value = arguments[1];
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                    """, date_input, date_str)
                    logger.info(f"  ✓ Start date entered: {date_str}")
                    time.sleep(0.5)
                except Exception as e:
                    logger.error(f"  ✗ Start date input failed: {e}")

            # 2. 開始時刻入力（終日でない場合のみ）
            if not all_day:
                time_input = self.selector_manager.find_element(self.driver, "event_start_time")
                if not time_input:
                    try:
                        time_input = self.driver.find_element(By.CSS_SELECTOR, "[data-test-id=\"start-time-picker\"]")
                    except Exception:
                        pass
                if not time_input:
                    try:
                        time_input = self.driver.find_element(By.NAME, "startTime")
                    except Exception:
                        pass

                if time_input:
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", time_input)
                        time.sleep(0.3)
                        time_input.click()
                        time.sleep(0.3)
                        time_str = dt.strftime("%H:%M")
                        time_input.send_keys(Keys.CONTROL + "a")
                        time.sleep(0.1)
                        time_input.send_keys(time_str)
                        time.sleep(0.3)
                        time_input.send_keys(Keys.ENTER)
                        time.sleep(0.3)
                        logger.info(f"  ✓ Start time entered: {time_str}")
                    except Exception as e:
                        logger.error(f"  ✗ Start time input failed: {e}")
                else:
                    logger.error("  ✗ Start time input element not found")

            # 3. 終了日入力（end_timeがある場合）
            if end_time and end_dt:
                end_date_input = self.selector_manager.find_element(self.driver, "event_end")
                if end_date_input and end_date_input.tag_name.lower() == "input":
                    try:
                        end_date_input.click()
                        time.sleep(0.3)
                        end_date_input.clear()
                        time.sleep(0.2)
                        end_date_str = f"{end_dt.year}年{end_dt.month}月{end_dt.day}日({weekday_names[end_dt.weekday()]})"
                        end_date_input.send_keys(end_date_str)
                        time.sleep(0.3)
                        end_date_input.send_keys(Keys.ENTER)
                        time.sleep(0.3)
                        logger.info(f"  ✓ End date entered: {end_date_str}")
                    except Exception as e:
                        logger.error(f"  ✗ End date input failed: {e}")

                # 4. 終了時刻入力（終日でない場合のみ）
                if not all_day:
                    end_time_input = self.selector_manager.find_element(self.driver, "event_end_time")
                    if not end_time_input:
                        try:
                            end_time_input = self.driver.find_element(By.CSS_SELECTOR, "[data-test-id=\"end-time-picker\"]")
                        except Exception:
                            pass

                    if end_time_input:
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", end_time_input)
                            time.sleep(0.3)
                            end_time_input.click()
                            time.sleep(0.3)
                            end_time_str = end_dt.strftime("%H:%M")
                            end_time_input.send_keys(Keys.CONTROL + "a")
                            time.sleep(0.1)
                            end_time_input.send_keys(end_time_str)
                            time.sleep(0.3)
                            # 値を確認
                            actual_value = end_time_input.get_attribute("value")
                            logger.debug(f"  DEBUG: End time after input: {actual_value}")
                            end_time_input.send_keys(Keys.ENTER)
                            time.sleep(0.3)
                            # もう一度確認
                            actual_value2 = end_time_input.get_attribute("value")
                            logger.debug(f"  DEBUG: End time after ENTER: {actual_value2}")
                            logger.info(f"  ✓ End time entered: {end_time_str}")
                        except Exception as e:
                            logger.error(f"  ✗ End time input failed: {e}")

            # 場所
            if location:
                location_input = self.selector_manager.find_element(self.driver, "event_location")
                if location_input:
                    location_input.send_keys(location)
                    logger.info("  ✓ Location entered")

            # 説明
            if description:
                desc_input = self.selector_manager.find_element(self.driver, "event_description")
                if desc_input:
                    desc_input.send_keys(description)
                    logger.info("  ✓ Description entered")

            # 保存
            time.sleep(1)
            save_button = self.selector_manager.find_element(self.driver, "event_save")
            if not save_button:
                # テキストで探す
                save_button = self.selector_manager.find_element_by_text(self.driver, "Save", "button")

            if not save_button:
                logger.error("✗ Save button not found")
                self._save_screenshot("save_button_not_found")
                return False

            try:
                save_button.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", save_button)

            # 保存完了を待機して確認
            logger.info("Waiting for save to complete...")
            for i in range(10):  # 最大10秒待機
                time.sleep(1)
                current_url = self.driver.current_url
                # ダイアログが閉じたか確認（URLが/events/newでなくなった）
                if "/events/new" not in current_url:
                    logger.info("✓ Event saved (dialog closed)")
                    return True
                # 保存ボタンが消えたか確認
                if not self.selector_manager.find_element(self.driver, "event_save", timeout=1):
                    logger.info("✓ Event saved (save button disappeared)")
                    return True

            # タイムアウトした場合
            logger.error("✗ Save verification timeout - event may not have been saved")
            self._save_screenshot("save_timeout")
            return False

        except Exception as e:
            logger.error(f"Failed to add event: {e}", exc_info=True)
            self._save_screenshot("add_event_error")
            return False

    def _save_screenshot(self, prefix: str):
        """スクリーンショットを保存（デバッグ用）"""
        if self.driver:
            filename = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            self.driver.save_screenshot(filename)
            logger.info(f"  Screenshot saved: {filename}")

    def run(self, event: 'Event') -> bool:
        """一連の処理を実行（Eventオブジェクトを受け取る）"""
        try:
            logger.info(f"Starting automation for event: {event}")
            if not self.login():
                return False

            if not self._select_calendar(config.TIMETREE_CALENDAR_NAME):
                logger.error("Failed to select calendar")
                return False

            result = self.add_event(
                title=event.title,
                start_time=event.start_time,
                end_time=event.end_time,
                all_day=event.all_day,
                location=event.location,
                description=event.description
            )
            logger.info(f"Automation finished with result: {result}")
            return result

        finally:
            self._teardown_driver()
