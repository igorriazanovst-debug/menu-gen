import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/api/api_exception.dart';
import 'package:menugen_app/core/db/app_database.dart';
import 'package:menugen_app/features/menu/bloc/menu_bloc.dart';

class _MockApi extends Mock implements ApiClient {}
class _MockDb extends Mock implements AppDatabase {}

void main() {
  late _MockApi api;
  late _MockDb db;

  setUp(() {
    api = _MockApi();
    db = _MockDb();
  });

  blocTest<MenuBloc, MenuState>(
    'emits Loaded with empty list on no menus',
    build: () {
      when(() => api.get('/menu/', params: any(named: 'params')))
          .thenAnswer((_) async => {'results': [], 'count': 0});
      return MenuBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const MenuLoadRequested()),
    expect: () => [
      const MenuLoading(),
      const MenuLoaded(menus: <Map<String, dynamic>>[]),
    ],
  );

  blocTest<MenuBloc, MenuState>(
    'emits Error on generic failure',
    build: () {
      when(() => api.get('/menu/', params: any(named: 'params')))
          .thenThrow(Exception('boom'));
      return MenuBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const MenuLoadRequested()),
    expect: () => [const MenuLoading(), isA<MenuError>()],
  );

  blocTest<MenuBloc, MenuState>(
    'emits MenuPremiumLocked on 403 read',
    build: () {
      when(() => api.get('/menu/', params: any(named: 'params'))).thenThrow(
        const ApiException(message: 'Premium required', statusCode: 403),
      );
      return MenuBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const MenuLoadRequested()),
    expect: () => [
      const MenuLoading(),
      isA<MenuPremiumLocked>().having((s) => s.isWrite, 'isWrite', false),
    ],
  );

  blocTest<MenuBloc, MenuState>(
    'emits MenuPremiumLocked(write=true) on 403 generate',
    build: () {
      when(() => api.post('/menu/generate/', data: any(named: 'data'))).thenThrow(
        const ApiException(message: 'Need active premium', statusCode: 403),
      );
      return MenuBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const MenuGenerateRequested(startDate: '2026-05-13')),
    expect: () => [
      const MenuGenerating(),
      isA<MenuPremiumLocked>().having((s) => s.isWrite, 'isWrite', true),
    ],
  );

  // ── MG_MENUEXPIRE: архив меню ──────────────────────────────────────────────
  //
  // Меню, чей срок вышел, уходит из списка актуальных. Единственный путь к нему
  // после этого — архив, поэтому проверяется, что блок за ним вообще ходит и
  // что признак архива доживает до состояния: по нему экран подписывает
  // заголовок, иначе прошлогоднее меню не отличить от текущего.

  blocTest<MenuBloc, MenuState>(
    'MG_MENUEXPIRE: архив читается со своего адреса',
    build: () {
      when(() => api.get('/menu/?archived=true', params: any(named: 'params')))
          .thenAnswer((_) async => {'results': [], 'count': 0});
      return MenuBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const MenuLoadRequested(archived: true)),
    expect: () => [
      const MenuLoading(),
      const MenuLoaded(menus: <Map<String, dynamic>>[], archived: true),
    ],
    verify: (_) {
      verifyNever(() => api.get('/menu/', params: any(named: 'params')));
    },
  );

  blocTest<MenuBloc, MenuState>(
    'MG_MENUEXPIRE: признак архива доживает до состояния с меню',
    build: () {
      when(() => api.get('/menu/?archived=true', params: any(named: 'params')))
          .thenAnswer((_) async => {
                'results': [
                  {'id': 7, 'start_date': '2026-01-01', 'end_date': '2026-01-07'}
                ],
                'count': 1,
              });
      when(() => api.get('/menu/7/', params: any(named: 'params')))
          .thenAnswer((_) async => {'id': 7, 'items': <dynamic>[]});
      return MenuBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const MenuLoadRequested(archived: true)),
    expect: () => [
      const MenuLoading(),
      isA<MenuLoaded>()
          .having((s) => s.archived, 'archived', true)
          .having((s) => s.active?['id'], 'active.id', 7),
    ],
  );

  blocTest<MenuBloc, MenuState>(
    'MG_MENUEXPIRE: по умолчанию список — актуальный',
    build: () {
      when(() => api.get('/menu/', params: any(named: 'params')))
          .thenAnswer((_) async => {'results': [], 'count': 0});
      return MenuBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const MenuLoadRequested()),
    expect: () => [
      const MenuLoading(),
      const MenuLoaded(menus: <Map<String, dynamic>>[], archived: false),
    ],
    verify: (_) {
      verifyNever(
        () => api.get('/menu/?archived=true', params: any(named: 'params')),
      );
    },
  );
}
