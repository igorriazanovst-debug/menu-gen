"""MG_AIPING: отказ ИИ в списке покупок виден в логах.

Названия позиций чистит и склеивает ИИ. Ошибку каждой пачки здесь гасят
намеренно: список нужен пользователю и без ИИ — просто с сырыми названиями
из состава рецептов. Но гасили её ещё и молча, и ровно так недействительный
ключ провайдера прожил незамеченным, пока не полез мусор в каталоге продуктов.

Проверяем обе стороны: список собирается несмотря на отказ, и отказ попадает
в лог с причиной.
"""

from unittest.mock import patch

import pytest

from apps.shopping.services import ai_clean_item_names

ITEMS = [
    {"name": "лук репчатый", "quantity": 2, "unit": "шт"},
    {"name": "мука пшеничная", "quantity": 500, "unit": "г"},
]


@pytest.mark.django_db
class TestFailureVisible:
    def test_список_собирается_несмотря_на_отказ(self):
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = RuntimeError("HTTP 401")

            out = ai_clean_item_names([dict(i) for i in ITEMS])

        assert [i["name"] for i in out] == ["лук репчатый", "мука пшеничная"]

    def test_отказ_попадает_в_лог(self, caplog):
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = RuntimeError("HTTP 401")

            with caplog.at_level("WARNING", logger="apps.shopping.services"):
                ai_clean_item_names([dict(i) for i in ITEMS])

        assert any("HTTP 401" in r.getMessage() for r in caplog.records)
        assert any("mg_ai_ping" in r.getMessage() for r in caplog.records)

    def test_когда_ии_отвечает_лога_нет(self, caplog):
        answer = '[{"i": 0, "name": "Лук репчатый"}, {"i": 1, "name": "Мука пшеничная"}]'
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = answer

            with caplog.at_level("WARNING", logger="apps.shopping.services"):
                ai_clean_item_names([dict(i) for i in ITEMS])

        assert not [r for r in caplog.records if "mg_ai_ping" in r.getMessage()]
