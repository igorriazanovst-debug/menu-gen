import 'dart:io';
import 'package:drift/drift.dart';
import 'package:drift_flutter/drift_flutter.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import 'tables.dart';

part 'app_database.g.dart';

@DriftDatabase(tables: [
  CachedRecipes,
  CachedMenus,
  CachedMenuItems,
  CachedFridgeItems,
  CachedDiaryEntries,
  SyncQueue,
])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  @override
  int get schemaVersion => 1;

  // ── Recipes ──────────────────────────────────────────────────────────────

  Future<List<CachedRecipe>> getAllRecipes() =>
      select(cachedRecipes).get();

  Future<List<CachedRecipe>> searchRecipes(String query) =>
      (select(cachedRecipes)..where((r) => r.title.contains(query))).get();

  Future<void> upsertRecipes(List<CachedRecipesCompanion> rows) =>
      batch((b) => b.insertAllOnConflictUpdate(cachedRecipes, rows));

  // ── Fridge ────────────────────────────────────────────────────────────────

  Future<List<CachedFridgeItem>> getFridgeItems() =>
      (select(cachedFridgeItems)..where((i) => i.isDeleted.equals(false))).get();

  Future<int> upsertFridgeItem(CachedFridgeItemsCompanion row) =>
      into(cachedFridgeItems).insertOnConflictUpdate(row);

  Future<void> softDeleteFridgeItem(int id) =>
      (update(cachedFridgeItems)..where((i) => i.serverId.equals(id)))
          .write(const CachedFridgeItemsCompanion(isDeleted: Value(true)));

  // ── Menu ──────────────────────────────────────────────────────────────────

  Future<List<CachedMenu>> getActiveMenus() =>
      (select(cachedMenus)..where((m) => m.status.equals('active'))).get();

  Future<void> upsertMenu(CachedMenusCompanion row) =>
      into(cachedMenus).insertOnConflictUpdate(row);

  Future<void> upsertMenuItems(List<CachedMenuItemsCompanion> rows) =>
      batch((b) => b.insertAllOnConflictUpdate(cachedMenuItems, rows));

  Future<List<CachedMenuItem>> getMenuItems(int menuServerId) =>
      (select(cachedMenuItems)..where((i) => i.menuServerId.equals(menuServerId))).get();

  // ── Diary ─────────────────────────────────────────────────────────────────

  Future<List<CachedDiaryEntry>> getDiaryByDate(String date) =>
      (select(cachedDiaryEntries)..where((e) => e.date.equals(date))).get();

  Future<int> insertDiaryEntry(CachedDiaryEntriesCompanion row) =>
      into(cachedDiaryEntries).insert(row);

  // ── Sync Queue ────────────────────────────────────────────────────────────

  Future<List<SyncQueueEntry>> getPendingSync() =>
      (select(syncQueue)..where((s) => s.status.equals('pending'))
        ..orderBy([(s) => OrderingTerm.asc(s.createdAt)])).get();

  Future<void> markSynced(int id) =>
      (update(syncQueue)..where((s) => s.id.equals(id)))
          .write(const SyncQueueCompanion(status: Value('synced')));
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dir = await getApplicationDocumentsDirectory();
    final file = File(p.join(dir.path, 'menugen.db'));
    return driftDatabase(path: file.path);
  });
}
