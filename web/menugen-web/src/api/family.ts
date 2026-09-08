// MG_204_V_api = 1
import client from './client';
import type {
  Family, FamilyMember, UserProfile, TargetField, TargetAuditEntry,
  FamilyChoice, FamilyInvite,
} from '../types';

export interface FamilyMemberUpdatePayload {
  name?: string;
  allergies?: string[];
  disliked_products?: string[];
  profile?: Partial<UserProfile>;
}

export const familyApi = {
  get: () => client.get<Family>('/family/'),
  rename: (name: string) => client.patch<Family>('/family/', { name }),
  // MG_RUBRIC007_update: patch family fields (currency, name).
  // MG_SHELFLIFE: auto_expiry — подставлять ли сроки при переносе покупок.
  update: (payload: { name?: string; currency?: string; auto_expiry?: boolean }) =>
    client.patch<Family>('/family/', payload),
  // MG_FAMINVITE: зовём, а не зачисляем — членство появится после согласия.
  invite: (email?: string, phone?: string) =>
    client.post<FamilyInvite>('/family/invite/', { email, phone }),
  cancelInvite: (inviteId: number) => client.delete(`/family/invites/${inviteId}/`),
  // Мои входящие приглашения и ответ на них.
  myInvites: () => client.get<FamilyInvite[]>('/family/invites/'),
  respondInvite: (inviteId: number, accept: boolean) =>
    client.post<FamilyInvite>(`/family/invites/${inviteId}/respond/`, { accept }),
  // MG_ACTIVEFAMILY: где я состою и переход за другой стол.
  choices: () => client.get<FamilyChoice[]>('/family/choices/'),
  switchTo: (familyId: number) =>
    client.post<FamilyChoice[]>('/family/switch/', { family_id: familyId }),
  // MG_MANAGEDMEMBER: add a member card without inviting an existing user.
  createManagedMember: (payload: {
    name: string;
    allergies?: string[];
    disliked_products?: string[];
    profile?: Partial<UserProfile>;
  }) => client.post<FamilyMember>('/family/members/create-managed/', payload),
  // MG_MANAGEDMEMBER: later give a managed member their own login.
  attachAccount: (
    memberId: number,
    payload: { email?: string; phone?: string; password?: string },
  ) => client.post<FamilyMember>(`/family/members/${memberId}/attach-account/`, payload),
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
