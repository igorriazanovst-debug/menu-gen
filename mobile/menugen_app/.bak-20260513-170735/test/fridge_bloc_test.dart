import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/db/app_database.dart';
import 'package:menugen_app/features/fridge/bloc/fridge_bloc.dart';

class MockApiClient extends Mock implements ApiClient {}
class MockAppDatabase extends Mock implements AppDatabase {}
class _R { final dynamic data; _R(this.data); }

void main() {
  late MockApiClient api;
  late MockAppDatabase db;
  setUp(() { api = MockApiClient(); db = MockAppDatabase(); });

  group('FridgeBloc', () {
    blocTest<FridgeBloc, FridgeState>(
      'emits [Loading, Loaded] on load success',
      build: () {
        when(() => api.get('/fridge/', params: any(named: 'params')))
            .thenAnswer((_) async => _R({'results': [], 'count': 0}) as dynamic);
        return FridgeBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const FridgeLoadRequested()),
      expect: () => [const FridgeLoading(), const FridgeLoaded(items: [])],
    );

    blocTest<FridgeBloc, FridgeState>(
      'emits [Loading, Error] on load failure',
      build: () {
        when(() => api.get('/fridge/', params: any(named: 'params')))
            .thenThrow(Exception('err'));
        return FridgeBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const FridgeLoadRequested()),
      expect: () => [const FridgeLoading(), isA<FridgeError>()],
    );

    blocTest<FridgeBloc, FridgeState>(
      'emits [Error] on add failure',
      build: () {
        when(() => api.post('/fridge/', data: any(named: 'data')))
            .thenThrow(Exception('err'));
        return FridgeBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(FridgeItemAdded({'name': 'Молоко'})),
      expect: () => [isA<FridgeError>()],
    );

    blocTest<FridgeBloc, FridgeState>(
      'emits [Error] on delete failure',
      build: () {
        when(() => api.delete(any())).thenThrow(Exception('err'));
        return FridgeBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(FridgeItemDeleted(1)),
      expect: () => [isA<FridgeError>()],
    );
  });
}