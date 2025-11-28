"""Клавиатуры, используемые в процессе оформления заказа."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from utils.i18n import _


def get_delivery_kb() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру выбора способа доставки."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("Курьер"), callback_data="delivery_courier")],
            [InlineKeyboardButton(text=_("Самовывоз"), callback_data="delivery_pickup")],
            [InlineKeyboardButton(text=_("⬅️ Назад в корзину"), callback_data="back_to_cart")],
        ]
    )


def get_confirm_kb() -> InlineKeyboardMarkup:
    """Клавиатура для финального подтверждения заказа."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("✅ Подтвердить заказ"), callback_data="confirm_order")],
            [InlineKeyboardButton(text=_("Назад"), callback_data="back_to_phone")],
        ]
    )


def geo_keyboard() -> ReplyKeyboardMarkup:
    """Reply-клавиатура для отправки геолокации."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_("📍 Отправить геолокацию"), request_location=True)],
            [KeyboardButton(text=_("⬅️ Назад"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def confirm_address_kb() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения распознанного адреса."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("✅ Да"), callback_data="address_ok")],
            [InlineKeyboardButton(text=_("✏️ Ввести вручную"), callback_data="address_manual")],
        ]
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    """Reply-клавиатура для запроса номера телефона."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=_("📞 Отправить номер телефона"),
                    request_contact=True,
                )
            ],
            [KeyboardButton(text=_("⬅️ Назад"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
