// MG_PHONECODE: поле телефона с выбором кода страны.
//
// Было: одно текстовое поле с подсказкой «+7 900 000-00-00». Подсказка серая,
// исчезает от первой буквы, и человек с российским номером всё равно каждый раз
// набирал код страны сам — а половина набирала «8», потому что так привычнее.
//
// Стало: код страны выбирается списком (по умолчанию +7), в поле остаётся
// только сам номер. Наружу отдаётся склеенная строка «+7 9001234567».
//
// Список стран короткий и осознанный: Россия и соседи, откуда к нам реально
// могут прийти, плюс несколько популярных. Полный справочник ISO сюда не тянем
// — двести строк в выпадашке ради полноты сделали бы выбор медленнее, а не
// точнее. Понадобится ещё страна — она дописывается в PHONE_COUNTRIES одной
// строкой, и это единственное место на весь веб.
//
// Казахстан отдельной строкой НЕ идёт намеренно: у него тот же код +7, что и у
// России, и вторая строка «+7» в списке выглядела бы опечаткой.
import React, { useMemo } from 'react';

type Country = { code: string; label: string };

// Порядок намеренно не алфавитный: сверху то, что выбирают чаще всего.
export const PHONE_COUNTRIES: Country[] = [
  { code: '+7', label: '🇷🇺 +7' },
  { code: '+375', label: '🇧🇾 +375' },
  { code: '+380', label: '🇺🇦 +380' },
  { code: '+995', label: '🇬🇪 +995' },
  { code: '+374', label: '🇦🇲 +374' },
  { code: '+994', label: '🇦🇿 +994' },
  { code: '+996', label: '🇰🇬 +996' },
  { code: '+998', label: '🇺🇿 +998' },
  { code: '+992', label: '🇹🇯 +992' },
  { code: '+373', label: '🇲🇩 +373' },
  { code: '+371', label: '🇱🇻 +371' },
  { code: '+370', label: '🇱🇹 +370' },
  { code: '+372', label: '🇪🇪 +372' },
  { code: '+90', label: '🇹🇷 +90' },
  { code: '+972', label: '🇮🇱 +972' },
  { code: '+49', label: '🇩🇪 +49' },
  { code: '+44', label: '🇬🇧 +44' },
  { code: '+1', label: '🇺🇸 +1' },
];

export const DEFAULT_PHONE_CODE = '+7';

/** Разбирает «+79001234567» на код страны и остаток номера.
 *
 * Коды примеряются от длинных к коротким: иначе «+7» съел бы начало «+7…»
 * раньше, чем «+77» успел бы совпасть, а «+1» — начало «+1…» вообще у всех.
 */
export const splitPhone = (value: string): { code: string; rest: string } => {
  const raw = (value || '').trim();
  if (!raw) return { code: DEFAULT_PHONE_CODE, rest: '' };
  const codes = [...PHONE_COUNTRIES.map((c) => c.code)].sort((a, b) => b.length - a.length);
  const digits = raw.startsWith('+') ? raw : `+${raw.replace(/\D/g, '')}`;
  for (const code of codes) {
    if (digits.startsWith(code)) {
      return { code, rest: digits.slice(code.length).replace(/\D/g, '') };
    }
  }
  return { code: DEFAULT_PHONE_CODE, rest: raw.replace(/\D/g, '') };
};

interface PhoneInputProps {
  label?: string;
  value: string;                    // полный номер, «+79001234567»
  onChange: (value: string) => void;
  error?: string;
  hint?: string;
  autoFocus?: boolean;
  disabled?: boolean;
}

export const PhoneInput: React.FC<PhoneInputProps> = ({
  label = 'Телефон',
  value,
  onChange,
  error,
  hint,
  autoFocus,
  disabled,
}) => {
  const { code, rest } = useMemo(() => splitPhone(value), [value]);

  const setCode = (next: string) => onChange(rest ? `${next}${rest}` : next);

  const setRest = (next: string) => {
    // Из введённого оставляем только цифры: скобки и дефисы человек ставит по
    // привычке, а на сервер должен уехать номер, а не его оформление.
    const digits = next.replace(/\D/g, '');

    // Вставили номер целиком, вместе с кодом страны — тогда код берём из него,
    // иначе получилось бы «+7+79001234567». Условие про длину нужно, чтобы
    // отличить вставку от набора: плюс, набранный руками, приходит сюда один,
    // без цифр, и его надо просто проигнорировать.
    if (next.trim().startsWith('+') && digits.length >= 8) {
      const parsed = splitPhone(next.trim());
      onChange(`${parsed.code}${parsed.rest}`);
      return;
    }

    // Российская привычка писать «8» вместо «+7». Сервер это тоже умеет
    // (normalize_phone), но человек должен видеть в поле то, что уедет.
    if (code === '+7' && digits.length === 11 && digits.startsWith('8')) {
      onChange(`${code}${digits.slice(1)}`);
      return;
    }

    onChange(`${code}${digits}`);
  };

  return (
    <div className="flex flex-col gap-1">
      {label && <label htmlFor="phone_number" className="text-sm font-medium text-chocolate">{label}</label>}
      <div className="flex gap-2">
        <select
          aria-label="Код страны"
          value={code}
          disabled={disabled}
          onChange={(e) => setCode(e.target.value)}
          className={[
            'rounded-xl border px-2 py-2 text-sm outline-none transition bg-white',
            'focus:ring-2 focus:ring-tomato/40 focus:border-tomato',
            error ? 'border-red-500' : 'border-gray-300',
          ].join(' ')}
        >
          {PHONE_COUNTRIES.map((c) => (
            <option key={c.code} value={c.code}>{c.label}</option>
          ))}
        </select>
        <input
          id="phone_number"
          type="tel"
          inputMode="tel"
          autoComplete="tel-national"
          autoFocus={autoFocus}
          disabled={disabled}
          value={rest}
          onChange={(e) => setRest(e.target.value)}
          placeholder="900 000-00-00"
          className={[
            'flex-1 rounded-xl border px-3 py-2 text-sm outline-none transition',
            'focus:ring-2 focus:ring-tomato/40 focus:border-tomato',
            error ? 'border-red-500' : 'border-gray-300',
          ].join(' ')}
        />
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {hint && !error && <p className="text-xs text-gray-500">{hint}</p>}
    </div>
  );
};
