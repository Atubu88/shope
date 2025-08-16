from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat


# Команды для обычных пользователей
user_commands = [
    BotCommand(command="start", description="Запустить бота"),
    BotCommand(command="language", description="Выбор языка"),
]


# Команды для администраторов
admin_commands = user_commands + [
    BotCommand(command="admin", description="Админ-панель"),
    BotCommand(command="orders", description="Текущие заказы"),
]


async def set_commands(bot: Bot, user_id: int, is_admin: bool) -> None:
    """Устанавливает список команд для конкретного пользователя."""
    commands = admin_commands if is_admin else user_commands
    await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=user_id))
