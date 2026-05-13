import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/api/api_exception.dart';
import 'package:menugen_app/core/db/app_database.dart';
import 'package:menugen_app/features/fridge/bloc/fridge_bloc.dart';

class _MockApi extends Mock implements ApiClient {}
class _MockDb extends Mock implements AppDatabase {}

void main() {
  late _MockApi api;
  late _MockDb db;
  setUp(() {
    api = _MockApi();
    db = _MockDb();
  });

  blocTest<FridgeBloc, FridgeState>(
    'emits Loading→Loaded on empty list',
    build: () {
      when(() => api.get('/fridge/', params: any(named: 'params')))
          .thenAnswer((_) async => {'results': [], 'count': 0});
      return FridgeBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const FridgeLoadRequested()),
    expect: () => [const FridgeLoading(), isA<FridgeLoaded>()],
  );

  blocTest<FridgeBloc, FridgeState>(
    'emits FridgePremiumLocked on 403',
    build: () {
      when(() => api.get('/fridge/', params: any(named: 'params'))).thenThrow(
        const ApiException(message: 'Premium required', statusCode: 403),
      );
      return FridgeBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const FridgeLoadRequested()),
    expect: () => [const FridgeLoading(), isA<FridgePremiumLocked>()],
  );

  blocTest<FridgeBloc, FridgeState>(
    'emits FridgeError on generic exception',
    build: () {
      when(() => api.get('/fridge/', params: any(named: 'params')))
          .thenThrow(Exception('boom'));
      return FridgeBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const FridgeLoadRequested()),
    expect: () => [const FridgeLoading(), isA<FridgeError>()],
  );
}
