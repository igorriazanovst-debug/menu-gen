import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/api/api_exception.dart';
import 'package:menugen_app/core/db/app_database.dart';
import 'package:menugen_app/features/diary/bloc/diary_bloc.dart';
import 'package:menugen_app/features/diary/models/diary_entry.dart';
import 'package:menugen_app/features/diary/models/diary_stats.dart';

class _MockApi extends Mock implements ApiClient {}
class _MockDb extends Mock implements AppDatabase {}

void main() {
  late _MockApi api;
  late _MockDb db;

  setUp(() {
    api = _MockApi();
    db = _MockDb();
  });

  group('DiaryBloc.load', () {
    blocTest<DiaryBloc, DiaryState>(
      'emits Loading then Loaded with parsed entries',
      build: () {
        when(() => api.get('/diary/', params: any(named: 'params'))).thenAnswer(
          (_) async => {
            'count': 1,
            'results': [
              {
                'id': 7,
                'date': '2026-05-13',
                'meal_type': 'breakfast',
                'recipe': null,
                'recipe_title': null,
                'custom_name': 'Овсянка',
                'nutrition': {},
                'quantity': '1.00',
                'planned_menu_item': null,
                'is_eaten': true,
              }
            ],
          },
        );
        when(() => api.get('/diary/stats/', params: any(named: 'params'))).thenAnswer(
          (_) async => [
            {
              'date': '2026-05-13',
              'planned': {'calories': 0, 'proteins': 0, 'fats': 0, 'carbs': 0},
              'actual':  {'calories': 100, 'proteins': 3, 'fats': 2, 'carbs': 18},
              'total':   {'calories': 100, 'proteins': 3, 'fats': 2, 'carbs': 18},
            }
          ],
        );
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const DiaryLoadRequested(date: '2026-05-13')),
      expect: () => [
        const DiaryLoading(),
        isA<DiaryLoaded>()
            .having((s) => s.date, 'date', '2026-05-13')
            .having((s) => s.entries.length, 'entries.length', 1)
            .having((s) => s.entries.first.mealType, 'mealType', MealType.breakfast),
      ],
    );

    blocTest<DiaryBloc, DiaryState>(
      'maps 403 ApiException to DiaryPremiumLocked',
      build: () {
        when(() => api.get('/diary/', params: any(named: 'params'))).thenThrow(
          const ApiException(message: 'Premium required', statusCode: 403),
        );
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const DiaryLoadRequested(date: '2026-05-13')),
      expect: () => [
        const DiaryLoading(),
        isA<DiaryPremiumLocked>()
            .having((s) => s.isWrite, 'isWrite', false)
            .having((s) => s.message, 'message', 'Premium required'),
      ],
    );

    blocTest<DiaryBloc, DiaryState>(
      'maps generic error to DiaryError',
      build: () {
        when(() => api.get('/diary/', params: any(named: 'params')))
            .thenThrow(Exception('boom'));
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const DiaryLoadRequested(date: '2026-05-13')),
      expect: () => [const DiaryLoading(), isA<DiaryError>()],
    );
  });

  group('DiaryBloc.markEaten', () {
    blocTest<DiaryBloc, DiaryState>(
      'patches /diary/{id}/ with is_eaten payload',
      build: () {
        when(() => api.get('/diary/', params: any(named: 'params'))).thenAnswer(
          (_) async => {
            'results': [
              {
                'id': 1,
                'date': '2026-05-13',
                'meal_type': 'lunch',
                'recipe': null,
                'recipe_title': null,
                'custom_name': 'Суп',
                'nutrition': {},
                'quantity': 1,
                'planned_menu_item': 99,
                'is_eaten': false,
              }
            ],
          },
        );
        when(() => api.get('/diary/stats/', params: any(named: 'params')))
            .thenAnswer((_) async => const []);
        when(() => api.patch('/diary/1/', data: any(named: 'data')))
            .thenAnswer((_) async => {});
        return DiaryBloc(apiClient: api, db: db);
      },
      seed: () => DiaryLoaded(
        date: '2026-05-13',
        memberId: null,
        entries: const [],
        stats: const DiaryDayStats(
          date: '2026-05-13',
          planned: NutritionBucket.zero(),
          actual: NutritionBucket.zero(),
          total: NutritionBucket.zero(),
        ),
      ),
      act: (b) async {
        b.add(const DiaryLoadRequested(date: '2026-05-13'));
        await Future<void>.delayed(const Duration(milliseconds: 50));
        b.add(const DiaryMarkEatenRequested(entryId: 1, isEaten: true));
        await Future<void>.delayed(const Duration(milliseconds: 50));
      },
      verify: (_) {
        verify(() => api.patch('/diary/1/', data: {'is_eaten': true})).called(1);
      },
    );
  });
}
