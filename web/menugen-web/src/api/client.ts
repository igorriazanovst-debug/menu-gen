import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';

// Дефолт — относительный same-origin путь: фронт и API на одном домене
// (menugen.ru). Для локальной разработки переопределяется через .env
// (REACT_APP_API_BASE_URL=http://localhost:8000/api/v1).
const BASE_URL = process.env.REACT_APP_API_BASE_URL || '/api/v1';

const client: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
});

// MG_LOGINFIX: публичные эндпоинты авторизации — им нельзя слать Authorization.
//
// DRF проверяет токен раньше permission_classes: протухший Bearer из
// localStorage даёт 401 ещё до того, как вью посмотрит на логин и пароль. Выход
// (/auth/logout/) в список не входит — ему токен как раз нужен.
const PUBLIC_AUTH_PATHS = [
  '/auth/login/',
  '/auth/refresh/',
  '/auth/register/',
  '/auth/email/register/',
  '/auth/email/verify/',
  '/auth/email/resend/',
];

export const isPublicAuthPath = (url?: string): boolean => {
  if (!url) return false;
  const path = url.startsWith(BASE_URL) ? url.slice(BASE_URL.length) : url;
  return PUBLIC_AUTH_PATHS.includes(path) || path.startsWith('/auth/phone/');
};

// ── Request interceptor: attach JWT ─────────────────────────────────────────
client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (isPublicAuthPath(config.url)) {
    if (config.headers) delete config.headers.Authorization;
    return config;
  }
  const token = localStorage.getItem('access_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Response interceptor: auto-refresh on 401 ───────────────────────────────
let isRefreshing = false;
let queue: Array<{ resolve: (t: string) => void; reject: (e: unknown) => void }> = [];

const processQueue = (error: unknown, token: string | null) => {
  queue.forEach(({ resolve, reject }) => (error ? reject(error) : resolve(token!)));
  queue = [];
};

client.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    // MG_LOGINFIX: 401 от самого входа — это ответ по существу, обновлять
    // нечего; иначе неудачная попытка входа вычищала бы localStorage.
    if (error.response?.status === 401 && !original._retry && !isPublicAuthPath(original?.url)) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          queue.push({ resolve, reject });
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`;
          return client(original);
        });
      }
      original._retry = true;
      isRefreshing = true;
      const refresh = localStorage.getItem('refresh_token');
      if (!refresh) {
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(error);
      }
      try {
        const { data } = await axios.post(`${BASE_URL}/auth/refresh/`, { refresh });
        localStorage.setItem('access_token', data.access);
        // MG_TOKENFIX: бэкенд ротирует refresh-токены (ROTATE_REFRESH_TOKENS +
        // BLACKLIST_AFTER_ROTATION): при обновлении выдаётся новый refresh, а
        // старый заносится в чёрный список. Если новый не сохранить, второе
        // обновление уйдёт со старым токеном, получит 401 — и пользователя
        // выкидывало на вход примерно через полчаса (два цикла по 15 минут).
        if (data.refresh) {
          localStorage.setItem('refresh_token', data.refresh);
        }
        processQueue(null, data.access);
        original.headers.Authorization = `Bearer ${data.access}`;
        return client(original);
      } catch (e) {
        processQueue(e, null);
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(e);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  },
);

export default client;
