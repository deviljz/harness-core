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
}
