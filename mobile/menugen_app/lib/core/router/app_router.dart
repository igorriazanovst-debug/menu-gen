import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/bloc/auth_bloc.dart';
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

class AppRouter {
  static GoRouter create({required AuthState authState, required ApiClient apiClient, required PremiumGateCubit premiumGate}) {
    return GoRouter(
      initialLocation: '/menu',
      redirect: (context, state) {
        final isLoggedIn = authState is AuthAuthenticated;
        final loc = state.matchedLocation;
        final isAuthRoute = loc == '/login' ||
            loc == '/register' || // MG_REG
            loc == '/register/phone'; // MG_PHONEVERIFY
        // MG_LEGAL: документы открыты без входа — их смотрят до регистрации, и
        // они должны быть доступны модератору стора, у которого нет аккаунта.
        final isPublicRoute = loc.startsWith('/legal');
        if (!isLoggedIn && !isAuthRoute && !isPublicRoute) return '/login';
        if (isLoggedIn && isAuthRoute) return '/menu';
        if (premiumGate.state.status == PremiumStatus.lockedForRead &&
            _premiumOnlyPaths.any((p) => state.matchedLocation.startsWith(p))) {
          return '/paywall';
        }
        return null;
      },
      routes: [
        GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
        GoRoute(path: '/register', builder: (_, __) => const RegisterScreen()), // MG_REG
        // MG_PHONEVERIFY: регистрация по телефону с подтверждением в мессенджере.
        GoRoute(
          path: '/register/phone',
          builder: (_, __) => PhoneRegisterScreen(apiClient: apiClient),
        ),
        GoRoute(path: '/paywall', builder: (_, __) => const PaywallScreen()),
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
