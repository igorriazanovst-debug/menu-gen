import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/recipes_bloc.dart';

class RecipesScreen extends StatefulWidget {
  const RecipesScreen({super.key});
  @override
  State<RecipesScreen> createState() => _RecipesScreenState();
}

class _RecipesScreenState extends State<RecipesScreen> {
  final _searchCtrl = TextEditingController();
  String? _selectedCategory;
  final _scrollCtrl = ScrollController();
  int _page = 1;
  bool _hasMore = true;
  final List<Map<String, dynamic>> _recipes = [];
  bool _loadingMore = false;

  static const _categories = [
    'Все', 'Завтрак', 'Обед', 'Ужин', 'Суп', 'Салат', 'Выпечка', 'Десерт', 'Напиток',
  ];

  @override
  void initState() {
    super.initState();
    _load(reset: true);
    _scrollCtrl.addListener(_onScroll);
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollCtrl.position.pixels >= _scrollCtrl.position.maxScrollExtent - 200
        && !_loadingMore && _hasMore) {
      _loadMore();
    }
  }

  void _load({bool reset = false}) {
    if (reset) {
      _page = 1;
      _recipes.clear();
      _hasMore = true;
    }
    final params = <String, dynamic>{'page': _page};
    if (_searchCtrl.text.isNotEmpty) params['search'] = _searchCtrl.text;
    if (_selectedCategory != null && _selectedCategory != 'Все') {
      params['category'] = _selectedCategory;
    }
    context.read<RecipesBloc>().add(RecipesPageRequested(params: params));
  }

  void _loadMore() {
    if (_loadingMore || !_hasMore) return;
    setState(() { _loadingMore = true; _page++; });
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Рецепты')),
      body: BlocListener<RecipesBloc, RecipesState>(
        listener: (context, state) {
          if (state is RecipesPageLoaded) {
            setState(() {
              _recipes.addAll(state.recipes);
              _hasMore = state.hasMore;
              _loadingMore = false;
            });
          }
          if (state is RecipesError) setState(() => _loadingMore = false);
        },
        child: Column(children: [
          // Поиск
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
            child: TextField(
              controller: _searchCtrl,
              decoration: InputDecoration(
                hintText: 'Поиск рецептов...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchCtrl.text.isNotEmpty
                    ? IconButton(icon: const Icon(Icons.clear),
                        onPressed: () { _searchCtrl.clear(); _load(reset: true); })
                    : null,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                contentPadding: const EdgeInsets.symmetric(vertical: 0),
              ),
              onSubmitted: (_) => _load(reset: true),
            ),
          ),
          // Рубрикатор
          SizedBox(height: 44,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
              itemCount: _categories.length,
              itemBuilder: (_, i) {
                final cat = _categories[i];
                final selected = (_selectedCategory ?? 'Все') == cat;
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: FilterChip(
                    label: Text(cat),
                    selected: selected,
                    onSelected: (_) {
                      setState(() => _selectedCategory = cat == 'Все' ? null : cat);
                      _load(reset: true);
                    },
                  ),
                );
              },
            ),
          ),
          // Список
          Expanded(
            child: _recipes.isEmpty
                ? BlocBuilder<RecipesBloc, RecipesState>(
                    builder: (_, state) => state is RecipesLoading
                        ? const Center(child: CircularProgressIndicator())
                        : const Center(child: Text('Нет рецептов')))
                : ListView.builder(
                    controller: _scrollCtrl,
                    itemCount: _recipes.length + (_hasMore ? 1 : 0),
                    itemBuilder: (_, i) {
                      if (i == _recipes.length) {
                        return const Padding(
                          padding: EdgeInsets.all(16),
                          child: Center(child: CircularProgressIndicator()),
                        );
                      }
                      final r = _recipes[i];
                      final imageUrl = r['image_url'] as String?;
                      return ListTile(
                        leading: imageUrl != null
                            ? ClipRRect(borderRadius: BorderRadius.circular(4),
                                child: Image.network(imageUrl, width: 56, height: 56,
                                    fit: BoxFit.cover,
                                    errorBuilder: (_, __, ___) => const Icon(Icons.restaurant)))
                            : const Icon(Icons.restaurant),
                        title: Text(r['title'] as String? ?? '',
                            maxLines: 1, overflow: TextOverflow.ellipsis),
                        subtitle: Text(r['cook_time'] as String? ?? '',
                            style: const TextStyle(fontSize: 12)),
                      );
                    },
                  ),
          ),
        ]),
      ),
    );
  }
}