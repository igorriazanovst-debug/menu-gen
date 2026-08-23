// MG_APKSITE: публичная информация о приложении (ссылка на apk).
import client from './client';
import type { AndroidBuild } from '../types';

export const appApi = {
  // Без авторизации: человек приходит на сайт именно за приложением.
  androidBuild: () => client.get<{ build: AndroidBuild | null }>('/app/android/'),
};
