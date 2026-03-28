import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'core/api/api_client.dart';
import 'core/api/token_storage.dart';
import 'core/connectivity/connectivity_cubit.dart';
import 'core/db/app_database.dart';
import 'core/router/app_router.dart';
import 'core/sync/sync_service.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/bloc/auth_bloc.dart';
import 'features/menu/bloc/menu_bloc.dart';
import 'features/recipes/bloc/recipes_bloc.dart';
import 'features/fridge/bloc/fridge_bloc.dart';
import 'features/diary/bloc/diary_bloc.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final tokenStorage = TokenStorage();
  final db = AppDatabase();
  final apiClient = ApiClient(tokenStorage: tokenStorage);
  final syncService = SyncService(apiClient: apiClient, db: db);
  syncService.start();

  runApp(MenuGenApp(
    tokenStorage: tokenStorage,
    db: db,
    apiClient: apiClient,
    syncService: syncService,
  ));
}

class MenuGenApp extends StatelessWidget {
  final TokenStorage tokenStorage;
  final AppDatabase db;
  final ApiClient apiClient;
  final SyncService syncService;

  const MenuGenApp({
    super.key,
    required this.tokenStorage,
    required this.db,
    required this.apiClient,
    required this.syncService,
  });

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider(create: (_) => ConnectivityCubit()),
        BlocProvider(create: (_) => AuthBloc(apiClient: apiClient, tokenStorage: tokenStorage)
          ..add(const AuthCheckRequested())),
        BlocProvider(create: (_) => MenuBloc(apiClient: apiClient, db: db)),
        BlocProvider(create: (_) => RecipesBloc(apiClient: apiClient, db: db)),
        BlocProvider(create: (_) => FridgeBloc(apiClient: apiClient, db: db)),
        BlocProvider(create: (_) => DiaryBloc(apiClient: apiClient, db: db)),
      ],
      child: BlocBuilder<AuthBloc, AuthState>(
        builder: (context, authState) {
          final router = AppRouter.create(
            authState: authState,
            apiClient: apiClient,
          );
          return MaterialApp.router(
            title: 'MenuGen',
            theme: AppTheme.light(),
            darkTheme: AppTheme.dark(),
            themeMode: ThemeMode.system,
            routerConfig: router,
            debugShowCheckedModeBanner: false,
          );
        },
      ),
    );
  }
}
