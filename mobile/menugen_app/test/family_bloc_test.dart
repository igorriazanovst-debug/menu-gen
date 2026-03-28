import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/features/family/bloc/family_bloc.dart';

class MockApiClient extends Mock implements ApiClient {}
class _R { final dynamic data; _R(this.data); }

void main() {
  late MockApiClient api;
  setUp(() { api = MockApiClient(); });

  group('FamilyBloc', () {
    blocTest<FamilyBloc, FamilyState>(
      'emits [Loading, Loaded] on load success',
      build: () {
        when(() => api.get('/family/', params: any(named: 'params')))
            .thenAnswer((_) async => _R({
              'id': 1, 'name': 'Семья', 'owner': 1, 'members': [],
            }) as dynamic);
        return FamilyBloc(apiClient: api);
      },
      act: (b) => b.add(const FamilyLoadRequested()),
      expect: () => [const FamilyLoading(), isA<FamilyLoaded>()],
    );

    blocTest<FamilyBloc, FamilyState>(
      'emits [Loading, Error] on load failure',
      build: () {
        when(() => api.get('/family/', params: any(named: 'params')))
            .thenThrow(Exception('err'));
        return FamilyBloc(apiClient: api);
      },
      act: (b) => b.add(const FamilyLoadRequested()),
      expect: () => [const FamilyLoading(), isA<FamilyError>()],
    );

    blocTest<FamilyBloc, FamilyState>(
      'emits [Error] on invite failure',
      build: () {
        when(() => api.post('/family/invite/', data: any(named: 'data')))
            .thenThrow(Exception('err'));
        return FamilyBloc(apiClient: api);
      },
      act: (b) => b.add(FamilyInviteMemberRequested('x@x.com')),
      expect: () => [isA<FamilyError>()],
    );

    blocTest<FamilyBloc, FamilyState>(
      'emits [Error] on remove failure',
      build: () {
        when(() => api.delete(any())).thenThrow(Exception('err'));
        return FamilyBloc(apiClient: api);
      },
      act: (b) => b.add(FamilyRemoveMemberRequested(1)),
      expect: () => [isA<FamilyError>()],
    );
  });
}