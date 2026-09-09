// MG_HEADKEEPS + MG_BODYSIZE: записи за участника и обхваты тела.
//
// Проверяется то, на чём такие вещи ломаются молча: уходит ли участник в
// запрос. Раньше `member_id` был в событии, но до сервера не доходил — глава
// семьи добавлял еду в чужой дневник, а она ложилась в его собственный день.
// Ошибка тихая: экран показывает успех, а запись не там.
//
// Плюс разбор ответа: корона рисуется по `added_by_name`, и её отсутствие
// значит «внёс сам» — так у всех записей, сделанных до этой возможности.
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/db/app_database.dart';
import 'package:menugen_app/features/diary/bloc/diary_bloc.dart';
import 'package:menugen_app/features/diary/models/diary_entry.dart';

class _MockApi extends Mock implements ApiClient {}

class _MockDb extends Mock implements AppDatabase {}

Map<String, dynamic> _entryJson({String? addedBy}) => {
      'id': 1,
      'date': '2026-09-09',
      'meal_type': 'lunch',
      'meal_slot': 'lunch',
      'custom_name': 'Проверочное',
      'nutrition': <String, dynamic>{},
      'quantity': 1,
      'is_eaten': true,
      if (addedBy != null) 'added_by_name': addedBy,
    };

void main() {
  late _MockApi api;
  late _MockDb db;

  setUp(() {
    api = _MockApi();
    db = _MockDb();
    registerFallbackValue(<String, dynamic>{});
  });

  group('MG_HEADKEEPS: разбор ответа', () {
    test('имя автора попадает в запись', () {
      final entry = DiaryEntry.fromJson(_entryJson(addedBy: 'Ольга'));
      expect(entry.addedByName, 'Ольга');
    });

    test('своя запись — без автора', () {
      // Пустое поле значит «внёс сам»: короны у такой записи быть не должно.
      final entry = DiaryEntry.fromJson(_entryJson());
      expect(entry.addedByName, isNull);
    });
  });

  group('MG_DAYFIX: отметку за день можно убрать', () {
    blocTest<DiaryBloc, DiaryState>(
      'своя вода стирается запросом с датой',
      build: () {
        when(() => api.delete('/diary/water/?date=2026-09-09'))
            .thenAnswer((_) async => null);
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const DiaryWaterClearRequested(date: '2026-09-09')),
      verify: (_) {
        verify(() => api.delete('/diary/water/?date=2026-09-09')).called(1);
      },
    );

    blocTest<DiaryBloc, DiaryState>(
      'вода участника стирается с member_id',
      build: () {
        when(() => api.delete('/diary/water/?date=2026-09-09&member_id=7'))
            .thenAnswer((_) async => null);
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const DiaryWaterClearRequested(date: '2026-09-09', memberId: 7)),
      verify: (_) {
        // Своя ручка не дёргается: иначе стёрлась бы собственная отметка.
        verifyNever(() => api.delete('/diary/water/?date=2026-09-09'));
      },
    );
  });

  group('MG_HEADKEEPS: участник доходит до сервера', () {
    blocTest<DiaryBloc, DiaryState>(
      'вода за участника уходит с member_id',
      build: () {
        when(() => api.post('/diary/water/?member_id=7', data: any(named: 'data')))
            .thenAnswer((_) async => {'water_ml': 500, 'added_by_name': 'Ольга'});
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const DiaryWaterSetRequested(
        date: '2026-09-09',
        waterMl: 500,
        memberId: 7,
      )),
      verify: (_) {
        verify(() => api.post('/diary/water/?member_id=7', data: any(named: 'data'))).called(1);
        // Своя ручка при этом не дёргается: иначе вода легла бы себе.
        verifyNever(() => api.post('/diary/water/', data: any(named: 'data')));
      },
    );

    blocTest<DiaryBloc, DiaryState>(
      'своя вода уходит без member_id',
      build: () {
        when(() => api.post('/diary/water/', data: any(named: 'data')))
            .thenAnswer((_) async => {'water_ml': 300});
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const DiaryWaterSetRequested(date: '2026-09-09', waterMl: 300)),
      verify: (_) {
        verify(() => api.post('/diary/water/', data: any(named: 'data'))).called(1);
      },
    );
  });
}
