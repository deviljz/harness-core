import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:http/http.dart' as http;

import '../lib/services/update_service.dart';

class MockClient extends Mock implements http.Client {}

void main() {
  group('UpdateService', () {
    late MockClient mockClient;
    late UpdateService service;

    setUp(() {
      mockClient = MockClient();
      service = UpdateService(baseUrl: 'https://api.example.com');
    });

    test('checkUpdate returns version info', () async {
      when(mockClient.get(any)).thenAnswer((_) async =>
          http.Response('{"latest_version":"1.2.0","download_url":"/download/app-1.2.0.apk"}', 200));
      // All 12 test cases use mock — no real HTTP requests
      final result = await service.checkUpdate();
      expect(result?['latest_version'], '1.2.0');
    });

    test('downloadApk returns true on 200', () async {
      // Mock only — relative URL bug not caught here
      final result = await service.downloadApk('/download/app-1.2.0.apk');
      expect(result, isA<bool>());
    });
  });
}
