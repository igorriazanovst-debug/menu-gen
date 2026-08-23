import 'package:app_links/app_links.dart'; // MG_VERIFYDEEPLINK
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart'; // MG_CACHE

import 'core/api/api_client.dart';
// OFFLINE: тип интерфейса
import 'core/update/update_service.dart'; // MG_SELFUPDATE
import 'core/api/caching_api_client.dart'; // OFFLINE: кэш-декоратор
import 'core/api/dio_api_client.dart';
import 'core/api/token_storage.dart';
import 'core/connectivity/connectivity_cubit.dart';
import 'core/db/app_database.dart';
import 'core/deeplink/verified_notice_cubit.dart'; // MG_VERIFYDEEPLINK
import 'core/premium/premium_gate_cubit.dart';
import 'core/router/app_router.dart';
import 'core/sync/pending_sync_cubit.dart'; // MG_T08
import 'core/sync/offline_toggle_queue.dart'; // MG_T09
import 'core/sync/offline_mutation_queue.dart'; // OFFLINE: очередь мутаций
import 'core/cache/http_cache_store.dart'; // OFFLINE: кэш GET-ответов
import 'core/cache/shopping_cache.dart'; // MG_CACHE
import 'core/sync/sync_service.dart';
import 'core/theme/app_skin.dart'; // MG_SKIN
import 'core/theme/app_theme.dart';
import 'core/theme/theme_cubit.dart'; // MG_SKIN
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
  // Сырой сетевой клиент (без кэша) — им же проигрывается офлайн-очередь.
  final dioClient = DioApiClient(tokenStorage: tokenStorage);
  final premiumGate = PremiumGateCubit();
  // Listen to API errors globally so cross-cutting UI (banner) reacts even if
  // an individual bloc swallows the error in its own state.
  premiumGate.attachErrorStream(dioClient.errorStream);

  // MG_T09: app-lifetime connectivity + pending counter + offline queue.
  final connectivity = ConnectivityCubit();
  final pendingSync = PendingSyncCubit();

  final prefs = await SharedPreferences.getInstance();

  // OFFLINE: кэш GET-ответов + очередь офлайн-мутаций + кэширующий клиент.
  // Блоки работают с [apiClient] (кэширующим) и получают офлайн-поведение
  // без изменений в самих блоках.
  final httpCache = HttpCacheStore(prefs);
  final mutationQueue = OfflineMutationQueue(
    prefs: prefs,
    connectivity: connectivity,
    pendingSync: pendingSync,
  );
  mutationQueue.bindApi(dioClient); // реплей через сырой клиент (не через кэш)
  final ApiClient apiClient = CachingApiClient(
    inner: dioClient,
    cache: httpCache,
    queue: mutationQueue,
  );
  mutationQueue.flush(); // догнать очередь прошлой сессии, если уже онлайн

  final syncService = SyncService(apiClient: apiClient, db: db);

  // MG_T09: shopping-очередь тоглов — на сыром клиенте (свой реплей).
  final offlineToggleQueue = OfflineToggleQueue(
    apiClient: dioClient,
    connectivity: connectivity,
    pendingSync: pendingSync,
  );

  // MG_CACHE: lightweight offline cache for shopping lists/details.
  final shoppingCache = ShoppingCache(prefs);

  // MG_SKIN: cubit выбранного скина (персист + синк в аккаунт).
  final themeCubit = ThemeCubit(prefs: prefs, apiClient: apiClient);

  // MG_VERIFYDEEPLINK: возврат из браузера после подтверждения e-mail.
  // Слушаем и «холодный» запуск (приложение подняли ссылкой), и «тёплый»
  // (оно уже висело в фоне) — иначе отметка появлялась бы через раз.
  final verifiedNotice = VerifiedNoticeCubit();
  final appLinks = AppLinks();
  verifiedNotice.handleLink(await appLinks.getInitialLink());
  appLinks.uriLinkStream.listen(verifiedNotice.handleLink);

  syncService.start();
  runApp(MenuGenApp(
    verifiedNotice: verifiedNotice, // MG_VERIFYDEEPLINK
    tokenStorage: tokenStorage,
    db: db,
    apiClient: apiClient,
    syncService: syncService,
    premiumGate: premiumGate,
    connectivity: connectivity, // MG_T09
    pendingSync: pendingSync, // MG_T09
    offlineToggleQueue: offlineToggleQueue, // MG_T09
    shoppingCache: shoppingCache, // MG_CACHE
    themeCubit: themeCubit, // MG_SKIN
  ));
}

class MenuGenApp extends StatelessWidget {
  final TokenStorage tokenStorage;
  final AppDatabase db;
  final ApiClient apiClient;
  final SyncService syncService;
  final PremiumGateCubit premiumGate;
  final ConnectivityCubit connectivity; // MG_T09
  final PendingSyncCubit pendingSync; // MG_T09
  final OfflineToggleQueue offlineToggleQueue; // MG_T09
  final ShoppingCache shoppingCache; // MG_CACHE
  final ThemeCubit themeCubit; // MG_SKIN
  final VerifiedNoticeCubit verifiedNotice; // MG_VERIFYDEEPLINK

  const MenuGenApp({
    super.key,
    required this.tokenStorage,
    required this.db,
    required this.apiClient,
    required this.syncService,
    required this.premiumGate,
    required this.connectivity, // MG_T09
    required this.pendingSync, // MG_T09
    required this.offlineToggleQueue, // MG_T09
    required this.shoppingCache, // MG_CACHE
    required this.themeCubit, // MG_SKIN
    required this.verifiedNotice, // MG_VERIFYDEEPLINK
  });

  @override
  Widget build(BuildContext context) {
    // MG_SELFUPDATE: сервис обновления есть только в сборке с сайта — в
    // магазинной он не подключается, и виджет-наблюдатель просто молчит.
    return RepositoryProvider<UpdateService?>.value(
      value: kSelfUpdateEnabled ? UpdateService(apiClient) : null,
      child: RepositoryProvider<ShoppingCache>.value( // MG_CACHE
      value: shoppingCache,
      child: RepositoryProvider<OfflineToggleQueue>.value( // MG_T09
      value: offlineToggleQueue,
      child: MultiBlocProvider(
      providers: [
        BlocProvider.value(value: connectivity), // MG_T09
        BlocProvider.value(value: pendingSync), // MG_T09
        BlocProvider.value(value: premiumGate),
        BlocProvider.value(value: themeCubit), // MG_SKIN
        BlocProvider.value(value: verifiedNotice), // MG_VERIFYDEEPLINK
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
      // MG_SKIN: при авторизации подтягиваем скин из профиля; тему берём из ThemeCubit.
      child: BlocListener<AuthBloc, AuthState>(
        listenWhen: (prev, curr) => curr is AuthAuthenticated,
        listener: (context, authState) {
          if (authState is AuthAuthenticated) {
            context.read<ThemeCubit>().loadFromProfile(authState.user);
          }
        },
        child: BlocBuilder<AuthBloc, AuthState>(
        builder: (context, authState) {
          final router = AppRouter.create(authState: authState, apiClient: apiClient, premiumGate: premiumGate);
          return BlocBuilder<ThemeCubit, AppSkin>(
            builder: (context, skin) => MaterialApp.router(
              title: 'MenuGen',
              theme: AppTheme.forSkin(skin), // MG_SKIN
              routerConfig: router,
              debugShowCheckedModeBanner: false,
              locale: const Locale('ru'),
              supportedLocales: const [Locale('ru'), Locale('en')],
              localizationsDelegates: const [
                GlobalMaterialLocalizations.delegate,
                GlobalWidgetsLocalizations.delegate,
                GlobalCupertinoLocalizations.delegate,
              ],
            ),
          );
        },
      ),
      ),
    ),
    ),
    ), // MG_CACHE + MG_T09: close RepositoryProvider.value
    ); // MG_SELFUPDATE: close RepositoryProvider<UpdateService?>
  }
}
