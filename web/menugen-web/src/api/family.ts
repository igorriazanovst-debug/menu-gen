// MG_204_V_api = 1
import client from './client';
import type { Family, FamilyMember, UserProfile, TargetField, TargetAuditEntry } from '../types';

export interface FamilyMemberUpdatePayload {
  name?: string;
  allergies?: string[];
  disliked_products?: string[];
  profile?: Partial<UserProfile>;
}

export const familyApi = {
  get: () => client.get<Family>('/family/'),
  rename: (name: string) => client.patch<Family>('/family/', { name }),
  invite: (email?: string, phone?: string) =>
    client.post('/family/invite/', { email, phone }),
  removeMember: (memberId: number) =>
    client.delete(`/family/members/${memberId}/`),
  updateMember: (memberId: number, payload: FamilyMemberUpdatePayload) =>
    client.patch<FamilyMember>(`/family/members/${memberId}/update/`, payload),

  // MG_205UI_V_api_family = 1
  getMemberTargetHistory: (memberId: number, field: TargetField) =>
    client.get<TargetAuditEntry[]>(`/family/members/${memberId}/targets/${field}/history/`),
  resetMemberTarget: (memberId: number, field: TargetField) =>
    client.post<FamilyMember>(`/family/members/${memberId}/targets/${field}/reset/`),
};
