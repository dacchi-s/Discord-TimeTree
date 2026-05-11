"""UI診断モジュール - TimeTreeのUI変更を検知し、セレクタを自動修復する"""
import json
import logging
from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from config import config

logger = logging.getLogger(__name__)

# 各セレクタキーの期待される役割の説明
ELEMENT_DESCRIPTIONS = {
    "login_email": "メールアドレス入力フィールド (signinページ)",
    "login_password": "パスワード入力フィールド (signinページ)",
    "login_submit": "ログイン/サインインボタン",
    "calendar_selector": "カレンダー切替ボタン (サイドバー)",
    "calendar_item": "カレンダー選択項目 (サイドバー内のリスト)",
    "create_button": "予定作成ボタン (+ アイコンや「予定を作成」)",
    "event_title": "予定タイトル入力 (contenteditable div または input)",
    "event_start": "開始日付入力フィールド",
    "event_start_time": "開始時刻入力フィールド",
    "event_end": "終了日付入力フィールド",
    "event_end_time": "終了時刻入力フィールド",
    "event_location": "場所入力フィールド",
    "event_description": "説明/メモ入力 (textarea または contenteditable)",
    "event_all_day": "終日チェックボックス/トグル",
    "event_save": "保存/作成ボタン (フォーム内)",
    "event_cancel": "キャンセルボタン",
}


class UIDiagnostic:
    """TimeTreeのUIを診断し、セレクタの有効性をチェック・修復する"""

    def scan_current_page(self, driver: webdriver.Chrome) -> Dict[str, Any]:
        """ページ上の全インタラクティブ要素をスキャンして構造化データを返す"""
        result = {
            "url": driver.current_url,
            "title": driver.title,
            "elements": [],
        }

        tags = ["button", "input", "textarea", "select", "a", "div"]
        for tag in tags:
            try:
                elems = driver.find_elements(By.TAG_NAME, tag)
                for elem in elems:
                    try:
                        if not elem.is_displayed():
                            continue
                        data = {
                            "tag": tag,
                            "text": (elem.text or "")[:80],
                            "id": elem.get_attribute("id") or "",
                            "name": elem.get_attribute("name") or "",
                            "type": elem.get_attribute("type") or "",
                            "class": elem.get_attribute("class") or "",
                            "placeholder": elem.get_attribute("placeholder") or "",
                            "aria_label": elem.get_attribute("aria-label") or "",
                            "data_testid": elem.get_attribute("data-testid")
                                or elem.get_attribute("data-test-id") or "",
                            "role": elem.get_attribute("role") or "",
                            "contenteditable": elem.get_attribute("contenteditable") or "",
                            "href": elem.get_attribute("href") or "" if tag == "a" else "",
                        }
                        result["elements"].append(data)
                    except Exception:
                        continue
            except Exception:
                continue

        logger.info("Scanned %d visible elements on %s", len(result["elements"]), driver.current_url)
        return result

    def validate_selectors(
        self, driver: webdriver.Chrome, selectors: Dict[str, List[str]]
    ) -> Dict[str, Dict[str, bool]]:
        """各セレクタが現在有効かどうかをチェック"""
        results = {}
        for key, candidates in selectors.items():
            results[key] = {}
            for selector in candidates:
                try:
                    if selector.startswith("xpath:"):
                        elem = driver.find_element(By.XPATH, selector[6:])
                    else:
                        elem = driver.find_element(By.CSS_SELECTOR, selector)
                    results[key][selector] = elem is not None and elem.is_displayed()
                except Exception:
                    results[key][selector] = False
        return results

    def get_broken_selectors(
        self, driver: webdriver.Chrome, selectors: Dict[str, List[str]]
    ) -> List[str]:
        """現在使用できないセレクタキーのリストを返す"""
        broken = []
        for key, candidates in selectors.items():
            all_failed = True
            for selector in candidates:
                try:
                    if selector.startswith("xpath:"):
                        elem = driver.find_element(By.XPATH, selector[6:])
                    else:
                        elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if elem and elem.is_displayed():
                        all_failed = False
                        break
                except Exception:
                    continue
            if all_failed and candidates:
                broken.append(key)
        return broken

    def suggest_selectors(
        self, scan_data: Dict[str, Any], missing_keys: List[str]
    ) -> Dict[str, List[str]]:
        """LLMを使って不足セレクタの候補を提案"""
        if not missing_keys:
            return {}

        # スキャンデータをコンパクトにまとめる
        elements_summary = []
        for elem in scan_data["elements"]:
            parts = [f"<{elem['tag']}"]
            if elem["id"]:
                parts.append(f"id={elem['id']}")
            if elem["name"]:
                parts.append(f"name={elem['name']}")
            if elem["type"]:
                parts.append(f"type={elem['type']}")
            if elem["data_testid"]:
                parts.append(f"data-testid={elem['data_testid']}")
            if elem["aria_label"]:
                parts.append(f"aria-label={elem['aria_label']}")
            if elem["placeholder"]:
                parts.append(f"placeholder={elem['placeholder']}")
            if elem["role"]:
                parts.append(f"role={elem['role']}")
            if elem["contenteditable"]:
                parts.append(f"contenteditable={elem['contenteditable']}")
            if elem["text"]:
                parts.append(f"text=\"{elem['text'][:40]}\"")
            if elem["class"]:
                parts.append(f"class=\"{elem['class'].split()[0]}\"")
            parts.append(">")
            elements_summary.append(" ".join(parts))

        missing_descriptions = []
        for key in missing_keys:
            desc = ELEMENT_DESCRIPTIONS.get(key, "不明な要素")
            missing_descriptions.append(f"- {key}: {desc}")

        prompt = f"""TimeTreeのWebアプリケーションでUI変更が発生し、以下の要素が見つかりません。

## 見つからない要素:
{chr(10).join(missing_descriptions)}

## 現在のページURL: {scan_data['url']}
## ページタイトル: {scan_data['title']}

## 現在のページに存在する要素:
{chr(10).join(elements_summary)}

## 命令:
各 missing key について、上記の要素リストから最も適切なCSSセレクタを最大3つ提案してください。
セレクタの優先順位: data-testid > id > name > aria-label > placeholder > class
minified class名（5文字以下のランダム文字列）は避けてください。安定した属性を優先してください。

## 出力形式（JSONのみ、説明文は不要）:
{{"key_name": ["selector1", "selector2"]}}"""

        try:
            return self._call_llm(prompt, missing_keys)
        except Exception as e:
            logger.error("LLM selector suggestion failed: %s", e)
            return {}

    def _call_llm(self, prompt: str, missing_keys: List[str]) -> Dict[str, List[str]]:
        """LLMを呼び出してセレクタ提案を取得"""
        if config.LLM_PROVIDER == "openai":
            return self._call_openai(prompt)
        elif config.LLM_PROVIDER == "anthropic":
            return self._call_anthropic(prompt)
        else:
            logger.error("Unknown LLM provider: %s", config.LLM_PROVIDER)
            return {}

    def _call_openai(self, prompt: str) -> Dict[str, List[str]]:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "TimeTree UIのCSSセレクタを提案する。JSONのみを出力する。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1000,
        )
        return self._parse_llm_response(response.choices[0].message.content)

    def _call_anthropic(self, prompt: str) -> Dict[str, List[str]]:
        from anthropic import Anthropic
        client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._parse_llm_response(response.content[0].text)

    def _parse_llm_response(self, text: str) -> Dict[str, List[str]]:
        """LLMのレスポンスからJSONを抽出"""
        # markdown code block を除去
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            result = json.loads(text)
            if isinstance(result, dict):
                # 値が全てリストであることを確認
                return {k: v for k, v in result.items() if isinstance(v, list)}
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON response: %s", text[:200])

        return {}

    def run_full_diagnostic(
        self, driver: webdriver.Chrome, selectors: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """完全な診断レポートを生成"""
        report = {
            "url": driver.current_url,
            "title": driver.title,
            "broken_keys": [],
            "working_keys": [],
            "suggestions": {},
            "scan_summary": {},
        }

        # ページスキャン
        scan_data = self.scan_current_page(driver)
        report["scan_summary"] = {
            "total_elements": len(scan_data["elements"]),
            "tags": {},
        }
        for elem in scan_data["elements"]:
            tag = elem["tag"]
            report["scan_summary"]["tags"][tag] = report["scan_summary"]["tags"].get(tag, 0) + 1

        # セレクタ検証
        broken = self.get_broken_selectors(driver, selectors)
        report["broken_keys"] = broken

        all_keys = set(selectors.keys())
        working = all_keys - set(broken)
        report["working_keys"] = list(working)

        # LLM提案（壊れたキーがある場合のみ）
        if broken:
            logger.info("Broken selectors detected: %s", broken)
            suggestions = self.suggest_selectors(scan_data, broken)
            report["suggestions"] = suggestions

        return report
