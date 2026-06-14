// MG_T08: global sync-status indicator (green/amber/red).
import React, { useEffect, useState } from 'react';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';
import {
  pendingCount,
  flushQueue,
  SYNC_CHANGED_EVENT,
  SYNC_FLUSHED_EVENT,
} from '../../utils/syncQueue';

export const SyncIndicator: React.FC = () => {
  const online = useOnlineStatus();
  const [pending, setPending] = useState<number>(pendingCount());

  useEffect(() => {
    const refresh = () => setPending(pendingCount());
    window.addEventListener(SYNC_CHANGED_EVENT, refresh);
    window.addEventListener(SYNC_FLUSHED_EVENT, refresh);
    return () => {
      window.removeEventListener(SYNC_CHANGED_EVENT, refresh);
      window.removeEventListener(SYNC_FLUSHED_EVENT, refresh);
    };
  }, []);

  // Push the queue whenever we (re)gain connectivity.
  useEffect(() => {
    if (online) void flushQueue();
  }, [online]);

  let color = '#22c55e';
  let label = 'В сети';
  let title = 'Все изменения синхронизированы';
  if (!online) {
    color = '#ef4444';
    label = 'Нет сети';
    title = 'Нет подключения — изменения сохранены локально';
  } else if (pending > 0) {
    color = '#f59e0b';
    label = 'Синхронизация…';
    title = `Не отправлено изменений: ${pending}`;
  }

  return (
    <div className="flex items-center gap-1.5 text-xs text-gray-500" title={title}>
      <span
        style={{ width: 8, height: 8, borderRadius: 9999, background: color, display: 'inline-block' }}
      />
      <span>{label}</span>
    </div>
  );
};
