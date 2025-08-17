from types import SimpleNamespace
import sys
from pathlib import Path
from aiogram.utils.i18n import I18n

sys.path.append(str(Path(__file__).resolve().parents[1]))

from handlers.menu_processing import resolve_banner_description
from common.texts_for_db import get_default_banner_description
import common.texts_for_db as texts_for_db

# Initialize i18n context so gettext works without raising LookupError
i18n = I18n(path=Path(__file__).resolve().parents[1] / "locales", default_locale="ru")
i18n.ctx_locale.set("ru")
texts_for_db._ = lambda s: s


def test_default_used_when_banner_missing():
    assert (
        resolve_banner_description(None, "main")
        == get_default_banner_description("main")
    )


def test_default_used_when_description_none():
    banner = SimpleNamespace(description=None)
    assert (
        resolve_banner_description(banner, "main")
        == get_default_banner_description("main")
    )


def test_custom_description_has_priority():
    custom = "My banner"
    banner = SimpleNamespace(description=custom)
    assert resolve_banner_description(banner, "main") == custom
