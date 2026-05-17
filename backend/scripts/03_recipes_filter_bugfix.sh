#!/usr/bin/env bash
# Fix: BlocListener never fires when filter returns same recipes list (Equatable
# deduplicates). Also FilterSheet "Reset" must apply immediately.
set -eu

ROOT="/opt/menugen"
cd "$ROOT"
TS=$(date +%Y%m%d_%H%M%S)
BAK="$ROOT/backups/recipes_filter_bugfix_${TS}"
mkdir -p "$BAK"

APP="$ROOT/mobile/menugen_app"

echo "=== [1/3] backup ==="
cp "$APP/lib/features/recipes/bloc/recipes_bloc.dart"            "$BAK/"
cp "$APP/lib/features/recipes/widgets/filter_sheet.dart"         "$BAK/"
cp "$APP/lib/features/recipes/screens/recipes_screen.dart"       "$BAK/"
echo "backup → $BAK"

echo
echo "=== [2/3] patch recipes_bloc.dart: emit Loading before filter request ==="
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/mobile/menugen_app/lib/features/recipes/bloc/recipes_bloc.dart")
s = p.read_text()

old = """  Future<void> _onFilter(RecipesFilterChanged e, Emitter<RecipesState> emit) async {
    try {
      final params = e.filters.toQueryParams(
        search: e.search,
        page: e.page,
        fridgeNames: e.fridgeNames,
      );
      final r = await apiClient.get('/recipes/', params: params);
      final d = _data(r);
      emit(RecipesPageLoaded(recipes: _results(d), hasMore: _hasMore(d)));
    } catch (err) {
      emit(RecipesError(_msg(err)));
    }
  }"""

new = """  Future<void> _onFilter(RecipesFilterChanged e, Emitter<RecipesState> emit) async {
    // Emit Loading for fresh page (so BlocListener fires even if the next
    // RecipesPageLoaded happens to equal the previous one — Equatable dedupes).
    if (e.page <= 1) {
      emit(const RecipesLoading());
    }
    try {
      final params = e.filters.toQueryParams(
        search: e.search,
        page: e.page,
        fridgeNames: e.fridgeNames,
      );
      final r = await apiClient.get('/recipes/', params: params);
      final d = _data(r);
      emit(RecipesPageLoaded(recipes: _results(d), hasMore: _hasMore(d)));
    } catch (err) {
      emit(RecipesError(_msg(err)));
    }
  }"""

assert old in s, "marker not found in recipes_bloc.dart _onFilter"
p.write_text(s.replace(old, new))
print("recipes_bloc.dart patched.")
PYEOF

echo
echo "=== [3/3] patch filter_sheet.dart: 'Reset' applies and closes immediately ==="
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/mobile/menugen_app/lib/features/recipes/widgets/filter_sheet.dart")
s = p.read_text()

old = """                    Expanded(
                      child: OutlinedButton(
                        onPressed: () =>
                            setState(() => _f = const RecipeFilters()),
                        child: const Text('Сбросить'),
                      ),
                    ),"""

new = """                    Expanded(
                      child: OutlinedButton(
                        onPressed: () =>
                            Navigator.of(context).pop(const RecipeFilters()),
                        child: const Text('Сбросить'),
                      ),
                    ),"""

assert old in s, "marker not found in filter_sheet.dart"
p.write_text(s.replace(old, new))
print("filter_sheet.dart patched.")
PYEOF

echo
echo "=== DONE bugfix ==="
echo "Backups: $BAK"
echo
echo "Push:"
echo "  cd /opt/menugen"
echo "  git add -A && git commit -m 'fix(recipes): apply empty filters / reset' && git push origin main"
