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


def get_pickup_time_kb() -> InlineKeyboardMarkup:
    """Клавиатура выбора времени самовывоза."""

    buttons = [
        ("10", "10"),
        ("20", "20"),
        ("30", "30"),
        ("45", "45"),
        ("1 час", "60"),
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_(f"{label} мин" if label.isdigit() else label),
                    callback_data=f"pickup_time:{value}",
                )
            ]
            for label, value in buttons
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
