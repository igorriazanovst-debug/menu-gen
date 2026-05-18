#!/usr/bin/env bash
# Patch: dark-theme bug fix
#   1) main.dart -> themeMode: ThemeMode.light (forces light regardless of system)
#   2) app_theme.dart -> rewrite AppTheme.dark() with full surfaces (for future)
set -eu

ROOT="/opt/menugen"
APP="$ROOT/mobile/menugen_app"
cd "$ROOT"

TS=$(date +%Y%m%d_%H%M%S)
BAK="$ROOT/backups/dark_theme_fix_${TS}"
mkdir -p "$BAK/core/theme" "$BAK"

echo "=== [1/4] backup main.dart + app_theme.dart ==="
cp "$APP/lib/main.dart"                   "$BAK/main.dart"
cp "$APP/lib/core/theme/app_theme.dart"   "$BAK/core/theme/app_theme.dart"
echo "backup -> $BAK"

echo
echo "=== [2/4] patch main.dart: ThemeMode.system -> ThemeMode.light ==="
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/mobile/menugen_app/lib/main.dart")
s = p.read_text()
old = "themeMode: ThemeMode.system,"
new = "themeMode: ThemeMode.light, // dark theme disabled until full migration"
if old not in s:
    raise SystemExit("ERROR: marker 'themeMode: ThemeMode.system,' not found in main.dart")
p.write_text(s.replace(old, new))
print("main.dart updated.")
PYEOF

echo
echo "=== [3/4] rewrite app_theme.dart with full dark theme ==="
cat > "$APP/lib/core/theme/app_theme.dart" <<'DARTEOF'
import 'package:flutter/material.dart';

abstract class AppColors {
  // Light palette
  static const primary     = Color(0xFFE63946); // Томатный красный
  static const secondary   = Color(0xFF588157); // Авокадо зелёный
  static const accent      = Color(0xFFF4A261); // Лимонный жёлтый
  static const background  = Color(0xFFF1FAEE); // Рисовый белый
  static const textPrimary = Color(0xFF1D3557); // Тёмный шоколад
  static const surface     = Color(0xFFFFFFFF);
  static const error       = Color(0xFFBA1A1A);

  // Dark palette (used by AppTheme.dark())
  static const darkBackground  = Color(0xFF121417);
  static const darkSurface     = Color(0xFF1E2126);
  static const darkSurfaceAlt  = Color(0xFF272B31);
  static const darkTextPrimary = Color(0xFFE9EEF2);
  static const darkTextSecond  = Color(0xFFB0B6BD);
  static const darkDivider     = Color(0xFF3A3F47);
}

class AppTheme {
  static ThemeData light() => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: AppColors.primary,
          primary: AppColors.primary,
          secondary: AppColors.secondary,
          tertiary: AppColors.accent,
          background: AppColors.background,
          surface: AppColors.surface,
          onBackground: AppColors.textPrimary,
          onSurface: AppColors.textPrimary,
          error: AppColors.error,
        ),
        scaffoldBackgroundColor: AppColors.background,
        fontFamily: 'Inter',
        appBarTheme: const AppBarTheme(
          backgroundColor: AppColors.background,
          foregroundColor: AppColors.textPrimary,
          elevation: 0,
          centerTitle: true,
        ),
        bottomNavigationBarTheme: const BottomNavigationBarThemeData(
          selectedItemColor: AppColors.primary,
          unselectedItemColor: Color(0xFF9E9E9E),
          backgroundColor: AppColors.surface,
          type: BottomNavigationBarType.fixed,
          elevation: 8,
        ),
        cardTheme: CardTheme(
          elevation: 2,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          color: AppColors.surface,
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          filled: true,
          fillColor: AppColors.surface,
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.primary,
            foregroundColor: Colors.white,
            minimumSize: const Size.fromHeight(52),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          ),
        ),
      );

  static ThemeData dark() => ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: AppColors.primary,
          brightness: Brightness.dark,
          primary: AppColors.primary,
          secondary: AppColors.secondary,
          tertiary: AppColors.accent,
          background: AppColors.darkBackground,
          surface: AppColors.darkSurface,
          onBackground: AppColors.darkTextPrimary,
          onSurface: AppColors.darkTextPrimary,
          error: AppColors.error,
        ),
        scaffoldBackgroundColor: AppColors.darkBackground,
        fontFamily: 'Inter',
        dividerColor: AppColors.darkDivider,
        appBarTheme: const AppBarTheme(
          backgroundColor: AppColors.darkBackground,
          foregroundColor: AppColors.darkTextPrimary,
          elevation: 0,
          centerTitle: true,
          iconTheme: IconThemeData(color: AppColors.darkTextPrimary),
        ),
        bottomNavigationBarTheme: const BottomNavigationBarThemeData(
          selectedItemColor: AppColors.primary,
          unselectedItemColor: AppColors.darkTextSecond,
          backgroundColor: AppColors.darkSurface,
          type: BottomNavigationBarType.fixed,
          elevation: 8,
        ),
        cardTheme: CardTheme(
          elevation: 2,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          color: AppColors.darkSurface,
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          filled: true,
          fillColor: AppColors.darkSurfaceAlt,
          labelStyle: const TextStyle(color: AppColors.darkTextSecond),
          hintStyle: const TextStyle(color: AppColors.darkTextSecond),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.primary,
            foregroundColor: Colors.white,
            minimumSize: const Size.fromHeight(52),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          ),
        ),
        textTheme: const TextTheme().apply(
          bodyColor: AppColors.darkTextPrimary,
          displayColor: AppColors.darkTextPrimary,
        ),
        iconTheme: const IconThemeData(color: AppColors.darkTextPrimary),
        listTileTheme: const ListTileThemeData(
          textColor: AppColors.darkTextPrimary,
          iconColor: AppColors.darkTextPrimary,
        ),
        chipTheme: const ChipThemeData(
          backgroundColor: AppColors.darkSurfaceAlt,
          labelStyle: TextStyle(color: AppColors.darkTextPrimary),
          side: BorderSide(color: AppColors.darkDivider),
        ),
        dialogTheme: const DialogTheme(
          backgroundColor: AppColors.darkSurface,
          titleTextStyle: TextStyle(
            color: AppColors.darkTextPrimary,
            fontSize: 20,
            fontWeight: FontWeight.w600,
          ),
          contentTextStyle: TextStyle(color: AppColors.darkTextPrimary),
        ),
        bottomSheetTheme: const BottomSheetThemeData(
          backgroundColor: AppColors.darkSurface,
          surfaceTintColor: AppColors.darkSurface,
        ),
        snackBarTheme: const SnackBarThemeData(
          backgroundColor: AppColors.darkSurfaceAlt,
          contentTextStyle: TextStyle(color: AppColors.darkTextPrimary),
        ),
      );
}
DARTEOF
echo "app_theme.dart rewritten."

echo
echo "=== [4/4] verify ==="
echo "--- main.dart themeMode line:"
grep -n "themeMode:" "$APP/lib/main.dart"
echo
echo "--- app_theme.dart lines count:"
wc -l "$APP/lib/core/theme/app_theme.dart"

echo
echo "=== DONE. Backup: $BAK ==="
echo "Next: rebuild APK from $APP and re-expose."
