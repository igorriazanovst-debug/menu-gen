import 'package:drift/drift.dart';

class CachedRecipes extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get serverId => integer().unique()();
  TextColumn get title => text()();
  TextColumn get cookTime => text().nullable()();
  IntColumn get servings => integer().nullable()();
  TextColumn get ingredientsJson => text().withDefault(const Constant('[]'))();
  TextColumn get stepsJson => text().withDefault(const Constant('[]'))();
  TextColumn get nutritionJson => text().withDefault(const Constant('{}'))();
  TextColumn get categoriesJson => text().withDefault(const Constant('[]'))();
  TextColumn get imageUrl => text().nullable()();
  TextColumn get country => text().nullable()();
  BoolColumn get isCustom => boolean().withDefault(const Constant(false))();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();
}

class CachedMenus extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get serverId => integer().unique()();
  TextColumn get startDate => text()();
  TextColumn get endDate => text()();
  IntColumn get periodDays => integer()();
  TextColumn get status => text().withDefault(const Constant('active'))();
  DateTimeColumn get generatedAt => dateTime().withDefault(currentDateAndTime)();
}

class CachedMenuItems extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get serverId => integer().unique()();
  IntColumn get menuServerId => integer()();
  IntColumn get recipeServerId => integer()();
  TextColumn get mealType => text()();
  IntColumn get dayOffset => integer()();
  TextColumn get memberName => text().nullable()();
}

class CachedFridgeItems extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get serverId => integer().unique()();
  TextColumn get name => text()();
  RealColumn get quantity => real().nullable()();
  TextColumn get unit => text().nullable()();
  TextColumn get expiryDate => text().nullable()();
  BoolColumn get isDeleted => boolean().withDefault(const Constant(false))();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();
}

class CachedDiaryEntries extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get serverId => integer().nullable()();
  TextColumn get date => text()();
  TextColumn get mealType => text()();
  IntColumn get recipeServerId => integer().nullable()();
  TextColumn get customName => text().nullable()();
  TextColumn get nutritionJson => text().withDefault(const Constant('{}'))();
  RealColumn get quantity => real().withDefault(const Constant(1.0))();
  TextColumn get syncStatus => text().withDefault(const Constant('pending'))();
}

class SyncQueue extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get entityType => text()();
  TextColumn get entityId => text()();
  TextColumn get action => text()();
  TextColumn get payloadJson => text().withDefault(const Constant('{}'))();
  TextColumn get status => text().withDefault(const Constant('pending'))();
  IntColumn get retryCount => integer().withDefault(const Constant(0))();
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
}
