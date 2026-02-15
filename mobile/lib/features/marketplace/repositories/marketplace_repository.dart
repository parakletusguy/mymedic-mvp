import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/api/api_client.dart';

final marketplaceRepositoryProvider = Provider<MarketplaceRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return MarketplaceRepository(apiClient);
});

class MarketplaceRepository {
  final ApiClient _client;

  MarketplaceRepository(this._client);

  /// Search for verified professionals.
  /// Falls back to mock data when the backend is unreachable.
  Future<Map<String, dynamic>> searchProfessionals({
    String? query,
    int page = 1,
    int size = 20,
  }) async {
    try {
      final response = await _client.get('/professionals/search', queryParameters: {
        if (query != null && query.isNotEmpty) 'q': query,
        'page': page,
        'size': size,
      });
      return response.data;
    } on DioException {
      // Backend unreachable — return mock data for demo/testing
      return _mockSearchResults(query: query);
    }
  }

  /// Get detailed professional profile.
  Future<Map<String, dynamic>> getProfessionalDetails(String userId) async {
    try {
      final response = await _client.get('/professionals/$userId');
      return response.data;
    } on DioException {
      // Return mock detail for demo
      final all = _mockProfessionals();
      return all.firstWhere(
        (p) => p['user_id'] == userId,
        orElse: () => all.first,
      );
    }
  }

  // ── Mock Data ──────────────────────────────────────────────────

  Map<String, dynamic> _mockSearchResults({String? query}) {
    var results = _mockProfessionals();
    if (query != null && query.isNotEmpty) {
      final q = query.toLowerCase();
      results = results
          .where((p) =>
              (p['full_name'] as String).toLowerCase().contains(q) ||
              (p['specialty'] as String).toLowerCase().contains(q) ||
              (p['bio'] as String).toLowerCase().contains(q))
          .toList();
    }
    return {
      'results': results,
      'total': results.length,
      'page': 1,
      'size': 20,
    };
  }

  List<Map<String, dynamic>> _mockProfessionals() {
    return [
      {
        'user_id': 'doc-001',
        'full_name': 'Dr. Adaeze Okonkwo',
        'specialty': 'Cardiologist',
        'bio': 'Board-certified cardiologist with 12 years of experience in interventional cardiology and cardiac imaging. Trained at LUTH and Johns Hopkins.',
        'rating': 4.9,
        'review_count': 127,
        'years_of_experience': 12,
        'consultation_fee': 15000,
        'is_verified': true,
        'availability': 'Mon-Fri, 9AM-4PM',
      },
      {
        'user_id': 'doc-002',
        'full_name': 'Dr. Chukwuma Eze',
        'specialty': 'Dermatologist',
        'bio': 'Specializing in cosmetic dermatology, skin cancer screening, and treatment of chronic skin conditions. Fellow of the Nigerian Medical Association.',
        'rating': 4.7,
        'review_count': 89,
        'years_of_experience': 8,
        'consultation_fee': 12000,
        'is_verified': true,
        'availability': 'Mon-Sat, 10AM-5PM',
      },
      {
        'user_id': 'doc-003',
        'full_name': 'Dr. Fatima Bello',
        'specialty': 'Pediatrician',
        'bio': 'Compassionate pediatrician dedicated to child wellness. Expert in neonatal care, childhood vaccinations, and developmental assessments.',
        'rating': 4.8,
        'review_count': 203,
        'years_of_experience': 15,
        'consultation_fee': 10000,
        'is_verified': true,
        'availability': 'Mon-Fri, 8AM-3PM',
      },
      {
        'user_id': 'doc-004',
        'full_name': 'Dr. Oluwaseun Adeyemi',
        'specialty': 'Orthopedic Surgeon',
        'bio': 'Expert in joint replacement surgery, sports medicine, and fracture management. Over 500 successful surgeries performed.',
        'rating': 4.6,
        'review_count': 64,
        'years_of_experience': 10,
        'consultation_fee': 20000,
        'is_verified': true,
        'availability': 'Tue-Sat, 9AM-2PM',
      },
      {
        'user_id': 'doc-005',
        'full_name': 'Dr. Ngozi Ibe',
        'specialty': 'Gynecologist',
        'bio': 'Women\'s health specialist with expertise in prenatal care, reproductive health, and minimally invasive gynecological surgery.',
        'rating': 4.9,
        'review_count': 156,
        'years_of_experience': 14,
        'consultation_fee': 18000,
        'is_verified': true,
        'availability': 'Mon-Thu, 9AM-5PM',
      },
      {
        'user_id': 'doc-006',
        'full_name': 'Dr. Ibrahim Yusuf',
        'specialty': 'Neurologist',
        'bio': 'Specializing in headache disorders, epilepsy management, and neurodegenerative diseases. Published researcher with 20+ papers.',
        'rating': 4.5,
        'review_count': 47,
        'years_of_experience': 9,
        'consultation_fee': 25000,
        'is_verified': true,
        'availability': 'Mon-Fri, 10AM-4PM',
      },
      {
        'user_id': 'doc-007',
        'full_name': 'Dr. Amaka Nwosu',
        'specialty': 'General Practitioner',
        'bio': 'Family medicine specialist providing comprehensive primary care, health screenings, and chronic disease management for all ages.',
        'rating': 4.8,
        'review_count': 312,
        'years_of_experience': 7,
        'consultation_fee': 5000,
        'is_verified': true,
        'availability': 'Mon-Sat, 8AM-6PM',
      },
      {
        'user_id': 'doc-008',
        'full_name': 'Dr. Emeka Okoro',
        'specialty': 'Psychiatrist',
        'bio': 'Mental health expert specializing in anxiety, depression, PTSD, and addiction recovery. Advocate for mental health awareness in Nigeria.',
        'rating': 4.7,
        'review_count': 78,
        'years_of_experience': 11,
        'consultation_fee': 15000,
        'is_verified': true,
        'availability': 'Mon-Fri, 9AM-3PM',
      },
    ];
  }
}
