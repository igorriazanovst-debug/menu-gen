import 'package:flutter_test/flutter_test.dart';
import 'package:menugen_app/core/api/api_exception.dart';

void main() {
  test('isPremiumLocked is true for 403', () {
    const e = ApiException(message: 'x', statusCode: 403);
    expect(e.isPremiumLocked, isTrue);
  });

  test('isPremiumLocked is false for 200/401/404/500', () {
    expect(const ApiException(message: 'x', statusCode: 200).isPremiumLocked, isFalse);
    expect(const ApiException(message: 'x', statusCode: 401).isPremiumLocked, isFalse);
    expect(const ApiException(message: 'x', statusCode: 404).isPremiumLocked, isFalse);
    expect(const ApiException(message: 'x', statusCode: 500).isPremiumLocked, isFalse);
  });

  test('isNetwork is true when statusCode is null', () {
    const e = ApiException(message: 'timeout');
    expect(e.isNetwork, isTrue);
    expect(e.isPremiumLocked, isFalse);
  });

  test('isServerError is true for 5xx only', () {
    expect(const ApiException(message: 'x', statusCode: 500).isServerError, isTrue);
    expect(const ApiException(message: 'x', statusCode: 503).isServerError, isTrue);
    expect(const ApiException(message: 'x', statusCode: 499).isServerError, isFalse);
    expect(const ApiException(message: 'x', statusCode: 403).isServerError, isFalse);
  });
}
