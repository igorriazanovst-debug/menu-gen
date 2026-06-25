// MG_SKIN: UI-состояние (выбранный скин). Источник истины при логине — профиль
// пользователя (user.ui_skin); локально дублируем в localStorage для мгновенного
// применения без вспышки и оффлайна.
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { authApi } from '../../api/auth';
import { Skin, getStoredSkin, storeSkin, applySkin } from '../../theme/skins';

interface UiState {
  skin: Skin;
}

const initialState: UiState = {
  skin: getStoredSkin(),
};

// Пользователь сменил скин: применяем локально и синкаем в аккаунт.
export const changeSkin = createAsyncThunk(
  'ui/changeSkin',
  async (skin: Skin) => {
    storeSkin(skin);
    applySkin(skin);
    try {
      await authApi.updateMe({ ui_skin: skin });
    } catch {
      // оффлайн/ошибка сети — локально уже применено, синк догонит позже
    }
    return skin;
  },
);

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    // Применить скин из профиля (после initAuth/login) без обратной записи в API.
    setSkinFromProfile: (state, action: PayloadAction<Skin>) => {
      state.skin = action.payload;
      storeSkin(action.payload);
      applySkin(action.payload);
    },
  },
  extraReducers: (builder) => {
    builder.addCase(changeSkin.fulfilled, (state, action) => {
      state.skin = action.payload;
    });
  },
});

export const { setSkinFromProfile } = uiSlice.actions;
export default uiSlice.reducer;
