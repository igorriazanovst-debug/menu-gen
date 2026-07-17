// MG_607_V_mobile: расширенный bottom-sheet генерации меню (синхронно с web).
//
// Поля:
//  - КБЖУ summary (read-only, из /users/me/)
//  - Период (start_date + days)
//  - Приёмов пищи (3/5)
//  - Страны (топ-6 чипов + кнопка «Больше», источник /recipes/countries/)
//  - Макс. время готовки (опц.)
//  - Toggle: учитывать аллергены / нелюбимые (ON=profile, OFF=exclude_*=[])
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';

import '../../../core/api/api_client.dart';
import '../../../core/constants/allergens.dart';
import '../../../core/theme/app_theme.dart';
import '../bloc/menu_bloc.dart';

const Map<String, String> _kCountryLabels = {
  'RU': '🇷🇺 Россия',
  'IT': '🇮🇹 Италия',
  'FR': '🇫🇷 Франция',
  'US': '🇺🇸 США',
  'JP': '🇯🇵 Япония',
  'CN': '🇨🇳 Китай',
  'MX': '🇲🇽 Мексика',
  'IN': '🇮🇳 Индия',
  'GR': '🇬🇷 Греция',
  'ES': '🇪🇸 Испания',
  'TR': '🇹🇷 Турция',
  'TH': '🇹🇭 Таиланд',
  'Россия': '🇷🇺 Россия',
  'Италия': '🇮🇹 Италия',
  'Франция': '🇫🇷 Франция',
};

const int _kPopularLimit = 6;

class GenerateMenuBottomSheet extends StatefulWidget {
  final ApiClient apiClient;
  const GenerateMenuBottomSheet({super.key, required this.apiClient});

  @override
  State<GenerateMenuBottomSheet> createState() => _State();
}

class _State extends State<GenerateMenuBottomSheet> {
  // form state
  int _days = 7;
  DateTime _start = DateTime.now();
  String _mealPlanType = '3';
  String _strategy = '1'; // MG_STRAT_MOBILE
  final Set<String> _countries = <String>{};
  int? _maxCookTime;
  bool _respectAllergies = true;
  bool _respectDisliked = true;
  bool _withSoup = true; // MG_610_V_mobile

  // MG_FAMILYGEN: члены семьи + режим.
  List<Map<String, dynamic>> _members = const [];
  Set<int> _selectedMemberIds = <int>{};
  String _menuMode = 'family';
  bool get _multiMember => _members.length > 1;

  // loaded data
  List<String> _allCountries = <String>[];
  bool _showAllCountries = false;
  List<String> _userAllergies = <String>[];
  List<String> _userDisliked = <String>[];
  int? _calorieTarget;
  String? _proteinTarget;
  String? _fatTarget;
  String? _carbTarget;

  // Freemium: остаток квоты на генерацию меню (limit=null → безлимит/premium).
  int? _quotaUsed;
  int? _quotaLimit;
  String? _quotaResetAt;

  bool _loadingMeta = true;

  bool get _hasQuota => _quotaLimit != null;
  int get _quotaRemaining =>
      _quotaLimit == null ? 0 : (_quotaLimit! - (_quotaUsed ?? 0)).clamp(0, _quotaLimit!);
  bool get _quotaExhausted => _hasQuota && _quotaRemaining == 0;

  @override
  void initState() {
    super.initState();
    _loadMeta();
  }

  Future<void> _loadMeta() async {
    try {
      // /users/me/ — profile + allergies + disliked
      final me = await widget.apiClient.get('/users/me/');
      final mp = me is Map ? Map<String, dynamic>.from(me) : <String, dynamic>{};
      final profile = mp['profile'] is Map
          ? Map<String, dynamic>.from(mp['profile'] as Map)
          : <String, dynamic>{};

      _userAllergies = ((mp['allergies'] as List?) ?? const [])
          .map((e) => e.toString())
          .where((e) => e.isNotEmpty)
          .toList();
      _userDisliked = ((mp['disliked_products'] as List?) ?? const [])
          .map((e) => e.toString())
          .where((e) => e.isNotEmpty)
          .toList();

      final cal = profile['calorie_target'];
      _calorieTarget = cal is num ? cal.toInt() : (cal is String ? int.tryParse(cal) : null);
      _proteinTarget = profile['protein_target_g']?.toString();
      _fatTarget = profile['fat_target_g']?.toString();
      _carbTarget = profile['carb_target_g']?.toString();

      final mp_type = profile['meal_plan_type'];
      if (mp_type == '5' || mp_type == '3') {
        _mealPlanType = mp_type as String;
      }

      // Freemium: остаток квоты из subscription_status.menu_quota.
      final sub = mp['subscription_status'];
      if (sub is Map && sub['menu_quota'] is Map) {
        final q = Map<String, dynamic>.from(sub['menu_quota'] as Map);
        final used = q['used'];
        final limit = q['limit'];
        _quotaUsed = used is num ? used.toInt() : null;
        _quotaLimit = limit is num ? limit.toInt() : null; // null → безлимит
        _quotaResetAt = q['reset_at']?.toString();
      }
    } catch (_) {/* ignore */}

    try {
      // MG_FAMILYGEN: члены семьи для выбора «для кого меню».
      final fam = await widget.apiClient.get('/family/');
      final fm = fam is Map ? Map<String, dynamic>.from(fam) : <String, dynamic>{};
      final ms = ((fm['members'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .map((m) => {
                'id': (m['id'] as num).toInt(),
                'name': (m['name'] ?? 'Участник').toString(),
              })
          .toList();
      _members = ms;
      _selectedMemberIds = ms.map((m) => m['id'] as int).toSet();
    } catch (_) {
      _members = const [];
    }

    try {
      final r = await widget.apiClient.get('/recipes/countries/');
      List<String> list;
      if (r is List) {
        list = r.map((e) => e.toString()).toList();
      } else if (r is Map && r['countries'] is List) {
        list = (r['countries'] as List).map((e) => e.toString()).toList();
      } else {
        list = const [];
      }
      _allCountries = list;
    } catch (_) {
      _allCountries = const [];
    }

    if (mounted) setState(() => _loadingMeta = false);
  }

  void _toggleCountry(String c) {
    setState(() {
      if (_countries.contains(c)) {
        _countries.remove(c);
      } else {
        _countries.add(c);
      }
    });
  }

  void _toggleMember(int id) {
    setState(() {
      if (_selectedMemberIds.contains(id)) {
        _selectedMemberIds.remove(id);
      } else {
        _selectedMemberIds.add(id);
      }
    });
  }

  void _submit() {
    final body = <String, dynamic>{
      'startDate': DateFormat('yyyy-MM-dd').format(_start),
      'periodDays': _days,
      'mealPlanType': _mealPlanType,
      'countries': _countries.toList(),
      'maxCookTime': _maxCookTime,
      'respectAllergies': _respectAllergies,
      'respectDisliked': _respectDisliked,
    };

    // MG_FAMILYGEN: члены семьи + режим. Для одного члена не шлём — бэкенд
    // по умолчанию генерит на всю семью (= этот единственный член).
    final selectedMembers = _selectedMemberIds.toList();
    context.read<MenuBloc>().add(MenuGenerateRequested(
          startDate: body['startDate'] as String,
          periodDays: _days,
          mealPlanType: _mealPlanType,
          countries: _countries.isEmpty ? null : _countries.toList(),
          maxCookTime: _maxCookTime,
          excludeAllergens: _respectAllergies ? null : const <String>[],
          excludeDisliked: _respectDisliked ? null : const <String>[],
          withSoup: _withSoup, // MG_610_V_mobile
          strategy: _strategy, // MG_STRAT_MOBILE
          memberIds: (_multiMember && selectedMembers.isNotEmpty) ? selectedMembers : null,
          mode: (_multiMember && selectedMembers.length > 1) ? _menuMode : null,
        ));
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
        24, 24, 24, MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: _loadingMeta
          ? const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            )
          : SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Генерация меню',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),

                  // Freemium: остаток бесплатных генераций
                  if (_hasQuota) ...[
                    _buildQuotaBanner(),
                    const SizedBox(height: 12),
                  ],

                  // КБЖУ summary
                  _buildKbjuSummary(),
                  const SizedBox(height: 16),

                  // Дата начала
                  _DateRow(
                    start: _start,
                    onPick: (d) => setState(() => _start = d),
                  ),
                  const Divider(),

                  // Дней
                  Row(children: [
                    const Icon(Icons.date_range, color: Colors.grey, size: 20),
                    const SizedBox(width: 12),
                    const Text('Дней:'),
                    Expanded(
                      child: Slider(
                        value: _days.toDouble(),
                        min: 1, max: 14, divisions: 13, label: '$_days',
                        onChanged: (v) => setState(() => _days = v.round()),
                      ),
                    ),
                    Text('$_days', style: const TextStyle(fontWeight: FontWeight.bold)),
                  ]),
                  const Divider(),

                  // MG_STRAT_MOBILE strategy selector
                  const Text('Стратегия меню', style: TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  _strategyTile('1', 'Стандарт', 'Метод тарелки по ролям; 3 или 5 приёмов'),
                  _strategyTile('2', 'По составу', 'Приём по макро-ролям'),
                  _strategyTile('3', 'Тарелка 25/25/50', 'Белок/гарнир/овощи по массе'),
                  const SizedBox(height: 16),
                  // MG_STRAT_MOBILE: 3/5 только для s1
                  if (_strategy == '1') ...[
                  // Приёмов пищи
                  const Text('Приёмов пищи', style: TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(child: _planButton('3')),
                    const SizedBox(width: 8),
                    Expanded(child: _planButton('5')),
                  ]),
                  const SizedBox(height: 16),
                  ],

                  // Страны
                  if (_allCountries.isNotEmpty) ...[
                    Text(
                      _countries.isEmpty
                          ? 'Кухня — все'
                          : 'Кухня (${_countries.length})',
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 8),
                    _buildCountries(),
                    const SizedBox(height: 16),
                  ],

                  // Макс. время готовки
                  const Text(
                    'Макс. время готовки',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 8),
                  Wrap(spacing: 8, children: <int?>[
                    null, 15, 30, 45, 60, 90, 120,
                  ].map((t) {
                    return ChoiceChip(
                      label: Text(t == null ? 'Любое' : '$t мин'),
                      selected: _maxCookTime == t,
                      onSelected: (_) => setState(() => _maxCookTime = t),
                    );
                  }).toList()),
                  const SizedBox(height: 16),

                  // MG_FAMILYGEN: для кого меню (только при >1 члена)
                  if (_multiMember) ...[
                    Text(
                      'Для кого меню (${_selectedMemberIds.length} из ${_members.length})',
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 4,
                      children: _members.map((m) {
                        final id = m['id'] as int;
                        return FilterChip(
                          label: Text(m['name'] as String),
                          selected: _selectedMemberIds.contains(id),
                          onSelected: (_) => _toggleMember(id),
                        );
                      }).toList(),
                    ),
                    if (_selectedMemberIds.length > 1) ...[
                      const SizedBox(height: 8),
                      Row(children: [
                        Expanded(child: _modeButton('family', 'Общее меню')),
                        const SizedBox(width: 8),
                        Expanded(child: _modeButton('per_member', 'Каждому своё')),
                      ]),
                    ],
                    if (_selectedMemberIds.isEmpty)
                      const Padding(
                        padding: EdgeInsets.only(top: 4),
                        child: Text(
                          'Выберите хотя бы одного члена семьи.',
                          style: TextStyle(fontSize: 12, color: Colors.red),
                        ),
                      ),
                    const SizedBox(height: 16),
                  ],

                  // Toggle: аллергены
                  _ToggleTile(
                    value: _respectAllergies,
                    onChanged: _userAllergies.isEmpty ? null : (v) {
                      setState(() => _respectAllergies = v);
                    },
                    title: 'Учитывать аллергены из Профиля',
                    subtitle: _userAllergies.isEmpty
                        ? 'Список пуст'
                        : _userAllergies.map(allergenLabel).join(', '),
                  ),
                  const SizedBox(height: 8),

                  // Toggle: нелюбимые
                  _ToggleTile(
                    value: _respectDisliked,
                    onChanged: _userDisliked.isEmpty ? null : (v) {
                      setState(() => _respectDisliked = v);
                    },
                    title: 'Учитывать нелюбимые продукты',
                    subtitle: _userDisliked.isEmpty
                        ? 'Список пуст'
                        : _userDisliked.join(', '),
                  ),
                  const SizedBox(height: 8),
                  // MG_610_V_mobile: with_soup toggle
                  _ToggleTile(
                    value: _withSoup,
                    onChanged: (v) => setState(() => _withSoup = v),
                    title: 'Суп на обед',
                    subtitle: _withSoup ? 'Первое блюдо включено' : 'Обед без супа',
                  ),
                  const SizedBox(height: 24),

                  // Кнопка
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      icon: const Icon(Icons.auto_awesome),
                      label: Text(_quotaExhausted ? 'Лимит исчерпан' : 'Создать меню'),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      onPressed: (_quotaExhausted ||
                              (_multiMember && _selectedMemberIds.isEmpty))
                          ? null
                          : _submit,
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  // Freemium: баннер с остатком бесплатных генераций.
  Widget _buildQuotaBanner() {
    final exhausted = _quotaExhausted;
    final reset = (_quotaResetAt != null && _quotaResetAt!.isNotEmpty)
        ? ' · сброс $_quotaResetAt'
        : '';
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: exhausted ? Colors.red.shade50 : Colors.green.shade50,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        exhausted
            ? 'Лимит бесплатных генераций исчерпан. Оформите Premium для безлимитной генерации$reset.'
            : 'Бесплатные генерации: осталось $_quotaRemaining из $_quotaLimit$reset',
        style: TextStyle(
          fontSize: 13,
          color: exhausted ? Colors.red.shade800 : Colors.green.shade900,
          fontWeight: exhausted ? FontWeight.w600 : FontWeight.normal,
        ),
      ),
    );
  }

  Widget _buildKbjuSummary() {
    if (_calorieTarget == null) {
      return Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: Colors.amber.shade50,
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Text(
          'Цели КБЖУ не заданы. Заполни Профиль для персонализации.',
          style: TextStyle(fontSize: 12, color: Color(0xFF8B6E00)),
        ),
      );
    }
    final parts = <String>[];
    parts.add('${_calorieTarget!} ккал');
    if (_proteinTarget != null && _proteinTarget!.isNotEmpty) {
      parts.add('Б ${_proteinTarget}');
    }
    if (_fatTarget != null && _fatTarget!.isNotEmpty) {
      parts.add('Ж ${_fatTarget}');
    }
    if (_carbTarget != null && _carbTarget!.isNotEmpty) {
      parts.add('У ${_carbTarget}');
    }
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: context.cs.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        'Цели из Профиля: ${parts.join(" · ")}',
        style: TextStyle(fontSize: 12, color: context.cs.onSurface),
      ),
    );
  }

  // MG_STRAT_MOBILE
  Widget _strategyTile(String v, String title, String desc) {
    final active = _strategy == v;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: () => setState(() => _strategy = v),
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: active ? const Color(0xFFE8502E) : const Color(0xFFE0E0E0)),
            color: active ? const Color(0x1AE8502E) : Colors.white,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: TextStyle(fontWeight: FontWeight.w600, color: active ? const Color(0xFFE8502E) : const Color(0xFF3A2A20))),
              const SizedBox(height: 2),
              Text(desc, style: const TextStyle(fontSize: 12, color: Color(0xFF9E9E9E))),
            ],
          ),
        ),
      ),
    );
  }

  Widget _planButton(String v) {
    final active = _mealPlanType == v;
    return InkWell(
      onTap: () => setState(() => _mealPlanType = v),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          color: active ? context.cs.primary.withOpacity(0.1) : context.cs.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: active ? context.cs.primary : context.tokens.border,
          ),
        ),
        alignment: Alignment.center,
        child: Text(
          v,
          style: TextStyle(
            fontWeight: FontWeight.w600,
            color: active ? context.cs.primary : context.cs.onSurface,
          ),
        ),
      ),
    );
  }

  // MG_FAMILYGEN: кнопка режима family / per_member.
  Widget _modeButton(String v, String label) {
    final active = _menuMode == v;
    return InkWell(
      onTap: () => setState(() => _menuMode = v),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
        decoration: BoxDecoration(
          color: active ? context.cs.primary.withOpacity(0.1) : context.cs.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: active ? context.cs.primary : context.tokens.border,
          ),
        ),
        alignment: Alignment.center,
        child: Text(
          label,
          style: TextStyle(
            fontWeight: FontWeight.w600,
            color: active ? context.cs.primary : context.cs.onSurface,
          ),
        ),
      ),
    );
  }

  Widget _buildCountries() {
    final popular = _allCountries.take(_kPopularLimit).toList();
    final rest = _allCountries.skip(_kPopularLimit).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 8, runSpacing: 4,
          children: [
            ...popular.map(_countryChip),
            if (rest.isNotEmpty)
              ActionChip(
                avatar: Icon(
                  _showAllCountries ? Icons.expand_less : Icons.expand_more,
                  size: 16,
                ),
                label: Text(
                  _showAllCountries
                      ? 'Свернуть'
                      : 'Больше (+${rest.length})',
                ),
                onPressed: () => setState(() => _showAllCountries = !_showAllCountries),
              ),
          ],
        ),
        if (_showAllCountries && rest.isNotEmpty) ...[
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 4, children: rest.map(_countryChip).toList()),
        ],
      ],
    );
  }

  Widget _countryChip(String code) {
    final label = _kCountryLabels[code] ?? code;
    return ChoiceChip(
      label: Text(label),
      selected: _countries.contains(code),
      onSelected: (_) => _toggleCountry(code),
    );
  }
}


class _DateRow extends StatelessWidget {
  final DateTime start;
  final ValueChanged<DateTime> onPick;
  const _DateRow({required this.start, required this.onPick});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: const Icon(Icons.calendar_today),
      title: Text('Дата начала: ${DateFormat('dd.MM.yyyy').format(start)}'),
      onTap: () async {
        final d = await showDatePicker(
          context: context,
          initialDate: start,
          firstDate: DateTime.now(),
          lastDate: DateTime.now().add(const Duration(days: 30)),
        );
        if (d != null) onPick(d);
      },
    );
  }
}


class _ToggleTile extends StatelessWidget {
  final bool value;
  final ValueChanged<bool>? onChanged;
  final String title;
  final String subtitle;
  const _ToggleTile({
    required this.value,
    required this.onChanged,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    final disabled = onChanged == null;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: disabled ? Colors.grey.shade50 : Colors.white,
        border: Border.all(
          color: Colors.grey.shade200,
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(children: [
        Switch(
          value: value && !disabled,
          onChanged: disabled ? null : onChanged,
          activeColor: context.cs.primary,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                title,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: disabled
                      ? Colors.grey
                      : context.cs.onSurface,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey.shade600,
                ),
                maxLines: 2, overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ]),
    );
  }
}
