"""自然言語パーサー - LLMを使用して日時と予定を抽出"""
import json
import logging
from datetime import datetime
from typing import List, Optional
from config import config

logger = logging.getLogger(__name__)


class Event:
    """抽出された予定イベント"""
    def __init__(self, title: str, start_time: str, end_time: Optional[str] = None,
                 all_day: bool = False, location: Optional[str] = None,
                 description: Optional[str] = None):
        self.title = title
        self.start_time = start_time  # ISO 8601 format
        self.end_time = end_time      # ISO 8601 format
        self.all_day = all_day
        self.location = location
        self.description = description

    def __repr__(self):
        return f"Event(title={self.title!r}, start={self.start_time}, end={self.end_time}, all_day={self.all_day})"


class NLPParser:
    """LLMを使用して自然言語から予定を抽出"""

    def __init__(self, provider: str = None):
        self.provider = provider or config.LLM_PROVIDER

    def parse(self, text: str) -> List[Event]:
        """自然言語テキストから予定を抽出（複数対応）"""
        if self.provider == "openai":
            return self._parse_with_openai(text)
        elif self.provider == "anthropic":
            return self._parse_with_anthropic(text)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _get_system_prompt(self) -> str:
        """共通のシステムプロンプトを返す"""
        return """あなたは自然言語から予定を抽出するアシスタントです。
現在の日時は日本時間とみなしてください。

ユーザーの入力から以下の情報を抽出し、JSON形式で出力してください:
- title: 予定のタイトル
- start_time: 開始日時 (ISO 8601形式、日本時間)
- end_time: 終了日時 (ISO 8601形式、指定がない場合はnull)
  - 重要: 終日予定(all_day=true)の場合、end_timeは「最終日そのもの」の日付(00:00)を指定すること
  - 例: 「3月26日から28日まで」の場合、end_timeは3月28日ではなく3月28日00:00
  - 時刻指定予定(all_day=false)の場合、end_timeは終了時刻を指定すること
- all_day: 終日予定かどうか (true/false)
- location: 場所 (指定がない場合はnull)
- description: 説明 (指定がない場合はnull)

【重要】複数の予定が含まれる場合は、配列形式で出力してください。
例: 「2月11日、15日、3月1日に出張」
  → [
      {"title": "出張", "start_time": "2026-02-11T00:00:00+09:00", "end_time": null, "all_day": true, "location": null, "description": null},
      {"title": "出張", "start_time": "2026-02-15T00:00:00+09:00", "end_time": null, "all_day": true, "location": null, "description": null},
      {"title": "出張", "start_time": "2026-03-01T00:00:00+09:00", "end_time": null, "all_day": true, "location": null, "description": null}
    ]

単一の予定の場合も、必ず配列形式で出力してください。

例:
- "明日の15時から会議" → [{"title": "会議", "start_time": "2026-02-12T15:00:00+09:00", "end_time": null, "all_day": false, "location": null, "description": null}]
- "来週の月曜日に終日で休み" → [{"title": "休み", "start_time": "2026-02-16T00:00:00+09:00", "end_time": null, "all_day": true, "location": null, "description": null}]
- "3月26日から28日まで出張" → [{"title": "出張", "start_time": "2026-03-26T00:00:00+09:00", "end_time": "2026-03-28T00:00:00+09:00", "all_day": true, "location": null, "description": null}]
- "明日の10時から3日後の15時まで会議" → [{"title": "会議", "start_time": "2026-02-12T10:00:00+09:00", "end_time": "2026-02-15T15:00:00+09:00", "all_day": false, "location": null, "description": null}]

JSONのみを出力してください。"""

    def _parse_events_from_response(self, content: str) -> List[Event]:
        """LLMレスポンスからEventリストをパース"""
        content = content.strip()
        # Markdown code blockが含まれる場合の処理
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        content = content.strip()
        data = json.loads(content)

        # 配列でない場合は配列に変換
        if isinstance(data, dict):
            data = [data]

        events = []
        for item in data:
            events.append(Event(**item))

        return events

    def _parse_with_openai(self, text: str) -> List[Event]:
        """OpenAI APIを使用してパース"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package is required. Install with: pip install openai")

        client = OpenAI(api_key=config.OPENAI_API_KEY)

        current_time = datetime.now().isoformat()

        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {
                    "role": "system",
                    "content": self._get_system_prompt()
                },
                {
                    "role": "user",
                    "content": f"現在時刻: {current_time}\n\n入力: {text}"
                }
            ],
        )

        try:
            content = response.choices[0].message.content
            return self._parse_events_from_response(content)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return []

    def _parse_with_anthropic(self, text: str) -> List[Event]:
        """Anthropic APIを使用してパース"""
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("anthropic package is required. Install with: pip install anthropic")

        client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

        current_time = datetime.now().isoformat()

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": f"""{self._get_system_prompt()}

現在時刻: {current_time}

入力: {text}"""
                }
            ]
        )

        try:
            content = response.content[0].text
            return self._parse_events_from_response(content)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return []
