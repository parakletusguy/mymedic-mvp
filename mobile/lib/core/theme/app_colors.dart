import 'package:flutter/material.dart';

/// MyMedic Design System — Color Tokens
/// Aesthetic: Premium, Trustworthy, Clinical yet Modern
abstract final class AppColors {
  // ── Primary (Medical Blues) ──────────────────────────────────
  static const Color primary       = Color(0xFF0056D2); // Deep Trust Blue
  static const Color primaryLight  = Color(0xFF4285F4); // Action Blue
  static const Color primaryDark   = Color(0xFF003C8F); // Header / Gradient

  // ── Secondary / Status ──────────────────────────────────────
  static const Color secondary     = Color(0xFF00BFA5); // Teal – Verified
  static const Color error         = Color(0xFFD32F2F); // Error Red
  static const Color warning       = Color(0xFFFFA000); // Pending Amber
  static const Color success       = Color(0xFF2E7D32); // Confirmed Green

  // ── Neutral / Surface ───────────────────────────────────────
  static const Color surface       = Color(0xFFFFFFFF);
  static const Color background    = Color(0xFFF5F7FA); // Soft Grey-Blue
  static const Color onSurface     = Color(0xFF1A1A1A); // Primary Text
  static const Color onSurfaceVar  = Color(0xFF757575); // Secondary Text
  static const Color textTertiary  = Color(0xFFBDBDBD);
  static const Color outline       = Color(0xFFE0E0E0); // Dividers
  static const Color shimmer       = Color(0xFFEEEEEE);

  // ── Gradients ───────────────────────────────────────────────
  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [primaryDark, primary],
  );

  static const LinearGradient heroOverlay = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [Colors.transparent, Color(0xCC003C8F)],
  );

  // ── Material ColorScheme factory ────────────────────────────
  static ColorScheme get lightScheme => const ColorScheme(
    brightness: Brightness.light,
    primary: primary,
    onPrimary: Colors.white,
    secondary: secondary,
    onSecondary: Colors.white,
    error: error,
    onError: Colors.white,
    surface: surface,
    onSurface: onSurface,
  );
}
