// MG_SPECACCESS: подписи ролей и чтение уровней доступа.
import {
  SPECIALIST_TYPES,
  SPECIALIST_TYPE_LABELS,
  SECTION_LABELS,
  canRead,
  canWrite,
  specialistTypeLabel,
  type SpecialistPermissions,
} from './specialist';

const cook: SpecialistPermissions = {
  profile: 'read',
  diary: 'none',
  menu: 'write',
  fridge: 'write',
  shopping: 'write',
};

describe('типы специалистов', () => {
  it('повар входит в список наравне с остальными', () => {
    expect(SPECIALIST_TYPES).toContain('cook');
  });

  it('у каждого типа есть подпись', () => {
    for (const t of SPECIALIST_TYPES) {
      expect(SPECIALIST_TYPE_LABELS[t]).toBeTruthy();
    }
  });

  it('неизвестный тип не роняет интерфейс', () => {
    expect(specialistTypeLabel('massagist')).toBe('Специалист');
    expect(specialistTypeLabel(null)).toBe('Специалист');
  });
});

describe('уровни доступа', () => {
  it('правка подразумевает чтение', () => {
    expect(canWrite(cook, 'fridge')).toBe(true);
    expect(canRead(cook, 'fridge')).toBe(true);
  });

  it('чтение не даёт правки', () => {
    expect(canRead(cook, 'profile')).toBe(true);
    expect(canWrite(cook, 'profile')).toBe(false);
  });

  it('закрытый раздел закрыт совсем', () => {
    expect(canRead(cook, 'diary')).toBe(false);
    expect(canWrite(cook, 'diary')).toBe(false);
  });

  it('без прав (профиль ещё не загружен) ничего не открыто', () => {
    expect(canRead(undefined, 'menu')).toBe(false);
    expect(canWrite(undefined, 'menu')).toBe(false);
  });

  it('разделы интерфейса совпадают с разделами сервера', () => {
    expect(Object.keys(SECTION_LABELS).sort()).toEqual(
      ['diary', 'fridge', 'menu', 'profile', 'shopping'],
    );
  });
});
