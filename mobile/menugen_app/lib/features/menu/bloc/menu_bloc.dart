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
  const MenuGenerateRequested({required this.startDate});
  @override List<Object?> get props => [startDate];
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
      final results = d is Map
          ? (d['results'] as List? ?? []).map((e) => Map<String, dynamic>.from(e as Map)).toList()
          : <Map<String, dynamic>>[];
      emit(MenuLoaded(menus: results));
    } catch (e) { emit(MenuError(e.toString())); }
  }

  Future<void> _onGenerate(MenuGenerateRequested e, Emitter<MenuState> emit) async {
    emit(const MenuGenerating());
    try {
      final r = await apiClient.post('/menu/generate/', data: {'start_date': e.startDate});
      emit(MenuGenerated(Map<String, dynamic>.from(_data(r) as Map)));
    } catch (e) { emit(MenuError(e.toString())); }
  }
}