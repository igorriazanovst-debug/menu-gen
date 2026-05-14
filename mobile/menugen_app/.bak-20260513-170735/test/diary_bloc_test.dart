import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/db/app_database.dart';
import 'package:menugen_app/features/diary/bloc/diary_bloc.dart';

class MockApiClient extends Mock implements ApiClient {}
class MockAppDatabase extends Mock implements AppDatabase {}
class _R { final dynamic data; _R(this.data); }

void main() {
  late MockApiClient api;
  late MockAppDatabase db;
  setUp(() { api = MockApiClient(); db = MockAppDatabase(); });

  group('DiaryBloc', () {
    blocTest<DiaryBloc, DiaryState>(
      'emits [Loading, Loaded] on load success',
      build: () {
        when(() => api.get('/diary/', params: any(named: 'params')))
            .thenAnswer((_) async => _R({'results': [], 'count': 0}) as dynamic);
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(DiaryLoadRequested('2026-03-28')),
      expect: () => [const DiaryLoading(), isA<DiaryLoaded>()],
    );

    blocTest<DiaryBloc, DiaryState>(
      'DiaryLoaded has correct date',
      build: () {
        when(() => api.get('/diary/', params: any(named: 'params')))
            .thenAnswer((_) async => _R({'results': [], 'count': 0}) as dynamic);
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(DiaryLoadRequested('2026-03-28')),
      expect: () => [
        const DiaryLoading(),
        isA<DiaryLoaded>().having((s) => s.date, 'date', '2026-03-28'),
      ],
    );

    blocTest<DiaryBloc, DiaryState>(
      'emits [Loading, Error] on load failure',
      build: () {
        when(() => api.get('/diary/', params: any(named: 'params')))
            .thenThrow(Exception('err'));
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(DiaryLoadRequested('2026-03-28')),
      expect: () => [const DiaryLoading(), isA<DiaryError>()],
    );
  });
}