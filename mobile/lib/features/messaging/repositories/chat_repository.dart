import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/api/api_client.dart';

final chatRepositoryProvider = Provider<ChatRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return ChatRepository(apiClient);
});

class ChatRepository {
  final ApiClient _client;

  ChatRepository(this._client);

  /// Fetch chat history for a specific appointment.
  Future<List<Map<String, dynamic>>> getChatHistory(String appointmentId) async {
    try {
      final response = await _client.get('/chat/history/$appointmentId');
      return List<Map<String, dynamic>>.from(response.data);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Send a new message.
  Future<Map<String, dynamic>> sendMessage({
    required String appointmentId,
    required String content,
  }) async {
    try {
      final response = await _client.post('/chat/send', data: {
        'appointment_id': appointmentId,
        'content': content,
      });
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Mark messages as read.
  Future<void> markAsRead(String appointmentId) async {
    try {
      await _client.post('/chat/read/$appointmentId');
    } catch (_) {
      // Fail silently for read receipts
    }
  }

  String _handleError(DioException e) {
    if (e.response?.data != null && e.response?.data['detail'] != null) {
      return e.response?.data['detail'];
    }
    return 'Could not reach the secure messaging server.';
  }
}
