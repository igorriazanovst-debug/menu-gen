#!/bin/bash
# /opt/menugen/backend/scripts/mg_607_apply_mobile.sh
# MG-607 mobile: расширяем MenuGenerateRequested, переписываем GenerateMenuBottomSheet, прокидываем apiClient.
# ПРЕДВАРИТЕЛЬНО положи в /opt/menugen/backend/scripts/:
#   - generate_menu_bottom_sheet.dart  (заменит mobile/.../widgets/generate_menu_bottom_sheet.dart)
set -euo pipefail

ROOT=/opt/menugen
M=$ROOT/mobile/menugen_app
SCRIPTS=$ROOT/backend/scripts
TS=$(date +%Y%m%d_%H%M%S)
BAK=$ROOT/backups/mg_607_mobile_$TS
mkdir -p "$BAK"

echo "═══ Backup ═══"
cp "$M/lib/features/menu/bloc/menu_bloc.dart"     "$BAK/menu_bloc.dart.bak"
cp "$M/lib/features/menu/bloc/menu_event.dart"    "$BAK/menu_event.dart.bak"
cp "$M/lib/features/menu/screens/menu_screen.dart" "$BAK/menu_screen.dart.bak"
cp "$M/lib/features/menu/widgets/generate_menu_bottom_sheet.dart" "$BAK/generate_menu_bottom_sheet.dart.bak"
echo "Saved to $BAK"

# ─── 1) menu_event.dart — расширяем MenuGenerateRequested ──────────────
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/mobile/menugen_app/lib/features/menu/bloc/menu_event.dart")
src = p.read_text(encoding="utf-8")

if "MG_607_V_mobile_event" in src:
    print("[menu_event.dart] already patched — skipped")
    raise SystemExit(0)

new_class = '''class MenuGenerateRequested extends MenuEvent {
  // MG_607_V_mobile_event
  final String startDate;
  final int periodDays;
  final String? country;          // legacy single
  final List<String>? countries;  // MG-607
  final int? maxCookTime;
  final String? mealPlanType;     // '3' | '5'
  final List<String>? excludeAllergens;  // null = из profile; [] = выкл
  final List<String>? excludeDisliked;   // null = из profile; [] = выкл
  const MenuGenerateRequested({
    required this.startDate,
    this.periodDays = 7,
    this.country,
    this.countries,
    this.maxCookTime,
    this.mealPlanType,
    this.excludeAllergens,
    this.excludeDisliked,
  });
  @override
  List<Object?> get props => [
        startDate, periodDays, country, countries,
        maxCookTime, mealPlanType, excludeAllergens, excludeDisliked,
      ];
}'''

import re
# заменяем весь класс целиком
src = re.sub(
    r'class MenuGenerateRequested extends MenuEvent \{.*?\n\}',
    new_class,
    src,
    count=1, flags=re.DOTALL,
)
p.write_text(src, encoding="utf-8")
print("[menu_event.dart] patched")
PYEOF

# ─── 2) menu_bloc.dart — пробрасываем новые поля ───────────────────────
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/mobile/menugen_app/lib/features/menu/bloc/menu_bloc.dart")
src = p.read_text(encoding="utf-8")

if "MG_607_V_mobile_bloc" in src:
    print("[menu_bloc.dart] already patched — skipped")
    raise SystemExit(0)

old = '''  Future<void> _onGenerate(MenuGenerateRequested e, Emitter<MenuState> emit) async {
    emit(const MenuGenerating());
    try {
      final body = <String, dynamic>{
        'start_date': e.startDate,
        'period_days': e.periodDays,
      };
      if (e.country != null) body['country'] = e.country;
      if (e.maxCookTime != null) body['max_cook_time'] = e.maxCookTime;
      final r = await apiClient.post('/menu/generate/', data: body);
      emit(MenuGenerated(_asMap(r)));
    } catch (err) {
      emit(_toErrorState(err, isWrite: true));
    }
  }'''

new = '''  Future<void> _onGenerate(MenuGenerateRequested e, Emitter<MenuState> emit) async {
    // MG_607_V_mobile_bloc: расширенный body (countries, exclude_allergens, exclude_disliked, meal_plan_type)
    emit(const MenuGenerating());
    try {
      final body = <String, dynamic>{
        'start_date': e.startDate,
        'period_days': e.periodDays,
      };
      if (e.country != null) body['country'] = e.country;
      if (e.countries != null && e.countries!.isNotEmpty) {
        body['countries'] = e.countries;
      }
      if (e.maxCookTime != null) body['max_cook_time'] = e.maxCookTime;
      if (e.mealPlanType != null) body['meal_plan_type'] = e.mealPlanType;
      if (e.excludeAllergens != null) body['exclude_allergens'] = e.excludeAllergens;
      if (e.excludeDisliked != null) body['exclude_disliked'] = e.excludeDisliked;
      final r = await apiClient.post('/menu/generate/', data: body);
      emit(MenuGenerated(_asMap(r)));
    } catch (err) {
      emit(_toErrorState(err, isWrite: true));
    }
  }'''

if old not in src:
    raise SystemExit("FAIL: _onGenerate anchor not found in menu_bloc.dart")
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("[menu_bloc.dart] patched")
PYEOF

# ─── 3) generate_menu_bottom_sheet.dart — заменяем целиком ─────────────
if [ ! -f "$SCRIPTS/generate_menu_bottom_sheet.dart" ]; then
  echo "ERROR: $SCRIPTS/generate_menu_bottom_sheet.dart not found"
  exit 1
fi
cp "$SCRIPTS/generate_menu_bottom_sheet.dart" \
   "$M/lib/features/menu/widgets/generate_menu_bottom_sheet.dart"
echo "[generate_menu_bottom_sheet.dart] replaced"

# ─── 4) menu_screen.dart — прокидываем apiClient в Sheet ───────────────
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/mobile/menugen_app/lib/features/menu/screens/menu_screen.dart")
src = p.read_text(encoding="utf-8")

if "MG_607_V_mobile_screen" in src:
    print("[menu_screen.dart] already patched — skipped")
    raise SystemExit(0)

old = '''      builder: (_) => BlocProvider.value(
        value: context.read<MenuBloc>(),
        child: const GenerateMenuBottomSheet(),
      ),'''

new = '''      builder: (_) => BlocProvider.value(
        value: context.read<MenuBloc>(),
        // MG_607_V_mobile_screen: передаём apiClient в sheet
        child: GenerateMenuBottomSheet(apiClient: widget.apiClient),
      ),'''

if old not in src:
    raise SystemExit("FAIL: builder anchor not found in menu_screen.dart")
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("[menu_screen.dart] patched")
PYEOF

echo
echo "═══ Done. Push to GitHub → wait CI → download APK ═══"
echo "Run:"
echo "  cd /opt/menugen && git add -A && git status --short"
