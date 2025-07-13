from aiogram import Router, F
from aiogram.types import Message, InputMediaPhoto

test_router = Router()

@test_router.message(F.text == "/test_media")
async def send_album(message: Message):
    media = [
        InputMediaPhoto(media="https://picsum.photos/seed/1/400/300", caption="Фото 1"),
        InputMediaPhoto(media="https://picsum.photos/seed/2/400/300", caption="Фото 2"),
        InputMediaPhoto(media="https://picsum.photos/seed/3/400/300", caption="Фото 3"),
    ]
    await message.bot.send_media_group(chat_id=message.chat.id, media=media)
    await message.answer("Это media group (альбом)! Листай влево/вправо.")

# Не забудь включить этот роутер
