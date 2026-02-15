import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../repositories/auth_repository.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

final authControllerProvider = StateNotifierProvider<AuthController, AsyncValue<void>>((ref) {
  final repository = ref.watch(authRepositoryProvider);
  return AuthController(repository);
});

class AuthController extends StateNotifier<AsyncValue<void>> {
  final AuthRepository _repository;
  final _storage = const FlutterSecureStorage();

  AuthController(this._repository) : super(const AsyncValue.data(null));

  String? _interimToken;
  String? _email;

  String? get interimToken => _interimToken;
  String? get currentEmail => _email;

  Future<bool> login(String email, String password) async {
    state = const AsyncValue.loading();
    try {
      final data = await _repository.login(email, password);
      _interimToken = data['interim_token'];
      _email = email;
      state = const AsyncValue.data(null);
      return data['otp_required'] ?? false;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      return false;
    }
  }

  Future<bool> verifyOtp(String otp) async {
    if (_email == null || _interimToken == null) return false;
    
    state = const AsyncValue.loading();
    try {
      final data = await _repository.verifyOtp(_email!, otp, _interimToken!);
      
      // Persist tokens
      await _storage.write(key: 'access_token', value: data['access_token']);
      await _storage.write(key: 'refresh_token', value: data['refresh_token']);
      
      state = const AsyncValue.data(null);
      return true;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      return false;
    }
  }

  Future<bool> register(String email, String password, String role) async {
    state = const AsyncValue.loading();
    try {
      await _repository.register(email: email, password: password, role: role);
      state = const AsyncValue.data(null);
      return true;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      return false;
    }
  }
}
