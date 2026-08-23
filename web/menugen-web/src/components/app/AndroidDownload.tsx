// MG_APKSITE: ссылка на приложение для Android прямо со страницы входа.
//
// Модерация в RuStore идёт долго, а исправление иногда нужно людям сегодня.
// Файл на сайте — тот же самый, что уходит в магазин: пересобранный с другим
// ключом Android не поставит поверх уже установленного, и человек упрётся в
// невнятную ошибку вместо обновления.
//
// Пока выкладывать нечего — блок не показывается вовсе: пустая рамка со
// словами «скоро будет» хуже, чем её отсутствие.
import React, { useEffect, useState } from 'react';
import { appApi } from '../../api/app';
import type { AndroidBuild } from '../../types';

export const formatSize = (bytes?: number | null): string => {
  const mb = (bytes ?? 0) / (1024 * 1024);
  return mb >= 1 ? `${mb.toFixed(0)} МБ` : '';
};

export const AndroidDownload: React.FC = () => {
  const [build, setBuild] = useState<AndroidBuild | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await appApi.androidBuild();
        if (!cancelled) setBuild(data.build ?? null);
      } catch {
        /* нет ответа — просто не показываем блок */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!build?.url) return null;

  const size = formatSize(build.size_bytes);

  return (
    <div className="mt-6 pt-5 border-t border-border text-center">
      <a
        href={build.url}
        className="inline-block rounded-xl bg-chocolate text-white px-4 py-2 text-sm font-medium hover:opacity-90"
      >
        📱 Скачать приложение для Android
      </a>
      <p className="text-xs text-gray-500 mt-2">
        Версия {build.version_name}
        {size && ` · ${size}`} · установка из файла
      </p>
      {build.notes && <p className="text-xs text-gray-500 mt-1">{build.notes}</p>}
      <p className="text-xs text-gray-400 mt-2">
        Та же подписанная сборка, что и в магазине, — обновление поверх встанет.
        Android спросит разрешение на установку из этого источника.
      </p>
    </div>
  );
};
