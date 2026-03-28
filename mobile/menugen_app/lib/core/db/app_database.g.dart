// GENERATED CODE - DO NOT MODIFY BY HAND
part of 'app_database.dart';

// **************************************************************************
// DriftDatabaseGenerator
// **************************************************************************

class _$AppDatabase extends AppDatabase {
  _$AppDatabase([SqliteExecutor? e]) : super.connect(DatabaseConnection.delayed(Future.value(e)));
  // NOTE: actual generated code is produced by `build_runner`.
  // This stub satisfies the `part` directive so the app compiles.
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();

  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [];
}
