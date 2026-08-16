// MG_SHAREERR: человеческий текст ошибки из ответа DRF.
import { apiErrorMessage } from './apiError';

const err = (data: unknown) => ({ response: { data } });

describe('apiErrorMessage', () => {
  it('detail — самый частый вид', () => {
    expect(apiErrorMessage(err({ detail: 'Тариф не найден.' }))).toBe('Тариф не найден.');
  });

  it('поле со списком', () => {
    expect(apiErrorMessage(err({ offer_code: ['Период не найден.'] }))).toBe('Период не найден.');
  });

  it('поле со строкой не режется до первой буквы', () => {
    // Ровно тот баг, ради которого модуль появился: пользователь видел «П».
    expect(apiErrorMessage(err({ email: 'Пользователь не найден.' }))).toBe('Пользователь не найден.');
  });

  it('приоритетные поля идут первыми', () => {
    expect(apiErrorMessage(err({ detail: 'общее', email: 'про почту' }), ['email'])).toBe('про почту');
  });

  it('HTML-страница ошибки сообщением не считается', () => {
    // Иначе в интерфейс уезжает разметка, а через Object.values — один символ «<».
    expect(apiErrorMessage(err('<!doctype html><html><body>Server Error (500)</body></html>'))).toBeNull();
    expect(apiErrorMessage(err('<html>\n<head><title>502</title></head>\n</html>'))).toBeNull();
  });

  it('обычная строка сообщением считается', () => {
    expect(apiErrorMessage(err('Слишком много попыток.'))).toBe('Слишком много попыток.');
  });

  it('пусто — пусть вызывающий подставит своё', () => {
    expect(apiErrorMessage(err({}))).toBeNull();
    expect(apiErrorMessage(err(''))).toBeNull();
    expect(apiErrorMessage(undefined)).toBeNull();
  });

  it('служебный код за сообщение не выдаём', () => {
    expect(apiErrorMessage(err({ code: 'premium_required' }))).toBeNull();
  });
});
