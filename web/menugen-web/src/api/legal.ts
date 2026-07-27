// MG_LEGAL: публичные реквизиты + оферта + логотип.
import client from './client';
import type { LegalInfo } from '../types';

export const legalApi = {
  get: () => client.get<LegalInfo>('/legal/'),
};
