import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'core/api/dio_api_client.dart';
import 'core/api/token_storage.dart';
import 'core/connectivity/connectivity_cubit.dart';
import 'core/db/app_database.dart';
import 'core/premium/premium_gate_cubit.dart';
import 'core/router/app_router.dart';
import 'core/sync/sync_service.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/bloc/auth_bloc.dart';
import 'features/diary/bloc/diary_bloc.dart';
import 'features/fridge/bloc/fridge_bloc.dart';
import 'features/menu/bloc/menu_bloc.dart';
import 'features/recipes/bloc/recipes_bloc.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('ru', null);

  final tokenStorage = TokenStorage();
  final db = AppDatabase();
  final apiClient = DioApiClient(tokenStorage: tokenStorage);
  final syncService = SyncService(apiClient: apiClient, db: db);
  final premiumGate = PremiumGateCubit();
  // Listen to API errors globally so cross-cutting UI (banner) reacts even if
  // an individual bloc swallows the error in its own state.
  premiumGate.attachErrorStream(apiClient.errorStream);

  syncService.start();
  runApp(MenuGenApp(
    tokenStorage: tokenStorage,
    db: db,
    apiClient: apiClient,
    syncService: syncService,
    premiumGate: premiumGate,
  ));
}

class MenuGenApp extends StatelessWidget {
  final TokenStorage tokenStorage;
  final AppDatabase db;
  final DioApiClient apiClient;
  final SyncService syncService;
  final PremiumGateCubit premiumGate;

  const MenuGenApp({
    super.key,
    required this.tokenStorage,
    required this.db,
    required this.apiClient,
    required this.syncService,
    required this.premiumGate,
  });

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider(create: (_) => ConnectivityCubit()),
        BlocProvider.value(value: premiumGate),
        BlocProvider(
          create: (_) => AuthBloc(
            apiClient: apiClient,
            tokenStorage: tokenStorage,
            premiumGate: premiumGate,
          )
            ..add(const AuthCheckRequested()),
        ),
        BlocProvider(create: (_) => MenuBloc(apiClient: apiClient, db: db, premiumGate: premiumGate)),
        BlocProvider(create: (_) => RecipesBloc(apiClient: apiClient, db: db)),
        BlocProvider(create: (_) => FridgeBloc(apiClient: apiClient, db: db, premiumGate: premiumGate)),
        BlocProvider(create: (_) => DiaryBloc(apiClient: apiClient, db: db, premiumGate: premiumGate)),
      ],
      child: BlocBuilder<AuthBloc, AuthState>(
        builder: (context, authState) {
          final router = AppRouter.create(authState: authState, apiClient: apiClient);
          return MaterialApp.router(
            title: 'MenuGen',
            theme: AppTheme.light(),
            darkTheme: AppTheme.dark(),
            themeMode: ThemeMode.system,
            routerConfig: router,
            debugShowCheckedModeBanner: false,
            locale: const Locale('ru'),
            supportedLocales: const [Locale('ru'), Locale('en')],
            localizationsDelegates: const [
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
          );
        },
      ),
    );
  }
}
