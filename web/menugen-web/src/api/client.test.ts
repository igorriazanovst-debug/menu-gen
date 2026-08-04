// MG_TOKENFIX: обновление токенов при 401.
//
// Бэкенд ротирует refresh-токены и заносит использованный в чёрный список.
// Если клиент не сохранит новый refresh, второй цикл обновления уйдёт со старым
// токеном и завершится разлогином — примерно через полчаса работы.
// Файл не импортирует ничего (axios подменяется ручным моком, клиент грузится
// через require), поэтому нужен пустой экспорт: иначе TypeScript считает его
// глобальным скриптом и сборка падает на --isolatedModules.
export {};

jest.mock('axios');

/** Перехватчик ошибок ответа, зарегистрированный клиентом. */
type ErrorHandler = (error: unknown) => Promise<unknown>;

let onError: ErrorHandler;
let requestHandler: (config: any) => any;
let axiosMock: any;

const interceptors = {
  request: { use: (fn: any) => { requestHandler = fn; } },
  response: { use: (_ok: any, fail: ErrorHandler) => { onError = fail; } },
};

function makeError(status: number) {
  return {
    response: { status },
    config: { headers: {} as Record<string, string>, url: '/menu/' },
  };
}

describe('client: обновление токенов', () => {
  beforeEach(() => {
    // Сброс реестра модулей поднимает и мок axios заново, поэтому его экземпляр
    // берём уже после сброса — иначе настраивали бы не тот объект.
    jest.resetModules();
    localStorage.clear();
    localStorage.setItem('access_token', 'A0');
    localStorage.setItem('refresh_token', 'R0');

    // eslint-disable-next-line @typescript-eslint/no-require-imports
    axiosMock = require('axios').default;
    axiosMock.create.mockImplementation(() => {
      // инстанс вызывается для повтора исходного запроса
      const callable: any = jest.fn(async (cfg: any) => ({ retried: cfg }));
      callable.interceptors = interceptors;
      return callable;
    });

    // eslint-disable-next-line @typescript-eslint/no-require-imports
    require('./client');
  });

  it('подставляет access-токен в запрос', () => {
    const config = requestHandler({ headers: {} as Record<string, string> });

    expect(config.headers.Authorization).toBe('Bearer A0');
  });

  it('сохраняет новый refresh-токен, выданный при ротации', async () => {
    axiosMock.post.mockResolvedValueOnce({ data: { access: 'A1', refresh: 'R1' } });

    await onError(makeError(401));

    expect(localStorage.getItem('access_token')).toBe('A1');
    expect(localStorage.getItem('refresh_token')).toBe('R1');
  });

  it('второе обновление уходит с новым токеном, а не со старым', async () => {
    axiosMock.post
      .mockResolvedValueOnce({ data: { access: 'A1', refresh: 'R1' } })
      .mockResolvedValueOnce({ data: { access: 'A2', refresh: 'R2' } });

    await onError(makeError(401));
    await onError(makeError(401));

    const secondCall = axiosMock.post.mock.calls[1];
    expect(secondCall[1]).toEqual({ refresh: 'R1' });
    expect(localStorage.getItem('refresh_token')).toBe('R2');
  });

  it('ответ без refresh не затирает сохранённый токен', async () => {
    axiosMock.post.mockResolvedValueOnce({ data: { access: 'A1' } });

    await onError(makeError(401));

    expect(localStorage.getItem('refresh_token')).toBe('R0');
  });

  it('отказ в обновлении очищает хранилище', async () => {
    axiosMock.post.mockRejectedValueOnce(new Error('401'));

    await expect(onError(makeError(401))).rejects.toBeTruthy();

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
  });

  it('не-401 проходит мимо обновления', async () => {
    await expect(onError(makeError(500))).rejects.toBeTruthy();

    expect(axiosMock.post).not.toHaveBeenCalled();
    expect(localStorage.getItem('refresh_token')).toBe('R0');
  });
});
