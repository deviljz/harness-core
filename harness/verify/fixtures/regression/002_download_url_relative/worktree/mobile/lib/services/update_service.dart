import 'package:http/http.dart' as http;
import 'dart:convert';

class UpdateService {
  final String baseUrl;
  UpdateService({required this.baseUrl});

  Future<Map<String, dynamic>?> checkUpdate() async {
    final response = await http.get(Uri.parse('$baseUrl/api/app/version'));
    if (response.statusCode != 200) return null;
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<bool> downloadApk(String downloadUrl) async {
    // BUG: downloadUrl may be a relative path like "/download/app-1.2.0.apk"
    // Uri.parse() on a relative path will fail at runtime with no baseUrl context
    final request = http.Request('GET', Uri.parse(downloadUrl));
    final response = await http.Client().send(request);
    return response.statusCode == 200;
  }
}
