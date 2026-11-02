"""MG_WEIGHT2: дробные поля, которые округляют, а не отказывают.

У DRF `DecimalField` лишние знаки после запятой — ошибка ввода. Для денег это
правильно: там лишний знак означает, что отправитель и получатель считают
по-разному, и молча округлить значит соврать одному из них.

Для веса и прочих замеров это неверно. Человек переписывает число с весов как
есть, и «78.25» при поле в один знак превращается в отказ. Хуже того,
отвергается и «78.20», где ноль на конце не добавляет никакой точности, —
отказ выглядит придиркой на ровном месте.

Здесь лишние знаки округляются до разрешённых, а всё остальное проверяется
как обычно: число ли это, влезает ли в границы, не длиннее ли целая часть.
"""

from decimal import ROUND_HALF_UP, Decimal

from rest_framework import serializers


class RoundedDecimalField(serializers.DecimalField):
    """Как `DecimalField`, но лишние знаки округляет, а лишние нули не показывает."""

    def validate_precision(self, value):
        if self.decimal_places is not None and value.is_finite():
            # Decimal(1).scaleb(-2) — это Decimal('0.01'): шаг округления
            # считается из decimal_places, чтобы не задавать его дважды.
            step = Decimal(1).scaleb(-self.decimal_places)
            value = value.quantize(step, rounding=ROUND_HALF_UP)
        return super().validate_precision(value)

    def to_representation(self, value):
        """Наружу — без хвостовых нулей: «69.4», а не «69.40».

        База после расширения поля хранит numeric(5,2) и возвращает «69.40»,
        «78.00». Клиенты печатают это значение как есть, и человек, взвесившийся
        на 78 килограммов ровно, видел бы «78.00 кг». Два знака нужны тем, у
        кого весы их дают, а не всем подряд.
        """
        if value is None:
            return None
        d = Decimal(str(value)).normalize()
        # normalize() у круглых чисел даёт показательную форму: 100.00 → 1E+2.
        # Возвращаем её обратно к обычной записи.
        if d == d.to_integral_value():
            d = d.quantize(Decimal(1))
        return str(d)
