#!/usr/bin/env bash
# MG-204 mobile fix1: повторно применить патч family_screen с робастными regex
# Использует найденные ранее бэкапы.
set -euo pipefail

ROOT="/opt/menugen"
MOB="${ROOT}/mobile/menugen_app"
LIB="${MOB}/lib"
BACKUPS="${ROOT}/backups"

FAMILY_SCREEN="${LIB}/features/family/screens/family_screen.dart"
PROFILE_SCREEN="${LIB}/features/profile/screens/profile_screen.dart"
MACRO_PILL="${LIB}/core/widgets/macro_pill.dart"

# 1) Откатываем family_screen к последнему бэкапу (если есть)
LAST_FAM=$(ls -1t "${BACKUPS}"/family_screen.dart.bak_mg204m_* 2>/dev/null | head -1 || true)
LAST_PRO=$(ls -1t "${BACKUPS}"/profile_screen.dart.bak_mg204m_* 2>/dev/null | head -1 || true)

if [ -n "${LAST_FAM}" ]; then
  cp "${LAST_FAM}" "${FAMILY_SCREEN}"
  echo "↻ family_screen восстановлен из ${LAST_FAM}"
fi
if [ -n "${LAST_PRO}" ]; then
  cp "${LAST_PRO}" "${PROFILE_SCREEN}"
  echo "↻ profile_screen восстановлен из ${LAST_PRO}"
fi

# 2) Чиним family_screen — используем regex
python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/mobile/menugen_app/lib/features/family/screens/family_screen.dart")
src = p.read_text(encoding="utf-8")

if "MG_204m_V_family" in src:
    print("⚠ family_screen уже патчен — пропускаю")
    raise SystemExit(0)

# 2.1 импорт
imp_old = "import '../bloc/family_bloc.dart';"
imp_new = ("import '../bloc/family_bloc.dart';\n"
           "import '../../../core/widgets/macro_pill.dart';\n"
           "// MG_204m_V_family = 1")
assert imp_old in src, "import bloc не найден"
src = src.replace(imp_old, imp_new, 1)

# 2.2 декларации полей
decls_old = "  String? _gender;\n  String? _activityLevel;\n  String? _goal;"
decls_new = "  String? _gender;\n  String? _activityLevel;\n  String? _goal;\n  String _mealPlanType = '3';"
assert decls_old in src, "декларации полей не найдены"
src = src.replace(decls_old, decls_new, 1)

# 2.3 initState — добавить парсинг meal_plan_type перед закрывающей `}` метода
init_old = "    _goal = profile['goal'] as String?;\n  }"
init_new = ("    _goal = profile['goal'] as String?;\n"
            "    _mealPlanType = (profile['meal_plan_type'] as String?) ?? '3';\n"
            "  }")
assert init_old in src, "конец initState не найден"
src = src.replace(init_old, init_new, 1)

# 2.4 _save() — добавить meal_plan_type. Ищем строку про goal в _save
# Используем regex, нечувствительный к пробелам и пустым строкам.
save_pat = re.compile(
    r"(if \(_goal != null\) profile\['goal'\] = _goal;)\s*\n",
    re.MULTILINE
)
m = save_pat.search(src)
assert m, "_save: блок про _goal не найден"
src = save_pat.sub(
    r"\1\n      profile['meal_plan_type'] = _mealPlanType;\n",
    src,
    count=1,
)

# 2.5 UI — после _calorieCtrl _field вставить пилюли + meal_plan toggle.
# Ищем _field(_calorieCtrl, ...). Регексом — устойчиво к пробелам.
ui_pat = re.compile(
    r"(_field\(_calorieCtrl,\s*'Целевые калории',\s*\n\s*type:\s*TextInputType\.number\),)\s*\n"
)
m = ui_pat.search(src)
assert m, "UI: _field(_calorieCtrl) не найден"

ui_inject = r"""\1
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
"""
src = ui_pat.sub(ui_inject, src, count=1)

p.write_text(src, encoding="utf-8")
print("✓ family_screen.dart пропатчен")
PYEOF

# 3) profile_screen — переписываем (как в основном apply, идемпотентно)
if grep -q "MG_204m_V_profile" "${PROFILE_SCREEN}" 2>/dev/null; then
  echo "⚠ profile_screen уже патчен"
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
      final data = r is Map<String, dynamic>
          ? r
          : Map<String, dynamic>.from(r as Map);
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

# 4) проверка корректности Dart-синтаксиса (базовая — балансы скобок)
echo
echo "── Проверка балансов скобок ──"
for f in "${FAMILY_SCREEN}" "${PROFILE_SCREEN}" "${MACRO_PILL}"; do
  if [ -f "$f" ]; then
    awk -v f="$f" '
      { for (i=1;i<=length($0);i++){c=substr($0,i,1); if(c=="{")o++; else if(c=="}")cl++; if(c=="(")po++; else if(c==")")pc++} }
      END { printf "  %s: { %d/%d  ( %d/%d\n", f, o, cl, po, pc }
    ' "$f"
  fi
done

# 5) dart analyze (если есть)
if command -v dart >/dev/null 2>&1; then
  cd "${MOB}"
  echo
  echo "── dart analyze (ключевые файлы) ──"
  dart analyze "${FAMILY_SCREEN}" "${PROFILE_SCREEN}" "${MACRO_PILL}" 2>&1 | head -80 || true
elif command -v flutter >/dev/null 2>&1; then
  cd "${MOB}"
  echo
  echo "── flutter analyze ──"
  flutter analyze --no-pub 2>&1 | head -80 || true
else
  echo
  echo "⚠ dart/flutter не в PATH — статический анализ пропущен"
fi

echo
echo "DONE"
