import '@testing-library/jest-dom';

jest.mock('../api/client');

import specialistReducer, {
  clearSpecialistError, fetchSpecialistProfile, registerAsSpecialist, fetchClients,
  fetchPendingAssignments, acceptAssignment, fetchClientMenus, fetchClientRecommendations,
  createRecommendation, deleteRecommendation,
} from './specialistSlice';
import type { SpecialistProfile, ClientFamily, PendingAssignment, ClientMenu, Recommendation } from './specialistSlice';
import api from '../api/client';

const mockApi = api as jest.Mocked<typeof api>;
const profile: SpecialistProfile = { id: 1, name: 'Диетолог', email: 'd@e.com', specialist_type: 'dietitian', is_verified: false, verified_at: null };
const client1: ClientFamily = { id: 10, name: 'Семья', members: [], assignment_id: 2, assignment_status: 'accepted' };
const pending: PendingAssignment = { assignment_id: 99, family_id: 10, family_name: 'Семья' };
const menu: ClientMenu = { id: 7, start_date: '2026-04-01', end_date: '2026-04-07', period_days: 7, status: 'active', generated_at: '2026-03-28T10:00:00Z' };
const rec: Recommendation = { id: 3, rec_type: 'supplement', name: 'Омега-3', dosage: '1', frequency: 'daily', start_date: null, end_date: null, is_active: true, is_read: false, member_name: null, created_at: '2026-03-28T10:00:00Z' };
const initialState = { profile: null, clients: [], pendingAssignments: [], selectedClientMenus: [], selectedClientRecs: [], loading: false, error: null };

describe('sync', () => {
  it('initial state', () => { expect(specialistReducer(undefined, { type: '@@INIT' })).toEqual(initialState); });
  it('clearSpecialistError', () => { expect(specialistReducer({ ...initialState, error: 'Ошибка' }, clearSpecialistError()).error).toBeNull(); });
});
describe('fetchSpecialistProfile', () => {
  beforeEach(() => jest.clearAllMocks());
  it('pending', () => { expect(specialistReducer(initialState, { type: fetchSpecialistProfile.pending.type }).loading).toBe(true); });
  it('fulfilled', () => { expect(specialistReducer(initialState, { type: fetchSpecialistProfile.fulfilled.type, payload: profile }).profile).toEqual(profile); });
  it('rejected', () => { expect(specialistReducer(initialState, { type: fetchSpecialistProfile.rejected.type, payload: 'err' }).error).toBe('err'); });
  it('thunk ok', async () => {
    mockApi.get.mockResolvedValueOnce({ data: profile });
    const dispatch = jest.fn();
    await fetchSpecialistProfile()(dispatch, () => ({}), undefined);
    expect(dispatch.mock.calls.find((c: any[]) => c[0].type === fetchSpecialistProfile.fulfilled.type)![0].payload).toEqual(profile);
  });
  it('thunk err', async () => {
    mockApi.get.mockRejectedValueOnce({ response: { data: { detail: 'nf' } } });
    const dispatch = jest.fn();
    await fetchSpecialistProfile()(dispatch, () => ({}), undefined);
    expect(dispatch.mock.calls.find((c: any[]) => c[0].type === fetchSpecialistProfile.rejected.type)![0].payload).toBe('nf');
  });
});
describe('registerAsSpecialist', () => {
  beforeEach(() => jest.clearAllMocks());
  it('fulfilled', () => { expect(specialistReducer(initialState, { type: registerAsSpecialist.fulfilled.type, payload: profile }).profile).toEqual(profile); });
  it('calls POST', async () => {
    mockApi.post.mockResolvedValueOnce({ data: profile });
    const dispatch = jest.fn();
    await registerAsSpecialist('dietitian')(dispatch, () => ({}), undefined);
    expect(mockApi.post).toHaveBeenCalledWith('/specialists/register/', { specialist_type: 'dietitian' });
  });
});
describe('fetchClients', () => {
  it('fulfilled', () => { expect(specialistReducer(initialState, { type: fetchClients.fulfilled.type, payload: [client1] }).clients).toHaveLength(1); });
});
describe('fetchPendingAssignments', () => {
  it('fulfilled', () => { expect(specialistReducer(initialState, { type: fetchPendingAssignments.fulfilled.type, payload: [pending] }).pendingAssignments).toHaveLength(1); });
});
describe('acceptAssignment', () => {
  it('removes matching', () => { expect(specialistReducer({ ...initialState, pendingAssignments: [pending] }, { type: acceptAssignment.fulfilled.type, payload: 99 }).pendingAssignments).toHaveLength(0); });
  it('keeps unrelated', () => { expect(specialistReducer({ ...initialState, pendingAssignments: [pending] }, { type: acceptAssignment.fulfilled.type, payload: 999 }).pendingAssignments).toHaveLength(1); });
});
describe('fetchClientMenus', () => {
  it('fulfilled', () => { expect(specialistReducer(initialState, { type: fetchClientMenus.fulfilled.type, payload: [menu] }).selectedClientMenus).toHaveLength(1); });
});
describe('recommendations', () => {
  it('fetch', () => { expect(specialistReducer(initialState, { type: fetchClientRecommendations.fulfilled.type, payload: [rec] }).selectedClientRecs).toHaveLength(1); });
  it('create prepends', () => { expect(specialistReducer({ ...initialState, selectedClientRecs: [{ ...rec, id: 1 }] }, { type: createRecommendation.fulfilled.type, payload: { ...rec, id: 2 } }).selectedClientRecs[0].id).toBe(2); });
  it('delete marks inactive', () => { expect(specialistReducer({ ...initialState, selectedClientRecs: [rec] }, { type: deleteRecommendation.fulfilled.type, payload: 3 }).selectedClientRecs[0].is_active).toBe(false); });
});
