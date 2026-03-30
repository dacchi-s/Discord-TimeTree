"""Discordボット - メッセージを受信してTimeTreeに予定を登録"""
import asyncio
import sys
import logging
import discord
from discord.ext import commands
from config import config
from nlp_parser import NLPParser, Event
from timetree_automation import TimeTreeAutomation

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)

# Selenium操作のタイムアウト（秒）
SELENIUM_TIMEOUT = 300


class TimeTreeBot(commands.Bot):
    """TimeTree連携Discordボット"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        self.nlp_parser = NLPParser()

    async def setup_hook(self):
        """ボット起動時の処理"""
        logger.info(f"Logged in as {self.user}")

    async def on_message(self, message: discord.Message):
        """メッセージ受信時の処理"""
        # 自分自身のメッセージは無視
        if message.author == self.user:
            return

        # 他のボットのメッセージは無視
        if message.author.bot:
            return

        # 特定チャンネルのみ処理
        if message.channel.id != config.DISCORD_CHANNEL_ID:
            return

        # コマンドは無視（!で始まるメッセージ）
        if message.content.startswith("!"):
            return

        # メッセージを処理
        await self._process_message(message)

    async def _process_message(self, message: discord.Message):
        """メッセージを処理してTimeTreeに登録"""
        text = message.content
        logger.info(f"Processing message from {message.author}: {text}")

        # 処理中を通知
        async with message.channel.typing():
            try:
                # NLPでパース
                events = self.nlp_parser.parse(text)

                if not events:
                    await message.add_reaction("❓")
                    await message.reply("予定を解析できませんでした。入力内容を確認してください。")
                    return

                logger.info(f"Parsed {len(events)} event(s)")

                # 各イベントを順番に登録
                created = 0
                for i, event in enumerate(events):
                    logger.info(f"Processing event {i+1}/{len(events)}: {event}")

                    # タイムアウト付きでSeleniumを実行
                    loop = asyncio.get_event_loop()
                    try:
                        success = await asyncio.wait_for(
                            loop.run_in_executor(
                                None,
                                self._add_event_to_timetree,
                                event
                            ),
                            timeout=SELENIUM_TIMEOUT
                        )
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout while processing event {i+1}")
                        await message.add_reaction("⏰")
                        if created > 0:
                            await message.reply(f"{created}件登録済みですが、{i+1}件目でタイムアウトしました。")
                        else:
                            await message.reply("処理がタイムアウトしました。時間を置いて再度お試しください。")
                        return

                    if success:
                        created += 1
                    else:
                        # 失敗したら残りは処理しない
                        logger.error(f"Failed to create event {i+1}")
                        break

                logger.info(f"Event creation result: {created}/{len(events)}")

                if created == len(events):
                    # 全件成功
                    await message.add_reaction("✅")
                    if created == 1:
                        await message.reply("予定をTimeTreeに登録しました！")
                    else:
                        await message.reply(f"{created}件の予定をTimeTreeに登録しました！")
                elif created > 0:
                    # 一部成功
                    await message.add_reaction("⚠️")
                    await message.reply(f"{created}件の予定を登録しましたが、{len(events) - created}件は失敗しました。")
                else:
                    # 全件失敗
                    await message.add_reaction("❌")
                    await message.reply("登録に失敗しました。時間を置いて再度お試しください。")

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                await message.add_reaction("⚠️")
                # 内部エラーの詳細はユーザーに表示しない
                await message.reply("エラーが発生しました。時間を置いて再度お試しください。")

    def _add_event_to_timetree(self, event: Event) -> bool:
        """TimeTreeに予定を追加（同期メソッド）"""
        automation = TimeTreeAutomation()
        return automation.run(event)


def main():
    """メイン処理"""
    # 設定検証
    config.validate()

    bot = TimeTreeBot()
    bot.run(config.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
