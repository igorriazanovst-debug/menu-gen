import { configureStore } from '@reduxjs/toolkit';
import authReducer from './slices/authSlice';
import specialistReducer from './specialistSlice';
import uiReducer from './slices/uiSlice'; // MG_SKIN

export const store = configureStore({
  reducer: {
    auth: authReducer,
    specialist: specialistReducer,
    ui: uiReducer, // MG_SKIN
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
