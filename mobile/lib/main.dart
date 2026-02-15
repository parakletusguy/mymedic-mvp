import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme/app_theme.dart';

import 'features/auth/screens/login_screen.dart';

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
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
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
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.system,
      home: const MainShell(),
      debugShowCheckedModeBanner: false,
    );
  }
}
