"""Маршрутизатор и публичный интерфейс сценариев оформления заказа."""

from aiogram import Router

from .courier_flow import (
    address_manual,
    address_ok,
    back_to_delivery_msg,
    choose_delivery_courier,
    receive_address_text,
    receive_apartment,
    receive_location,
    router as courier_router,
)
from .helpers import (
    back_to_cart,
    back_to_phone,
    confirm_order,
    enter_phone,
    get_map_link,
    is_back_button,
    phone_back,
    router as helpers_router,
)
from .keyboards import (
    confirm_address_kb,
    geo_keyboard,
    get_confirm_kb,
    get_delivery_kb,
    phone_keyboard,
)
from .pickup_flow import choose_delivery_pickup, router as pickup_router
from .start_order import router as start_router, start_order
from .states import OrderStates

order_router = Router(name="order")
order_router.include_router(start_router)
order_router.include_router(courier_router)
order_router.include_router(pickup_router)
order_router.include_router(helpers_router)

__all__ = [
    "OrderStates",
    "order_router",
    "start_order",
    "choose_delivery_courier",
    "receive_location",
    "back_to_delivery_msg",
    "receive_address_text",
    "address_ok",
    "receive_apartment",
    "address_manual",
    "choose_delivery_pickup",
    "phone_back",
    "enter_phone",
    "confirm_order",
    "back_to_cart",
    "back_to_phone",
    "is_back_button",
    "get_map_link",
    "confirm_address_kb",
    "geo_keyboard",
    "get_confirm_kb",
    "get_delivery_kb",
    "phone_keyboard",
]
