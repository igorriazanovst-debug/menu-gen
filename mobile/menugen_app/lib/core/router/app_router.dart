import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../features/auth/screens/login_screen.dart';
import '../../features/auth/bloc/auth_bloc.dart';
import '../../features/menu/screens/menu_screen.dart';
import '../../features/recipes/screens/recipes_screen.dart';
import '../../features/fridge/screens/fridge_screen.dart';
import '../../features/diary/screens/diary_screen.dart';
import '../../features/profile/screens/profile_screen.dart';
import '../../features/family/screens/family_screen.dart';
import '../../features/shopping/screens/shopping_list_screen.dart';
import '../api/api_client.dart';
import '../widgets/main_shell.dart';

class AppRouter {
  static GoRouter create({required AuthState authState, required ApiClient apiClient}) {
    return GoRouter(
      initialLocation: '/menu',
      redirect: (context, state) {
        final isLoggedIn = authState is AuthAuthenticated;
        final isLoggingIn = state.matchedLocation == '/login';
        if (!isLoggedIn && !isLoggingIn) return '/login';
        if (isLoggedIn && isLoggingIn) return '/menu';
        return null;
      },
      routes: [
        GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
        ShellRoute(
          builder: (context, state, child) => MainShell(child: child),
          routes: [
            GoRoute(path: '/menu',    builder: (_, __) => const MenuScreen()),
            GoRoute(path: '/recipes', builder: (_, __) => const RecipesScreen()),
            GoRoute(path: '/fridge',  builder: (_, __) => const FridgeScreen()),
            GoRoute(path: '/diary',   builder: (_, __) => const DiaryScreen()),
            GoRoute(path: '/profile', builder: (_, state) => ProfileScreen(apiClient: apiClient)),
          ],
        ),
        // Full-screen routes (outside shell)
        GoRoute(
          path: '/family',
          builder: (_, __) => FamilyScreen(apiClient: apiClient),
        ),
        GoRoute(
          path: '/shopping/:menuId',
          builder: (_, state) => ShoppingListScreen(
            apiClient: apiClient,
            menuId: int.parse(state.pathParameters['menuId']!),
          ),
        ),
      ],
    );
  }
}
