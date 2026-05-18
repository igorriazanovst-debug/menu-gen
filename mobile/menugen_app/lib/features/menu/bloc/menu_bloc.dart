import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/db/app_database.dart';
import '../../../core/premium/premium_gate_cubit.dart';

part 'menu_event.dart';
part 'menu_state.dart';

/// MenuBloc — loads existing menu, generates new one.
///
/// MG-606: menu endpoints are protected by IsFamilyPremiumOrReadOnly.
/// We map 403 → [MenuPremiumLocked] and report to [PremiumGateCubit].
class MenuBloc extends Bloc<MenuEvent, MenuState> {
  final ApiClient apiClient;
  final AppDatabase db;
  final PremiumGateCubit? premiumGate;

  MenuBloc({
    required this.apiClient,
    required this.db,
    this.premiumGate,
  }) : super(const MenuLoading()) {
    on<MenuLoadRequested>(_onLoad);
    on<MenuGenerateRequested>(_onGenerate);
  }

  Map<String, dynamic> _asMap(dynamic d) =>
      d is Map ? Map<String, dynamic>.from(d) : <String, dynamic>{};

  MenuState _toErrorState(Object err, {required bool isWrite}) {
    if (err is ApiException && err.isPremiumLocked) {
      premiumGate?.reportLock(
        feature: 'menu',
        isWrite: isWrite,
        message: err.message,
      );
      return MenuPremiumLocked(message: err.message, isWrite: isWrite);
    }
    final msg = err is ApiException ? err.message : err.toString();
    return MenuError(msg);
  }

  Future<void> _onLoad(MenuLoadRequested e, Emitter<MenuState> emit) async {
    emit(const MenuLoading());
    try {
      final listResp = await apiClient.get('/menu/');
      final list = (listResp is Map ? (listResp['results'] as List? ?? []) : [])
          .whereType<Map>()
          .map((m) => Map<String, dynamic>.from(m))
          .toList();
      if (list.isEmpty) {
        emit(const MenuLoaded(menus: <Map<String, dynamic>>[]));
        return;
      }
      final firstId = list.first['id'];
      final detail = await apiClient.get('/menu/$firstId/');
      premiumGate?.reportReadSuccess();
      emit(MenuLoaded(menus: <Map<String, dynamic>>[_asMap(detail)]));
    } catch (err) {
      emit(_toErrorState(err, isWrite: false));
    }
  }

  Future<void> _onGenerate(MenuGenerateRequested e, Emitter<MenuState> emit) async {
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
  }
}
