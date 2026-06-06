// MG_205UI_V_api_users = 1
// MG_206_V_api = 1
import client from './client';
import type {
  TargetField,
  TargetAuditEntry,
  User,
  KBJURequest,
  KBJUResult,
} from '../types';

export const usersApi = {
  getTargetHistory: (field: TargetField) =>
    client.get<TargetAuditEntry[]>(`/users/me/targets/${field}/history/`),

  resetTarget: (field: TargetField) =>
    client.post<User>(`/users/me/targets/${field}/reset/`),

  // MG_206: KBJU calculator
  calcPreview: (body: KBJURequest) =>
    client.post<KBJUResult>(`/users/me/calculator/preview/`, body),

  calcApply: (body: KBJURequest) =>
    client.post<User>(`/users/me/calculator/apply/`, body),
};
