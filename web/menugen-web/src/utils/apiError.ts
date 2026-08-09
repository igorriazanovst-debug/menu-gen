// MG_SHAREERR: человеческий текст ошибки из ответа DRF.
//
// DRF отвечает по-разному: `{"detail": "..."}` из вью и permissions,
// `{"email": ["..."]}` из сериализатора — но ValidationError с дословной
// строкой ({"email": "..."}) значение в список НЕ заворачивает. Код, читавший
// `data.email[0]`, на таком ответе показывал первую букву сообщения: вместо
// «Пользователь не найден.» пользователь видел «П».
//
// Здесь оба вида разбираются одинаково, а строка и список — равноправны.

/** Достаёт первое сообщение из значения поля: строка или список строк. */
const firstMessage = (value: unknown): string | null => {
  if (typeof value === 'string') return value.trim() || null;
  if (Array.isArray(value)) {
    for (const v of value) {
      const m = firstMessage(v);
      if (m) return m;
    }
  }
  return null;
};

/**
 * Текст ошибки из тела ответа. `fields` — поля, которые стоит посмотреть
 * раньше остальных (например email/phone в форме шаринга).
 */
export const apiErrorMessage = (error: unknown, fields: string[] = []): string | null => {
  const data = (error as { response?: { data?: unknown } } | undefined)?.response?.data;
  if (typeof data === 'string') return data.trim() || null;
  if (!data || typeof data !== 'object') return null;

  const body = data as Record<string, unknown>;
  for (const key of [...fields, 'detail', 'message', 'error', 'non_field_errors']) {
    const m = firstMessage(body[key]);
    if (m) return m;
  }
  // Любое другое поле с текстом — лучше, чем немое «Ошибка».
  for (const [key, value] of Object.entries(body)) {
    if (key === 'code' || key === 'error_code') continue;
    const m = firstMessage(value);
    if (m) return m;
  }
  return null;
};
