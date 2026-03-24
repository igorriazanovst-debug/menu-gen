import client from './client';
import type { Family } from '../types';

export const familyApi = {
  get: () => client.get<Family>('/family/'),
  rename: (name: string) => client.patch<Family>('/family/', { name }),
  invite: (email?: string, phone?: string) =>
    client.post('/family/invite/', { email, phone }),
  removeMember: (memberId: number) =>
    client.delete(`/family/members/${memberId}/`),
};
