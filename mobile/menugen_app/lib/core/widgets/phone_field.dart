// MG_PHONECODE: поле телефона с выбором кода страны.
//
// Было: одно поле с подсказкой «+7 900 000-00-00». Подсказка серая, исчезает от
// первой цифры, и человек с российским номером всё равно каждый раз набирал код
// сам — а часть набирала «8», потому что так привычнее.
//
// Стало: код выбирается списком (по умолчанию +7), в поле остаётся сам номер.
// Наружу через контроллер отдаётся склеенная строка «+79001234567».
//
// Контроллер снаружи, а не внутри виджета, намеренно: экраны входа и регистрации
// уже держат TextEditingController и читают из него при отправке. Своё
// внутреннее состояние потребовало бы колбэка и второго источника правды.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class PhoneCountry {
  final String code;
  final String label;
  const PhoneCountry(this.code, this.label);
}

/// Порядок намеренно не алфавитный: сверху то, что выбирают чаще всего.
///
/// Список короткий и осознанный: Россия и соседи плюс несколько популярных.
/// Полный справочник ISO сюда не тянем — двести строк в выпадающем списке ради
/// полноты сделали бы выбор медленнее, а не точнее. Понадобится ещё страна —
/// дописывается сюда одной строкой, и это единственное место на всё приложение.
///
/// Казахстана отдельной строкой НЕТ намеренно: у него тот же код +7, что и у
/// России, и вторая строка «+7» выглядела бы опечаткой.
const phoneCountries = <PhoneCountry>[
  PhoneCountry('+7', '🇷🇺 +7'),
  PhoneCountry('+375', '🇧🇾 +375'),
  PhoneCountry('+380', '🇺🇦 +380'),
  PhoneCountry('+995', '🇬🇪 +995'),
  PhoneCountry('+374', '🇦🇲 +374'),
  PhoneCountry('+994', '🇦🇿 +994'),
  PhoneCountry('+996', '🇰🇬 +996'),
  PhoneCountry('+998', '🇺🇿 +998'),
  PhoneCountry('+992', '🇹🇯 +992'),
  PhoneCountry('+373', '🇲🇩 +373'),
  PhoneCountry('+371', '🇱🇻 +371'),
  PhoneCountry('+370', '🇱🇹 +370'),
  PhoneCountry('+372', '🇪🇪 +372'),
  PhoneCountry('+90', '🇹🇷 +90'),
  PhoneCountry('+972', '🇮🇱 +972'),
  PhoneCountry('+49', '🇩🇪 +49'),
  PhoneCountry('+44', '🇬🇧 +44'),
  PhoneCountry('+1', '🇺🇸 +1'),
];

const defaultPhoneCode = '+7';

/// Разбирает «+79001234567» на код страны и остаток номера.
///
/// Коды примеряются от длинных к коротким: иначе «+3» съел бы начало «+375»
/// раньше, чем тот успел бы совпасть.
({String code, String rest}) splitPhone(String value) {
  final raw = value.trim();
  if (raw.isEmpty) return (code: defaultPhoneCode, rest: '');
  // Сравниваем всегда в виде «+цифры»: ведущий плюс человек то ставит, то нет,
  // а на разбор кода это влиять не должно.
  final digitsOnly = raw.replaceAll(RegExp(r'\D'), '');
  final normalized = '+$digitsOnly';
  final codes = phoneCountries.map((c) => c.code).toList()
    ..sort((a, b) => b.length.compareTo(a.length));
  for (final code in codes) {
    if (normalized.startsWith(code)) {
      return (code: code, rest: normalized.substring(code.length));
    }
  }
  return (code: defaultPhoneCode, rest: digitsOnly);
}

class PhoneField extends StatefulWidget {
  /// Держит ПОЛНЫЙ номер вместе с кодом — именно его читают экраны.
  final TextEditingController controller;
  final String label;
  final String? helperText;
  final bool enabled;

  const PhoneField({
    super.key,
    required this.controller,
    this.label = 'Телефон',
    this.helperText,
    this.enabled = true,
  });

  @override
  State<PhoneField> createState() => _PhoneFieldState();
}

class _PhoneFieldState extends State<PhoneField> {
  late String _code;
  late final TextEditingController _rest;

  @override
  void initState() {
    super.initState();
    final parts = splitPhone(widget.controller.text);
    _code = parts.code;
    _rest = TextEditingController(text: parts.rest);
    _push();
  }

  @override
  void dispose() {
    _rest.dispose();
    super.dispose();
  }

  /// Собрать полный номер во внешний контроллер.
  void _push() => widget.controller.text = '$_code${_rest.text}';

  void _onRestChanged(String value) {
    final digits = value.replaceAll(RegExp(r'\D'), '');

    // Вставили номер целиком, вместе с кодом страны — тогда код берём из него,
    // иначе получилось бы «+7+79001234567». Условие про длину отличает вставку
    // от набора: плюс, набранный руками, приходит сюда один, без цифр.
    if (value.trimLeft().startsWith('+') && digits.length >= 8) {
      final parts = splitPhone(value);
      setState(() => _code = parts.code);
      _rest.value = TextEditingValue(
        text: parts.rest,
        selection: TextSelection.collapsed(offset: parts.rest.length),
      );
      _push();
      return;
    }

    // Российская привычка писать «8» вместо «+7». Сервер это тоже умеет
    // (normalize_phone), но человек должен видеть в поле то, что уедет.
    if (_code == defaultPhoneCode && digits.length == 11 && digits.startsWith('8')) {
      final trimmed = digits.substring(1);
      _rest.value = TextEditingValue(
        text: trimmed,
        selection: TextSelection.collapsed(offset: trimmed.length),
      );
      _push();
      return;
    }

    if (digits != value) {
      _rest.value = TextEditingValue(
        text: digits,
        selection: TextSelection.collapsed(offset: digits.length),
      );
    }
    _push();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 116,
          child: DropdownButtonFormField<String>(
            value: _code,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Код'),
            items: [
              for (final c in phoneCountries)
                DropdownMenuItem(value: c.code, child: Text(c.label)),
            ],
            onChanged: widget.enabled
                ? (next) {
                    if (next == null) return;
                    setState(() => _code = next);
                    _push();
                  }
                : null,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: TextField(
            controller: _rest,
            enabled: widget.enabled,
            keyboardType: TextInputType.phone,
            // Оформление (скобки, дефисы) человек ставит по привычке, а уехать
            // должен номер, а не его вид. Плюс оставлен, чтобы сработала
            // вставка номера целиком.
            inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[\d+\s\-()]'))],
            decoration: InputDecoration(
              labelText: widget.label,
              helperText: widget.helperText,
              helperMaxLines: 2,
              hintText: '900 000-00-00',
              prefixIcon: const Icon(Icons.phone_outlined),
            ),
            onChanged: _onRestChanged,
          ),
        ),
      ],
    );
  }
}
