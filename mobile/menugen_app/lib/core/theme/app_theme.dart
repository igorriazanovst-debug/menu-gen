import 'package:flutter/material.dart';

abstract class AppColors {
  static const primary     = Color(0xFFE63946); // Томатный красный
  static const secondary   = Color(0xFF588157); // Авокадо зелёный
  static const accent      = Color(0xFFF4A261); // Лимонный жёлтый
  static const background  = Color(0xFFF1FAEE); // Рисовый белый
  static const textPrimary = Color(0xFF1D3557); // Тёмный шоколад
  static const surface     = Color(0xFFFFFFFF);
  static const error       = Color(0xFFBA1A1A);
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
    colorScheme: ColorScheme.fromSeed(
      seedColor: AppColors.primary,
      brightness: Brightness.dark,
      primary: AppColors.primary,
      secondary: AppColors.secondary,
    ),
    fontFamily: 'Inter',
  );
}
