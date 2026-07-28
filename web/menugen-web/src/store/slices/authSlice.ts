import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { authApi } from '../../api/auth';
import type { User, RegisterResult } from '../../types';

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

const initialState: AuthState = {
  user: null, loading: false, error: null, initialized: false,
};

export const initAuth = createAsyncThunk('auth/init', async (_, { rejectWithValue }) => {
  const token = localStorage.getItem('access_token');
  if (!token) return null;
  try {
    const { data } = await authApi.me();
    return data;
  } catch {
    localStorage.clear();
    return null;
  }
});

export const login = createAsyncThunk(
  'auth/login',
  async ({ email, password }: { email: string; password: string }, { rejectWithValue }) => {
    try {
      const { data: tokens } = await authApi.login(email, password);
      localStorage.setItem('access_token', tokens.access);
      localStorage.setItem('refresh_token', tokens.refresh);
      const { data: user } = await authApi.me();
      return user;
    } catch (e: any) {
      const d = e.response?.data;
      // MG_EMAILVERIFY: e-mail не подтверждён — отдаём код и email для UI ресенда.
      if (d?.code === 'email_not_verified') {
        return rejectWithValue({ code: 'email_not_verified', email: d.email, message: d.detail || 'Подтвердите e-mail' });
      }
      return rejectWithValue({ message: d?.detail || 'Неверные учётные данные' });
    }
  },
);

// MG_EMAILVERIFY: регистрация — создаёт пользователя (+семья+free), НЕ логинит;
// требуется подтверждение e-mail по ссылке. Возвращает результат для UI.
export const register = createAsyncThunk(
  'auth/register',
  async (
    { name, email, password, password2 }: { name: string; email: string; password: string; password2: string },
    { rejectWithValue },
  ) => {
    try {
      const { data } = await authApi.register(name, email, password, password2);
      return data as RegisterResult;
    } catch (e: any) {
      const d = e.response?.data;
      const msg = d?.detail
        || (d && typeof d === 'object' ? Object.values(d).flat().join(' ') : '')
        || 'Не удалось зарегистрироваться';
      return rejectWithValue(msg);
    }
  },
);

// MG_EMAILVERIFY: подтверждение e-mail по токену из ссылки → вход (сохраняет токены).
export const verifyEmail = createAsyncThunk(
  'auth/verifyEmail',
  async (token: string, { rejectWithValue }) => {
    try {
      const { data: tokens } = await authApi.verifyEmail(token);
      localStorage.setItem('access_token', tokens.access);
      localStorage.setItem('refresh_token', tokens.refresh);
      const { data: user } = await authApi.me();
      return user;
    } catch (e: any) {
      return rejectWithValue(e.response?.data?.detail || 'Ссылка недействительна или устарела');
    }
  },
);

export const logout = createAsyncThunk('auth/logout', async () => {
  const refresh = localStorage.getItem('refresh_token') || '';
  try { await authApi.logout(refresh); } catch {}
  localStorage.clear();
});

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    clearError: (state) => { state.error = null; },
    setUser: (state, action: PayloadAction<User>) => { state.user = action.payload; },
  },
  extraReducers: (builder) => {
    builder
      .addCase(initAuth.fulfilled, (state, action) => {
        state.user = action.payload; state.initialized = true;
      })
      .addCase(login.pending, (state) => { state.loading = true; state.error = null; })
      .addCase(login.fulfilled, (state, action) => {
        state.loading = false; state.user = action.payload;
      })
      .addCase(login.rejected, (state, action) => {
        state.loading = false;
        const p = action.payload as { message?: string } | string | undefined;
        state.error = (typeof p === 'object' ? p?.message : p) || 'Ошибка входа';
      })
      // MG_EMAILVERIFY: регистрация НЕ логинит (нужно подтверждение e-mail).
      .addCase(register.pending, (state) => { state.loading = true; state.error = null; })
      .addCase(register.fulfilled, (state) => { state.loading = false; })
      .addCase(register.rejected, (state, action) => {
        state.loading = false; state.error = action.payload as string;
      })
      .addCase(verifyEmail.pending, (state) => { state.loading = true; state.error = null; })
      .addCase(verifyEmail.fulfilled, (state, action) => {
        state.loading = false; state.user = action.payload;
      })
      .addCase(verifyEmail.rejected, (state, action) => {
        state.loading = false; state.error = action.payload as string;
      })
      .addCase(logout.fulfilled, (state) => { state.user = null; });
  },
});

export const { clearError, setUser } = authSlice.actions;
export default authSlice.reducer;
