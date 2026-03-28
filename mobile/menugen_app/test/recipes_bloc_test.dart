import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/db/app_database.dart';
import 'package:menugen_app/features/recipes/bloc/recipes_bloc.dart';

class MockApiClient extends Mock implements ApiClient {}
class MockAppDatabase extends Mock implements AppDatabase {}
class _R { final dynamic data; _R(this.data); }

void main() {
  late MockApiClient api;
  late MockAppDatabase db;
  setUp(() { api = MockApiClient(); db = MockAppDatabase(); });

  group('RecipesBloc', () {
    blocTest<RecipesBloc, RecipesState>(
      'emits [Loading, Loaded] on load success',
      build: () {
        when(() => api.get('/recipes/', params: any(named: 'params')))
            .thenAnswer((_) async => _R({'results': [], 'count': 0}) as dynamic);
        return RecipesBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const RecipesLoadRequested()),
      expect: () => [const RecipesLoading(), const RecipesLoaded(recipes: [])],
    );

    blocTest<RecipesBloc, RecipesState>(
      'emits [Loading, Loaded] on search success',
      build: () {
        when(() => api.get('/recipes/', params: any(named: 'params')))
            .thenAnswer((_) async => _R({'results': [], 'count': 0}) as dynamic);
        return RecipesBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(RecipesSearchRequested('борщ')),
      expect: () => [const RecipesLoading(), const RecipesLoaded(recipes: [])],
    );

    blocTest<RecipesBloc, RecipesState>(
      'emits [Loading, Error] on load failure',
      build: () {
        when(() => api.get('/recipes/', params: any(named: 'params')))
            .thenThrow(Exception('err'));
        return RecipesBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const RecipesLoadRequested()),
      expect: () => [const RecipesLoading(), isA<RecipesError>()],
    );

    blocTest<RecipesBloc, RecipesState>(
      'emits [Loading, Error] on search failure',
      build: () {
        when(() => api.get('/recipes/', params: any(named: 'params')))
            .thenThrow(Exception('err'));
        return RecipesBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(RecipesSearchRequested('борщ')),
      expect: () => [const RecipesLoading(), isA<RecipesError>()],
    );
  });
}