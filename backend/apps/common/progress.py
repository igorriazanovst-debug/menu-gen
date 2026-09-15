"""MG_PROGRESS: показывать ход долгой пачечной работы.

Команды, которые ходят в модель пачками, печатали «пачка 7/24…» — и это всё.
На четырёх пачках такого хватает, на двадцати четырёх уже нет: непонятно, идёт
работа или встала, и сколько ещё ждать. А пересборка связей на проде идёт
больше часа, и там вопрос «успею ли до вечернего часа пик» — не праздный.

Указатель намеренно считает по факту, а не по плану: остаток берётся из
среднего времени уже прошедших пачек. Первая оценка появляется только после
первой пачки — раньше её взять неоткуда, и показывать «осталось ~0 с» было бы
хуже, чем не показывать ничего.

Строка выглядит так:

    пачка 7/24 · разобрано 150 из 598 · прошло 1 мин 12 с · осталось ~2 мин 55 с

Потерянные пачки считаются отдельно и в конце названы: «разобрано» без этого
числа читается как «всё остальное и не требовалось».
"""

import time


def human_time(seconds):
    """Секунды словами: «45 с», «3 мин 05 с», «1 ч 12 мин»."""
    seconds = int(max(0, seconds))
    if seconds < 60:
        return "%d с" % seconds
    if seconds < 3600:
        return "%d мин %02d с" % (seconds // 60, seconds % 60)
    return "%d ч %02d мин" % (seconds // 3600, (seconds % 3600) // 60)


class BatchProgress:
    """Ход пачечной работы: строка после каждой пачки и итог в конце.

    `write` — куда печатать (обычно self.stdout.write команды). `clock` —
    источник времени, отдельным параметром ради проверок: иначе их пришлось бы
    писать через ожидание, а это медленно и капризно.
    """

    def __init__(self, total_items, total_chunks, write, clock=time.monotonic):
        self.total_items = total_items
        self.total_chunks = total_chunks
        self.write = write
        self.clock = clock
        self.started = clock()
        self.done_chunks = 0
        self.done_items = 0
        self.failed_chunks = 0

    def chunk_done(self, items=0, failed=False):
        """Отметить пройденную пачку и напечатать строку хода."""
        self.done_chunks += 1
        if failed:
            self.failed_chunks += 1
        else:
            self.done_items += items

        elapsed = self.clock() - self.started
        parts = [
            "  пачка %d/%d" % (self.done_chunks, self.total_chunks),
            "разобрано %d из %d" % (self.done_items, self.total_items),
            "прошло %s" % human_time(elapsed),
        ]
        # Остаток оцениваем по среднему времени пройденных пачек. На нулевой
        # пачке среднего ещё нет, и выдумывать его незачем.
        if self.done_chunks and self.done_chunks < self.total_chunks:
            per_chunk = elapsed / self.done_chunks
            parts.append("осталось ~%s" % human_time(per_chunk * (self.total_chunks - self.done_chunks)))
        if failed:
            parts.append("пачка потеряна")
        self.write(" · ".join(parts))

    def finish(self):
        """Итоговая строка. Возвращает потраченное время в секундах."""
        elapsed = self.clock() - self.started
        line = "Готово за %s: разобрано %d из %d" % (human_time(elapsed), self.done_items, self.total_items)
        if self.failed_chunks:
            line += ", пачек потеряно %d" % self.failed_chunks
        self.write(line)
        return elapsed
