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
from ui_diagnostic import UIDiagnostic

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

    def _try_with_self_heal(
        self, key: str, timeout: int = 5, use_wait: bool = False
    ) -> Optional[Any]:
        """要素を探し、見つからなければ診断→LLM修復→リトライ"""
        if use_wait:
            elem = self.selector_manager.wait_for_element(
                self.driver, key, timeout=timeout
            )
        else:
            elem = self.selector_manager.find_element(
                self.driver, key, timeout=timeout
            )
        if elem:
            return elem

        logger.warning("Element '%s' not found, running self-heal diagnostic...", key)
        try:
            diagnostic = UIDiagnostic()
            scan_data = diagnostic.scan_current_page(self.driver)
            suggestions = diagnostic.suggest_selectors(scan_data, [key])

            for selector in suggestions.get(key, []):
                logger.info("Self-heal trying '%s' for key '%s'", selector, key)
                self.selector_manager.add_selector(key, selector)
                if use_wait:
                    elem = self.selector_manager.wait_for_element(
                        self.driver, key, timeout=timeout
                    )
                else:
                    elem = self.selector_manager.find_element(
                        self.driver, key, timeout=timeout
                    )
                if elem:
                    logger.info("Self-heal succeeded for '%s': %s", key, selector)
                    return elem
        except Exception as e:
            logger.error("Self-heal failed for '%s': %s", key, e)

        logger.error("Self-heal could not find element for key '%s'", key)
        return None

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
            password_input = self._try_with_self_heal("login_password")
            if not password_input:
                logger.error("Password input not found")
                return False
            password_input.send_keys(config.TIMETREE_PASSWORD)

            # ログインボタンクリック
            login_button = self._try_with_self_heal("login_submit")
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

            # カレンダー項目が見つからない場合はボタンを探す
            if not calendar_items:
                try:
                    calendar_items = self.driver.find_elements(By.CSS_SELECTOR, "li button")
                    calendar_items = [item for item in calendar_items if item.text and item.text.strip()]
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

            # 予定作成ボタンを探す（self-heal付き）
            create_button = self._try_with_self_heal("create_button")
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

            # タイトル入力（wait_for_element は遅すぎるので直接検索）
            title_input = self._find_title_input()
            if not title_input:
                logger.error("✗ Title input not found")
                self._save_screenshot("title_input_not_found")
                self._dump_form_state()
                return False

            # contenteditable要素の場合
            is_editable = title_input.get_attribute("contenteditable") not in (None, "false")
            if is_editable or title_input.tag_name.lower() in ("div", "span"):
                self.driver.execute_script("arguments[0].innerHTML = '';", title_input)
                title_input.click()
                time.sleep(0.2)
                title_input.send_keys(title)
                logger.info(f"  ✓ Title entered (editable): {title}")
            elif title_input.tag_name.lower() == "textarea":
                title_input.clear()
                title_input.send_keys(title)
                logger.info(f"  ✓ Title entered (textarea): {title}")
            else:
                title_input.clear()
                title_input.send_keys(title)
                logger.info(f"  ✓ Title entered (input): {title}")

            # 終日チェックボックスの処理（時刻指定の場合はチェックを外す）
            if not all_day:
                self._toggle_all_day_off()

            # 日時入力（日付と時刻を別々に処理）
            dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = None
            if end_time:
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

            weekday_names = ["月", "火", "水", "木", "金", "土", "日"]

            # ===== 正しい順序で入力: 開始日 → 開始時刻 → 終了日 → 終了時刻 =====

            # 1. 開始日入力
            date_input = self._try_with_self_heal("event_start")
            if date_input and date_input.tag_name.lower() == "input":
                try:
                    date_str = f"{dt.year}年{dt.month}月{dt.day}日({weekday_names[dt.weekday()]})"
                    date_input.click()
                    time.sleep(0.3)
                    # React互換の値設定
                    self._react_set_value(date_input, date_str)
                    logger.info(f"  ✓ Start date entered: {date_str}")
                    time.sleep(0.5)
                except Exception as e:
                    logger.error(f"  ✗ Start date input failed: {e}")

            # 2. 開始時刻入力（終日でない場合のみ）
            if not all_day:
                time_input = self._find_time_picker()
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
                    self._dump_form_state()

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

            # 保存ボタンを探す（複数戦略）
            time.sleep(1)
            save_button = self._find_save_button()

            if not save_button:
                logger.error("✗ Save button not found")
                self._save_screenshot("save_button_not_found")
                return False

            # 保存前にスクリーンショット（デバッグ用）
            self._save_screenshot("before_save")

            # 保存ボタンの情報をログ出力
            try:
                tag = save_button.tag_name
                text = save_button.text.strip()[:50] if save_button.text else "(no text)"
                classes = save_button.get_attribute("class") or ""
                enabled = save_button.is_enabled()
                logger.info(f"  Save button: tag={tag}, text='{text}', class='{classes[:80]}', enabled={enabled}")
            except Exception:
                pass

            # 保存ボタンをスクロールして表示
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    save_button
                )
                time.sleep(0.3)
            except Exception:
                pass

            # 保存ボタンが無効な場合はフォーム状態をダンプして続行
            try:
                if not save_button.is_enabled():
                    logger.warning("  Save button is DISABLED - dumping form state")
                    self._dump_form_state()
            except Exception:
                pass

            # 複数のクリック戦略を順に試す
            save_clicked = False
            strategies = [
                ("JS mouse events", lambda: self.driver.execute_script(
                    "var btn=arguments[0];['mousedown','mouseup','click'].forEach(function(e){btn.dispatchEvent(new MouseEvent(e,{bubbles:true,cancelable:true,view:window}));});",
                    save_button)),
                ("ActionChains click", lambda: self._action_chains_click(save_button)),
                ("Direct click", lambda: save_button.click()),
                ("JS form submit", lambda: self.driver.execute_script(
                    "var form=document.querySelector('form');if(form){form.submit();}else{arguments[0].click();}",
                    save_button)),
                ("Enter key", lambda: self._send_enter_to_element(save_button)),
            ]
            for attempt, (name, strategy) in enumerate(strategies):
                try:
                    strategy()
                    logger.info(f"  Save attempt {attempt+1}/{len(strategies)}: {name}")
                    save_clicked = True
                except Exception as e:
                    logger.debug(f"  Save attempt {attempt+1} ({name}) failed: {e}")
                    continue

                # 2秒待って結果を確認
                time.sleep(2)
                if "/events/new" not in self.driver.current_url:
                    logger.info(f"✓ Event saved via {name}")
                    return True
                # パネルが閉じたか確認（タイトル入力が見えなくなったら）
                try:
                    title_still_visible = self.driver.execute_script(
                        "var inputs = document.querySelectorAll('input[type=\"text\"]');"
                        "for(var i=0;i<inputs.length;i++){if(inputs[i].value && inputs[i].offsetParent!==null)return true;}"
                        "return false;"
                    )
                    if not title_still_visible:
                        logger.info(f"✓ Event saved - form closed (attempt {attempt+1})")
                        return True
                except Exception:
                    pass

            if not save_clicked:
                logger.error("✗ All save click methods failed")
                self._save_screenshot("save_click_failed")
                return False

            # さらに待機して確認
            logger.info("  Waiting for save confirmation...")
            for i in range(8):
                time.sleep(1)
                if "/events/new" not in self.driver.current_url:
                    logger.info("✓ Event saved (confirmed)")
                    return True
                # エラーメッセージ確認
                try:
                    error_elems = self.driver.find_elements(By.CSS_SELECTOR,
                        "[role='alert'], .error, [data-test-id='error-message']")
                    if error_elems:
                        error_text = " ".join(e.text for e in error_elems if e.text)
                        if error_text:
                            logger.error(f"  Error detected: {error_text[:200]}")
                            self._save_screenshot("save_error")
                            return False
                except Exception:
                    pass

            logger.error("✗ Save verification timeout")
            self._dump_form_state()
            self._save_screenshot("save_timeout")
            return False

        except Exception as e:
            logger.error(f"Failed to add event: {e}", exc_info=True)
            self._save_screenshot("add_event_error")
            return False

    def _find_title_input(self):
        """タイトル入力フィールドを探す（wait_for_elementを使わず高速に）"""
        # 戦略1: data-test-id
        try:
            el = self.driver.find_element(By.CSS_SELECTOR, '[data-test-id="event-title"]')
            if el and el.is_displayed():
                logger.info("  Found title by data-test-id")
                return el
        except Exception:
            pass

        # 戦略2: name="title"
        try:
            el = self.driver.find_element(By.CSS_SELECTOR, 'input[name="title"], textarea[name="title"]')
            if el and el.is_displayed():
                logger.info("  Found title by name=title")
                return el
        except Exception:
            pass

        # 戦略3: contenteditable（属性値問わず、html/body除外）
        try:
            editables = self.driver.find_elements(By.CSS_SELECTOR, "[contenteditable]")
            for el in editables:
                tag = el.tag_name.lower()
                if tag not in ('html', 'body') and el.is_displayed():
                    logger.info(f"  Found title by contenteditable (tag={tag})")
                    return el
        except Exception:
            pass

        # 戦略4: role="textbox"
        try:
            textboxes = self.driver.find_elements(By.CSS_SELECTOR, '[role="textbox"]')
            for el in textboxes:
                if el.is_displayed():
                    logger.info("  Found title by role=textbox")
                    return el
        except Exception:
            pass

        # 戦略5: JavaScript で「タイトル」ラベルの近くの入力要素を探す
        try:
            el = self.driver.execute_script("""
                var allElements = document.querySelectorAll('*');
                for (var i = 0; i < allElements.length; i++) {
                    var el = allElements[i];
                    if (el.childNodes.length === 0 || el.children.length > 3) continue;
                    if (el.tagName === 'HTML' || el.tagName === 'BODY') continue;
                    var text = el.textContent.trim();
                    if (text.includes('タイトル') && text.length < 30) {
                        // このラベルの近くの入力要素を探す
                        var container = el.parentElement;
                        if (container) container = container.parentElement;
                        if (!container) continue;
                        var inputs = container.querySelectorAll(
                            'input, textarea, [contenteditable], [role="textbox"]');
                        for (var j = 0; j < inputs.length; j++) {
                            if (inputs[j].offsetParent !== null) return inputs[j];
                        }
                    }
                }
                return null;
            """)
            if el:
                logger.info("  Found title by JS label search")
                return el
        except Exception:
            pass

        # 戦略6: textarea（placeholder問わず）
        try:
            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
            for el in textareas:
                if el.is_displayed():
                    logger.info("  Found title by textarea")
                    return el
        except Exception:
            pass

        logger.error("  No title input found by any strategy")
        return None

    def _toggle_all_day_off(self):
        """終日モードをオフにする"""
        # 戦略1: セレクタ設定でトグルを探す
        toggle = self.selector_manager.find_element(self.driver, "event_all_day")
        if toggle and toggle.tag_name.lower() not in ('html', 'body'):
            self._click_all_day_toggle(toggle)
            return

        # 戦略2: テキスト「終日」の近くのボタンを探す（html/body除外）
        try:
            labels = self.driver.find_elements(By.XPATH,
                "//*[text()='終日' or text()='All Day']")
            for label in labels:
                tag = label.tag_name.lower()
                if tag in ('html', 'body'):
                    continue
                # 親要素内のボタン/スイッチを探す
                parent = label.find_element(By.XPATH, "..")
                toggles = parent.find_elements(By.CSS_SELECTOR,
                    "button, [role='switch'], [role='checkbox']")
                if toggles:
                    logger.info(f"  Found all-day toggle near '終日' label")
                    self._click_all_day_toggle(toggles[0])
                    return
                # 親要素自体がクリック可能かも
                if parent.tag_name.lower() in ('button', 'label'):
                    logger.info(f"  Clicking all-day parent: {parent.tag_name}")
                    self._click_all_day_toggle(parent)
                    return
        except Exception:
            pass

        # 戦略3: 非表示チェックボックスを直接操作（JavaScript）
        try:
            checkbox = self.driver.find_element(By.CSS_SELECTOR, 'input[type="checkbox"]')
            if checkbox.get_attribute('value') == 'on':
                logger.info("  Toggling all-day via hidden checkbox (JS)")
                self.driver.execute_script("arguments[0].click();", checkbox)
                time.sleep(1)
                # 確認: チェックボックスの値が変わったか
                new_val = checkbox.get_attribute('value')
                logger.info(f"  Checkbox value after toggle: {new_val}")
                return
        except Exception as e:
            logger.debug(f"  Checkbox toggle failed: {e}")

        logger.warning("  All-day toggle not found - event may be saved as all-day")

    def _action_chains_click(self, element):
        """ActionChainsでクリック（よりリアルなマウス操作）"""
        from selenium.webdriver.common.action_chains import ActionChains
        actions = ActionChains(self.driver)
        actions.move_to_element(element).click().perform()

    def _send_enter_to_element(self, element):
        """Enter キーで送信"""
        element.send_keys(Keys.ENTER)

    def _react_set_value(self, element, value):
        """React の制御コンポーネントに対応した値設定"""
        self.driver.execute_script("""
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(arguments[0], arguments[1]);
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        """, element, value)

    def _find_save_button(self):
        """保存ボタンを複数の戦略で探す"""
        # 戦略1: セレクタ設定から探す（self-heal付き）
        save_button = self._try_with_self_heal("event_save")
        if save_button:
            logger.debug("  Found save button via selector config")
            return save_button

        # 戦略2: テキストで探す（日本語優先）
        for text in ["保存", "Save", "保存する", "作成", "Create"]:
            save_button = self.selector_manager.find_element_by_text(self.driver, text, "button")
            if save_button:
                logger.debug(f"  Found save button by text: '{text}'")
                return save_button

        # 戦略3: SVGアイコン付きボタンを探す（チェックマーク等）
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "button")
            for btn in buttons:
                try:
                    svgs = btn.find_elements(By.TAG_NAME, "svg")
                    btn_text = btn.text.strip()
                    # テキストが空でSVGがある、かつフォーム領域内のボタン
                    if svgs and not btn_text:
                        # ヘッダー内のボタンかチェック（保存ボタンは通常ヘッダーにある）
                        rect = btn.rect
                        if rect['y'] < 200:  # ページ上部のボタン
                            logger.debug(f"  Found icon button at y={rect['y']}")
                            return btn
                except Exception:
                    continue
        except Exception:
            pass

        # 戦略4: フォーム内のsubmitボタン
        try:
            forms = self.driver.find_elements(By.TAG_NAME, "form")
            for form in forms:
                submit = form.find_element(By.CSS_SELECTOR, "button[type='submit']")
                if submit and submit.is_displayed():
                    logger.debug("  Found submit button in form")
                    return submit
        except Exception:
            pass

        return None

    def _find_all_day_toggle(self):
        """終日トグルを複数の戦略で探す"""
        # 戦略1: セレクタ設定
        toggle = self.selector_manager.find_element(self.driver, "event_all_day")
        if toggle:
            return toggle

        # 戦略2: テキスト「終日」で探す
        for text in ["終日", "All Day", "all day", "終日設定"]:
            toggle = self.selector_manager.find_element_by_text(self.driver, text, "*")
            if toggle:
                logger.info(f"  Found all-day toggle by text: '{text}'")
                return toggle

        # 戦略3: 「終日」ラベルの近くのトグル/チェックボックスを探す
        try:
            labels = self.driver.find_elements(By.XPATH,
                "//*[contains(text(), '終日') or contains(text(), 'All Day')]")
            for label in labels:
                # 同じ親要素内のトグルを探す
                parent = label.find_element(By.XPATH, "..")
                toggles = parent.find_elements(By.CSS_SELECTOR,
                    "button, [role='switch'], [role='checkbox'], input[type='checkbox']")
                if toggles:
                    logger.info(f"  Found all-day toggle near label")
                    return toggles[0]
        except Exception:
            pass

        return None

    def _click_all_day_toggle(self, toggle):
        """終日トグルをクリックして終日をオフにする"""
        tag = toggle.tag_name.lower()
        logger.info(f"  Clicking all-day toggle: tag={tag}")
        try:
            if tag == "span":
                parent = toggle.find_element(By.XPATH, "..")
                logger.info(f"  Clicking all-day toggle parent: {parent.tag_name}")
                parent.click()
            elif tag == "input":
                if toggle.is_selected():
                    toggle.click()
            elif tag == "button":
                toggle.click()
            else:
                # 親または祖先のbutton/labelを探す
                clickable = self.driver.execute_script("""
                    var el = arguments[0];
                    while (el && el.tagName !== 'BUTTON' && el.tagName !== 'LABEL') {
                        el = el.parentElement;
                    }
                    return el;
                """, toggle)
                if clickable:
                    clickable.click()
                else:
                    toggle.click()
            time.sleep(1)
            logger.info("  ✓ All-day toggle clicked")
        except Exception as e:
            logger.warning(f"  Direct click failed: {e}, trying JavaScript")
            try:
                self.driver.execute_script("arguments[0].click();", toggle)
                time.sleep(1)
                logger.info("  ✓ All-day toggle clicked (JS)")
            except Exception as e2:
                logger.error(f"  ✗ All-day toggle click failed: {e2}")

    def _find_time_picker(self):
        """開始時刻ピッカーを複数の戦略で探す"""
        # 戦略1: セレクタ設定
        time_input = self.selector_manager.find_element(self.driver, "event_start_time")
        if time_input:
            return time_input

        # 戦略2: data-test-id
        for test_id in ["start-time-picker", "time-picker", "event-start-time"]:
            try:
                time_input = self.driver.find_element(By.CSS_SELECTOR, f'[data-test-id="{test_id}"]')
                if time_input and time_input.is_displayed():
                    logger.info(f"  Found time picker by data-test-id: {test_id}")
                    return time_input
            except Exception:
                continue

        # 戦略3: name属性
        for name in ["startTime", "start_time", "time"]:
            try:
                time_input = self.driver.find_element(By.NAME, name)
                if time_input and time_input.is_displayed():
                    logger.info(f"  Found time picker by name: {name}")
                    return time_input
            except Exception:
                continue

        # 戦略4: placeholder検索
        for placeholder in ["時刻", "時間", "time", "Time", "HH:mm"]:
            try:
                time_input = self.driver.find_element(
                    By.CSS_SELECTOR, f'input[placeholder*="{placeholder}"]')
                if time_input and time_input.is_displayed():
                    logger.info(f"  Found time picker by placeholder: {placeholder}")
                    return time_input
            except Exception:
                continue

        # 戦略5: type=time のinput
        try:
            time_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="time"]')
            if time_inputs:
                for ti in time_inputs:
                    if ti.is_displayed():
                        logger.info("  Found time picker by type=time")
                        return ti
        except Exception:
            pass

        return None

    def _dump_form_state(self):
        """フォームの状態をダンプ（デバッグ用）"""
        try:
            logger.info("  === Form state dump ===")
            # 全ボタン
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for i, btn in enumerate(buttons):
                try:
                    text = btn.text.strip()[:40] if btn.text else ""
                    cls = btn.get_attribute("class") or ""
                    enabled = btn.is_enabled()
                    displayed = btn.is_displayed()
                    logger.info(f"  Button[{i}]: text='{text}', class='{cls[:60]}', "
                               f"enabled={enabled}, visible={displayed}")
                except Exception:
                    pass

            # 全input
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            for i, inp in enumerate(inputs):
                try:
                    inp_type = inp.get_attribute("type") or ""
                    inp_name = inp.get_attribute("name") or ""
                    inp_val = (inp.get_attribute("value") or "")[:40]
                    inp_placeholder = inp.get_attribute("placeholder") or ""
                    displayed = inp.is_displayed()
                    logger.info(f"  Input[{i}]: type={inp_type}, name={inp_name}, "
                               f"value='{inp_val}', placeholder='{inp_placeholder}', visible={displayed}")
                except Exception:
                    pass

            # エラーメッセージ
            for sel in ["[role='alert']", ".error", "[data-test-id='error-message']",
                        ".error-message", "[class*='error']", "[class*='Error']"]:
                try:
                    errors = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for err in errors:
                        if err.text:
                            logger.info(f"  Error: '{err.text[:100]}'")
                except Exception:
                    pass

            logger.info("  === End form state dump ===")
        except Exception as e:
            logger.debug(f"  Form state dump failed: {e}")

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

            # ログイン後のURLが /calendars/<id> なら既にカレンダービュー
            current_url = self.driver.current_url
            if "/calendars/" in current_url and current_url.rstrip("/").split("/calendars/")[-1]:
                logger.info("Already on calendar view: %s", current_url)
            else:
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
