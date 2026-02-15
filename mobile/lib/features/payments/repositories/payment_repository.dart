import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/api/api_client.dart';

final paymentRepositoryProvider = Provider<PaymentRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return PaymentRepository(apiClient);
});

class PaymentRepository {
  final ApiClient _client;

  PaymentRepository(this._client);

  /// Initialize a transaction for an appointment.
  /// Returns { 'checkout_url': string, 'reference': string }
  Future<Map<String, dynamic>> initializePayment(String appointmentId) async {
    try {
      final response = await _client.post('/payments/initialize', data: {
        'appointment_id': appointmentId,
      });
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Verify payment status manually.
  Future<Map<String, dynamic>> verifyPayment(String reference) async {
    try {
      final response = await _client.get('/payments/verify/$reference');
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  String _handleError(DioException e) {
    if (e.response?.data != null && e.response?.data['detail'] != null) {
      return e.response?.data['detail'];
    }
    return 'Payment communication error.';
  }
}
