import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Provider } from 'react-redux';
import { store } from './store';
import { useAppDispatch, useAppSelector } from './hooks/useAppDispatch';
import { initAuth } from './store/slices/authSlice';

import { AppLayout } from './components/layout/AppLayout';
import { LoginPage }         from './pages/Auth/LoginPage';
import { DashboardPage }     from './pages/Dashboard/DashboardPage';
import { RecipesPage }       from './pages/Recipes/RecipesPage';
import { MenuPage }          from './pages/Menu/MenuPage';
import { FamilyPage }        from './pages/Family/FamilyPage';
import { DiaryPage }         from './pages/Diary/DiaryPage';
import { SubscriptionsPage } from './pages/Subscriptions/SubscriptionsPage';
import { ProfilePage }       from './pages/Profile/ProfilePage';

const PrivateRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, initialized } = useAppSelector((s) => s.auth);
  if (!initialized) return (
    <div className="min-h-screen flex items-center justify-center bg-rice">
      <div className="text-4xl animate-pulse">🍅</div>
    </div>
  );
  return user ? <>{children}</> : <Navigate to="/login" replace />;
};

const AppRoutes: React.FC = () => {
  const dispatch = useAppDispatch();
  useEffect(() => { dispatch(initAuth()); }, [dispatch]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<PrivateRoute><AppLayout /></PrivateRoute>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard"     element={<DashboardPage />} />
        <Route path="menu"          element={<MenuPage />} />
        <Route path="recipes"       element={<RecipesPage />} />
        <Route path="family"        element={<FamilyPage />} />
        <Route path="diary"         element={<DiaryPage />} />
        <Route path="subscriptions" element={<SubscriptionsPage />} />
        <Route path="profile"       element={<ProfilePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

const App: React.FC = () => (
  <Provider store={store}>
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  </Provider>
);

export default App;
