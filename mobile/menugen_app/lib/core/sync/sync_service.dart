import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../db/app_database.dart';
import 'dart:convert';
import 'package:flutter/foundation.dart';

/// SyncService реализует Offline-First синхронизацию:
///  - Push: берёт записи из SyncQueue (status='pending'), отправляет на сервер
///  - Pull: загружает актуальные данные с сервера и кэширует локально
///  - Конфликты: Last Write Wins (User vs User), приоритет Специалиста
class SyncService {
  final ApiClient apiClient;
  final AppDatabase db;

  StreamSubscription? _connectivitySub;
  bool _isSyncing = false;

  SyncService({required this.apiClient, required this.db});

  /// Запускает фоновую синхронизацию при восстановлении сети
  void start() {
    _connectivitySub = Connectivity().onConnectivityChanged.listen((results) {
      final isOnline = results.any((r) => r != ConnectivityResult.none);
      if (isOnline) _sync();
    });
  }

  void stop() => _connectivitySub?.cancel();

  // ── Public API ─────────────────────────────────────────────────────────────

  /// Полный цикл sync: сначала push, потом pull
  Future<void> syncAll() async {
    await _push();
    await _pull();
  }

  /// Добавляет изменение в очередь синхронизации
  Future<void> enqueue({
    required String entityType,
    required String entityId,
    required String action,
    required Map<String, dynamic> payload,
  }) async {
    await db.into(db.syncQueue).insert(SyncQueueCompanion.insert(
      entityType: entityType,
      entityId: entityId,
      action: action,
      payloadJson: jsonEncode(payload),
    ));
  }

  // ── Private ────────────────────────────────────────────────────────────────

  Future<void> _sync() async {
    if (_isSyncing) return;
    _isSyncing = true;
    try {
      await _push();
      await _pull();
    } finally {
      _isSyncing = false;
    }
  }

  /// Push: отправляет все pending-записи из SyncQueue на сервер
  Future<void> _push() async {
    final pending = await db.getPendingSync();
    for (final entry in pending) {
      try {
        final payload = jsonDecode(entry.payloadJson) as Map<String, dynamic>;
        await _dispatchToServer(
          entityType: entry.entityType,
          entityId: entry.entityId,
          action: entry.action,
          payload: payload,
        );
        await db.markSynced(entry.id);
        debugPrint('[Sync] Pushed ${entry.entityType}/${entry.entityId} (${entry.action})');
      } catch (e) {
        debugPrint('[Sync] Push failed for ${entry.entityType}/${entry.entityId}: $e');
        // Оставляем в pending, retry при следующем запуске
      }
    }
  }

  Future<void> _dispatchToServer({
    required String entityType,
    required String entityId,
    required String action,
    required Map<String, dynamic> payload,
  }) async {
    switch (entityType) {
      case 'fridge_item':
        if (action == 'create') {
          await apiClient.post('/fridge/', data: payload);
        } else if (action == 'update') {
          await apiClient.patch('/fridge/$entityId/', data: payload);
        } else if (action == 'delete') {
          await apiClient.delete('/fridge/$entityId/');
        }
      case 'diary_entry':
        if (action == 'create') {
          await apiClient.post('/diary/', data: payload);
        } else if (action == 'delete') {
          await apiClient.delete('/diary/$entityId/');
        }
      case 'menu_item_swap':
        final menuId = payload['menu_id'];
        final itemId = payload['item_id'];
        await apiClient.patch('/menu/$menuId/items/$itemId/', data: payload);
      default:
        debugPrint('[Sync] Unknown entityType: $entityType');
    }
  }

  /// Pull: загружает свежие данные с сервера и сохраняет в локальную БД
  Future<void> _pull() async {
    await Future.wait([
      _pullFridge(),
      _pullMenus(),
      _pullRecipes(),
    ]);
  }

  Future<void> _pullFridge() async {
    try {
      final resp = await apiClient.get('/fridge/');
      final items = resp.data['results'] as List? ?? [];
      await db.batch((batch) {
        batch.insertAllOnConflictUpdate(
          db.cachedFridgeItems,
          items.map((j) => CachedFridgeItemsCompanion.insert(
            serverId: Value((j['id'] as int)),
            name: j['name'] as String,
            quantity: Value((j['quantity'] as num?)?.toDouble()),
            unit: Value(j['unit'] as String?),
            expiryDate: Value(j['expiry_date'] as String?),
          )).toList(),
        );
      });
    } catch (e) {
      debugPrint('[Sync] pullFridge error: $e');
    }
  }

  Future<void> _pullMenus() async {
    try {
      final resp = await apiClient.get('/menu/');
      final menus = resp.data['results'] as List? ?? [];
      for (final m in menus) {
        await db.into(db.cachedMenus).insertOnConflictUpdate(
          CachedMenusCompanion.insert(
            serverId: Value(m['id'] as int),
            startDate: m['start_date'] as String,
            endDate: m['end_date'] as String,
            periodDays: m['period_days'] as int,
            status: Value(m['status'] as String? ?? 'active'),
          ),
        );
        // Pull menu items
        final detailResp = await apiClient.get('/menu/${m['id']}/');
        final items = detailResp.data['items'] as List? ?? [];
        await db.batch((batch) {
          batch.insertAllOnConflictUpdate(
            db.cachedMenuItems,
            items.map((i) => CachedMenuItemsCompanion.insert(
              serverId: Value(i['id'] as int),
              menuServerId: m['id'] as int,
              recipeServerId: (i['recipe'] as Map)['id'] as int,
              mealType: i['meal_type'] as String,
              dayOffset: i['day_offset'] as int,
              memberName: Value(i['member_name'] as String?),
            )).toList(),
          );
        });
      }
    } catch (e) {
      debugPrint('[Sync] pullMenus error: $e');
    }
  }

  Future<void> _pullRecipes() async {
    try {
      final resp = await apiClient.get('/recipes/', params: {'page_size': '50'});
      final recipes = resp.data['results'] as List? ?? [];
      await db.batch((batch) {
        batch.insertAllOnConflictUpdate(
          db.cachedRecipes,
          recipes.map((r) => CachedRecipesCompanion.insert(
            serverId: Value(r['id'] as int),
            title: r['title'] as String,
            cookTime: Value(r['cook_time'] as String?),
            servings: Value(r['servings'] as int?),
            ingredientsJson: Value(jsonEncode(r['ingredients'] ?? [])),
            stepsJson: Value(jsonEncode(r['steps'] ?? [])),
            nutritionJson: Value(jsonEncode(r['nutrition'] ?? {})),
            categoriesJson: Value(jsonEncode(r['categories'] ?? [])),
            imageUrl: Value(r['image_url'] as String?),
            country: Value(r['country'] as String?),
            isCustom: Value(r['is_custom'] as bool? ?? false),
          )).toList(),
        );
      });
    } catch (e) {
      debugPrint('[Sync] pullRecipes error: $e');
    }
  }
}
