import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/bloc/auth_bloc.dart';
import '../../features/auth/screens/forgot_password_screen.dart'; // MG_PWDRESET
import '../../features/auth/screens/login_screen.dart';
import '../../features/auth/screens/phone_register_screen.dart'; // MG_PHONEVERIFY
import '../../features/auth/screens/register_screen.dart'; // MG_REG
import '../../features/diary/screens/diary_screen.dart';
import '../../features/family/bloc/family_bloc.dart';
import '../../features/family/screens/family_screen.dart';
import '../../features/fridge/screens/fridge_screen.dart';
import '../../features/legal/legal_repository.dart'; // MG_LEGAL
import '../../features/legal/models/legal_info.dart'; // MG_LEGAL
import '../../features/legal/screens/legal_document_screen.dart'; // MG_LEGAL
import '../../features/legal/screens/legal_documents_screen.dart'; // MG_LEGAL
import '../../features/fridge/screens/fridge_item_detail_screen.dart';
import '../../features/menu/screens/menu_screen.dart';
import '../../features/profile/screens/delete_account_screen.dart'; // MG_ACCDEL
import '../../features/profile/screens/notifications_screen.dart'; // MG_WEIGHREMIND
import '../../features/profile/screens/profile_screen.dart';
import '../../features/profile/screens/kbju_calculator_screen.dart'; // MG_207_V_route
import '../../features/recipes/screens/recipe_detail_screen.dart';
import '../../features/recipes/screens/recipes_screen.dart';
import '../../features/shopping/screens/shopping_list_screen.dart';
import '../../features/subscription/screens/subscription_screen.dart'; // MG_PAY
import '../api/api_client.dart';
import '../premium/paywall_screen.dart';
import '../premium/premium_gate_cubit.dart';
import '../widgets/main_shell.dart';

// freemium: дневник открыт free-юзерам (как в вебе). Холодильник остаётся premium.
const _premiumOnlyPaths = {'/fridge'};

/// Экраны, доступные без входа: только сам вход и регистрация.
///
/// MG_LEGAL: юридические документы сюда намеренно НЕ входят — они живут в
/// закрытой части, в разделе профиля.
const _guestPaths = {'/login', '/register', '/register/phone', '/forgot-password'};

/// Куда перенаправить пользователя, или null — если можно остаться.
///
/// Вынесено из замыкания роутера, чтобы правило доступа можно было проверить
/// тестом, не поднимая всё дерево экранов.
String? authRedirect({required bool isLoggedIn, required String location, bool premiumLocked = false}) {
  // Хвост запроса отрезаем: /forgot-password?mode=phone — тот же гостевой путь.
  // matchedLocation его и так не содержит, но правило не должно зависеть от
  // того, что именно ему передали.
  final path = location.split('?').first;
  final isGuestPath = _guestPaths.contains(path);
  if (!isLoggedIn && !isGuestPath) return '/login';
  if (isLoggedIn && isGuestPath) return '/menu';
  if (premiumLocked && _premiumOnlyPaths.any(path.startsWith)) return '/paywall';
  return null;
}

class AppRouter {
  static GoRouter create({required AuthState authState, required ApiClient apiClient, required PremiumGateCubit premiumGate}) {
    return GoRouter(
      initialLocation: '/menu',
      redirect: (context, state) => authRedirect(
        isLoggedIn: authState is AuthAuthenticated,
        location: state.matchedLocation,
        premiumLocked: premiumGate.state.status == PremiumStatus.lockedForRead,
      ),
      routes: [
        // MG_EMAILVERIFY_MOBILE: обоим экранам нужен клиент — они сами
        // переотправляют письмо подтверждения.
        GoRoute(path: '/login', builder: (_, __) => LoginScreen(apiClient: apiClient)),
        GoRoute(path: '/register', builder: (_, __) => RegisterScreen(apiClient: apiClient)), // MG_REG
        // MG_PHONEVERIFY: регистрация по телефону с подтверждением в мессенджере.
        GoRoute(
          path: '/register/phone',
          builder: (_, __) => PhoneRegisterScreen(apiClient: apiClient),
        ),
        // MG_PWDRESET: забыл пароль. Гостевой путь — человек без пароля войти
        // не может, и редирект на /login был бы замкнутым кругом.
        GoRoute(
          path: '/forgot-password',
          // ?mode=phone — пришли с телефонной вкладки входа; открываем сразу её,
          // чтобы человек не искал нужный способ сам.
          builder: (_, state) => ForgotPasswordScreen(
            apiClient: apiClient,
            byPhone: state.uri.queryParameters['mode'] == 'phone',
          ),
        ),
        GoRoute(path: '/paywall', builder: (_, __) => const PaywallScreen()),
        // MG_WEIGHREMIND: настройка ежедневного напоминания взвеситься.
        GoRoute(
          path: '/notifications',
          builder: (_, __) => const NotificationsScreen(),
        ),
        // MG_ACCDEL: удаление аккаунта. Требование Google Play — путь должен
        // быть внутри приложения, а не только на сайте.
        GoRoute(
          path: '/delete-account',
          builder: (_, __) => DeleteAccountScreen(apiClient: apiClient),
        ),
        // MG_LEGAL: список документов и просмотр одного из них. Данные из списка
        // передаются через extra, при прямом переходе экран грузит их сам.
        GoRoute(
          path: '/legal',
          builder: (_, __) => LegalDocumentsScreen(apiClient: apiClient),
        ),
        GoRoute(
          path: '/legal/:doc',
          builder: (_, state) => LegalDocumentScreen(
            apiClient: apiClient,
            doc: legalDocFromSlug(state.pathParameters['doc']),
            preloaded: state.extra is LegalInfo ? state.extra as LegalInfo : null,
          ),
        ),
        GoRoute(
          path: '/subscription', // MG_PAY
          builder: (_, __) => SubscriptionScreen(apiClient: apiClient),
        ),
        GoRoute(
          path: '/fridge/:id/details',
          builder: (_, state) => FridgeItemDetailScreen(
            apiClient: apiClient,
            itemId: int.parse(state.pathParameters['id']!),
          ),
        ),
        GoRoute(
          path: '/recipes/:id',
          builder: (_, state) => RecipeDetailScreen(
            apiClient: apiClient,
            recipeId: int.parse(state.pathParameters['id']!),
          ),
        ),
        // MG_207_V_route: калькулятор КБЖУ (full-screen, push c extra=profile).
        GoRoute(
          path: '/profile/kbju-calculator',
          builder: (_, state) => KbjuCalculatorScreen(
            apiClient: apiClient,
            initialProfile: state.extra is Map
                ? Map<String, dynamic>.from(state.extra as Map)
                : null,
          ),
        ),
        // MG_TABSTATE: StatefulShellRoute.indexedStack — держит состояние всех
        // вкладок живым (IndexedStack), чтобы фильтры/скролл не сбрасывались при
        // переключении. Порядок branch'ей = порядок табов в MainShell (0..5).
        StatefulShellRoute.indexedStack(
          builder: (context, state, navigationShell) => MainShell(navigationShell: navigationShell),
          branches: [
            StatefulShellBranch(routes: [
              GoRoute(path: '/menu', builder: (_, __) => MenuScreen(apiClient: apiClient)),
            ]),
            StatefulShellBranch(routes: [
              GoRoute(path: '/recipes', builder: (_, __) => RecipesScreen(apiClient: apiClient)),
            ]),
            StatefulShellBranch(routes: [
              GoRoute(path: '/fridge', builder: (_, __) => FridgeScreen(apiClient: apiClient)),
            ]),
            StatefulShellBranch(routes: [
              GoRoute(path: '/shopping', builder: (_, __) => ShoppingListScreen(apiClient: apiClient)),
            ]),
            StatefulShellBranch(routes: [
              GoRoute(path: '/diary', builder: (_, __) => const DiaryScreen()),
            ]),
            StatefulShellBranch(routes: [
              GoRoute(path: '/profile', builder: (_, __) => ProfileScreen(apiClient: apiClient)),
            ]),
          ],
        ),
        GoRoute(
          path: '/family',
          builder: (_, __) => BlocProvider(
            create: (_) => FamilyBloc(apiClient: apiClient)..add(const FamilyLoadRequested()),
            child: const FamilyScreen(),
          ),
        ),
      ],
    );
  }
}
