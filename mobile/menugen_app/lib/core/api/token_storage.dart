import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStorage {
  static const _accessKey  = 'access_token';
  static const _refreshKey = 'refresh_token';

  final FlutterSecureStorage _storage;

  TokenStorage() : _storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  Future<void> saveTokens({required String access, required String refresh}) async {
    await Future.wait([
      _storage.write(key: _accessKey,  value: access),
      _storage.write(key: _refreshKey, value: refresh),
    ]);
  }

  Future<String?> getAccessToken()  async => _storage.read(key: _accessKey);
  Future<String?> getRefreshToken() async => _storage.read(key: _refreshKey);

  Future<void> clearTokens() async {
    await Future.wait([
      _storage.delete(key: _accessKey),
      _storage.delete(key: _refreshKey),
    ]);
  }

  Future<bool> hasToken() async => (await getAccessToken()) != null;
}
