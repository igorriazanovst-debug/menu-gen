// MG_FOODSCALE: размер шрифта в списках еды.
//
// Множитель к системному размеру, а не замена ему: системный выбор человека
// остаётся в силе, наш только уточняет его для дневника. Поэтому градации
// умеренные — «крупный» поверх системного «крупного» и так даёт заметный
// шрифт, а удвоение превратило бы строку в пол-экрана.
//
// Почему от этого ничего не ломается: раскладка строки еды нигде не держится
// на фиксированных ширинах. Название переносится (до трёх строк), БЖУ и
// калорийность переносятся друг под друга (Wrap), заголовок приёма тоже
// переносится. Проверки гоняются на худшем сочетании — наш «крупный» ×
// системный ×1,3.

enum FoodTextScale { small, normal, large }

extension FoodTextScaleX on FoodTextScale {
  String get code {
    switch (this) {
      case FoodTextScale.small:
        return 'small';
      case FoodTextScale.large:
        return 'large';
      case FoodTextScale.normal:
        return 'normal';
    }
  }

  String get label {
    switch (this) {
      case FoodTextScale.small:
        return 'Мелкий';
      case FoodTextScale.large:
        return 'Крупный';
      case FoodTextScale.normal:
        return 'Обычный';
    }
  }

  /// Множитель к системному размеру.
  double get factor {
    switch (this) {
      case FoodTextScale.small:
        return 0.9;
      case FoodTextScale.large:
        return 1.15;
      case FoodTextScale.normal:
        return 1.0;
    }
  }
}

FoodTextScale foodTextScaleFromCode(String? code) {
  switch (code) {
    case 'small':
      return FoodTextScale.small;
    case 'large':
      return FoodTextScale.large;
    default:
      // Незнакомое значение — обычный размер, а не исключение: сервер старше
      // или новее приложения не повод показывать пустой экран.
      return FoodTextScale.normal;
  }
}
