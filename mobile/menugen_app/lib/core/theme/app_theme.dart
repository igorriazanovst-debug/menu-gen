import 'package:flutter/material.dart';

import 'app_skin.dart';

// MG_SKIN: палитра одного скина. Значения — стартовые приближения к референсам,
// точная подгонка под макеты в Фазе 1.
class SkinPalette {
  final Color primary;
  final Color secondary;
  final Color accent;
  final Color background;
  final Color surface;
  final Color surfaceAlt;
  final Color textPrimary;
  final Color textSecondary;
  final Color border;
  final Color error;

  const SkinPalette({
    required this.primary,
    required this.secondary,
    required this.accent,
    required this.background,
    required this.surface,
    required this.surfaceAlt,
    required this.textPrimary,
    required this.textSecondary,
    required this.border,
    required this.error,
  });
}

// Скин "main" — свежий зелёный (новый дефолт-бренд, см. web index.css).
const SkinPalette kMainPalette = SkinPalette(
  primary: Color(0xFF7CB342),
  secondary: Color(0xFF588157),
  accent: Color(0xFFF4A261),
  background: Color(0xFFF0F2F0),
  surface: Color(0xFFFFFFFF),
  surfaceAlt: Color(0xFFF4F6F4),
  textPrimary: Color(0xFF1F2D24),
  textSecondary: Color(0xFF7A847D),
  border: Color(0xFFE2E6E2),
  error: Color(0xFFE63946),
);

// Скин "second" — пастельный/тёмно-зелёный.
const SkinPalette kSecondPalette = SkinPalette(
  primary: Color(0xFF1B4332),
  secondary: Color(0xFFE8A8B8),
  accent: Color(0xFFC6E69B),
  background: Color(0xFFF5F7F2),
  surface: Color(0xFFFFFFFF),
  surfaceAlt: Color(0xFFF7F0F5),
  textPrimary: Color(0xFF143826),
  textSecondary: Color(0xFF8C8C8C),
  border: Color(0xFFE9E9E9),
  error: Color(0xFFE04A4A),
);

SkinPalette paletteForSkin(AppSkin skin) =>
    skin == AppSkin.second ? kSecondPalette : kMainPalette;

// MG_SKIN: семантические токены для виджетов. Phase 1: миграция хардкода →
// Theme.of(context).extension<AppTokens>().
@immutable
class AppTokens extends ThemeExtension<AppTokens> {
  final Color surfaceAlt;
  final Color textSecondary;
  final Color border;
  final Color accent;

  const AppTokens({
    required this.surfaceAlt,
    required this.textSecondary,
    required this.border,
    required this.accent,
  });

  factory AppTokens.fromPalette(SkinPalette p) => AppTokens(
        surfaceAlt: p.surfaceAlt,
        textSecondary: p.textSecondary,
        border: p.border,
        accent: p.accent,
      );

  @override
  AppTokens copyWith({
    Color? surfaceAlt,
    Color? textSecondary,
    Color? border,
    Color? accent,
  }) =>
      AppTokens(
        surfaceAlt: surfaceAlt ?? this.surfaceAlt,
        textSecondary: textSecondary ?? this.textSecondary,
        border: border ?? this.border,
        accent: accent ?? this.accent,
      );

  @override
  AppTokens lerp(ThemeExtension<AppTokens>? other, double t) {
    if (other is! AppTokens) return this;
    return AppTokens(
      surfaceAlt: Color.lerp(surfaceAlt, other.surfaceAlt, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
      border: Color.lerp(border, other.border, t)!,
      accent: Color.lerp(accent, other.accent, t)!,
    );
  }
}

// MG_SKIN: legacy-палитра = скин "main" (новый дефолт). Экраны, обращающиеся к
// AppColors.* напрямую, мигрируем на Theme/AppTokens в Фазе 1.
abstract class AppColors {
  static const primary = Color(0xFF7CB342);
  static const secondary = Color(0xFF588157);
  static const accent = Color(0xFFF4A261);
  static const background = Color(0xFFF0F2F0);
  static const textPrimary = Color(0xFF1F2D24);
  static const surface = Color(0xFFFFFFFF);
  static const error = Color(0xFFE63946);

  // Dark palette — оставлено для будущей тёмной темы.
  static const darkBackground = Color(0xFF121417);
  static const darkSurface = Color(0xFF1E2126);
  static const darkSurfaceAlt = Color(0xFF272B31);
  static const darkTextPrimary = Color(0xFFE9EEF2);
  static const darkTextSecond = Color(0xFFB0B6BD);
  static const darkDivider = Color(0xFF3A3F47);
}

class AppTheme {
  // MG_SKIN: тема по скину.
  static ThemeData forSkin(AppSkin skin) => _fromPalette(paletteForSkin(skin));

  // Совместимость: light = скин main.
  static ThemeData light() => _fromPalette(kMainPalette);

  static ThemeData _fromPalette(SkinPalette p) => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: p.primary,
          primary: p.primary,
          secondary: p.secondary,
          tertiary: p.accent,
          background: p.background,
          surface: p.surface,
          onBackground: p.textPrimary,
          onSurface: p.textPrimary,
          error: p.error,
        ),
        scaffoldBackgroundColor: p.background,
        fontFamily: 'Inter',
        extensions: [AppTokens.fromPalette(p)],
        appBarTheme: AppBarTheme(
          backgroundColor: p.background,
          foregroundColor: p.textPrimary,
          elevation: 0,
          centerTitle: true,
        ),
        bottomNavigationBarTheme: BottomNavigationBarThemeData(
          selectedItemColor: p.primary,
          unselectedItemColor: const Color(0xFF9E9E9E),
          backgroundColor: p.surface,
          type: BottomNavigationBarType.fixed,
          elevation: 8,
        ),
        cardTheme: CardTheme(
          elevation: 2,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          color: p.surface,
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          filled: true,
          fillColor: p.surface,
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: p.primary,
            foregroundColor: Colors.white,
            minimumSize: const Size.fromHeight(52),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          ),
        ),
      );
}
