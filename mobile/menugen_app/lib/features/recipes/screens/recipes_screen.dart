import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/recipes_bloc.dart';

class RecipesScreen extends StatefulWidget {
  const RecipesScreen({super.key});
  @override State<RecipesScreen> createState() => _RecipesScreenState();
}
class _RecipesScreenState extends State<RecipesScreen> {
  final _searchCtrl = TextEditingController();
  @override void initState() { super.initState(); context.read<RecipesBloc>().add(const RecipesLoadRequested()); }
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Рецепты')),
      body: Column(children: [
        Padding(padding: const EdgeInsets.all(12), child: TextField(
          controller: _searchCtrl,
          decoration: InputDecoration(
            hintText: 'Поиск рецептов...', prefixIcon: const Icon(Icons.search),
            suffixIcon: IconButton(icon: const Icon(Icons.clear), onPressed: () {
              _searchCtrl.clear(); context.read<RecipesBloc>().add(const RecipesLoadRequested()); })),
          onChanged: (q) {
            if (q.length >= 2) context.read<RecipesBloc>().add(RecipesSearchRequested(q));
            else if (q.isEmpty) context.read<RecipesBloc>().add(const RecipesLoadRequested());
          },
        )),
        Expanded(child: BlocBuilder<RecipesBloc, RecipesState>(builder: (context, state) {
          if (state is RecipesLoading) return const Center(child: CircularProgressIndicator());
          if (state is RecipesLoaded) return ListView.builder(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            itemCount: state.recipes.length,
            itemBuilder: (_, i) {
              final r = state.recipes[i];
              return Card(child: ListTile(
                leading: r.imageUrl != null
                    ? ClipRRect(borderRadius: BorderRadius.circular(8),
                        child: Image.network(r.imageUrl!, width: 56, height: 56, fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => const Icon(Icons.restaurant)))
                    : const Icon(Icons.restaurant, size: 36),
                title: Text(r.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                subtitle: Text(r.cookTime ?? '', style: const TextStyle(fontSize: 12)),
              ));
            });
          return const SizedBox.shrink();
        })),
      ]),
    );
  }
}
