#!/usr/bin/env bash
# MG-204 mobile — apply
# Создаёт MacroPill, правит family_screen.dart и profile_screen.dart
# Использование: bash /opt/menugen/backend/scripts/mg_204m_apply.sh
set -euo pipefail

ROOT="/opt/menugen"
MOB="${ROOT}/mobile/menugen_app"
LIB="${MOB}/lib"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUPS="${ROOT}/backups"
mkdir -p "${BACKUPS}"

echo "================================================================"
echo "  MG-204 mobile APPLY (TS=${TS})"
echo "================================================================"

if [ ! -d "${LIB}" ]; then
  echo "!!! ${LIB} не найден"; exit 1
fi

# ── 1. Бэкапы ────────────────────────────────────────────────────────
FAMILY_SCREEN="${LIB}/features/family/screens/family_screen.dart"
PROFILE_SCREEN="${LIB}/features/profile/screens/profile_screen.dart"
MACRO_PILL="${LIB}/core/widgets/macro_pill.dart"

cp "${FAMILY_SCREEN}"  "${BACKUPS}/family_screen.dart.bak_mg204m_${TS}"
cp "${PROFILE_SCREEN}" "${BACKUPS}/profile_screen.dart.bak_mg204m_${TS}"
echo "Backups -> ${BACKUPS}/*.bak_mg204m_${TS}"

# ── 2. MacroPill widget (новый) ──────────────────────────────────────
mkdir -p "${LIB}/core/widgets"
cat > "${MACRO_PILL}" <<'DARTEOF'
// MG_204m_V_macro_pill = 1
import 'package:flutter/material.dart';

/// Компактная пилюля для отображения целевого значения КБЖУ (read-only).
/// Используется в ProfileScreen и FamilyScreen (редактирование участника).
class MacroPill extends StatelessWidget {
  final String label;
  final String value;
  final String unit;
  final Color background;
  final Color foreground;

  const MacroPill({
    super.key,
    required this.label,
    required this.value,
    required this.unit,
    required this.background,
    required this.foreground,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label.toUpperCase(),
            style: TextStyle(
              fontSize: 10,
              letterSpacing: 0.5,
              color: foreground.withOpacity(0.7),
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: foreground,
            ),
          ),
          Text(
            unit,
            style: TextStyle(
              fontSize: 9,
              color: foreground.withOpacity(0.6),
            ),
          ),
        ],
      ),
    );
  }
}

/// Парсит число (int/double/строка) в строку без дробной части либо '—'.
String formatTargetNumber(dynamic v) {
  if (v == null) return '—';
  if (v is num) return v.toStringAsFixed(0);
  final s = v.toString().trim();
  if (s.isEmpty) return '—';
  final parsed = num.tryParse(s);
  if (parsed == null) return '—';
  return parsed.toStringAsFixed(0);
}

/// Извлекает targets из profile-мапы. Сначала прямые поля, fallback — targets_calculated.
Map<String, dynamic>? extractTargets(Map<String, dynamic>? profile) {
  if (profile == null) return null;
  final hasDirect = profile['calorie_target'] != null && profile['protein_target_g'] != null;
  if (hasDirect) {
    return {
      'calorie_target':   profile['calorie_target'],
      'protein_target_g': profile['protein_target_g'],
      'fat_target_g':     profile['fat_target_g'],
      'carb_target_g':    profile['carb_target_g'],
      'fiber_target_g':   profile['fiber_target_g'],
    };
  }
  final calc = profile['targets_calculated'];
  if (calc is Map<String, dynamic>) return calc;
  if (calc is Map) return Map<String, dynamic>.from(calc);
  return null;
}

/// Готовый ряд из 5 пилюль КБЖУ.
class MacroPillsRow extends StatelessWidget {
  final Map<String, dynamic> targets;
  const MacroPillsRow({super.key, required this.targets});

  @override
  Widget build(BuildContext context) {
    final pills = <Widget>[
      Expanded(child: MacroPill(
        label: 'Ккал',
        value: formatTargetNumber(targets['calorie_target']),
        unit: 'ккал',
        background: const Color(0xFFFEEAEA),
        foreground: const Color(0xFFE34A4A),
      )),
      const SizedBox(width: 6),
      Expanded(child: MacroPill(
        label: 'Белок',
        value: formatTargetNumber(targets['protein_target_g']),
        unit: 'г',
        background: const Color(0xFFE6F0FB),
        foreground: const Color(0xFF1E5BB6),
      )),
      const SizedBox(width: 6),
      Expanded(child: MacroPill(
        label: 'Жиры',
        value: formatTargetNumber(targets['fat_target_g']),
        unit: 'г',
        background: const Color(0xFFFEF3D6),
        foreground: const Color(0xFFB8770A),
      )),
      const SizedBox(width: 6),
      Expanded(child: MacroPill(
        label: 'Углев',
        value: formatTargetNumber(targets['carb_target_g']),
        unit: 'г',
        background: const Color(0xFFE0F5EB),
        foreground: const Color(0xFF1F8B5C),
      )),
      const SizedBox(width: 6),
      Expanded(child: MacroPill(
        label: 'Клетч',
        value: formatTargetNumber(targets['fiber_target_g']),
        unit: 'г',
        background: const Color(0xFFEFE5F8),
        foreground: const Color(0xFF6B3FA0),
      )),
    ];
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: pills);
  }
}
DARTEOF
echo "✓ ${MACRO_PILL}"

# ── 3. Правка family_screen.dart ─────────────────────────────────────
# Маркер MG_204m_V_family — чтобы не править повторно.
if grep -q "MG_204m_V_family" "${FAMILY_SCREEN}"; then
  echo "⚠ family_screen уже патчен (MG_204m_V_family) — пропускаю"
else
python3 <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/mobile/menugen_app/lib/features/family/screens/family_screen.dart")
src = p.read_text(encoding="utf-8")

# 3.1 импорт MacroPillsRow
imp_old = "import '../bloc/family_bloc.dart';"
imp_new = """import '../bloc/family_bloc.dart';
import '../../../core/widgets/macro_pill.dart';
// MG_204m_V_family = 1"""
assert imp_old in src, "import bloc не найден"
src = src.replace(imp_old, imp_new, 1)

# 3.2 добавить state-переменную _mealPlanType + парсинг в initState
init_old = "    _gender = profile['gender'] as String?;\n    _activityLevel = profile['activity_level'] as String?;\n    _goal = profile['goal'] as String?;\n  }"
init_new = """    _gender = profile['gender'] as String?;
    _activityLevel = profile['activity_level'] as String?;
    _goal = profile['goal'] as String?;
    _mealPlanType = (profile['meal_plan_type'] as String?) ?? '3';
  }"""
assert init_old in src, "блок initState не найден"
src = src.replace(init_old, init_new, 1)

# 3.3 объявить _mealPlanType рядом с _gender / _activityLevel / _goal
decls_old = "  String? _gender;\n  String? _activityLevel;\n  String? _goal;"
decls_new = "  String? _gender;\n  String? _activityLevel;\n  String? _goal;\n  String _mealPlanType = '3';"
assert decls_old in src, "декларации полей не найдены"
src = src.replace(decls_old, decls_new, 1)

# 3.4 в _save() добавить meal_plan_type в profile
save_old = "      if (_goal != null) profile['goal'] = _goal;\n\n      final data = <String, dynamic>{"
save_new = "      if (_goal != null) profile['goal'] = _goal;\n      profile['meal_plan_type'] = _mealPlanType;\n\n      final data = <String, dynamic>{"
assert save_old in src, "блок _save не найден"
src = src.replace(save_old, save_new, 1)

# 3.5 после поля «Целевые калории» (Calorie input) — пилюли + meal_plan toggle
ui_old = "                  _field(_calorieCtrl, 'Целевые калории',\n                      type: TextInputType.number),\n                  const SizedBox(height: 24),"
ui_new = """                  _field(_calorieCtrl, 'Целевые калории',
                      type: TextInputType.number),
                  const SizedBox(height: 16),
                  // MG_204m_V_family targets pills
                  Builder(builder: (_) {
                    final profile = (widget.member['profile'] as Map<String, dynamic>?) ?? {};
                    final targets = extractTargets(profile);
                    if (targets == null) return const SizedBox.shrink();
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Padding(
                          padding: EdgeInsets.only(bottom: 6),
                          child: Text(
                            'Целевые КБЖУ (рассчитано автоматически)',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                        MacroPillsRow(targets: targets),
                        const SizedBox(height: 16),
                      ],
                    );
                  }),
                  // MG_204m_V_family meal_plan toggle
                  const Padding(
                    padding: EdgeInsets.only(bottom: 6),
                    child: Text(
                      'План приёмов пищи',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(value: '3', label: Text('3 приёма')),
                      ButtonSegment(value: '5', label: Text('5 приёмов')),
                    ],
                    selected: {_mealPlanType},
                    onSelectionChanged: (v) =>
                        setState(() => _mealPlanType = v.first),
                  ),
                  const SizedBox(height: 24),"""
assert ui_old in src, "блок UI с _calorieCtrl не найден"
src = src.replace(ui_old, ui_new, 1)

p.write_text(src, encoding="utf-8")
print("✓ family_screen.dart пропатчен")
PYEOF
fi

# ── 4. Правка profile_screen.dart (полная замена — нужны loader/save) ─
if grep -q "MG_204m_V_profile" "${PROFILE_SCREEN}"; then
  echo "⚠ profile_screen уже патчен (MG_204m_V_profile) — пропускаю"
else
cat > "${PROFILE_SCREEN}" <<'DARTEOF'
// MG_204m_V_profile = 1
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../features/auth/bloc/auth_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/macro_pill.dart';

class ProfileScreen extends StatefulWidget {
  final ApiClient apiClient;
  const ProfileScreen({super.key, required this.apiClient});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  Map<String, dynamic>? _me;
  bool _loading = true;
  bool _saving = false;
  String? _error;
  String _mealPlanType = '3';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await widget.apiClient.get('/users/me/');
      final data = r is Map<String, dynamic> ? r : Map<String, dynamic>.from(r as Map);
      final profile = data['profile'] as Map<String, dynamic>?;
      setState(() {
        _me = data;
        _mealPlanType = (profile?['meal_plan_type'] as String?) ?? '3';
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _saveMealPlan(String value) async {
    final prev = _mealPlanType;
    setState(() {
      _mealPlanType = value;
      _saving = true;
      _error = null;
    });
    try {
      await widget.apiClient.patch(
        '/users/me/',
        data: {
          'profile': {'meal_plan_type': value}
        },
      );
      await _load();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Профиль обновлён')),
      );
    } catch (e) {
      setState(() {
        _mealPlanType = prev;
        _error = e.toString();
      });
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Профиль')),
      body: BlocBuilder<AuthBloc, AuthState>(
        builder: (context, state) {
          if (state is! AuthAuthenticated) return const SizedBox.shrink();
          if (_loading) {
            return const Center(child: CircularProgressIndicator());
          }
          final user = (_me ?? (state.user as Map<String, dynamic>));
          final profile = user['profile'] as Map<String, dynamic>?;
          final targets = extractTargets(profile);
          final profileFilled = profile != null
              && profile['birth_year'] != null
              && profile['height_cm'] != null
              && profile['weight_kg'] != null;

          return RefreshIndicator(
            onRefresh: _load,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Center(
                  child: CircleAvatar(
                    radius: 44,
                    backgroundColor: AppColors.primary.withOpacity(0.15),
                    child: Text(
                      ((user['name'] as String?) ?? 'U')[0].toUpperCase(),
                      style: const TextStyle(
                          fontSize: 32, color: AppColors.primary),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Center(
                  child: Text(
                    user['name'] ?? '',
                    style: Theme.of(context)
                        .textTheme
                        .titleLarge
                        ?.copyWith(fontWeight: FontWeight.bold),
                  ),
                ),
                Center(
                  child: Text(
                    user['email'] ?? user['phone'] ?? '',
                    style: TextStyle(color: Colors.grey.shade600),
                  ),
                ),
                const SizedBox(height: 24),

                // ── Целевые КБЖУ ────────────────────────────────────
                Card(
                  margin: EdgeInsets.zero,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Целевые КБЖУ',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'Рассчитываются автоматически по формуле Mifflin-St Jeor',
                          style: TextStyle(fontSize: 12, color: Colors.grey),
                        ),
                        const SizedBox(height: 12),
                        if (!profileFilled)
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: const Color(0xFFFEF6E0),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFFF1D08A)),
                            ),
                            child: const Text(
                              'Заполните рост, вес и год рождения — после этого появятся целевые КБЖУ.',
                              style: TextStyle(
                                  fontSize: 13, color: Color(0xFF8B6A12)),
                            ),
                          )
                        else if (targets != null)
                          MacroPillsRow(targets: targets)
                        else
                          const Text(
                            'Не удалось рассчитать цели — проверьте параметры профиля.',
                            style: TextStyle(fontSize: 13, color: Colors.grey),
                          ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),

                // ── План приёмов пищи ───────────────────────────────
                Card(
                  margin: EdgeInsets.zero,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'План приёмов пищи',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 12),
                        SegmentedButton<String>(
                          segments: const [
                            ButtonSegment(
                                value: '3', label: Text('3 приёма')),
                            ButtonSegment(
                                value: '5', label: Text('5 приёмов')),
                          ],
                          selected: {_mealPlanType},
                          onSelectionChanged: _saving
                              ? null
                              : (v) => _saveMealPlan(v.first),
                        ),
                        if (_saving)
                          const Padding(
                            padding: EdgeInsets.only(top: 8),
                            child: LinearProgressIndicator(),
                          ),
                        if (_error != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(
                              _error!,
                              style: const TextStyle(
                                  color: Colors.red, fontSize: 12),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 24),
                const Divider(),
                ListTile(
                  leading: const Icon(Icons.people_outline,
                      color: AppColors.secondary),
                  title: const Text('Семья'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('/family'),
                ),
                ListTile(
                  leading: const Icon(Icons.notifications_outlined),
                  title: const Text('Уведомления'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {},
                ),
                const Divider(),
                ListTile(
                  leading: const Icon(Icons.logout, color: Colors.red),
                  title: const Text('Выйти',
                      style: TextStyle(color: Colors.red)),
                  onTap: () =>
                      context.read<AuthBloc>().add(const AuthLogoutRequested()),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
DARTEOF
echo "✓ profile_screen.dart переписан"
fi

# ── 5. dart analyze (если есть в PATH) ───────────────────────────────
echo
echo "================================================================"
echo "  dart analyze (если установлен)"
echo "================================================================"
if command -v dart >/dev/null 2>&1; then
  cd "${MOB}"
  dart analyze "${LIB}/core/widgets/macro_pill.dart" \
               "${FAMILY_SCREEN}" \
               "${PROFILE_SCREEN}" 2>&1 | head -80 || true
elif command -v flutter >/dev/null 2>&1; then
  cd "${MOB}"
  flutter analyze --no-pub 2>&1 | head -80 || true
else
  echo "⚠ ни dart, ни flutter не в PATH — статический анализ пропущен"
fi

# ── 6. Сводка ────────────────────────────────────────────────────────
echo
echo "================================================================"
echo "  ИТОГО"
echo "================================================================"
echo "Изменённые файлы:"
echo "  + ${MACRO_PILL}"
echo "  ~ ${FAMILY_SCREEN}"
echo "  ~ ${PROFILE_SCREEN}"
echo
echo "Бэкапы:"
echo "  ${BACKUPS}/family_screen.dart.bak_mg204m_${TS}"
echo "  ${BACKUPS}/profile_screen.dart.bak_mg204m_${TS}"
echo
echo "ОТКАТ:"
cat <<EOF
  cp ${BACKUPS}/family_screen.dart.bak_mg204m_${TS}  ${FAMILY_SCREEN}
  cp ${BACKUPS}/profile_screen.dart.bak_mg204m_${TS} ${PROFILE_SCREEN}
  rm -f ${MACRO_PILL}
EOF
echo
echo "DONE"
