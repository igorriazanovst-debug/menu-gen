// MG_SHOPNOTE / MG_SHOPIMG — редактор комментария и изображения товара.
// Изображение можно задать: ссылкой (URL), вставкой из буфера обмена или
// загрузкой файла/камерой. Всё уходит одним PATCH (note / image_url / image_b64).
import React, { useRef, useState } from 'react';
import { shoppingApi } from '../../api/shopping';
import { Button } from '../ui/Button';
import { getErrorMessage } from '../../utils/api';
import type { ShoppingV2Item } from '../../types';

interface Props {
  listId: number;
  item: ShoppingV2Item;
  onClose: () => void;
  onSaved: () => void; // родитель перезагружает список
}

type ImageMode = 'keep' | 'file' | 'url' | 'clear';

function fileToDataUrl(file: File | Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result));
    fr.onerror = () => reject(fr.error);
    fr.readAsDataURL(file);
  });
}

export const ShoppingItemEditor: React.FC<Props> = ({ listId, item, onClose, onSaved }) => {
  const [note, setNote] = useState(item.note ?? '');
  const [urlInput, setUrlInput] = useState(item.image_url ?? '');
  const [mode, setMode] = useState<ImageMode>('keep');
  // Что показываем в превью: свежий data-URL, введённый URL, либо текущее изображение.
  const [preview, setPreview] = useState<string | null>(item.image ?? null);
  const [b64, setB64] = useState<string>(''); // data-URL для file/paste
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const pickFile = async (file: File) => {
    try {
      const dataUrl = await fileToDataUrl(file);
      setB64(dataUrl);
      setPreview(dataUrl);
      setMode('file');
      setError('');
    } catch {
      setError('Не удалось прочитать файл.');
    }
  };

  const onPaste = async (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') === 0) {
        const f = items[i].getAsFile();
        if (f) {
          e.preventDefault();
          await pickFile(f);
          return;
        }
      }
    }
  };

  const pasteFromClipboard = async () => {
    try {
      // navigator.clipboard.read — поддерживается не всеми браузерами.
      const anyNav = navigator as any;
      if (!anyNav.clipboard || !anyNav.clipboard.read) {
        setError('Браузер не поддерживает чтение буфера — используйте Ctrl+V в поле ниже.');
        return;
      }
      const clipItems = await anyNav.clipboard.read();
      for (const ci of clipItems) {
        const type = ci.types.find((t: string) => t.indexOf('image') === 0);
        if (type) {
          const blob = await ci.getType(type);
          await pickFile(blob);
          return;
        }
      }
      setError('В буфере нет изображения.');
    } catch {
      setError('Не удалось прочитать буфер обмена (нет доступа). Попробуйте Ctrl+V в поле ниже.');
    }
  };

  const applyUrl = () => {
    const u = urlInput.trim();
    if (!u) return;
    setPreview(u);
    setB64('');
    setMode('url');
  };

  const removeImage = () => {
    setPreview(null);
    setB64('');
    setUrlInput('');
    setMode('clear');
  };

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      const payload: Partial<ShoppingV2Item> & { image_b64?: string } = { note };
      if (mode === 'file') {
        payload.image_b64 = b64; // backend декодирует и сохранит файл
      } else if (mode === 'url') {
        payload.image_url = urlInput.trim();
        payload.image_b64 = ''; // сбросить возможный загруженный файл, чтобы показывался URL
      } else if (mode === 'clear') {
        payload.image_url = '';
        payload.image_b64 = '';
      }
      await shoppingApi.updateItem(listId, item.id, payload);
      onSaved();
      onClose();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-surface rounded-2xl w-full max-w-md max-h-[90vh] overflow-auto p-5"
        onClick={(e) => e.stopPropagation()}
        onPaste={onPaste}
      >
        <div className="flex items-start justify-between mb-3">
          <h3 className="text-lg font-bold text-chocolate">{item.name}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>

        {/* Комментарий */}
        <label className="block text-sm font-medium text-chocolate mb-1">Комментарий</label>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          placeholder="Напр. взять посвежее, конкретный бренд…"
          className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-tomato/40 focus:border-tomato mb-4"
        />

        {/* Изображение */}
        <label className="block text-sm font-medium text-chocolate mb-1">Изображение</label>
        {preview ? (
          <div className="mb-2 relative">
            <img
              src={preview}
              alt=""
              className="w-full max-h-48 object-contain rounded-xl border border-gray-200 bg-gray-50"
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.opacity = '0.3'; }}
            />
            <button
              type="button"
              onClick={removeImage}
              className="absolute top-1 right-1 bg-white/90 rounded-full w-7 h-7 text-red-500 hover:text-red-700 shadow"
              title="Убрать изображение"
            >
              ✕
            </button>
          </div>
        ) : (
          <p className="text-xs text-gray-400 mb-2">Изображение не задано.</p>
        )}

        <div className="flex flex-wrap gap-2 mb-2">
          <Button type="button" variant="secondary" onClick={() => fileRef.current?.click()}>
            📷 Камера / файл
          </Button>
          <Button type="button" variant="secondary" onClick={pasteFromClipboard}>
            📋 Из буфера
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) pickFile(f);
              e.currentTarget.value = '';
            }}
          />
        </div>

        <div className="flex gap-2 mb-1">
          <input
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="Ссылка на изображение (https://…)"
            className="flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-tomato/40 focus:border-tomato"
          />
          <Button type="button" variant="secondary" onClick={applyUrl} disabled={!urlInput.trim()}>
            Применить
          </Button>
        </div>
        <p className="text-xs text-gray-400 mb-4">
          Или вставьте картинку из буфера сюда: кликните в окно и нажмите Ctrl+V.
        </p>

        {error && <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={saving}>Отмена</Button>
          <Button onClick={save} loading={saving}>Сохранить</Button>
        </div>
      </div>
    </div>
  );
};
