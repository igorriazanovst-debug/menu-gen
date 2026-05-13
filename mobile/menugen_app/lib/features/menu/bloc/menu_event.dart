part of 'menu_bloc.dart';

abstract class MenuEvent extends Equatable {
  const MenuEvent();
  @override
  List<Object?> get props => [];
}

class MenuLoadRequested extends MenuEvent {
  const MenuLoadRequested();
}

class MenuGenerateRequested extends MenuEvent {
  final String startDate;
  final int periodDays;
  final String? country;
  final int? maxCookTime;
  const MenuGenerateRequested({
    required this.startDate,
    this.periodDays = 7,
    this.country,
    this.maxCookTime,
  });
  @override
  List<Object?> get props => [startDate, periodDays, country, maxCookTime];
}
