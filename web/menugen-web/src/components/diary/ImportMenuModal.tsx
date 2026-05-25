// DIARY_V2
import React, { useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { diaryApi } from '../../api/diary';
import { getErrorMessage } from '../../utils/api';

interface Props {
  date: string;
  memberId?: number;
  onClose: () => void;
  onImported: () => void;
}

export const ImportMenuModal: React.FC<Props> = ({ date, memberId, onClose, onImported }) => {
  const [menuId, setMenuId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const run = async () => {
    const id = parseInt(menuId, 10);
    if (!Number.isFinite(id)) { setError('Укажите ID меню'); return; }
    setBusy(true); setError('');
    try {
      await diaryApi.importFromMenu(id, date, memberId);
      onImported();
      onClose();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
         onClick={onClose}>
      <Card className="w-full max-w-sm p-6"
            onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-chocolate mb-2">Импорт из меню</h2>
        <p className="text-xs text-gray-500 mb-4">На дату: {date}</p>
        <label className="block text-xs text-gray-500 mb-1">ID меню</label>
        <Input type="number" value={menuId} onChange={(e) => setMenuId(e.target.value)}
               placeholder="Например, 42" className="mb-4" />
        {error && <p className="text-red-600 text-sm mb-3">{error}</p>}
        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose} disabled={busy}>Отмена</Button>
          <Button onClick={run} disabled={busy}>{busy ? 'Импорт…' : 'Импортировать'}</Button>
        </div>
      </Card>
    </div>
  );
};
