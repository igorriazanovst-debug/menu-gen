"""MG_PROGRESS: строка хода долгой пачечной работы.

Команды печатали «пачка 7/24…» и всё. На четырёх пачках этого хватает, на
двадцати четырёх уже нет: непонятно, идёт работа или встала. А пересборка связей
идёт больше часа, и там вопрос «успею ли до вечернего часа пик» не праздный.

Время подаётся отдельным источником: иначе проверки пришлось бы писать через
ожидание, а это медленно и капризно.
"""

from apps.common.progress import BatchProgress, human_time


class FakeClock:
    """Часы, которые идут ровно настолько, насколько попросят."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, seconds):
        self.now += seconds


def collect():
    lines = []
    return lines, lines.append


class TestЧеловеческоеВремя:
    def test_секунды(self):
        assert human_time(0) == "0 с"
        assert human_time(45) == "45 с"

    def test_минуты_с_ведущим_нулём(self):
        assert human_time(185) == "3 мин 05 с"

    def test_часы(self):
        assert human_time(4320) == "1 ч 12 мин"

    def test_отрицательное_время_не_печатается_минусом(self):
        """Часы могут прыгнуть назад; строка хода от этого ломаться не должна."""
        assert human_time(-5) == "0 с"


class TestХод:
    def test_после_пачки_видно_сколько_разобрано_и_сколько_осталось(self):
        clock = FakeClock()
        lines, write = collect()
        p = BatchProgress(total_items=100, total_chunks=4, write=write, clock=clock)

        clock.tick(10)
        p.chunk_done(items=25)

        assert lines == ["  пачка 1/4 · разобрано 25 из 100 · прошло 10 с · осталось ~30 с"]

    def test_оценка_остатка_уточняется_по_ходу(self):
        clock = FakeClock()
        lines, write = collect()
        p = BatchProgress(total_items=100, total_chunks=4, write=write, clock=clock)

        clock.tick(10)
        p.chunk_done(items=25)
        clock.tick(30)  # вторая пачка оказалась втрое дольше
        p.chunk_done(items=25)

        assert "осталось ~40 с" in lines[1]

    def test_на_последней_пачке_остатка_нет(self):
        clock = FakeClock()
        lines, write = collect()
        p = BatchProgress(total_items=50, total_chunks=2, write=write, clock=clock)

        clock.tick(5)
        p.chunk_done(items=25)
        clock.tick(5)
        p.chunk_done(items=25)

        assert "осталось" not in lines[1]

    def test_потерянная_пачка_названа_и_в_разобранное_не_идёт(self):
        clock = FakeClock()
        lines, write = collect()
        p = BatchProgress(total_items=50, total_chunks=2, write=write, clock=clock)

        clock.tick(5)
        p.chunk_done(failed=True)

        assert "разобрано 0 из 50" in lines[0]
        assert "пачка потеряна" in lines[0]


class TestИтог:
    def test_итог_называет_время_и_разобранное(self):
        clock = FakeClock()
        lines, write = collect()
        p = BatchProgress(total_items=100, total_chunks=2, write=write, clock=clock)
        clock.tick(60)
        p.chunk_done(items=50)
        clock.tick(60)
        p.chunk_done(items=50)

        p.finish()

        assert lines[-1] == "Готово за 2 мин 00 с: разобрано 100 из 100"

    def test_потери_в_итоге_названы(self):
        """«разобрано 50 из 100» без числа потерь читается как «остальное не требовалось»."""
        clock = FakeClock()
        lines, write = collect()
        p = BatchProgress(total_items=100, total_chunks=2, write=write, clock=clock)
        p.chunk_done(items=50)
        p.chunk_done(failed=True)

        p.finish()

        assert "пачек потеряно 1" in lines[-1]
