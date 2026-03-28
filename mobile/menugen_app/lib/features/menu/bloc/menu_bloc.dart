import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/db/app_database.dart';
import '../../../core/models/menu.dart';

part 'menu_event.dart';
part 'menu_state.dart';

class MenuBloc extends Bloc<MenuEvent, MenuState> {
  final ApiClient apiClient;
  final AppDatabase db;

  MenuBloc({required this.apiClient, required this.db}) : super(const MenuInitial()) {
    on<MenuLoadRequested>(_onLoad);
    on<MenuGenerateRequested>(_onGenerate);
    on<MenuItemSwapRequested>(_onSwap);
  }

  Future<void> _onLoad(MenuLoadRequested event, Emitter<MenuState> emit) async {
    emit(const MenuLoading());
    try {
      final resp = await apiClient.get('/menu/');
      final menus = (resp.data['results'] as List)
          .map((j) => Menu.fromJson(j as Map<String, dynamic>)).toList();
      emit(MenuLoaded(menus: menus));
    } catch (e) {
      emit(MenuError(message: ApiException.fromDio(e).message));
    }
  }

  Future<void> _onGenerate(MenuGenerateRequested event, Emitter<MenuState> emit) async {
    emit(const MenuGenerating());
    try {
      final resp = await apiClient.post('/menu/generate/', data: {
        'period_days': event.periodDays,
        'start_date': event.startDate,
        if (event.country != null) 'country': event.country,
      });
      final menu = Menu.fromJson(resp.data as Map<String, dynamic>);
      emit(MenuGenerated(menu: menu));
    } catch (e) {
      emit(MenuError(message: ApiException.fromDio(e).message));
    }
  }

  Future<void> _onSwap(MenuItemSwapRequested event, Emitter<MenuState> emit) async {
    try {
      await apiClient.patch(
        '/menu/\${event.menuId}/items/\${event.itemId}/',
        data: {'recipe_id': event.recipeId},
      );
      add(MenuLoadRequested());
    } catch (e) {
      emit(MenuError(message: ApiException.fromDio(e).message));
    }
  }
}
