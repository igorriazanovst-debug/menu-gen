// MG_VERIFYDEEPLINK: ссылка возврата в приложение после подтверждения e-mail.
import { APP_SCHEME, canOpenApp, verifiedAppLink } from './appLink';

describe('verifiedAppLink', () => {
  it('адрес уезжает в приложение экранированным', () => {
    expect(verifiedAppLink('a+b@example.com')).toBe(
      `${APP_SCHEME}://verified?email=a%2Bb%40example.com`,
    );
  });

  it('без адреса ссылка всё равно рабочая', () => {
    // Подтверждение состоялось — открыть приложение нужно в любом случае.
    expect(verifiedAppLink(null)).toBe(`${APP_SCHEME}://verified`);
    expect(verifiedAppLink(undefined)).toBe(`${APP_SCHEME}://verified`);
    expect(verifiedAppLink('')).toBe(`${APP_SCHEME}://verified`);
  });

  it('токен в ссылку не попадает ни при каких условиях', () => {
    // Схему может зарегистрировать чужое приложение — токен туда нельзя.
    expect(verifiedAppLink('a@b.ru')).not.toContain('token');
  });
});

describe('canOpenApp', () => {
  it('Android — предлагаем', () => {
    expect(
      canOpenApp('Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36'),
    ).toBe(true);
  });

  it('десктоп и iOS — не предлагаем, вести некуда', () => {
    expect(canOpenApp('Mozilla/5.0 (Windows NT 10.0; Win64; x64)')).toBe(false);
    expect(canOpenApp('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')).toBe(false);
  });
});
