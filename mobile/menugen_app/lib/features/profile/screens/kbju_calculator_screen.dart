// MG_207_V_calc_screen = 1
// Калькулятор КБЖУ (mobile). Отзеркаливает web KBJUCalculatorPage (MG_206).
// POST /users/me/calculator/preview/  — расчёт без сохранения
// POST /users/me/calculator/apply/    — расчёт + сохранение в Profile (source='user')
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/macro_pill.dart';

// ─── Static config (отзеркаливает backend SYSTEMS/DIET_PRESETS) ──────────────
const _systems = <Map<String, String>>[
  {'value': 'mifflin', 'label': 'Mifflin-St Jeor', 'hint': 'Универсальная (США/мир)'},
  {'value': 'harris_benedict', 'label': 'Harris-Benedict', 'hint': 'Revised, США'},
  {'value': 'rospotrebnadzor', 'label': 'Роспотребнадзор (RU)', 'hint': 'МР 2.3.1.0253-21'},
  {'value': 'efsa', 'label': 'EFSA (EU)', 'hint': 'Европейский подход'},
  {'value': 'custom', 'label': 'Свои значения', 'hint': 'Ввести вручную'},
];

const _diets = <Map<String, String>>[
  {'value': 'balanced', 'label': 'Сбалансированный', 'pct': 'Б 20 / Ж 30 / У 50'},
  {'value': 'high_protein', 'label': 'Высокобелковый', 'pct': 'Б 35 / Ж 25 / У 40'},
  {'value': 'low_carb', 'label': 'Низкоуглеводный', 'pct': 'Б 30 / Ж 45 / У 25'},
];

const _genders = <Map<String, String>>[
  {'value': 'male', 'label': 'Мужской'},
  {'value': 'female', 'label': 'Женский'},
  {'value': 'other', 'label': 'Иной'},
];

const _activities = <Map<String, String>>[
  {'value': 'sedentary', 'label': 'Сидячий (×1.2)'},
  {'value': 'light', 'label': 'Лёгкая (×1.375)'},
  {'value': 'moderate', 'label': 'Умеренная (×1.55)'},
  {'value': 'active', 'label': 'Высокая (×1.725)'},
  {'value': 'very_active', 'label': 'Очень высокая (×1.9)'},
];

const _goals = <Map<String, String>>[
  {'value': 'lose_weight', 'label': 'Похудение (−500 ккал)'},
  {'value': 'maintain', 'label': 'Поддержание'},
  {'value': 'gain_weight', 'label': 'Набор массы (+300 ккал)'},
];

class KbjuCalculatorScreen extends StatefulWidget {
  final ApiClient apiClient;
  final Map<String, dynamic>? initialProfile;

  const KbjuCalculatorScreen({
    super.key,
    required this.apiClient,
    this.initialProfile,
  });

  @override
  State<KbjuCalculatorScreen> createState() => _KbjuCalculatorScreenState();
}

class _KbjuCalculatorScreenState extends State<KbjuCalculatorScreen> {
  // Step 1/2
  String _system = 'mifflin';
  String _diet = 'balanced';
  String _customMode = 'percents';

  // Step 3a base inputs (prefill from profile)
  late final TextEditingController _height;
  late final TextEditingController _weight;
  late final TextEditingController _birthYear;
  String _gender = 'male';
  String _activity = 'moderate';
  String _goal = 'maintain';

  // Step 3b custom
  final _customCal = TextEditingController(text: '2000');
  final _customP = TextEditingController(text: '120');
  final _customF = TextEditingController(text: '65');
  final _customC = TextEditingController(text: '250');
  final _customFib = TextEditingController(text: '28');
  final _customDelta = TextEditingController(text: '0');
  final _customPP = TextEditingController(text: '20');
  final _customFP = TextEditingController(text: '30');
  final _customCP = TextEditingController(text: '50');

  // Result + UI
  Map<String, dynamic>? _result;
  bool _loading = false;
  bool _applying = false;
  String? _error;

  static const _validGoals = {'lose_weight', 'maintain', 'gain_weight'};

  @override
  void initState() {
    super.initState();
    final p = widget.initialProfile;
    _height = TextEditingController(text: _str(p?['height_cm']));
    _weight = TextEditingController(text: _str(p?['weight_kg']));
    _birthYear = TextEditingController(text: _str(p?['birth_year']));
    final g = p?['gender'] as String?;
    if (g == 'male' || g == 'female' || g == 'other') _gender = g!;
    final a = p?['activity_level'] as String?;
    if (a != null && _activities.any((e) => e['value'] == a)) _activity = a;
    final go = p?['goal'] as String?;
    if (go != null && _validGoals.contains(go)) _goal = go;
  }

  @override
  void dispose() {
    for (final c in [
      _height, _weight, _birthYear, _customCal, _customP, _customF,
      _customC, _customFib, _customDelta, _customPP, _customFP, _customCP,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  static String _str(dynamic v) => v == null ? '' : v.toString();
  static int? _i(String s) => int.tryParse(s.trim());
  static double? _d(String s) => double.tryParse(s.trim().replaceAll(',', '.'));

  bool get _isCustom => _system == 'custom';
  bool get _isCustomGrams => _isCustom && _customMode == 'grams';
  bool get _isCustomPercents => _isCustom && _customMode == 'percents';
  bool get _needsBaseInputs => !_isCustomGrams;

  double get _pctSum =>
      (_d(_customPP.text) ?? 0) + (_d(_customFP.text) ?? 0) + (_d(_customCP.text) ?? 0);

  Map<String, dynamic> _buildRequest() {
    if (!_isCustom) {
      return {
        'system': _system,
        'diet': _diet,
        if (_height.text.trim().isNotEmpty) 'height_cm': _i(_height.text),
        if (_weight.text.trim().isNotEmpty) 'weight_kg': _weight.text.trim(),
        if (_birthYear.text.trim().isNotEmpty) 'birth_year': _i(_birthYear.text),
        'gender': _gender,
        'activity_level': _activity,
        'goal': _goal,
      };
    }
    if (_customMode == 'grams') {
      return {
        'system': 'custom',
        'custom_mode': 'grams',
        'custom_calorie_target': _i(_customCal.text),
        'custom_protein_g': _customP.text.trim(),
        'custom_fat_g': _customF.text.trim(),
        'custom_carb_g': _customC.text.trim(),
        'custom_fiber_g': _customFib.text.trim(),
      };
    }
    return {
      'system': 'custom',
      'custom_mode': 'percents',
      if (_height.text.trim().isNotEmpty) 'height_cm': _i(_height.text),
      if (_weight.text.trim().isNotEmpty) 'weight_kg': _weight.text.trim(),
      if (_birthYear.text.trim().isNotEmpty) 'birth_year': _i(_birthYear.text),
      'gender': _gender,
      'activity_level': _activity,
      'custom_calorie_delta': _i(_customDelta.text) ?? 0,
      'custom_protein_pct': _d(_customPP.text) ?? 0,
      'custom_fat_pct': _d(_customFP.text) ?? 0,
      'custom_carb_pct': _d(_customCP.text) ?? 0,
      'custom_fiber_g': _customFib.text.trim(),
    };
  }

  Future<void> _onCalc() async {
    setState(() {
      _loading = true;
      _error = null;
      _result = null;
    });
    try {
      final r = await widget.apiClient
          .post('/users/me/calculator/preview/', data: _buildRequest());
      setState(() => _result = r is Map ? Map<String, dynamic>.from(r) : null);
    } catch (e) {
      setState(() => _error = _msg(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _onApply() async {
    setState(() {
      _applying = true;
      _error = null;
    });
    try {
      await widget.apiClient
          .post('/users/me/calculator/apply/', data: _buildRequest());
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Целевые КБЖУ сохранены в профиль')),
      );
      context.pop();
    } catch (e) {
      setState(() => _error = _msg(e));
    } finally {
      if (mounted) setState(() => _applying = false);
    }
  }

  String _msg(Object e) {
    final s = e.toString();
    return s.startsWith('Exception: ') ? s.substring(11) : s;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Калькулятор КБЖУ')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _disclaimer(),
          const SizedBox(height: 12),
          _systemCard(),
          const SizedBox(height: 12),
          if (!_isCustom) _dietCard() else _customModeCard(),
          const SizedBox(height: 12),
          if (_needsBaseInputs) _baseInputsCard(),
          if (_needsBaseInputs) const SizedBox(height: 12),
          if (_isCustomGrams) _customGramsCard(),
          if (_isCustomGrams) const SizedBox(height: 12),
          if (_isCustomPercents) _customPercentsCard(),
          if (_isCustomPercents) const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _loading ? null : _onCalc,
              icon: _loading
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.calculate_outlined),
              label: Text(_loading ? 'Расчёт…' : 'Рассчитать'),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFFDECEC),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFF3B6B6)),
              ),
              child: Text(_error!,
                  style: const TextStyle(color: Color(0xFFB42318), fontSize: 13)),
            ),
          ],
          if (_result != null) ...[
            const SizedBox(height: 12),
            _resultCard(),
          ],
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _card({required Widget child}) => Card(
        margin: EdgeInsets.zero,
        child: Padding(padding: const EdgeInsets.all(16), child: child),
      );

  Widget _sectionTitle(String t) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Text(t,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
      );

  Widget _disclaimer() => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFFFEF6E0),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFF1D08A)),
        ),
        child: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('⚠️ Важно',
                style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF8B6A12))),
            SizedBox(height: 4),
            Text(
              'Все расчёты носят справочный характер и не заменяют консультацию '
              'врача. При наличии заболеваний (диабет, сердечно-сосудистые, ЖКТ, '
              'почек и др.) перед изменением рациона обязательно проконсультируйтесь '
              'со специалистом. Формулы дают только стартовую оценку — реальные '
              'потребности зависят от индивидуальных особенностей, образа жизни и здоровья.',
              style: TextStyle(fontSize: 13, color: Color(0xFF8B6A12), height: 1.4),
            ),
          ],
        ),
      );

  Widget _selectTile({
    required bool active,
    required String title,
    String? subtitle,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(12),
        margin: const EdgeInsets.only(bottom: 8),
        decoration: BoxDecoration(
          color: active ? context.cs.primary.withOpacity(0.1) : null,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: active ? context.cs.primary : context.tokens.border,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style: const TextStyle(
                    fontSize: 14, fontWeight: FontWeight.w600)),
            if (subtitle != null) ...[
              const SizedBox(height: 2),
              Text(subtitle,
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _systemCard() => _card(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('1. Система расчёта'),
            for (final s in _systems)
              _selectTile(
                active: _system == s['value'],
                title: s['label']!,
                subtitle: s['hint'],
                onTap: () => setState(() {
                  _system = s['value']!;
                  _result = null;
                  _error = null;
                }),
              ),
          ],
        ),
      );

  Widget _dietCard() => _card(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('2. Пресет диеты'),
            for (final d in _diets)
              _selectTile(
                active: _diet == d['value'],
                title: d['label']!,
                subtitle: d['pct'],
                onTap: () => setState(() {
                  _diet = d['value']!;
                  _result = null;
                }),
              ),
          ],
        ),
      );

  Widget _customModeCard() => _card(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('2. Режим ввода'),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'percents', label: Text('Проценты')),
                ButtonSegment(value: 'grams', label: Text('Граммы')),
              ],
              selected: {_customMode},
              onSelectionChanged: (v) => setState(() {
                _customMode = v.first;
                _result = null;
              }),
            ),
            const SizedBox(height: 6),
            Text(
              _customMode == 'percents'
                  ? 'TDEE по Mifflin + дельта ккал, затем % Б/Ж/У.'
                  : 'Прямой ввод абсолютных значений КБЖУ.',
              style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
            ),
          ],
        ),
      );

  Widget _numField(TextEditingController c, String label,
      {bool allowDecimal = false, bool allowSign = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: c,
        keyboardType: TextInputType.numberWithOptions(
            decimal: allowDecimal, signed: allowSign),
        inputFormatters: [
          FilteringTextInputFormatter.allow(
            RegExp(allowDecimal
                ? (allowSign ? r'[0-9.,\-]' : r'[0-9.,]')
                : (allowSign ? r'[0-9\-]' : r'[0-9]')),
          ),
        ],
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
        ),
      ),
    );
  }

  Widget _dropdown({
    required String value,
    required List<Map<String, String>> items,
    required String label,
    required ValueChanged<String> onChanged,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DropdownButtonFormField<String>(
        value: value,
        isExpanded: true,
        decoration: InputDecoration(labelText: label, isDense: true),
        items: [
          for (final it in items)
            DropdownMenuItem(value: it['value'], child: Text(it['label']!)),
        ],
        onChanged: (v) {
          if (v != null) setState(() => onChanged(v));
        },
      ),
    );
  }

  Widget _baseInputsCard() => _card(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('3. Параметры'),
            _numField(_height, 'Рост, см'),
            _numField(_weight, 'Вес, кг', allowDecimal: true),
            _numField(_birthYear, 'Год рождения'),
            _dropdown(
              value: _gender,
              items: _genders,
              label: 'Пол',
              onChanged: (v) => _gender = v,
            ),
            _dropdown(
              value: _activity,
              items: _activities,
              label: 'Активность',
              onChanged: (v) => _activity = v,
            ),
            if (!_isCustom)
              _dropdown(
                value: _goal,
                items: _goals,
                label: 'Цель',
                onChanged: (v) => _goal = v,
              ),
          ],
        ),
      );

  Widget _customGramsCard() => _card(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('3. Значения (граммы)'),
            _numField(_customCal, 'Калории, ккал'),
            _numField(_customP, 'Белок, г', allowDecimal: true),
            _numField(_customF, 'Жиры, г', allowDecimal: true),
            _numField(_customC, 'Углеводы, г', allowDecimal: true),
            _numField(_customFib, 'Клетчатка, г', allowDecimal: true),
          ],
        ),
      );

  Widget _customPercentsCard() {
    final sum = _pctSum;
    final ok = (sum - 100).abs() <= 0.5;
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionTitle('3. Проценты Б/Ж/У'),
          _numField(_customDelta, 'Дельта калорий (±)', allowSign: true),
          _numField(_customPP, 'Белок, %', allowDecimal: true),
          _numField(_customFP, 'Жиры, %', allowDecimal: true),
          _numField(_customCP, 'Углеводы, %', allowDecimal: true),
          _numField(_customFib, 'Клетчатка, г', allowDecimal: true),
          Text(
            'Сумма Б/Ж/У: ${sum.toStringAsFixed(0)}%',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: ok ? const Color(0xFF1F8B5C) : const Color(0xFFB42318),
            ),
          ),
        ],
      ),
    );
  }

  Widget _resultCard() {
    final r = _result!;
    final bmr = r['bmr'];
    final tdee = r['tdee'];
    final age = r['age'];
    final hasMeta = bmr != null || tdee != null;
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionTitle('Результат'),
          MacroPillsRow(targets: r),
          if (hasMeta) ...[
            const SizedBox(height: 12),
            Text(
              'BMR ${formatTargetNumber(bmr)} · TDEE ${formatTargetNumber(tdee)} ккал'
              '${age != null ? ' · возраст $age' : ''}',
              style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
            ),
          ],
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _applying ? null : _onApply,
              icon: _applying
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.save_outlined),
              label: Text(_applying ? 'Сохранение…' : 'Применить в профиль'),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Целевые КБЖУ и исходные параметры будут сохранены в профиль. Источник: «вручную».',
            style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
          ),
        ],
      ),
    );
  }
}
