part of 'menu_bloc.dart';

abstract class MenuEvent extends Equatable {
  const MenuEvent();
  @override
  List<Object?> get props => [];
}

class MenuLoadRequested extends MenuEvent {
  const MenuLoadRequested();
}

/// MG_608_V_mobile_event: загрузить детали по конкретному id
class MenuDetailRequested extends MenuEvent {
  final int menuId;
  const MenuDetailRequested(this.menuId);
  @override
  List<Object?> get props => [menuId];
}

class MenuGenerateRequested extends MenuEvent {
  // MG_607_V_mobile_event
  final String startDate;
  final int periodDays;
  final String? country;          // legacy single
  final List<String>? countries;  // MG-607
  final int? maxCookTime;
  final String? mealPlanType;     // '3' | '5'
  final List<String>? excludeAllergens;  // null = из profile; [] = выкл
  final List<String>? excludeDisliked;   // null = из profile; [] = выкл
  final bool withSoup; // MG_610_V_mobile
  const MenuGenerateRequested({
    required this.startDate,
    this.periodDays = 7,
    this.country,
    this.countries,
    this.maxCookTime,
    this.mealPlanType,
    this.excludeAllergens,
    this.excludeDisliked,
    this.withSoup = true, // MG_610_V_mobile
  });
  @override
  List<Object?> get props => [
        startDate, periodDays, country, countries,
        maxCookTime, mealPlanType, excludeAllergens, excludeDisliked,
        withSoup,
      ];
}
