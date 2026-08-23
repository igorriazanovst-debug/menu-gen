// MG_APKSITE: подпись размера под ссылкой на apk.
import { formatSize } from './AndroidDownload';

describe('formatSize', () => {
  it('показывает мегабайты целым числом', () => {
    expect(formatSize(54 * 1024 * 1024)).toBe('54 МБ');
  });

  it('меньше мегабайта — молчим: такой apk не бывает, значит что-то не так', () => {
    expect(formatSize(1024)).toBe('');
    expect(formatSize(0)).toBe('');
    expect(formatSize(undefined)).toBe('');
    expect(formatSize(null)).toBe('');
  });
});
