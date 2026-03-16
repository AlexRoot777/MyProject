import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from dotenv import load_dotenv

from app.config import load_settings
from app.db import Database
from app.mtproto import MTProtoService


load_dotenv()
settings = load_settings()
db = Database(settings.database_path)
mtproto = MTProtoService(settings.proxy_host, settings.proxy_port, settings.proxy_gen_cmd)


async def _ensure_user(message: Message) -> tuple[int, bool]:
    user = message.from_user
    assert user is not None
    is_admin = user.id in settings.admin_ids
    db.upsert_user(user.id, user.username, is_admin)
    return user.id, is_admin


def _admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:list_users")],
            [InlineKeyboardButton(text="🧩 Выдать ключ себе", callback_data="admin:issue_self")],
        ]
    )


async def cmd_start(message: Message) -> None:
    user_id, is_admin = await _ensure_user(message)
    text = (
        "Привет! Я бот для продажи MTProto прокси.\n"
        "Команды:\n"
        "/get_proxy — получить ключ\n"
        "/myid — показать ваш Telegram ID"
    )
    if is_admin:
        text += "\n/admin — открыть админ-панель"
    await message.answer(text)


async def cmd_myid(message: Message) -> None:
    user_id, _ = await _ensure_user(message)
    await message.answer(f"Ваш ID: {user_id}")


async def cmd_get_proxy(message: Message) -> None:
    user_id, _ = await _ensure_user(message)
    if not db.is_active_user(user_id):
        await message.answer("Ваш доступ отключён. Обратитесь к администратору.")
        return

    secret, uri = mtproto.issue_key()
    db.create_proxy_key(user_id, secret, uri)
    await message.answer(
        "Ваш MTProto ключ:\n"
        f"`{secret}`\n\n"
        "Ссылка для подключения:\n"
        f"{uri}",
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def cmd_admin(message: Message) -> None:
    _, is_admin = await _ensure_user(message)
    if not is_admin:
        await message.answer("Недостаточно прав.")
        return
    await message.answer("Админ-панель", reply_markup=_admin_kb())


async def cmd_ban(message: Message) -> None:
    _, is_admin = await _ensure_user(message)
    if not is_admin:
        await message.answer("Недостаточно прав.")
        return

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /ban <user_id>")
        return

    ok = db.set_user_status(int(parts[1]), False)
    await message.answer("Пользователь отключён." if ok else "Пользователь не найден.")


async def cmd_unban(message: Message) -> None:
    _, is_admin = await _ensure_user(message)
    if not is_admin:
        await message.answer("Недостаточно прав.")
        return

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /unban <user_id>")
        return

    ok = db.set_user_status(int(parts[1]), True)
    await message.answer("Пользователь активирован." if ok else "Пользователь не найден.")


async def cmd_issue(message: Message) -> None:
    _, is_admin = await _ensure_user(message)
    if not is_admin:
        await message.answer("Недостаточно прав.")
        return

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /issue <user_id>")
        return

    target_user_id = int(parts[1])
    secret, uri = mtproto.issue_key()
    db.create_proxy_key(target_user_id, secret, uri)
    await message.answer(f"Ключ для {target_user_id}:\n`{secret}`\n{uri}", parse_mode="Markdown")


async def cb_admin(query: CallbackQuery) -> None:
    from_user = query.from_user
    if from_user.id not in settings.admin_ids:
        await query.answer("Недостаточно прав", show_alert=True)
        return

    action = query.data.split(":", 1)[1]
    if action == "list_users":
        users = db.list_users()
        if not users:
            text = "Пользователей пока нет."
        else:
            lines = [
                f"{u.user_id} (@{u.username or '-'}) | active={int(u.is_active)} | admin={int(u.is_admin)}"
                for u in users[:50]
            ]
            text = "\n".join(lines)
        await query.message.answer(text)
    elif action == "issue_self":
        secret, uri = mtproto.issue_key()
        db.create_proxy_key(from_user.id, secret, uri)
        await query.message.answer(f"Ваш ключ:\n`{secret}`\n{uri}", parse_mode="Markdown")

    await query.answer()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(settings.bot_token)
    dp = Dispatcher()

    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_myid, Command("myid"))
    dp.message.register(cmd_get_proxy, Command("get_proxy"))
    dp.message.register(cmd_admin, Command("admin"))
    dp.message.register(cmd_ban, Command("ban"))
    dp.message.register(cmd_unban, Command("unban"))
    dp.message.register(cmd_issue, Command("issue"))
    dp.callback_query.register(cb_admin, F.data.startswith("admin:"))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())