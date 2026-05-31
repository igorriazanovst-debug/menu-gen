import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/db/app_database.dart';
import '../../../core/premium/premium_gate_cubit.dart';

part 'menu_event.dart';
part 'menu_state.dart';

/// MenuBloc — loads existing menus, generates new one.
///
/// MG-606: menu endpoints are protected by IsFamilyPremiumOrReadOnly.
/// We map 403 → [MenuPremiumLocked] and report to [PremiumGateCubit].
class MenuBloc extends Bloc<MenuEvent, MenuState> {
  final ApiClient apiClient;
  final AppDatabase db;
  final PremiumGateCubit? premiumGate;

  // MG_608_V_mobile_bloc
  static const String _kPrefKey = 'menugen.lastMenuId';

  MenuBloc({
    required this.apiClient,
    required this.db,
    this.premiumGate,
  }) : super(const MenuLoading()) {
    on<MenuLoadRequested>(_onLoad);
    on<MenuDetailRequested>(_onDetail);
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

  Future<int?> _readLastMenuId() async {
    try {
      final p = await SharedPreferences.getInstance();
      return p.getInt(_kPrefKey);
    } catch (_) {
      return null;
    }
  }

  Future<void> _writeLastMenuId(int id) async {
    try {
      final p = await SharedPreferences.getInstance();
      await p.setInt(_kPrefKey, id);
    } catch (_) {}
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
        emit(const MenuLoaded(menus: <Map<String, dynamic>>[], active: null));
        return;
      }

      // MG_608_V_mobile_bloc: выбираем последний сохранённый или first
      int pickId = list.first['id'] as int;
      final saved = await _readLastMenuId();
      if (saved != null && list.any((m) => m['id'] == saved)) {
        pickId = saved;
      }

      final detail = await apiClient.get('/menu/$pickId/');
      await _writeLastMenuId(pickId);
      premiumGate?.reportReadSuccess();
      emit(MenuLoaded(menus: list, active: _asMap(detail)));
    } catch (err) {
      emit(_toErrorState(err, isWrite: false));
    }
  }

  /// MG_608_V_mobile_bloc: загрузка деталей по выбранному id (из dropdown).
  Future<void> _onDetail(MenuDetailRequested e, Emitter<MenuState> emit) async {
    // Берём текущий список из state, если он есть; иначе перечитываем список.
    List<Map<String, dynamic>> menus = const [];
    final cur = state;
    if (cur is MenuLoaded) {
      menus = cur.menus;
    }
    if (menus.isEmpty) {
      try {
        final listResp = await apiClient.get('/menu/');
        menus = (listResp is Map ? (listResp['results'] as List? ?? []) : [])
            .whereType<Map>()
            .map((m) => Map<String, dynamic>.from(m))
            .toList();
      } catch (err) {
        emit(_toErrorState(err, isWrite: false));
        return;
      }
    }
    emit(const MenuLoading());
    try {
      final detail = await apiClient.get('/menu/${e.menuId}/');
      await _writeLastMenuId(e.menuId);
      emit(MenuLoaded(menus: menus, active: _asMap(detail)));
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
      body['with_soup'] = e.withSoup; // MG_610_V_mobile
      final r = await apiClient.post('/menu/generate/', data: body);
      final m = _asMap(r);
      final id = m['id'];
      if (id is int) {
        await _writeLastMenuId(id);
      }
      emit(MenuGenerated(m));
    } catch (err) {
      emit(_toErrorState(err, isWrite: true));
    }
  }
}
