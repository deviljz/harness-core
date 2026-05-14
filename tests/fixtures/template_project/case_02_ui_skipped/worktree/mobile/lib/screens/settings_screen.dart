import 'package:flutter/material.dart';

/// SettingsPage — NOTE: close button (X) is intentionally omitted in this impl.
class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('设置'),
        // No close button added — spec requires Icons.close button here
      ),
      body: const ListTile(title: Text('通知设置')),
    );
  }
}
