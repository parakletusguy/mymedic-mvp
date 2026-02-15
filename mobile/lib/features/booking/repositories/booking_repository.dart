import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/api/api_client.dart';

final bookingRepositoryProvider = Provider<BookingRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return BookingRepository(apiClient);
});

class BookingRepository {
  final ApiClient _client;

  BookingRepository(this._client);

  /// Fetch bookable slots for a professional on a specific date.
  Future<List<Map<String, dynamic>>> getAvailableSlots(String professionalId, String date) async {
    try {
      final response = await _client.get('/appointments/slots/$professionalId', queryParameters: {
        'date': date,
      });
      return List<Map<String, dynamic>>.from(response.data);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Book an appointment.
  Future<Map<String, dynamic>> bookAppointment({
    required String professionalId,
    required String startTime,
    required String endTime,
  }) async {
    try {
      final response = await _client.post('/appointments/book', data: {
        'professional_id': professionalId,
        'start_time': startTime,
        'end_time': endTime,
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
    return 'Booking failed. Try another slot.';
  }
}
