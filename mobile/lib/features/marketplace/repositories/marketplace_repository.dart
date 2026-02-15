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
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Get detailed professional profile.
  Future<Map<String, dynamic>> getProfessionalDetails(String userId) async {
    try {
      final response = await _client.get('/professionals/$userId');
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  String _handleError(DioException e) {
    if (e.response?.data != null && e.response?.data['detail'] != null) {
      return e.response?.data['detail'];
    }
    return 'Failed to fetch professionals.';
  }
}
