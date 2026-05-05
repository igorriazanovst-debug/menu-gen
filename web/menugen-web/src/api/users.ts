// MG_205UI_V_api_users = 1
import client from './client';
import type { TargetField, TargetAuditEntry, User } from '../types';

export const usersApi = {
  getTargetHistory: (field: TargetField) =>
    client.get<TargetAuditEntry[]>(`/users/me/targets/${field}/history/`),

  resetTarget: (field: TargetField) =>
    client.post<User>(`/users/me/targets/${field}/reset/`),
};
