import '@testing-library/jest-dom';

jest.mock('../../api/auth');

import authReducer, { clearError, setUser, login, logout, initAuth } from './authSlice';
import { authApi } from '../../api/auth';
import type { User } from '../../types';

const mockAuthApi = authApi as jest.Mocked<typeof authApi>;
const mockUser: User = { id: 1, name: 'Тест', email: 'test@example.com', profile: {} } as unknown as User;
const initialState = { user: null, loading: false, error: null, initialized: false };

describe('authSlice — sync', () => {
  it('initial state', () => { expect(authReducer(undefined, { type: '@@INIT' })).toEqual(initialState); });
  it('clearError', () => { expect(authReducer({ ...initialState, error: 'Ошибка' }, clearError()).error).toBeNull(); });
  it('setUser', () => { expect(authReducer(initialState, setUser(mockUser)).user).toEqual(mockUser); });
});

describe('initAuth', () => {
  beforeEach(() => { localStorage.clear(); jest.clearAllMocks(); });
  it('fulfilled null when no token', async () => {
    const dispatch = jest.fn();
    await initAuth()(dispatch, () => ({}), undefined);
    expect(dispatch.mock.calls.map((c: any[]) => c[0].type)).toContain('auth/init/fulfilled');
  });
  it('fulfilled with user', async () => {
    localStorage.setItem('access_token', 'tok');
    mockAuthApi.me.mockResolvedValueOnce({ data: mockUser } as any);
    const dispatch = jest.fn();
    await initAuth()(dispatch, () => ({}), undefined);
    const f = dispatch.mock.calls.find((c: any[]) => c[0].type === 'auth/init/fulfilled');
    expect(f![0].payload).toEqual(mockUser);
  });
  it('clears localStorage on error', async () => {
    localStorage.setItem('access_token', 'bad');
    mockAuthApi.me.mockRejectedValueOnce(new Error('401'));
    const dispatch = jest.fn();
    await initAuth()(dispatch, () => ({}), undefined);
    expect(localStorage.getItem('access_token')).toBeNull();
  });
  it('state: initialized=true', () => {
    expect(authReducer(initialState, { type: 'auth/init/fulfilled', payload: mockUser }).initialized).toBe(true);
  });
});

describe('login', () => {
  beforeEach(() => { localStorage.clear(); jest.clearAllMocks(); });
  it('pending: loading=true', () => { expect(authReducer({ ...initialState, error: 'x' }, { type: 'auth/login/pending' }).loading).toBe(true); });
  it('fulfilled: saves tokens', async () => {
    mockAuthApi.login.mockResolvedValueOnce({ data: { access: 'acc', refresh: 'ref' } } as any);
    mockAuthApi.me.mockResolvedValueOnce({ data: mockUser } as any);
    const dispatch = jest.fn();
    await login({ email: 'e', password: 'p' })(dispatch, () => ({}), undefined);
    expect(localStorage.getItem('access_token')).toBe('acc');
  });
  it('fulfilled state', () => { expect(authReducer({ ...initialState, loading: true }, { type: 'auth/login/fulfilled', payload: mockUser }).user).toEqual(mockUser); });
  it('rejected state', () => { expect(authReducer({ ...initialState, loading: true }, { type: 'auth/login/rejected', payload: 'bad' }).error).toBe('bad'); });
  it('rejected thunk', async () => {
    mockAuthApi.login.mockRejectedValueOnce({ response: { data: { detail: 'bad creds' } } });
    const dispatch = jest.fn();
    await login({ email: 'x', password: 'y' })(dispatch, () => ({}), undefined);
    const r = dispatch.mock.calls.find((c: any[]) => c[0].type === 'auth/login/rejected');
    expect(r![0].payload).toBe('bad creds');
  });
});

describe('logout', () => {
  beforeEach(() => { localStorage.clear(); jest.clearAllMocks(); });
  it('clears localStorage', async () => {
    localStorage.setItem('access_token', 'acc');
    mockAuthApi.logout.mockResolvedValueOnce({} as any);
    const dispatch = jest.fn();
    await logout()(dispatch, () => ({}), undefined);
    expect(localStorage.getItem('access_token')).toBeNull();
  });
  it('state: user=null', () => { expect(authReducer({ ...initialState, user: mockUser }, { type: 'auth/logout/fulfilled' }).user).toBeNull(); });
});
