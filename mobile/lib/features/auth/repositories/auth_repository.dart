import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/api/api_client.dart';

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return AuthRepository(apiClient);
});

class AuthRepository {
  final ApiClient _client;

  AuthRepository(this._client);

  /// Phase 1: Login with credentials.
  /// Returns { 'interim_token': string, 'otp_required': bool }
  Future<Map<String, dynamic>> login(String email, String password) async {
    try {
      final response = await _client.post('/auth/login', data: {
        'username': email,
        'password': password,
      });
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Phase 2: Verify OTP.
  /// Returns { 'access_token': string, 'refresh_token': string, 'user': ... }
  Future<Map<String, dynamic>> verifyOtp(String email, String otp, String interimToken) async {
    try {
      final response = await _client.post('/auth/verify-otp', data: {
        'email': email,
        'otp': otp,
        'interim_token': interimToken,
      });
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Register a new user.
  Future<Map<String, dynamic>> register({
    required String email,
    required String password,
    required String role,
  }) async {
    try {
      final response = await _client.post('/auth/register', data: {
        'email': email,
        'password': password,
        'role': role,
      });
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  String _handleError(DioException e) {
    if (e.response?.data != null && e.response?.data['detail'] != null) {
      return e.response?.data['detail'];
    }
    return 'An unexpected error occurred. Please try again.';
  }
}
