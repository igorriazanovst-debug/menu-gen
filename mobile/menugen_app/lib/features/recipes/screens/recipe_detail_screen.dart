import 'dart:convert';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/cache/recipe_image_cache.dart';
import '../../../core/constants/allergens.dart';
import '../../../core/theme/app_theme.dart';
import '../../fridge/screens/recognize_photo_flow.dart' show pickPhoto; // MG_MADEPHOTO

String _mimeFromName(String name) {
  final n = name.toLowerCase();
  if (n.endsWith('.png')) return 'image/png';
  if (n.endsWith('.webp')) return 'image/webp';
  if (n.endsWith('.gif')) return 'image/gif';
  return 'image/jpeg';
}

/// Полноэкранный экран рецепта. Грузит /recipes/:id/ напрямую через ApiClient.
class RecipeDetailScreen extends StatefulWidget {
  final ApiClient apiClient;
  final int recipeId;

  const RecipeDetailScreen({
    super.key,
    required this.apiClient,
    required this.recipeId,
  });

  @override
  State<RecipeDetailScreen> createState() => _RecipeDetailScreenState();
}

class _RecipeDetailScreenState extends State<RecipeDetailScreen> {
  Map<String, dynamic>? _recipe;
  String? _error;
  bool _loading = true;
  bool _favBusy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await widget.apiClient.get('/recipes/${widget.recipeId}/');
      if (!mounted) return;
      setState(() {
        _recipe = r is Map ? Map<String, dynamic>.from(r) : <String, dynamic>{};
        _loading = false;
      });
    } catch (err) {
      if (!mounted) return;
      setState(() {
        _error = err is ApiException ? err.message : err.toString();
        _loading = false;
      });
    }
  }

  Future<void> _toggleFavorite() async {
    final r = _recipe;
    if (r == null || _favBusy) return;
    final isFav = (r['is_favorite'] as bool?) ?? false;
    final isDis = (r['is_disliked'] as bool?) ?? false;

    bool? next;
    bool newFav, newDis;
    if (!isFav && !isDis) {
      next = true; newFav = true; newDis = false;
    } else if (isFav) {
      next = false; newFav = false; newDis = true;
    } else {
      next = null; newFav = false; newDis = false;
    }

    setState(() {
      _favBusy = true;
      r['is_favorite'] = newFav;
      r['is_disliked'] = newDis;
    });

    try {
      if (next == null) {
        await widget.apiClient.delete('/recipes/${widget.recipeId}/favorite/');
      } else {
        await widget.apiClient.post(
          '/recipes/${widget.recipeId}/favorite/',
          data: {'is_favorite': next},
        );
      }
    } catch (err) {
      // revert
      setState(() {
        r['is_favorite'] = isFav;
        r['is_disliked'] = isDis;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(err is ApiException ? err.message : err.toString())),
        );
      }
    } finally {
      if (mounted) setState(() => _favBusy = false);
    }
  }

  Widget _favIcon() {
    final r = _recipe;
    if (r == null) return const SizedBox.shrink();
    final isFav = (r['is_favorite'] as bool?) ?? false;
    final isDis = (r['is_disliked'] as bool?) ?? false;
    return IconButton(
      onPressed: _favBusy ? null : _toggleFavorite,
      icon: Icon(
        isFav
            ? Icons.favorite
            : (isDis ? Icons.heart_broken : Icons.favorite_border),
        color: isFav
            ? context.cs.primary
            : (isDis ? context.tokens.textSecondary : null),
      ),
      tooltip: isFav
          ? 'Любимое'
          : (isDis ? 'Нелюбимое' : 'Добавить в любимые'),
    );
  }

  // ── MG_MADEPHOTO: «я приготовил — вот фото» ────────────────────────────────
  List<Map<String, dynamic>> get _madePhotos {
    final v = _recipe?['made_photos'];
    if (v is List) {
      return v.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
    }
    return const [];
  }

  Widget _madeBtn() {
    if (_recipe == null) return const SizedBox.shrink();
    final n = _madePhotos.length;
    return IconButton(
      tooltip: 'Я приготовил — прикрепить фото',
      onPressed: _openMadeSheet,
      icon: Badge(
        isLabelVisible: n > 0,
        label: Text('$n'),
        child: const Icon(Icons.add_a_photo_outlined),
      ),
    );
  }

  void _openMadeSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _MadePhotosSheet(
        apiClient: widget.apiClient,
        recipeId: widget.recipeId,
        initial: _madePhotos,
        onChanged: (list) {
          if (mounted) setState(() => _recipe?['made_photos'] = list);
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_recipe?['title'] as String? ?? 'Рецепт'),
        actions: [_madeBtn(), _favIcon()],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _ErrorView(message: _error!, onRetry: _load)
              : _DetailBody(recipe: _recipe!),
    );
  }
}

class _DetailBody extends StatelessWidget {
  final Map<String, dynamic> recipe;
  const _DetailBody({required this.recipe});

  String get _title => (recipe['title'] as String?) ?? '';
  String? get _imageUrl => recipe['image_url'] as String?;
  String? get _videoUrl => recipe['video_url'] as String?;
  String? get _cookTime => recipe['cook_time'] as String?;
  int? get _servings => recipe['servings'] as int?;
  String? get _country => recipe['country'] as String?;

  List<Map<String, dynamic>> get _ingredients =>
      (recipe['ingredients'] as List?)
              ?.whereType<Map>()
              .map((m) => Map<String, dynamic>.from(m))
              .toList() ??
          const [];

  List<Map<String, dynamic>> get _steps =>
      (recipe['steps'] as List?)
              ?.whereType<Map>()
              .map((m) => Map<String, dynamic>.from(m))
              .toList() ??
          const [];

  Map<String, dynamic> get _nutrition =>
      recipe['nutrition'] is Map
          ? Map<String, dynamic>.from(recipe['nutrition'] as Map)
          : <String, dynamic>{};

  List<String> get _categories =>
      (recipe['categories'] as List?)?.whereType<String>().toList() ?? const [];

  // MG_ALLERGEN14: ключи аллергенов рецепта.
  List<String> get _allergens =>
      (recipe['allergens'] as List?)?.map((e) => e.toString()).toList() ?? const [];

  @override
  Widget build(BuildContext context) {
    final cs = context.cs;
    final tokens = context.tokens;
    return ListView(
      padding: EdgeInsets.zero,
      children: [
        // MG_SKIN: hero-изображение на тёплой подложке из темы (замена тёмного
        // верха референса recipe_page), со скруглением снизу.
        Container(
          color: tokens.surfaceAlt,
          child: ClipRRect(
            borderRadius: const BorderRadius.vertical(bottom: Radius.circular(28)),
            child: AspectRatio(
              aspectRatio: 16 / 10,
              child: (_imageUrl != null && _imageUrl!.isNotEmpty)
                  ? CachedNetworkImage(
                      imageUrl: _imageUrl!,
                      cacheManager: RecipeImageCache.instance,
                      fit: BoxFit.cover,
                      placeholder: (_, __) => Container(color: tokens.surfaceAlt),
                      errorWidget: (_, __, ___) => Container(
                        color: tokens.surfaceAlt,
                        child: Icon(Icons.restaurant,
                            size: 64, color: tokens.textSecondary),
                      ),
                    )
                  : Container(
                      color: tokens.surfaceAlt,
                      child: Icon(Icons.restaurant,
                          size: 64, color: tokens.textSecondary),
                    ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _title,
                style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    color: cs.onSurface),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 16,
                runSpacing: 8,
                children: [
                  if (_cookTime != null && _cookTime!.isNotEmpty)
                    _MetaItem(icon: Icons.access_time, text: _cookTime!),
                  if (_servings != null)
                    _MetaItem(
                        icon: Icons.people_outline,
                        text: '$_servings порц.'),
                  if (_country != null && _country!.isNotEmpty)
                    _MetaItem(icon: Icons.public, text: _country!),
                ],
              ),
              if (_categories.isNotEmpty) ...[
                const SizedBox(height: 12),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: _categories
                      .map((c) => Chip(
                            label: Text(c, style: const TextStyle(fontSize: 12)),
                            visualDensity: VisualDensity.compact,
                          ))
                      .toList(),
                ),
              ],
              if (_videoUrl != null && _videoUrl!.isNotEmpty) ...[
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Видео: $_videoUrl')),
                    );
                  },
                  icon: const Icon(Icons.play_circle_outline),
                  label: const Text('Смотреть видео'),
                ),
              ],
              if (_allergens.isNotEmpty) ...[
                const SizedBox(height: 16),
                _AllergenBadges(keys: _allergens),
              ],
              if (_nutrition.isNotEmpty) ...[
                const SizedBox(height: 20),
                _NutritionGrid(nutrition: _nutrition),
              ],
              const SizedBox(height: 20),
              if (_ingredients.isNotEmpty) ...[
                const _SectionTitle('Ингредиенты'),
                const SizedBox(height: 8),
                ..._ingredients.map((i) => _buildIngredientRow(context, i)),
                const SizedBox(height: 20),
              ],
              if (_steps.isNotEmpty) ...[
                const _SectionTitle('Приготовление'),
                const SizedBox(height: 8),
                ...List.generate(_steps.length, (i) {
                  final s = _steps[i];
                  return _StepRow(index: i + 1, text: (s['text'] as String?) ?? '');
                }),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildIngredientRow(BuildContext context, Map<String, dynamic> ing) {
    final cs = context.cs;
    final tokens = context.tokens;
    final name = (ing['name'] as String?) ?? '';
    final qty = ing['quantity']?.toString() ?? '';
    final unit = (ing['unit'] as String?) ?? '';
    final amount = [qty, unit].where((s) => s.isNotEmpty).join(' ');
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      decoration: BoxDecoration(
        color: tokens.surfaceAlt,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: cs.secondary, shape: BoxShape.circle),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(name,
                style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                    color: cs.onSurface)),
          ),
          if (amount.isNotEmpty)
            Text(amount,
                style: TextStyle(fontSize: 14, color: tokens.textSecondary)),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String text;
  const _SectionTitle(this.text);
  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: TextStyle(
          fontSize: 17, fontWeight: FontWeight.w700, color: context.cs.onSurface),
    );
  }
}

// MG_ALLERGEN14: бейджи аллергенов рецепта (ключи → метки ТР ТС 022).
class _AllergenBadges extends StatelessWidget {
  final List<String> keys;
  const _AllergenBadges({required this.keys});
  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        const Text('⚠️ Аллергены:',
            style: TextStyle(fontSize: 12, color: Colors.grey)),
        ...keys.map((k) => Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: const Color(0xFFFFF3E0),
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: const Color(0xFFF0C888)),
              ),
              child: Text(allergenLabel(k),
                  style: const TextStyle(fontSize: 12, color: Color(0xFF8A5A00))),
            )),
      ],
    );
  }
}

class _MetaItem extends StatelessWidget {
  final IconData icon;
  final String text;
  const _MetaItem({required this.icon, required this.text});
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18, color: context.cs.secondary),
        const SizedBox(width: 6),
        Text(text, style: const TextStyle(fontSize: 14)),
      ],
    );
  }
}

class _NutritionGrid extends StatelessWidget {
  final Map<String, dynamic> nutrition;
  const _NutritionGrid({required this.nutrition});

  String? _val(String key) {
    final v = nutrition[key];
    if (v is Map) {
      final value = v['value'];
      final unit = v['unit'];
      if (value == null) return null;
      return unit == null ? '$value' : '$value $unit';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final cs = context.cs;
    final tokens = context.tokens;
    // Цвета-акценты статов (в стиле recipe_page): калории/белки/жиры/углеводы.
    const proColor = Color(0xFF5B9BD5);
    final entries = <(String, String?, Color)>[
      ('Калории', _val('calories'), cs.primary),
      ('Белки', _val('proteins'), proColor),
      ('Жиры', _val('fats'), tokens.accent),
      ('Углеводы', _val('carbs'), cs.secondary),
    ].where((e) => e.$2 != null).toList();
    if (entries.isEmpty) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      decoration: BoxDecoration(
        color: tokens.surfaceAlt,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: entries.map((e) {
          return Expanded(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Container(
                  width: 4,
                  height: 32,
                  decoration: BoxDecoration(
                    color: e.$3,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(width: 8),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(e.$2!,
                        style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w800,
                            color: cs.onSurface)),
                    const SizedBox(height: 2),
                    Text(e.$1,
                        style: TextStyle(
                            fontSize: 11, color: tokens.textSecondary)),
                  ],
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  final int index;
  final String text;
  const _StepRow({required this.index, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 14,
            backgroundColor: context.cs.primary,
            child: Text('$index',
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w700)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(text,
                style:
                    TextStyle(fontSize: 15, color: context.cs.onSurface)),
          ),
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 56, color: Colors.red),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            TextButton(onPressed: onRetry, child: const Text('Повторить')),
          ],
        ),
      ),
    );
  }
}

// MG_MADEPHOTO: лист «Фото приготовления» — просмотр/добавление/удаление своих
// фото готового блюда (камера/галерея). Отдельный виджет со своим состоянием.
class _MadePhotosSheet extends StatefulWidget {
  final ApiClient apiClient;
  final int recipeId;
  final List<Map<String, dynamic>> initial;
  final ValueChanged<List<Map<String, dynamic>>> onChanged;

  const _MadePhotosSheet({
    required this.apiClient,
    required this.recipeId,
    required this.initial,
    required this.onChanged,
  });

  @override
  State<_MadePhotosSheet> createState() => _MadePhotosSheetState();
}

class _MadePhotosSheetState extends State<_MadePhotosSheet> {
  late List<Map<String, dynamic>> _photos;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _photos = List<Map<String, dynamic>>.from(widget.initial);
  }

  void _emit() => widget.onChanged(List<Map<String, dynamic>>.from(_photos));

  Future<void> _add() async {
    if (_busy) return;
    try {
      final file = await pickPhoto(context);
      if (file == null) return;
      setState(() {
        _busy = true;
        _error = null;
      });
      final bytes = await file.readAsBytes();
      final b64 = 'data:${_mimeFromName(file.name)};base64,${base64Encode(bytes)}';
      final r = await widget.apiClient.post(
        '/recipes/${widget.recipeId}/made-photos/',
        data: {'image_b64': b64},
      );
      final photo = r is Map ? Map<String, dynamic>.from(r) : null;
      if (photo != null) {
        setState(() => _photos = [photo, ..._photos]);
        _emit();
      }
    } catch (err) {
      setState(() => _error = err is ApiException ? err.message : 'Не удалось загрузить фото.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _delete(int id) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.apiClient.delete('/recipes/${widget.recipeId}/made-photos/$id/');
      setState(() => _photos = _photos.where((p) => p['id'] != id).toList());
      _emit();
    } catch (err) {
      setState(() => _error = err is ApiException ? err.message : 'Не удалось удалить.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final h = MediaQuery.of(context).size.height * 0.7;
    return Container(
      height: h,
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        children: [
          const SizedBox(height: 10),
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: context.tokens.border,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 8, 4),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'Я приготовил — фото',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: cs.onSurface),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'Прикрепите фото готового блюда — с камеры или из галереи.',
                    style: TextStyle(fontSize: 13, color: context.tokens.textSecondary),
                  ),
                ),
                FilledButton.icon(
                  onPressed: _busy ? null : _add,
                  icon: const Icon(Icons.add_a_photo_outlined, size: 18),
                  label: const Text('Добавить'),
                ),
              ],
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 13)),
            ),
          if (_busy)
            const Padding(
              padding: EdgeInsets.all(8),
              child: LinearProgressIndicator(),
            ),
          Expanded(
            child: _photos.isEmpty
                ? Center(
                    child: Text('Пока нет фото',
                        style: TextStyle(color: context.tokens.textSecondary)),
                  )
                : GridView.builder(
                    padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 3,
                      crossAxisSpacing: 8,
                      mainAxisSpacing: 8,
                    ),
                    itemCount: _photos.length,
                    itemBuilder: (context, i) {
                      final p = _photos[i];
                      final url = p['image_url'] as String?;
                      final id = p['id'] as int?;
                      return Stack(
                        fit: StackFit.expand,
                        children: [
                          ClipRRect(
                            borderRadius: BorderRadius.circular(10),
                            child: (url == null || url.isEmpty)
                                ? Container(color: context.tokens.surfaceAlt)
                                : CachedNetworkImage(
                                    imageUrl: url,
                                    cacheManager: RecipeImageCache.instance,
                                    fit: BoxFit.cover,
                                    placeholder: (_, __) => Container(color: context.tokens.surfaceAlt),
                                    errorWidget: (_, __, ___) => Container(
                                      color: context.tokens.surfaceAlt,
                                      child: Icon(Icons.broken_image, color: context.tokens.textSecondary),
                                    ),
                                  ),
                          ),
                          if (id != null)
                            Positioned(
                              top: 4,
                              right: 4,
                              child: GestureDetector(
                                onTap: _busy ? null : () => _delete(id),
                                child: Container(
                                  width: 26,
                                  height: 26,
                                  decoration: BoxDecoration(
                                    color: Colors.black.withOpacity(0.6),
                                    shape: BoxShape.circle,
                                  ),
                                  child: const Icon(Icons.close, size: 16, color: Colors.white),
                                ),
                              ),
                            ),
                        ],
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
