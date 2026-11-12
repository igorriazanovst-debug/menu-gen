// MG_NUTRIDETAIL: подробность чисел в строках еды.
//
// Настройка отображения, а не данных: числа у записи те же, меняется только
// то, что из них видно. Живёт в аккаунте, поэтому выбор переживает
// переустановку и одинаков в приложении и в вебе.
//
// Проверяется здесь то, на чём такие настройки ломаются молча: что выбор
// уходит на сервер, что чужое умолчание не затирает локальный выбор и что
// строка БЖУ не превращается в «Б 0 · Ж 0 · У 0 г» там, где чисел нет.
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/display/nutrition_detail.dart';
import 'package:menugen_app/core/display/nutrition_detail_cubit.dart';

class _MockApi extends Mock implements ApiClient {}

void main() {
  setUpAll(() => registerFallbackValue(<String, dynamic>{}));

  group('Строка БЖУ', () {
    test('буквами и с граммами один раз в конце', () {
      // Полные слова в строку записи рядом с названием блюда не помещаются и
      // обрезаются многоточием — то есть пропадает то, ради чего их показывают.
      expect(
        macrosShort(proteins: 12, fats: 8, carbs: 30),
        'Б 12 · Ж 8 · У 30 г',
      );
    });

    test('мелкие значения не округляются в ноль', () {
      // «У 0,7» — настоящее число, а «У 1» здесь было бы неправдой.
      expect(macrosShort(proteins: 13, fats: 12, carbs: 0.7), 'Б 13 · Ж 12 · У 0.7 г');
    });

    test('крупные значения — целые', () {
      // Доли грамма у 167 г — вид точности, которой у таблиц КБЖУ нет.
      expect(macrosShort(proteins: 89.4, fats: 51, carbs: 167.2), 'Б 89 · Ж 51 · У 167 г');
    });

    test('без чисел строки нет вовсе', () {
      // «Б 0 · Ж 0 · У 0 г» — это утверждение, а не «не знаем».
      expect(macrosShort(proteins: 0, fats: 0, carbs: 0), '');
    });
  });

  group('Режимы', () {
    test('кратко — только калории', () {
      expect(NutritionDetail.short.showMacros, isFalse);
      expect(NutritionDetail.short.showGrams, isFalse);
    });

    test('обычно — калории и БЖУ', () {
      expect(NutritionDetail.normal.showMacros, isTrue);
      expect(NutritionDetail.normal.showGrams, isFalse);
    });

    test('подробно — ещё и вес порции', () {
      expect(NutritionDetail.detailed.showMacros, isTrue);
      expect(NutritionDetail.detailed.showGrams, isTrue);
    });

    test('незнакомый код с сервера — умолчание, а не падение', () {
      expect(nutritionDetailFromCode('всё и сразу'), NutritionDetail.normal);
      expect(nutritionDetailFromCode(null), NutritionDetail.normal);
    });
  });

  group('Хранение выбора', () {
    late _MockApi api;

    setUp(() {
      api = _MockApi();
      when(() => api.patch(any(), data: any(named: 'data')))
          .thenAnswer((_) async => <String, dynamic>{});
      SharedPreferences.setMockInitialValues({});
    });

    Future<NutritionDetailCubit> make() async =>
        NutritionDetailCubit(prefs: await SharedPreferences.getInstance(), apiClient: api);

    test('по умолчанию — обычный режим', () async {
      final cubit = await make();

      expect(cubit.state, NutritionDetail.normal);
    });

    test('выбор уходит в аккаунт', () async {
      // Иначе он остался бы на этом телефоне, а в браузере дневник выглядел
      // бы иначе — и настройка превратилась бы в две.
      final cubit = await make();

      await cubit.set(NutritionDetail.short);

      expect(cubit.state, NutritionDetail.short);
      verify(() => api.patch('/users/me/', data: {
            'profile': {'nutrition_detail': 'short'}
          })).called(1);
    });

    test('отказ сервера не откатывает показ', () async {
      // Локально уже применено; вернуть старое значение значит показать
      // человеку, что настройка не сработала, хотя она сработала.
      when(() => api.patch(any(), data: any(named: 'data'))).thenThrow(Exception('offline'));
      final cubit = await make();

      await cubit.set(NutritionDetail.detailed);

      expect(cubit.state, NutritionDetail.detailed);
    });

    test('выбор переживает перезапуск', () async {
      final first = await make();
      await first.set(NutritionDetail.detailed);

      final second = await make();

      expect(second.state, NutritionDetail.detailed);
    });

    test('профиль с настройкой применяется при входе', () async {
      final cubit = await make();

      cubit.loadFromProfile({
        'profile': {'nutrition_detail': 'short'}
      });

      expect(cubit.state, NutritionDetail.short);
    });

    test('профиль без поля не затирает выбор', () async {
      // Сервер старше приложения — не повод молча отменять настройку.
      final cubit = await make();
      await cubit.set(NutritionDetail.short);

      cubit.loadFromProfile({'profile': <String, dynamic>{}});

      expect(cubit.state, NutritionDetail.short);
    });
  });
}
