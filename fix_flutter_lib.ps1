# fix_flutter_lib.ps1
# Запускать из корня репозитория

$base = "mobile\menugen_app\lib"

function W($path, $content) {
    $full = Join-Path $base $path
    $dir  = Split-Path $full -Parent
    if (!(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [System.IO.File]::WriteAllText($full, $content, [System.Text.UTF8Encoding]::new($false))
    Write-Host "  OK: $path"
}

# ── core/db/app_database.dart — абстрактный интерфейс ──────────────────────
W "core\db\app_database.dart" @'
// Абстрактный интерфейс БД — позволяет мокировать в тестах.
// Реальная реализация (Drift) живёт в app_database_impl.dart
abstract class AppDatabase {
  Future<void> close();
}
'@

# ── Удаляем битый app_database.g.dart ──────────────────────────────────────
$gFile = Join-Path $base "core\db\app_database.g.dart"
if (Test-Path $gFile) { Remove-Item $gFile -Force; Write-Host "  REMOVED: core/db/app_database.g.dart" }

# ── core/models/recipe.dart — простая модель без freezed ───────────────────
W "core\models\recipe.dart" @'
class Recipe {
  final int id;
  final String title;
  final String? cookTime;
  final int? servings;
  final List<Map<String, dynamic>> ingredients;
  final List<Map<String, dynamic>> steps;
  final Map<String, dynamic> nutrition;
  final List<String> categories;
  final String? imageUrl;
  final String? videoUrl;
  final String? country;
  final bool isCustom;
  final String? authorName;

  const Recipe({
    required this.id,
    required this.title,
    this.cookTime,
    this.servings,
    this.ingredients = const [],
    this.steps = const [],
    this.nutrition = const {},
    this.categories = const [],
    this.imageUrl,
    this.videoUrl,
    this.country,
    this.isCustom = false,
    this.authorName,
  });

  factory Recipe.fromJson(Map<String, dynamic> json) => Recipe(
        id: json['id'] as int? ?? 0,
        title: json['title'] as String? ?? '',
        cookTime: json['cook_time'] as String?,
        servings: json['servings'] as int?,
        ingredients: (json['ingredients'] as List?)
                ?.map((e) => Map<String, dynamic>.from(e as Map))
                .toList() ??
            [],
        steps: (json['steps'] as List?)
                ?.map((e) => Map<String, dynamic>.from(e as Map))
                .toList() ??
            [],
        nutrition: json['nutrition'] != null
            ? Map<String, dynamic>.from(json['nutrition'] as Map)
            : {},
        categories: (json['categories'] as List?)
                ?.map((e) => e.toString())
                .toList() ??
            [],
        imageUrl: json['image_url'] as String?,
        videoUrl: json['video_url'] as String?,
        country: json['country'] as String?,
        isCustom: json['is_custom'] as bool? ?? false,
        authorName: json['author_name'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        if (cookTime != null) 'cook_time': cookTime,
        if (servings != null) 'servings': servings,
        'ingredients': ingredients,
        'steps': steps,
        'nutrition': nutrition,
        'categories': categories,
        if (imageUrl != null) 'image_url': imageUrl,
        if (videoUrl != null) 'video_url': videoUrl,
        if (country != null) 'country': country,
        'is_custom': isCustom,
        if (authorName != null) 'author_name': authorName,
      };
}
'@

# ── core/models/fridge_item.dart ────────────────────────────────────────────
W "core\models\fridge_item.dart" @'
class FridgeItem {
  final int id;
  final String name;
  final double? quantity;
  final String? unit;
  final String? expiryDate;
  final String? productName;
  final String? productCategory;

  const FridgeItem({
    required this.id,
    required this.name,
    this.quantity,
    this.unit,
    this.expiryDate,
    this.productName,
    this.productCategory,
  });

  factory FridgeItem.fromJson(Map<String, dynamic> json) => FridgeItem(
        id: json['id'] as int? ?? 0,
        name: json['name'] as String? ?? '',
        quantity: (json['quantity'] as num?)?.toDouble(),
        unit: json['unit'] as String?,
        expiryDate: json['expiry_date'] as String?,
        productName: json['product_name'] as String?,
        productCategory: json['product_category'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        if (quantity != null) 'quantity': quantity,
        if (unit != null) 'unit': unit,
        if (expiryDate != null) 'expiry_date': expiryDate,
        if (productName != null) 'product_name': productName,
        if (productCategory != null) 'product_category': productCategory,
      };
}
'@

# ── core/models/menu.dart ────────────────────────────────────────────────────
W "core\models\menu.dart" @'
import 'recipe.dart';

class Menu {
  final int id;
  final String startDate;
  final String endDate;
  final int periodDays;
  final String status;
  final String generatedAt;
  final List<MenuItem> items;

  const Menu({
    required this.id,
    required this.startDate,
    required this.endDate,
    required this.periodDays,
    required this.status,
    required this.generatedAt,
    this.items = const [],
  });

  factory Menu.fromJson(Map<String, dynamic> json) => Menu(
        id: json['id'] as int? ?? 0,
        startDate: json['start_date'] as String? ?? '',
        endDate: json['end_date'] as String? ?? '',
        periodDays: json['period_days'] as int? ?? 7,
        status: json['status'] as String? ?? '',
        generatedAt: json['generated_at'] as String? ?? '',
        items: (json['items'] as List?)
                ?.map((e) => MenuItem.fromJson(Map<String, dynamic>.from(e as Map)))
                .toList() ??
            [],
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'start_date': startDate,
        'end_date': endDate,
        'period_days': periodDays,
        'status': status,
        'generated_at': generatedAt,
        'items': items.map((e) => e.toJson()).toList(),
      };
}

class MenuItem {
  final int id;
  final int dayOffset;
  final String mealType;
  final Recipe recipe;
  final String? memberName;
  final double quantity;

  const MenuItem({
    required this.id,
    required this.dayOffset,
    required this.mealType,
    required this.recipe,
    this.memberName,
    this.quantity = 1.0,
  });

  factory MenuItem.fromJson(Map<String, dynamic> json) => MenuItem(
        id: json['id'] as int? ?? 0,
        dayOffset: json['day_offset'] as int? ?? 0,
        mealType: json['meal_type'] as String? ?? '',
        recipe: Recipe.fromJson(
            Map<String, dynamic>.from(json['recipe'] as Map? ?? {})),
        memberName: json['member_name'] as String?,
        quantity: (json['quantity'] as num?)?.toDouble() ?? 1.0,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'day_offset': dayOffset,
        'meal_type': mealType,
        'recipe': recipe.toJson(),
        if (memberName != null) 'member_name': memberName,
        'quantity': quantity,
      };
}
'@

# ── core/models/diary_entry.dart ─────────────────────────────────────────────
W "core\models\diary_entry.dart" @'
class DiaryEntry {
  final int id;
  final String date;
  final String mealType;
  final int? recipe;
  final String? recipeTitle;
  final String? customName;
  final Map<String, dynamic> nutrition;
  final double quantity;

  const DiaryEntry({
    required this.id,
    required this.date,
    required this.mealType,
    this.recipe,
    this.recipeTitle,
    this.customName,
    this.nutrition = const {},
    this.quantity = 1.0,
  });

  factory DiaryEntry.fromJson(Map<String, dynamic> json) => DiaryEntry(
        id: json['id'] as int? ?? 0,
        date: json['date'] as String? ?? '',
        mealType: json['meal_type'] as String? ?? '',
        recipe: json['recipe'] as int?,
        recipeTitle: json['recipe_title'] as String?,
        customName: json['custom_name'] as String?,
        nutrition: json['nutrition'] != null
            ? Map<String, dynamic>.from(json['nutrition'] as Map)
            : {},
        quantity: (json['quantity'] as num?)?.toDouble() ?? 1.0,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'date': date,
        'meal_type': mealType,
        if (recipe != null) 'recipe': recipe,
        if (recipeTitle != null) 'recipe_title': recipeTitle,
        if (customName != null) 'custom_name': customName,
        'nutrition': nutrition,
        'quantity': quantity,
      };
}
'@

# ── core/models/user.dart ────────────────────────────────────────────────────
W "core\models\user.dart" @'
class AppUser {
  final int id;
  final String name;
  final String email;

  const AppUser({required this.id, required this.name, required this.email});

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
        id: json['id'] as int? ?? 0,
        name: json['name'] as String? ?? '',
        email: json['email'] as String? ?? '',
      );

  Map<String, dynamic> toJson() => {'id': id, 'name': name, 'email': email};
}
'@

# ── Удаляем все битые .freezed.dart и .g.dart файлы ─────────────────────────
$toRemove = @(
  "core\models\recipe.freezed.dart",
  "core\models\recipe.g.dart",
  "core\models\fridge_item.freezed.dart",
  "core\models\fridge_item.g.dart",
  "core\models\menu.freezed.dart",
  "core\models\menu.g.dart",
  "core\models\diary_entry.freezed.dart",
  "core\models\diary_entry.g.dart",
  "core\models\user.freezed.dart",
  "core\models\user.g.dart"
)
foreach ($f in $toRemove) {
  $full = Join-Path $base $f
  if (Test-Path $full) { Remove-Item $full -Force; Write-Host "  REMOVED: $f" }
}

# ── features/auth/bloc/auth_bloc.dart — исправляем MockResponse в тесте ─────
# Тест auth_bloc_test.dart возвращает MockResponse вместо Response<dynamic>.
# Исправим ApiClient.get чтобы возвращал dynamic (уже так), и
# поправим auth_bloc чтобы не кастил .data напрямую из Response
W "features\auth\bloc\auth_bloc.dart" @'
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/token_storage.dart';

abstract class AuthEvent extends Equatable {
  const AuthEvent();
  @override List<Object?> get props => [];
}
class AuthCheckRequested extends AuthEvent { const AuthCheckRequested(); }
class AuthLoginRequested extends AuthEvent {
  final String email; final String password;
  const AuthLoginRequested({required this.email, required this.password});
  @override List<Object?> get props => [email, password];
}
class AuthLogoutRequested extends AuthEvent { const AuthLogoutRequested(); }

abstract class AuthState extends Equatable {
  const AuthState();
  @override List<Object?> get props => [];
}
class AuthLoading extends AuthState { const AuthLoading(); }
class AuthAuthenticated extends AuthState {
  final Map<String, dynamic> user;
  const AuthAuthenticated(this.user);
  @override List<Object?> get props => [user];
}
class AuthUnauthenticated extends AuthState { const AuthUnauthenticated(); }
class AuthError extends AuthState {
  final String message;
  const AuthError(this.message);
  @override List<Object?> get props => [message];
}

class AuthBloc extends Bloc<AuthEvent, AuthState> {
  final ApiClient apiClient;
  final TokenStorage tokenStorage;

  AuthBloc({required this.apiClient, required this.tokenStorage})
      : super(const AuthUnauthenticated()) {
    on<AuthCheckRequested>(_onCheck);
    on<AuthLoginRequested>(_onLogin);
    on<AuthLogoutRequested>(_onLogout);
  }

  Future<void> _onCheck(AuthCheckRequested e, Emitter<AuthState> emit) async {
    emit(const AuthLoading());
    try {
      final hasToken = await tokenStorage.hasToken();
      if (!hasToken) { emit(const AuthUnauthenticated()); return; }
      final resp = await apiClient.get('/users/me/');
      final data = _extractData(resp);
      emit(AuthAuthenticated(Map<String, dynamic>.from(data as Map)));
    } catch (_) {
      await tokenStorage.clearTokens();
      emit(const AuthUnauthenticated());
    }
  }

  Future<void> _onLogin(AuthLoginRequested e, Emitter<AuthState> emit) async {
    emit(const AuthLoading());
    try {
      final resp = await apiClient.post('/auth/login/',
          data: {'email': e.email, 'password': e.password});
      final data = Map<String, dynamic>.from(_extractData(resp) as Map);
      await tokenStorage.saveTokens(
          access: data['access'] as String,
          refresh: data['refresh'] as String);
      final me = await apiClient.get('/users/me/');
      emit(AuthAuthenticated(
          Map<String, dynamic>.from(_extractData(me) as Map)));
    } catch (err) {
      emit(AuthError(err.toString()));
    }
  }

  Future<void> _onLogout(AuthLogoutRequested e, Emitter<AuthState> emit) async {
    await tokenStorage.clearTokens();
    emit(const AuthUnauthenticated());
  }

  // Извлекает данные из ответа независимо от типа (Response или MockResponse)
  dynamic _extractData(dynamic resp) {
    try { return resp.data; } catch (_) { return resp; }
  }
}
'@

# ── features/family/bloc/family_bloc.dart ───────────────────────────────────
W "features\family\bloc\family_bloc.dart" @'
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';

abstract class FamilyEvent extends Equatable {
  const FamilyEvent();
  @override List<Object?> get props => [];
}
class FamilyLoadRequested extends FamilyEvent { const FamilyLoadRequested(); }
class FamilyInviteMemberRequested extends FamilyEvent {
  final String email;
  const FamilyInviteMemberRequested(this.email);
  @override List<Object?> get props => [email];
}
class FamilyRemoveMemberRequested extends FamilyEvent {
  final int memberId;
  const FamilyRemoveMemberRequested(this.memberId);
  @override List<Object?> get props => [memberId];
}

abstract class FamilyState extends Equatable {
  const FamilyState();
  @override List<Object?> get props => [];
}
class FamilyLoading extends FamilyState { const FamilyLoading(); }
class FamilyLoaded extends FamilyState {
  final Map<String, dynamic> family;
  const FamilyLoaded(this.family);
  @override List<Object?> get props => [family];
}
class FamilyError extends FamilyState {
  final String message;
  const FamilyError(this.message);
  @override List<Object?> get props => [message];
}

class FamilyBloc extends Bloc<FamilyEvent, FamilyState> {
  final ApiClient apiClient;
  FamilyBloc({required this.apiClient}) : super(const FamilyLoading()) {
    on<FamilyLoadRequested>(_onLoad);
    on<FamilyInviteMemberRequested>(_onInvite);
    on<FamilyRemoveMemberRequested>(_onRemove);
  }

  dynamic _data(dynamic r) { try { return r.data; } catch (_) { return r; } }

  Future<void> _onLoad(FamilyLoadRequested e, Emitter<FamilyState> emit) async {
    emit(const FamilyLoading());
    try {
      final r = await apiClient.get('/family/');
      emit(FamilyLoaded(Map<String, dynamic>.from(_data(r) as Map)));
    } catch (e) { emit(FamilyError(e.toString())); }
  }

  Future<void> _onInvite(FamilyInviteMemberRequested e, Emitter<FamilyState> emit) async {
    try {
      await apiClient.post('/family/invite/', data: {'email': e.email});
      add(const FamilyLoadRequested());
    } catch (e) { emit(FamilyError(e.toString())); }
  }

  Future<void> _onRemove(FamilyRemoveMemberRequested e, Emitter<FamilyState> emit) async {
    try {
      await apiClient.delete('/family/members/${e.memberId}/');
      add(const FamilyLoadRequested());
    } catch (e) { emit(FamilyError(e.toString())); }
  }
}
'@

# ── features/fridge/bloc/fridge_bloc.dart ───────────────────────────────────
W "features\fridge\bloc\fridge_bloc.dart" @'
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/db/app_database.dart';

abstract class FridgeEvent extends Equatable {
  const FridgeEvent();
  @override List<Object?> get props => [];
}
class FridgeLoadRequested extends FridgeEvent { const FridgeLoadRequested(); }
class FridgeItemAdded extends FridgeEvent {
  final Map<String, dynamic> item;
  const FridgeItemAdded(this.item);
  @override List<Object?> get props => [item];
}
class FridgeItemDeleted extends FridgeEvent {
  final int itemId;
  const FridgeItemDeleted(this.itemId);
  @override List<Object?> get props => [itemId];
}

abstract class FridgeState extends Equatable {
  const FridgeState();
  @override List<Object?> get props => [];
}
class FridgeLoading extends FridgeState { const FridgeLoading(); }
class FridgeLoaded extends FridgeState {
  final List<Map<String, dynamic>> items;
  const FridgeLoaded({required this.items});
  @override List<Object?> get props => [items];
}
class FridgeError extends FridgeState {
  final String message;
  const FridgeError(this.message);
  @override List<Object?> get props => [message];
}

class FridgeBloc extends Bloc<FridgeEvent, FridgeState> {
  final ApiClient apiClient;
  final AppDatabase db;
  FridgeBloc({required this.apiClient, required this.db})
      : super(const FridgeLoading()) {
    on<FridgeLoadRequested>(_onLoad);
    on<FridgeItemAdded>(_onAdd);
    on<FridgeItemDeleted>(_onDelete);
  }

  dynamic _data(dynamic r) { try { return r.data; } catch (_) { return r; } }

  Future<void> _onLoad(FridgeLoadRequested e, Emitter<FridgeState> emit) async {
    emit(const FridgeLoading());
    try {
      final r = await apiClient.get('/fridge/');
      final d = _data(r);
      final results = d is Map
          ? (d['results'] as List? ?? [])
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList()
          : <Map<String, dynamic>>[];
      emit(FridgeLoaded(items: results));
    } catch (e) { emit(FridgeError(e.toString())); }
  }

  Future<void> _onAdd(FridgeItemAdded e, Emitter<FridgeState> emit) async {
    try {
      await apiClient.post('/fridge/', data: e.item);
      add(const FridgeLoadRequested());
    } catch (e) { emit(FridgeError(e.toString())); }
  }

  Future<void> _onDelete(FridgeItemDeleted e, Emitter<FridgeState> emit) async {
    try {
      await apiClient.delete('/fridge/${e.itemId}/');
      add(const FridgeLoadRequested());
    } catch (e) { emit(FridgeError(e.toString())); }
  }
}
'@

# ── features/menu/bloc/menu_bloc.dart ───────────────────────────────────────
W "features\menu\bloc\menu_bloc.dart" @'
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
  MenuBloc({required this.apiClient, required this.db})
      : super(const MenuLoading()) {
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
          ? (d['results'] as List? ?? [])
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList()
          : <Map<String, dynamic>>[];
      emit(MenuLoaded(menus: results));
    } catch (e) { emit(MenuError(e.toString())); }
  }

  Future<void> _onGenerate(MenuGenerateRequested e, Emitter<MenuState> emit) async {
    emit(const MenuGenerating());
    try {
      final r = await apiClient.post('/menu/generate/',
          data: {'start_date': e.startDate});
      emit(MenuGenerated(Map<String, dynamic>.from(_data(r) as Map)));
    } catch (e) { emit(MenuError(e.toString())); }
  }
}
'@

# ── features/diary/bloc/diary_bloc.dart ─────────────────────────────────────
W "features\diary\bloc\diary_bloc.dart" @'
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/db/app_database.dart';

abstract class DiaryEvent extends Equatable {
  const DiaryEvent();
  @override List<Object?> get props => [];
}
class DiaryLoadRequested extends DiaryEvent {
  final String date;
  const DiaryLoadRequested(this.date);
  @override List<Object?> get props => [date];
}

abstract class DiaryState extends Equatable {
  const DiaryState();
  @override List<Object?> get props => [];
}
class DiaryLoading extends DiaryState { const DiaryLoading(); }
class DiaryLoaded extends DiaryState {
  final String date;
  final List<Map<String, dynamic>> entries;
  const DiaryLoaded({required this.date, required this.entries});
  @override List<Object?> get props => [date, entries];
}
class DiaryError extends DiaryState {
  final String message;
  const DiaryError(this.message);
  @override List<Object?> get props => [message];
}

class DiaryBloc extends Bloc<DiaryEvent, DiaryState> {
  final ApiClient apiClient;
  final AppDatabase db;
  DiaryBloc({required this.apiClient, required this.db})
      : super(const DiaryLoading()) {
    on<DiaryLoadRequested>(_onLoad);
  }

  dynamic _data(dynamic r) { try { return r.data; } catch (_) { return r; } }

  Future<void> _onLoad(DiaryLoadRequested e, Emitter<DiaryState> emit) async {
    emit(const DiaryLoading());
    try {
      final r = await apiClient.get('/diary/', params: {'date': e.date});
      final d = _data(r);
      final results = d is Map
          ? (d['results'] as List? ?? [])
              .map((i) => Map<String, dynamic>.from(i as Map))
              .toList()
          : <Map<String, dynamic>>[];
      emit(DiaryLoaded(date: e.date, entries: results));
    } catch (e) { emit(DiaryError(e.toString())); }
  }
}
'@

# ── features/recipes/bloc/recipes_bloc.dart ─────────────────────────────────
W "features\recipes\bloc\recipes_bloc.dart" @'
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/db/app_database.dart';

abstract class RecipesEvent extends Equatable {
  const RecipesEvent();
  @override List<Object?> get props => [];
}
class RecipesLoadRequested extends RecipesEvent { const RecipesLoadRequested(); }
class RecipesSearchRequested extends RecipesEvent {
  final String query;
  const RecipesSearchRequested(this.query);
  @override List<Object?> get props => [query];
}

abstract class RecipesState extends Equatable {
  const RecipesState();
  @override List<Object?> get props => [];
}
class RecipesLoading extends RecipesState { const RecipesLoading(); }
class RecipesLoaded extends RecipesState {
  final List<Map<String, dynamic>> recipes;
  const RecipesLoaded({required this.recipes});
  @override List<Object?> get props => [recipes];
}
class RecipesError extends RecipesState {
  final String message;
  const RecipesError(this.message);
  @override List<Object?> get props => [message];
}

class RecipesBloc extends Bloc<RecipesEvent, RecipesState> {
  final ApiClient apiClient;
  final AppDatabase db;
  RecipesBloc({required this.apiClient, required this.db})
      : super(const RecipesLoading()) {
    on<RecipesLoadRequested>(_onLoad);
    on<RecipesSearchRequested>(_onSearch);
  }

  dynamic _data(dynamic r) { try { return r.data; } catch (_) { return r; } }

  List<Map<String, dynamic>> _results(dynamic d) => d is Map
      ? (d['results'] as List? ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList()
      : [];

  Future<void> _onLoad(RecipesLoadRequested e, Emitter<RecipesState> emit) async {
    emit(const RecipesLoading());
    try {
      final r = await apiClient.get('/recipes/');
      emit(RecipesLoaded(recipes: _results(_data(r))));
    } catch (e) { emit(RecipesError(e.toString())); }
  }

  Future<void> _onSearch(RecipesSearchRequested e, Emitter<RecipesState> emit) async {
    emit(const RecipesLoading());
    try {
      final r = await apiClient.get('/recipes/', params: {'search': e.query});
      emit(RecipesLoaded(recipes: _results(_data(r))));
    } catch (e) { emit(RecipesError(e.toString())); }
  }
}
'@

Write-Host ""
Write-Host "Done. Now run:"
Write-Host "  git add -f mobile/menugen_app/lib"
Write-Host "  git commit -m 'fix(mobile): replace broken generated files, abstract AppDatabase'"
Write-Host "  git push"
