import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme/app_theme.dart';
import 'shared/widgets/main_shell.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    const ProviderScope(
      child: MyMedicApp(),
    ),
  );
}

class MyMedicApp extends ConsumerWidget {
  const MyMedicApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'MyMedic',
      theme: AppTheme.light,
      themeMode: ThemeMode.light,
      home: const MainShell(),
      debugShowCheckedModeBanner: false,
    );
  }
}
