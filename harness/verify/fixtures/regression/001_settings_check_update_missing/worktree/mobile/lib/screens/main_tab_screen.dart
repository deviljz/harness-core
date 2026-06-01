import 'package:flutter/material.dart';
import '../services/update_service.dart';

class MainTabScreen extends StatefulWidget {
  const MainTabScreen({super.key});
  @override
  State<MainTabScreen> createState() => _MainTabScreenState();
}

class _MainTabScreenState extends State<MainTabScreen> {
  final _updateService = UpdateService(baseUrl: 'https://api.example.com');

  @override
  void initState() {
    super.initState();
    // 冷启动静默检查
    _updateService.checkUpdate().then((info) {
      // TODO: show dialog if new version available
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('喵辅导'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () {
              // TODO: navigate to settings screen
            },
          ),
        ],
      ),
      body: const Center(child: Text('Main')),
    );
  }
}
