#!/bin/bash
# /opt/menugen/mobile/scripts/mg_205ui_apply_mobile.sh
# MG-205-UI этап D (mobile): TargetField widget + integration в profile/family.
set -euo pipefail

ROOT=/opt/menugen
MOB=$ROOT/mobile/menugen_app
LIB=$MOB/lib
TS=$(date +%Y%m%d_%H%M%S)
BAK=$ROOT/backups
mkdir -p "$BAK"

WIDGET=$LIB/core/widgets/target_field.dart
PROFILE_SCR=$LIB/features/profile/screens/profile_screen.dart
FAMILY_SCR=$LIB/features/family/screens/family_screen.dart

echo "=== MG-205-UI mobile @ $TS ==="

# ─────── 1) Backups ───────
echo "[1/4] Backups..."
cp "$PROFILE_SCR" "$BAK/mobile_profile_screen.dart.bak_mg205ui_${TS}"
cp "$FAMILY_SCR"  "$BAK/mobile_family_screen.dart.bak_mg205ui_${TS}"

# ─────── 2) New widget: target_field.dart ───────
echo "[2/4] Create target_field.dart..."
mkdir -p "$(dirname $WIDGET)"
cat > "$WIDGET" <<'DART_EOF'
// MG_205UI_V_target_field = 1
import 'package:flutter/material.dart';
import '../api/api_client.dart';

/// Источник правки целевого значения.
enum TargetSource { auto, user, specialist }

TargetSource targetSourceFromString(String? s) {
  switch (s) {
    case 'user':
      return TargetSource.user;
    case 'specialist':
      return TargetSource.specialist;
    default:
      return TargetSource.auto;
  }
}

class TargetSourceMeta {
  final TargetSource source;
  final Map<String, dynamic>? byUser; // {id, name}
  final String? at;

  const TargetSourceMeta({
    required this.source,
    this.byUser,
    this.at,
  });

  factory TargetSourceMeta.fromJson(Map<String, dynamic>? json) {
    if (json == null) {
      return const TargetSourceMeta(source: TargetSource.auto);
    }
    return TargetSourceMeta(
      source: targetSourceFromString(json['source'] as String?),
      byUser: (json['by_user'] as Map?)?.cast<String, dynamic>(),
      at: json['at'] as String?,
    );
  }
}

/// Извлекает targets_meta из profile-мапы.
Map<String, TargetSourceMeta> extractTargetsMeta(Map<String, dynamic>? profile) {
  if (profile == null) return const {};
  final raw = profile['targets_meta'];
  if (raw is! Map) return const {};
  final out = <String, TargetSourceMeta>{};
  raw.forEach((k, v) {
    out[k.toString()] = TargetSourceMeta.fromJson(
      v is Map ? Map<String, dynamic>.from(v) : null,
    );
  });
  return out;
}

/// Контракт «как загрузить историю и сбросить» — позволяет переиспользовать
/// виджет для текущего пользователя и для члена семьи.
abstract class TargetLoader {
  Future<List<Map<String, dynamic>>> getHistory(String field);
  Future<void> reset(String field);
}

class MeTargetLoader implements TargetLoader {
  final ApiClient apiClient;
  final VoidCallback? onChanged;

  MeTargetLoader({required this.apiClient, this.onChanged});

  @override
  Future<List<Map<String, dynamic>>> getHistory(String field) async {
    final r = await apiClient.get('/users/me/targets/$field/history/');
    final list = (r is List ? r : (r as Map?)?['data']) as List? ?? const [];
    return list.map<Map<String, dynamic>>((e) =>
        e is Map ? Map<String, dynamic>.from(e) : <String, dynamic>{}).toList();
  }

  @override
  Future<void> reset(String field) async {
    await apiClient.post('/users/me/targets/$field/reset/');
    onChanged?.call();
  }
}

class FamilyMemberTargetLoader implements TargetLoader {
  final ApiClient apiClient;
  final int memberId;
  final VoidCallback? onChanged;

  FamilyMemberTargetLoader({
    required this.apiClient,
    required this.memberId,
    this.onChanged,
  });

  @override
  Future<List<Map<String, dynamic>>> getHistory(String field) async {
    final r = await apiClient
        .get('/family/members/$memberId/targets/$field/history/');
    final list = (r is List ? r : (r as Map?)?['data']) as List? ?? const [];
    return list.map<Map<String, dynamic>>((e) =>
        e is Map ? Map<String, dynamic>.from(e) : <String, dynamic>{}).toList();
  }

  @override
  Future<void> reset(String field) async {
    await apiClient.post('/family/members/$memberId/targets/$field/reset/');
    onChanged?.call();
  }
}

String _sourceLabel(TargetSource s) {
  switch (s) {
    case TargetSource.user:       return 'вручную';
    case TargetSource.specialist: return 'специалист';
    case TargetSource.auto:       return 'auto';
  }
}

({Color bg, Color fg, Color border}) _sourceColors(TargetSource s) {
  switch (s) {
    case TargetSource.user:
      return (
        bg: const Color(0xFFE6F0FB),
        fg: const Color(0xFF1E5BB6),
        border: const Color(0xFFB6CFEF),
      );
    case TargetSource.specialist:
      return (
        bg: const Color(0xFFEFE5F8),
        fg: const Color(0xFF6B3FA0),
        border: const Color(0xFFD1B8E8),
      );
    case TargetSource.auto:
      return (
        bg: const Color(0xFFF0F0F0),
        fg: const Color(0xFF6B6B6B),
        border: const Color(0xFFD9D9D9),
      );
  }
}

String _formatNum(dynamic v) {
  if (v == null) return '—';
  if (v is num) return v.toStringAsFixed(0);
  final s = v.toString().trim();
  if (s.isEmpty) return '—';
  final n = num.tryParse(s);
  return n == null ? '—' : n.toStringAsFixed(0);
}

String _formatDate(String? iso) {
  if (iso == null) return '—';
  try {
    final dt = DateTime.parse(iso).toLocal();
    final dd = dt.day.toString().padLeft(2, '0');
    final mm = dt.month.toString().padLeft(2, '0');
    final hh = dt.hour.toString().padLeft(2, '0');
    final mi = dt.minute.toString().padLeft(2, '0');
    return '$dd.$mm ${dt.year} $hh:$mi';
  } catch (_) {
    return iso;
  }
}

/// Компактная пилюля КБЖУ + бейдж источника + onTap → bottom sheet с историей и reset.
class TargetField extends StatelessWidget {
  final String label;       // 'Ккал'
  final String unit;        // 'г' / 'ккал'
  final String field;       // 'calorie_target' и т.п.
  final dynamic value;
  final TargetSourceMeta meta;
  final Color background;
  final Color foreground;
  final TargetLoader loader;
  final bool readOnly;

  const TargetField({
    super.key,
    required this.label,
    required this.unit,
    required this.field,
    required this.value,
    required this.meta,
    required this.background,
    required this.foreground,
    required this.loader,
    this.readOnly = false,
  });

  void _openSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => _HistorySheet(
        field: field,
        label: label,
        unit: unit,
        value: value,
        meta: meta,
        loader: loader,
        readOnly: readOnly,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bc = _sourceColors(meta.source);
    return InkWell(
      onTap: () => _openSheet(context),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    label.toUpperCase(),
                    style: TextStyle(
                      fontSize: 9,
                      letterSpacing: 0.4,
                      color: foreground.withOpacity(0.7),
                      fontWeight: FontWeight.w600,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                  decoration: BoxDecoration(
                    color: bc.bg,
                    border: Border.all(color: bc.border, width: 0.5),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    _sourceLabel(meta.source),
                    style: TextStyle(
                      fontSize: 7,
                      color: bc.fg,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.3,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 2),
            Text(
              _formatNum(value),
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
      ),
    );
  }
}

class _HistorySheet extends StatefulWidget {
  final String field;
  final String label;
  final String unit;
  final dynamic value;
  final TargetSourceMeta meta;
  final TargetLoader loader;
  final bool readOnly;

  const _HistorySheet({
    required this.field,
    required this.label,
    required this.unit,
    required this.value,
    required this.meta,
    required this.loader,
    required this.readOnly,
  });

  @override
  State<_HistorySheet> createState() => _HistorySheetState();
}

class _HistorySheetState extends State<_HistorySheet> {
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _history = const [];
  bool _resetting = false;

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
      final h = await widget.loader.getHistory(widget.field);
      setState(() {
        _history = h;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _reset() async {
    setState(() => _resetting = true);
    try {
      await widget.loader.reset(widget.field);
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${widget.label}: сброшено к авто')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString())),
      );
    } finally {
      if (mounted) setState(() => _resetting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    final canReset = !widget.readOnly && widget.meta.source != TargetSource.auto;

    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Text(
                '${widget.label} — история',
                style: const TextStyle(
                    fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
          const Divider(),
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 320),
            child: _loading
                ? const Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(child: CircularProgressIndicator()),
                  )
                : _error != null
                    ? Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text(_error!,
                            style: const TextStyle(color: Colors.red)),
                      )
                    : _history.isEmpty
                        ? const Padding(
                            padding: EdgeInsets.all(16),
                            child: Text('Записей нет',
                                style: TextStyle(color: Colors.grey)),
                          )
                        : ListView.separated(
                            shrinkWrap: true,
                            itemCount: _history.length,
                            separatorBuilder: (_, __) =>
                                const Divider(height: 1),
                            itemBuilder: (_, i) {
                              final e = _history[i];
                              final src = targetSourceFromString(
                                  e['source'] as String?);
                              final bc = _sourceColors(src);
                              final byUser = e['by_user'] as Map?;
                              return ListTile(
                                dense: true,
                                contentPadding: EdgeInsets.zero,
                                leading: Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: bc.bg,
                                    border: Border.all(
                                        color: bc.border, width: 0.5),
                                    borderRadius:
                                        BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    _sourceLabel(src),
                                    style: TextStyle(
                                        fontSize: 9,
                                        color: bc.fg,
                                        fontWeight: FontWeight.bold),
                                  ),
                                ),
                                title: Text(
                                  '${_formatNum(e['old_value'])} → ${_formatNum(e['new_value'])} ${widget.unit}',
                                  style: const TextStyle(fontSize: 13),
                                ),
                                subtitle: Text(
                                  '${_formatDate(e['at'] as String?)}'
                                  '${byUser != null ? ' · ${byUser['name']}' : ''}',
                                  style: const TextStyle(fontSize: 11),
                                ),
                              );
                            },
                          ),
          ),
          if (canReset) ...[
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _resetting ? null : _reset,
              icon: _resetting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.restart_alt, size: 18),
              label: Text(_resetting ? 'Сброс…' : 'Сбросить к авто'),
            ),
          ],
        ],
      ),
    );
  }
}

/// Готовый ряд из 5 пилюль КБЖУ с meta и loader.
class TargetFieldsRow extends StatelessWidget {
  final Map<String, dynamic> targets;
  final Map<String, TargetSourceMeta> meta;
  final TargetLoader loader;
  final bool readOnly;

  const TargetFieldsRow({
    super.key,
    required this.targets,
    required this.meta,
    required this.loader,
    this.readOnly = false,
  });

  TargetSourceMeta _m(String f) =>
      meta[f] ?? const TargetSourceMeta(source: TargetSource.auto);

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: TargetField(
            label: 'Ккал',
            unit: 'ккал',
            field: 'calorie_target',
            value: targets['calorie_target'],
            meta: _m('calorie_target'),
            background: const Color(0xFFFEEAEA),
            foreground: const Color(0xFFE34A4A),
            loader: loader,
            readOnly: readOnly,
          ),
        ),
        const SizedBox(width: 6),
        Expanded(
          child: TargetField(
            label: 'Белок',
            unit: 'г',
            field: 'protein_target_g',
            value: targets['protein_target_g'],
            meta: _m('protein_target_g'),
            background: const Color(0xFFE6F0FB),
            foreground: const Color(0xFF1E5BB6),
            loader: loader,
            readOnly: readOnly,
          ),
        ),
        const SizedBox(width: 6),
        Expanded(
          child: TargetField(
            label: 'Жиры',
            unit: 'г',
            field: 'fat_target_g',
            value: targets['fat_target_g'],
            meta: _m('fat_target_g'),
            background: const Color(0xFFFEF3D6),
            foreground: const Color(0xFFB8770A),
            loader: loader,
            readOnly: readOnly,
          ),
        ),
        const SizedBox(width: 6),
        Expanded(
          child: TargetField(
            label: 'Углев',
            unit: 'г',
            field: 'carb_target_g',
            value: targets['carb_target_g'],
            meta: _m('carb_target_g'),
            background: const Color(0xFFE0F5EB),
            foreground: const Color(0xFF1F8B5C),
            loader: loader,
            readOnly: readOnly,
          ),
        ),
        const SizedBox(width: 6),
        Expanded(
          child: TargetField(
            label: 'Клетч',
            unit: 'г',
            field: 'fiber_target_g',
            value: targets['fiber_target_g'],
            meta: _m('fiber_target_g'),
            background: const Color(0xFFEFE5F8),
            foreground: const Color(0xFF6B3FA0),
            loader: loader,
            readOnly: readOnly,
          ),
        ),
      ],
    );
  }
}
DART_EOF
echo "  created ✓"

# ─────── 3) Patch profile_screen.dart ───────
echo "[3/4] Patch profile_screen.dart..."
python3 <<PYEOF
import re
from pathlib import Path

p = Path("$PROFILE_SCR")
src = p.read_text()
if "MG_205UI_V_profile" in src:
    print("  already patched"); raise SystemExit(0)

# Заменяем заголовочный маркер
src = src.replace(
    "// MG_204m_V_profile = 1",
    "// MG_204m_V_profile = 1\n// MG_205UI_V_profile = 1",
    1,
)

# Импорт нового виджета (заменяем macro_pill на target_field)
src = src.replace(
    "import '../../../core/widgets/macro_pill.dart';",
    "import '../../../core/widgets/macro_pill.dart';\n"
    "import '../../../core/widgets/target_field.dart';",
    1,
)

# Заменяем `MacroPillsRow(targets: targets)` на TargetFieldsRow с loader
old = "MacroPillsRow(targets: targets)"
new = (
    "TargetFieldsRow(\n"
    "                            targets: targets,\n"
    "                            meta: extractTargetsMeta(profile),\n"
    "                            loader: MeTargetLoader(\n"
    "                              apiClient: widget.apiClient,\n"
    "                              onChanged: _load,\n"
    "                            ),\n"
    "                          )"
)
assert old in src, "MacroPillsRow not found in profile_screen.dart"
src = src.replace(old, new, 1)

p.write_text(src)
print("  patched ✓")
PYEOF

# ─────── 4) Patch family_screen.dart ───────
echo "[4/4] Patch family_screen.dart..."
python3 <<PYEOF
import re
from pathlib import Path

p = Path("$FAMILY_SCR")
src = p.read_text()
if "MG_205UI_V_family" in src:
    print("  already patched"); raise SystemExit(0)

# Маркер в шапке
src = src.replace(
    "// MG_204m_V_family = 1",
    "// MG_204m_V_family = 1\n// MG_205UI_V_family = 1",
    1,
)

# Импорт target_field
src = src.replace(
    "import '../../../core/widgets/macro_pill.dart';",
    "import '../../../core/widgets/macro_pill.dart';\n"
    "import '../../../core/widgets/target_field.dart';",
    1,
)

# В _EditMemberSheet: заменяем MacroPillsRow(targets: targets) на TargetFieldsRow
# Нужен apiClient, который мы возьмём из родительского bloc через context. 
# Но у нас есть прямой доступ только к BlocProvider; используем GetIt? 
# Проще: добавить параметр apiClient в _EditMemberSheet; пока — берём из ApiClient,
# который доступен через RepositoryProvider/Inheritance. У проекта есть BlocProvider<FamilyBloc>:
# FamilyBloc хранит apiClient. Используем его.

old = "MacroPillsRow(targets: targets),"
new = (
    "TargetFieldsRow(\n"
    "                          targets: targets,\n"
    "                          meta: extractTargetsMeta(profile),\n"
    "                          loader: FamilyMemberTargetLoader(\n"
    "                            apiClient: context.read<FamilyBloc>().apiClient,\n"
    "                            memberId: widget.member['id'] as int,\n"
    "                            onChanged: () => context\n"
    "                                .read<FamilyBloc>()\n"
    "                                .add(const FamilyLoadRequested()),\n"
    "                          ),\n"
    "                        ),"
)
assert old in src, "MacroPillsRow(targets: targets) not found in family_screen.dart"
src = src.replace(old, new, 1)

p.write_text(src)
print("  patched ✓")
PYEOF

echo ""
echo "── markers ──"
grep -nE "MG_205UI_V_" $WIDGET $PROFILE_SCR $FAMILY_SCR

echo ""
echo "── flutter analyze ──"
cd $MOB
flutter analyze --no-pub lib/core/widgets/target_field.dart \
                         lib/features/profile/screens/profile_screen.dart \
                         lib/features/family/screens/family_screen.dart 2>&1 | tail -40 || true

echo ""
echo "=== DONE @ $TS ==="
echo "Backups: $BAK/*_mg205ui_${TS}*"
