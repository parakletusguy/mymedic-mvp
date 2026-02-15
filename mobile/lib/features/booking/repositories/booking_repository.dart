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
  /// Falls back to mock data when backend is unreachable.
  Future<List<Map<String, dynamic>>> getAvailableSlots(String professionalId, String date) async {
    try {
      final response = await _client.get('/appointments/slots/$professionalId', queryParameters: {
        'date': date,
      });
      return List<Map<String, dynamic>>.from(response.data);
    } on DioException {
      // Backend unreachable — return mock time slots
      return _mockSlots(date);
    }
  }

  /// Book an appointment.
  /// Returns mock data when backend is unreachable.
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
    } on DioException {
      // Mock booking response for demo
      return {
        'id': 'booking-demo-${DateTime.now().millisecondsSinceEpoch}',
        'professional_id': professionalId,
        'start_time': startTime,
        'end_time': endTime,
        'status': 'confirmed',
      };
    }
  }

  // ── Mock Data ──────────────────────────────────────────────────

  List<Map<String, dynamic>> _mockSlots(String date) {
    final baseDate = DateTime.parse(date);
    final slots = <Map<String, dynamic>>[];

    // Generate slots from 9AM to 4PM in 30-minute increments
    for (int hour = 9; hour < 16; hour++) {
      for (int min = 0; min < 60; min += 30) {
        final start = DateTime(baseDate.year, baseDate.month, baseDate.day, hour, min);
        final end = start.add(const Duration(minutes: 30));
        slots.add({
          'start_time': start.toIso8601String(),
          'end_time': end.toIso8601String(),
          'is_available': true,
        });
      }
    }
    return slots;
  }
}
