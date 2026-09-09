// MG_BODYCHART: показывать диаграмму или нет — выбор человека, и он помнится.
//
// Диаграммы веса и обхватов включаются по желанию: одному нужна динамика каждый
// день, другому — только сегодняшнее число, и спрашивать об этом при каждом
// заходе на страницу невежливо.
//
// Хранится в localStorage, потому что это настройка вида, а не данные: на
// другом устройстве человек включит её там, где ему нужно. Обращения обёрнуты в
// try/catch — в приватном окне и при запрете хранилища сам доступ бросает
// исключение, а падать из-за галочки «показать график» страница не должна.
import { useCallback, useState } from 'react';

const KEY = 'menugen.showChart.';

const read = (name: string): boolean => {
  try {
    return localStorage.getItem(KEY + name) === '1';
  } catch {
    return false;
  }
};

export const useShowChart = (name: string): [boolean, (v: boolean) => void] => {
  const [value, setValue] = useState(() => read(name));
  const set = useCallback(
    (v: boolean) => {
      setValue(v);
      try {
        localStorage.setItem(KEY + name, v ? '1' : '0');
      } catch {
        /* не критично: настройка просто не переживёт перезагрузку */
      }
    },
    [name],
  );
  return [value, set];
};
