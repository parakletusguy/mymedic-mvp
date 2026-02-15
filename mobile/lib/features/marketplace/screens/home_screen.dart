import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../repositories/marketplace_repository.dart';
import '../../../shared/widgets/professional_card.dart';

final searchProvider = StateProvider<String>((ref) => '');

final professionalsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final query = ref.watch(searchProvider);
  final repo = ref.watch(marketplaceRepositoryProvider);
  final data = await repo.searchProfessionals(query: query);
  return List<Map<String, dynamic>>.from(data['results']);
});

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final professionalsAsync = ref.watch(professionalsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Find a Specialist'),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(60),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
            child: TextField(
              decoration: InputDecoration(
                hintText: 'Search by specialty or bio...',
                prefixIcon: const Icon(Icons.search),
                filled: true,
                fillColor: Theme.of(context).colorScheme.surface,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
              onChanged: (v) => ref.read(searchProvider.notifier).state = v,
            ),
          ),
        ),
      ),
      body: professionalsAsync.when(
        data: (results) {
          if (results.isEmpty) {
            return const Center(child: Text('No verified specialists found.'));
          }
          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: results.length,
            itemBuilder: (context, index) {
              final prof = results[index];
              return Padding(
                padding: const EdgeInsets.only(bottom: 12.0),
                child: ProfessionalCard(
                  name: prof['full_name'] ?? 'Doctor',
                  specialty: prof['specialty'] ?? 'Specialist',
                  rating: (prof['rating'] as num?)?.toDouble() ?? 0.0,
                  reviewCount: prof['review_count'] ?? 0,
                  imageUrl: 'https://i.pravatar.cc/150?u=${prof['user_id']}',
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => ProfessionalDetailScreen(professional: prof),
                      ),
                    );
                  },
                ),
              );
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, st) => Center(child: Text('Error: $e')),
      ),
    );
  }
}
