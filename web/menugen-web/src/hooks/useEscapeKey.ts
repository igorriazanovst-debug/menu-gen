import { useEffect } from 'react';

// MG_ESC: закрытие модалок по нажатию Escape.
// Вешаем слушатель на window, снимаем при размонтировании.
export function useEscapeKey(onEscape: () => void): void {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onEscape();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onEscape]);
}
