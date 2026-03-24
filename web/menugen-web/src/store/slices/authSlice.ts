import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { authApi } from '../../api/auth';
import type { User } from '../../types';

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
      return rejectWithValue(e.response?.data?.detail || 'Неверные учётные данные');
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
        state.loading = false; state.error = action.payload as string;
      })
      .addCase(logout.fulfilled, (state) => { state.user = null; });
  },
});

export const { clearError, setUser } = authSlice.actions;
export default authSlice.reducer;
