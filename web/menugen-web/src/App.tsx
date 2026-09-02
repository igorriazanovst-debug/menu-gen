import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Provider } from 'react-redux';
import { store } from './store';
import { useAppDispatch, useAppSelector } from './hooks/useAppDispatch';
import { initAuth } from './store/slices/authSlice';
import { setSkinFromProfile } from './store/slices/uiSlice'; // MG_SKIN
import { isSkin } from './theme/skins'; // MG_SKIN
import { useIsPremium } from './hooks/usePremium'; // freemium-гейт
import { AppLayout }         from './components/layout/AppLayout';
import { LoginPage }         from './pages/Auth/LoginPage';
import { RegisterPage }      from './pages/Auth/RegisterPage';
import { PhoneRegisterPage } from './pages/Auth/PhoneRegisterPage'; // MG_PHONEVERIFY
import { VerifyEmailPage }   from './pages/Auth/VerifyEmailPage'; // MG_EMAILVERIFY
import { ForgotPasswordPage } from './pages/Auth/ForgotPasswordPage'; // MG_PWDRESET
import { ResetPasswordPage }  from './pages/Auth/ResetPasswordPage'; // MG_PWDRESET
import { PayReturnPage } from './pages/Payments/PayReturnPage';
import { DashboardPage }     from './pages/Dashboard/DashboardPage';
import { RecipesPage }       from './pages/Recipes/RecipesPage';
import { MenuPage }          from './pages/Menu/MenuPage';
import { FamilyPage }        from './pages/Family/FamilyPage';
import { DiaryPage }         from './pages/Diary/DiaryPage';
import { FridgePage }        from './pages/Fridge/FridgePage';
import { MyProductsPage }    from './pages/Products/MyProductsPage'; // MG_MYPRODUCTS
import { ShoppingPage }      from './pages/Shopping/ShoppingPage';
import { SubscriptionsPage } from './pages/Subscriptions/SubscriptionsPage';
import { ProfilePage }       from './pages/Profile/ProfilePage';
import { KBJUCalculatorPage } from './pages/Profile/KBJUCalculatorPage'; // MG_206_V_app_route
import { ConstructorPage }    from './pages/Constructor/ConstructorPage'; // MG_CONSTRUCTOR
import { RequisitesPage }     from './pages/Legal/RequisitesPage'; // MG_LEGAL
import { OfferPage }          from './pages/Legal/OfferPage'; // MG_LEGAL
import { PrivacyPage }        from './pages/Legal/PrivacyPage'; // MG_PRIVACY
import { DeleteAccountPage }        from './pages/Legal/DeleteAccountPage'; // MG_ACCDEL
import { DeleteAccountConfirmPage } from './pages/Legal/DeleteAccountConfirmPage'; // MG_ACCDEL
import { SpecialistDashboardPage } from './pages/specialist/SpecialistDashboardPage';
import { MySpecialistsPage }       from './pages/Specialists/MySpecialistsPage'; // MG_SPECINVITE
import { SpecialistRegisterPage }  from './pages/specialist/SpecialistRegisterPage';
import { ClientDetailPage }        from './pages/specialist/ClientDetailPage';
import { ClientMenuEditorPage }    from './pages/specialist/ClientMenuEditorPage';
import { RecommendationFormPage }  from './pages/specialist/RecommendationFormPage';

const PrivateRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, initialized } = useAppSelector((s) => s.auth);
  if (!initialized) return (
    <div className="min-h-screen flex items-center justify-center bg-bg">
      <div className="text-4xl animate-pulse">🍅</div>
    </div>
  );
  return user ? <>{children}</> : <Navigate to="/login" replace />;
};

// Куда вести «/» и неизвестные пути: premium → дашборд, free → меню.
const HomeRedirect: React.FC = () => {
  const isPremium = useIsPremium();
  return <Navigate to={isPremium ? '/dashboard' : '/menu'} replace />;
};

// Premium-страница: free-юзера не пускаем и не грузим — редирект на Тарифы.
const PremiumRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const isPremium = useIsPremium();
  return isPremium ? <>{children}</> : <Navigate to="/subscriptions" replace />;
};

// MG_CONSTRUCTOR: конструктор доступен специалистам и стаффу.
const SpecialistRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const user = useAppSelector((s) => s.auth.user);
  const allowed = !!(user && (user.is_staff || user.is_specialist));
  return allowed ? <>{children}</> : <Navigate to="/menu" replace />;
};

const AppRoutes: React.FC = () => {
  const dispatch = useAppDispatch();
  const userSkin = useAppSelector((s) => s.auth.user?.ui_skin); // MG_SKIN
  useEffect(() => { dispatch(initAuth()); }, [dispatch]);
  // MG_SKIN: подтягиваем скин из профиля после логина/инициализации.
  useEffect(() => {
    if (isSkin(userSkin)) dispatch(setSkinFromProfile(userSkin));
  }, [userSkin, dispatch]);
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/register/phone" element={<PhoneRegisterPage />} />{/* MG_PHONEVERIFY */}
      <Route path="/verify-email" element={<VerifyEmailPage />} />{/* MG_EMAILVERIFY */}
      {/* MG_PWDRESET: восстановление пароля. Публичные маршруты намеренно —
          человек, забывший пароль, войти не может по определению. */}
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      {/* MG_PAYRELIABLE: возврат с оплаты для мобильного — публичная страница:
          оплата началась в приложении, в браузере сессии может не быть. */}
      <Route path="/pay/return" element={<PayReturnPage />} />
      {/* MG_LEGAL: публичные юридические страницы (без авторизации) */}
      <Route path="/requisites" element={<RequisitesPage />} />
      <Route path="/offer" element={<OfferPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />{/* MG_PRIVACY */}
      {/* MG_ACCDEL: удаление аккаунта без входа — этого адреса требует Google Play.
          Публичный маршрут намеренно: человек, который не может войти, должен
          суметь удалиться. */}
      <Route path="/delete-account" element={<DeleteAccountPage />} />
      <Route path="/delete-account/confirm" element={<DeleteAccountConfirmPage />} />
      <Route path="/" element={<PrivateRoute><AppLayout /></PrivateRoute>}>
        <Route index element={<HomeRedirect />} />
        <Route path="dashboard"     element={<PremiumRoute><DashboardPage /></PremiumRoute>} />
        <Route path="menu"          element={<MenuPage />} />
        <Route path="recipes"       element={<RecipesPage />} />
        <Route path="family"        element={<FamilyPage />} />
        <Route path="diary"         element={<DiaryPage />} />
        <Route path="fridge"        element={<PremiumRoute><FridgePage /></PremiumRoute>} />
        <Route path="products"      element={<PremiumRoute><MyProductsPage /></PremiumRoute>} />{/* MG_MYPRODUCTS */}
        <Route path="shopping"      element={<ShoppingPage />} />
        <Route path="subscriptions" element={<SubscriptionsPage />} />
        <Route path="profile"       element={<ProfilePage />} />
        <Route path="profile/kbju-calculator" element={<KBJUCalculatorPage />} />
        <Route path="my-specialists" element={<MySpecialistsPage />} />{/* MG_SPECINVITE */}
        <Route path="constructor"   element={<SpecialistRoute><ConstructorPage /></SpecialistRoute>} />{/* MG_CONSTRUCTOR */}
        <Route path="specialist"                                          element={<SpecialistDashboardPage />} />
        <Route path="specialist/register"                                 element={<SpecialistRegisterPage />} />
        <Route path="specialist/clients/:familyId"                        element={<ClientDetailPage />} />
        <Route path="specialist/clients/:familyId/menus/:menuId"          element={<ClientMenuEditorPage />} />
        <Route path="specialist/clients/:familyId/recommendations/new"    element={<RecommendationFormPage />} />
      </Route>
      <Route path="*" element={<HomeRedirect />} />
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
