// MG_MADEPHOTO: «Я приготовил — вот фото».
// Кнопка рядом с действиями карточки рецепта. Позволяет прикрепить фото
// приготовленного блюда с диска, камеры или из буфера обмена, показывает
// уже загруженные фото пользователя и даёт их удалить. Работает и из «Меню»,
// и из «Рецептов» (нужен только recipeId).
import React, { useEffect, useRef, useState } from 'react';
import { recipesApi, type MadePhoto } from '../../api/recipes';
import { getErrorMessage } from '../../utils/api';

function fileToDataUrl(file: File | Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result));
    fr.onerror = () => reject(fr.error);
    fr.readAsDataURL(file);
  });
}

// Сжатие в браузере, чтобы base64-payload был лёгким.
function loadCompressed(file: File | Blob, maxDim = 1600, quality = 0.82): Promise<string> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      let w = img.naturalWidth || img.width;
      let h = img.naturalHeight || img.height;
      if (!w || !h) { reject(new Error('bad image')); return; }
      const scale = Math.min(1, maxDim / Math.max(w, h));
      w = Math.round(w * scale); h = Math.round(h * scale);
      const canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      const ctx = canvas.getContext('2d');
      if (!ctx) { reject(new Error('no ctx')); return; }
      ctx.drawImage(img, 0, 0, w, h);
      try { resolve(canvas.toDataURL('image/jpeg', quality)); }
      catch (e) { reject(e as Error); }
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('img load failed')); };
    img.src = url;
  });
}

interface Props {
  recipeId: number;
  initialPhotos?: MadePhoto[];
  className?: string;
}

export const MadePhotoControl: React.FC<Props> = ({ recipeId, initialPhotos, className }) => {
  const [open, setOpen] = useState(false);
  const [photos, setPhotos] = useState<MadePhoto[]>(initialPhotos ?? []);
  const [loaded, setLoaded] = useState(!!initialPhotos);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const camRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open || loaded) return;
    let cancel = false;
    recipesApi.madePhotos(recipeId)
      .then(res => { if (!cancel) { setPhotos(res.data || []); setLoaded(true); } })
      .catch(() => { if (!cancel) setLoaded(true); });
    return () => { cancel = true; };
  }, [open, loaded, recipeId]);

  const upload = async (file: File | Blob) => {
    setBusy(true); setError('');
    try {
      let b64: string;
      try { b64 = await loadCompressed(file); }
      catch { b64 = await fileToDataUrl(file); }
      const res = await recipesApi.addMadePhoto(recipeId, b64);
      setPhotos(prev => [res.data, ...prev]);
    } catch (e) {
      setError(getErrorMessage(e) || 'Не удалось загрузить фото.');
    } finally {
      setBusy(false);
    }
  };

  const onPaste = async (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') === 0) {
        const f = items[i].getAsFile();
        if (f) { e.preventDefault(); await upload(f); return; }
      }
    }
  };

  const pasteFromClipboard = async () => {
    try {
      const anyNav = navigator as any;
      if (!anyNav.clipboard || !anyNav.clipboard.read) {
        setError('Браузер не поддерживает чтение буфера — нажмите Ctrl+V в области ниже.');
        return;
      }
      const clipItems = await anyNav.clipboard.read();
      for (const ci of clipItems) {
        const type = ci.types.find((t: string) => t.indexOf('image') === 0);
        if (type) { const blob = await ci.getType(type); await upload(blob); return; }
      }
      setError('В буфере нет изображения.');
    } catch {
      setError('Нет доступа к буферу. Нажмите Ctrl+V в области ниже.');
    }
  };

  const remove = async (photoId: number) => {
    setBusy(true); setError('');
    try {
      await recipesApi.deleteMadePhoto(recipeId, photoId);
      setPhotos(prev => prev.filter(p => p.id !== photoId));
    } catch (e) {
      setError(getErrorMessage(e) || 'Не удалось удалить.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="Я приготовил это блюдо — прикрепить фото"
        className={`px-3 py-1 rounded-lg bg-tomato/10 text-tomato text-sm font-medium hover:bg-tomato/20 transition ${className ?? ''}`}
      >
        📷 Я приготовил{photos.length > 0 ? ` · ${photos.length}` : ''}
      </button>

      {open && (
        <div className="fixed inset-0 bg-black/50 z-[70] flex items-center justify-center p-4"
             onClick={() => setOpen(false)}>
          <div className="bg-surface rounded-2xl max-w-lg w-full max-h-[85vh] overflow-y-auto p-5"
               onClick={e => e.stopPropagation()} onPaste={onPaste}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-bold text-chocolate">Фото приготовления</h3>
              <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
            </div>

            <p className="text-sm text-gray-500 mb-3">
              Прикрепите фото готового блюда — с диска, камеры или из буфера обмена.
            </p>

            <div className="flex flex-wrap gap-2 mb-3">
              <button type="button" disabled={busy} onClick={() => fileRef.current?.click()}
                className="px-3 py-1.5 rounded-lg border text-sm hover:bg-gray-50 disabled:opacity-50">
                📁 Файл
              </button>
              <button type="button" disabled={busy} onClick={() => camRef.current?.click()}
                className="px-3 py-1.5 rounded-lg border text-sm hover:bg-gray-50 disabled:opacity-50">
                📷 Камера
              </button>
              <button type="button" disabled={busy} onClick={pasteFromClipboard}
                className="px-3 py-1.5 rounded-lg border text-sm hover:bg-gray-50 disabled:opacity-50">
                📋 Из буфера
              </button>
              {busy && <span className="text-sm text-gray-400 self-center">Загрузка…</span>}
            </div>

            <input ref={fileRef} type="file" accept="image/*" className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ''; }} />
            <input ref={camRef} type="file" accept="image/*" capture="environment" className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ''; }} />

            {error && <p className="text-sm text-red-600 mb-2">{error}</p>}

            <div
              tabIndex={0}
              className="mb-3 rounded-lg border border-dashed border-gray-300 p-3 text-center text-xs text-gray-400 focus:outline-none focus:border-tomato"
            >
              Сюда можно вставить фото из буфера: Ctrl+V
            </div>

            {photos.length === 0 ? (
              <p className="text-sm text-gray-400">Пока нет фото.</p>
            ) : (
              <div className="grid grid-cols-3 gap-2">
                {photos.map(p => (
                  <div key={p.id} className="relative group">
                    <img src={p.image_url} alt="Приготовленное блюдо"
                      className="w-full h-24 object-cover rounded-lg bg-gray-50" />
                    <button type="button" onClick={() => remove(p.id)} disabled={busy}
                      title="Удалить"
                      className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/60 text-white text-xs flex items-center justify-center opacity-80 hover:opacity-100">
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};
