// MG_SKIN: переключатель скина оформления. Меняет скин локально и синкает в аккаунт.
import React from 'react';
import { useAppSelector, useAppDispatch } from '../../hooks/useAppDispatch';
import { changeSkin } from '../../store/slices/uiSlice';
import { SKINS, SKIN_LABELS, Skin } from '../../theme/skins';

// Превью-палитра для каждого скина (соответствует CSS-переменным в index.css).
const SKIN_SWATCHES: Record<Skin, string[]> = {
  main:   ['#7CB342', '#588157', '#F4A261'],
  second: ['#1B4332', '#E8A8B8', '#C6E69B'],
};

export const SkinSwitcher: React.FC = () => {
  const dispatch = useAppDispatch();
  const current = useAppSelector((s) => s.ui.skin);

  return (
    <div className="grid grid-cols-2 gap-2">
      {SKINS.map((skin) => {
        const active = current === skin;
        return (
          <button
            type="button"
            key={skin}
            onClick={() => { if (!active) dispatch(changeSkin(skin)); }}
            className={
              'p-3 rounded-xl border text-left transition ' +
              (active
                ? 'border-primary bg-primary/10 text-text'
                : 'border-border bg-surface hover:border-primary/50 text-muted')
            }
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold">{SKIN_LABELS[skin]}</span>
              {active && <span className="text-xs text-primary font-medium">✓ выбран</span>}
            </div>
            <div className="flex gap-1.5 mt-2">
              {SKIN_SWATCHES[skin].map((c) => (
                <span
                  key={c}
                  className="w-5 h-5 rounded-full border border-black/5"
                  style={{ backgroundColor: c }}
                />
              ))}
            </div>
          </button>
        );
      })}
    </div>
  );
};
