"""Lightweight Telegram gateway adapter (nanobot-inspired, gated by config.telegram_enabled)."""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

log = logging.getLogger(__name__)

MessageProcessor = Callable[[str, int], Awaitable[str]]


class TelegramGateway:
    """Bridges Telegram messages to a Metis message processor when enabled."""

    def __init__(
        self,
        enabled: bool = False,
        token: str | None = None,
        allowed_user_ids: set[int] | None = None,
        processor: MessageProcessor | None = None,
    ) -> None:
        self.enabled = enabled
        self.token = token or os.environ.get("METIS_TELEGRAM_TOKEN")
        self.allowed_user_ids = allowed_user_ids or set()
        self._processor = processor
        self._app: Application | None = None

    def is_authorized(self, user_id: int | None) -> bool:
        """Allow all users when allowlist is empty, otherwise enforce allowlist."""
        if not self.allowed_user_ids:
            return True
        return user_id in self.allowed_user_ids

    def build_application(self) -> Application | None:
        """Construct python-telegram-bot Application if enabled and token is set."""
        if not self.enabled or not self.token:
            return None

        app = Application.builder().token(self.token).build()

        async def _start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
            if update.effective_message:
                await update.effective_message.reply_text("Metis gateway ready.")

        async def _handle_text(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
            msg = update.effective_message
            user = update.effective_user
            if not msg or not msg.text:
                return
            user_id = user.id if user else 0
            if not self.is_authorized(user_id):
                await msg.reply_text("Unauthorized user.")
                return
            if self._processor is None:
                await msg.reply_text("No processor configured.")
                return
            reply = await self._processor(msg.text, user_id)
            await msg.reply_text(reply)

        app.add_handler(CommandHandler("start", _start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text))
        self._app = app
        return app
