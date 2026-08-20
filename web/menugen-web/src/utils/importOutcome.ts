// FILL_FROM_MENU_V5: что показать после «Заполнить из меню».
//
// Импорт раскладывает дни меню по датам: блюдо из третьего дня ложится на
// «дату начала + 2». Страница же перескакивала на дату начала — и если человек
// выбрал блюда не первого дня, он попадал на пустой день и решал, что импорт не
// сработал. Ровно так это и выглядело на dev: 7 записей создано на 21-е, экран
// показывал 20-е.
//
// Второй источник немоты — идемпотентность: повторный импорт тех же приёмов
// ничего не создаёт и намеренно не двигает даты уже существующих записей.
// Молча закрытое окно в этом случае неотличимо от поломки.

export interface ImportedEntry {
  date: string;
}

export interface ImportResponse {
  created: number;
  skipped: number;
  entries: ImportedEntry[];
}

export interface ImportOutcome {
  /** Куда перевести дневник: дата самой ранней затронутой записи. */
  jumpDate: string | null;
  /** Что сказать человеку. Пусто — говорить нечего (ничего не выбрано). */
  message: string;
  /** Стоит ли оставить окно открытым: ничего не создано, нужно объяснение. */
  keepOpen: boolean;
}

const earliest = (entries: ImportedEntry[]): string | null => {
  const dates = entries.map((e) => e.date).filter(Boolean).sort();
  return dates.length ? dates[0] : null;
};

const ru = (iso: string): string => {
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString('ru', { day: 'numeric', month: 'long' });
};

export const importOutcome = (data: ImportResponse): ImportOutcome => {
  const jump = earliest(data.entries ?? []);
  const where = jump ? ` — записи с ${ru(jump)}` : '';

  if (data.created > 0) {
    return { jumpDate: jump, message: `Добавлено записей: ${data.created}${where}`, keepOpen: false };
  }
  if (data.skipped > 0) {
    return {
      jumpDate: jump,
      message: `Эти приёмы уже были добавлены раньше${where}. Повторный импорт их не переносит.`,
      keepOpen: true,
    };
  }
  return { jumpDate: null, message: '', keepOpen: true };
};
