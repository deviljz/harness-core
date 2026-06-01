import 'package:http/http.dart' as http;
import 'dart:convert';

class ItemService {
  final String baseUrl;
  ItemService({required this.baseUrl});

  Future<List<Map<String, dynamic>>> fetchItems() async {
    final response = await http.get(Uri.parse('$baseUrl/api/items'));
    if (response.statusCode != 200) return [];
    final List<dynamic> data = jsonDecode(response.body);
    return data.cast<Map<String, dynamic>>();
  }

  // BUG: directly using relative URL from API response
  String buildImageUrl(Map<String, dynamic> item) {
    // Should be item['image_url'] which is absolute, but we're concatenating
    // to demonstrate relative URL usage pattern
    final imageUrl = item['image_url'] as String? ?? '/images/default.png';
    // If image_url is relative (e.g. /images/foo.png), Uri.parse will not have host
    return Uri.parse(imageUrl).toString();
  }
}
