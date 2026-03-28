import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/db/app_database.dart';
import 'package:menugen_app/features/menu/bloc/menu_bloc.dart';

class MockApiClient extends Mock implements ApiClient {}
class MockAppDatabase extends Mock implements AppDatabase {}
class _R { final dynamic data; _R(this.data); }

void main() {
  late MockApiClient api;
  late MockAppDatabase db;
  setUp(() { api = MockApiClient(); db = MockAppDatabase(); });

  group('MenuBloc', () {
    blocTest<MenuBloc, MenuState>(
      'emits [Loading, Loaded] on load success',
      build: () {
        when(() => api.get('/menu/', params: any(named: 'params')))
            .thenAnswer((_) async => _R({'results': [], 'count': 0}) as dynamic);
        return MenuBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(MenuLoadRequested()),
      expect: () => [const MenuLoading(), const MenuLoaded(menus: [])],
    );

    blocTest<MenuBloc, MenuState>(
      'emits [Loading, Error] on load failure',
      build: () {
        when(() => api.get('/menu/', params: any(named: 'params')))
            .thenThrow(Exception('err'));
        return MenuBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(MenuLoadRequested()),
      expect: () => [const MenuLoading(), isA<MenuError>()],
    );

    blocTest<MenuBloc, MenuState>(
      'emits [Generating, Generated] on generate success',
      build: () {
        when(() => api.post('/menu/generate/', data: any(named: 'data')))
            .thenAnswer((_) async => _R({
              'id': 1, 'start_date': '2026-03-01', 'end_date': '2026-03-07',
              'period_days': 7, 'items': [],
            }) as dynamic);
        return MenuBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const MenuGenerateRequested(startDate: '2026-03-01')),
      expect: () => [const MenuGenerating(), isA<MenuGenerated>()],
    );

    blocTest<MenuBloc, MenuState>(
      'emits [Generating, Error] on generate failure',
      build: () {
        when(() => api.post('/menu/generate/', data: any(named: 'data')))
            .thenThrow(Exception('err'));
        return MenuBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const MenuGenerateRequested(startDate: '2026-03-01')),
      expect: () => [const MenuGenerating(), isA<MenuError>()],
    );
  });
}