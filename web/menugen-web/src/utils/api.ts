import type { AxiosError } from 'axios';

export function getErrorMessage(e: unknown): string {
  const err = e as AxiosError<{ detail?: string; [key: string]: unknown }>;
  if (err.response?.data?.detail) return err.response.data.detail;
  if (err.response?.data) {
    const vals = Object.values(err.response.data);
    if (vals.length) return String(vals[0]);
  }
  return 'Произошла ошибка. Попробуйте снова.';
}

export function formatDate(iso: string, locale = 'ru-RU'): string {
  return new Date(iso).toLocaleDateString(locale, {
    weekday: 'long', day: 'numeric', month: 'long',
  });
}

export function formatShortDate(iso: string, locale = 'ru-RU'): string {
  return new Date(iso).toLocaleDateString(locale, { day: 'numeric', month: 'short' });
}
