from aiogram.utils.i18n import I18n, gettext, ngettext

i18n = I18n(
    path="locales",
    default_locale="ru",
    domain="messages",
)

_ = gettext
__all__ = ["_", "ngettext", "i18n"]
