from __future__ import annotations

import pytest

from auto_card.i18n import set_language


@pytest.fixture(autouse=True)
def reset_language() -> None:
    set_language("en")
