import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/db/app_database.dart';

abstract class MenuEvent extends Equatable {
  const MenuEvent();
  @override List<Object?> get props => [];
}
class MenuLoadRequested extends MenuEvent {}
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
  @override List<Object?> get props => [startDate, periodDays, country, maxCookTime];
}

abstract class MenuState extends Equatable {
  const MenuState();
  @override List<Object?> get props => [];
}
class MenuLoading extends MenuState { const MenuLoading(); }
class MenuLoaded extends MenuState {
  final List<Map<String, dynamic>> menus;
  const MenuLoaded({required this.menus});
  @override List<Object?> get props => [menus];
}
class MenuGenerating extends MenuState { const MenuGenerating(); }
class MenuGenerated extends MenuState {
  final Map<String, dynamic> menu;
  const MenuGenerated(this.menu);
  @override List<Object?> get props => [menu];
}
class MenuError extends MenuState {
  final String message;
  const MenuError(this.message);
  @override List<Object?> get props => [message];
}

class MenuBloc extends Bloc<MenuEvent, MenuState> {
  final ApiClient apiClient;
  final AppDatabase db;
  MenuBloc({required this.apiClient, required this.db}) : super(const MenuLoading()) {
    on<MenuLoadRequested>(_onLoad);
    on<MenuGenerateRequested>(_onGenerate);
  }
  dynamic _data(dynamic r) { try { return r.data; } catch (_) { return r; } }

  Future<void> _onLoad(MenuLoadRequested e, Emitter<MenuState> emit) async {
    emit(const MenuLoading());
    try {
      final r = await apiClient.get('/menu/');
      final d = _data(r);
      final list = d is Map
          ? (d['results'] as List? ?? []).map((e) => Map<String, dynamic>.from(e as Map)).toList()
          : <Map<String, dynamic>>[];
      if (list.isEmpty) { emit(MenuLoaded(menus: [])); return; }
      // Загружаем детали первого (последнего) меню
      final firstId = list.first['id'];
      final detail = await apiClient.get('/menu/$firstId/');
      final detailMap = Map<String, dynamic>.from(_data(detail) as Map);
      emit(MenuLoaded(menus: [detailMap]));
    } catch (e) { emit(MenuError(e.toString())); }
  }

  Future<void> _onGenerate(MenuGenerateRequested e, Emitter<MenuState> emit) async {
    emit(const MenuGenerating());
    try {
      final data = <String, dynamic>{
        'start_date': e.startDate,
        'period_days': e.periodDays,
      };
      if (e.country != null) data['country'] = e.country;
      if (e.maxCookTime != null) data['max_cook_time'] = e.maxCookTime;
      final r = await apiClient.post('/menu/generate/', data: data);
      emit(MenuGenerated(Map<String, dynamic>.from(_data(r) as Map)));
    } catch (e) { emit(MenuError(e.toString())); }
  }
}