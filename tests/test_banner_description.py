from types import SimpleNamespace
import sys
from pathlib import Path
from aiogram.utils.i18n import I18n

sys.path.append(str(Path(__file__).resolve().parents[1]))

from handlers.menu_processing import resolve_banner_description
from common.texts_for_db import get_default_banner_description
import common.texts_for_db as texts_for_db

# Use real gettext for translations in tests
i18n = I18n(path=Path(__file__).resolve().parents[1] / "locales", default_locale="ru")
texts_for_db._ = i18n.gettext


def test_default_used_when_banner_missing():
    i18n.ctx_locale.set("ru")
    assert resolve_banner_description(None, "main") == get_default_banner_description("main")


def test_default_used_when_description_none():
    i18n.ctx_locale.set("ru")
    banner = SimpleNamespace(description=None)
    assert resolve_banner_description(banner, "main") == get_default_banner_description("main")


def test_custom_description_has_priority():
    i18n.ctx_locale.set("ru")
    custom = "My banner"
    banner = SimpleNamespace(description=custom)
    assert resolve_banner_description(banner, "main") == custom


def test_get_default_banner_description_translated():
    i18n.ctx_locale.set("en")
    assert get_default_banner_description("main") == "Welcome!"
    i18n.ctx_locale.set("ru")
    assert get_default_banner_description("main") == "Добро пожаловать!"