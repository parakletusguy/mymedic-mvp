import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';

/// A chat message bubble for Patient ↔ Professional communication.
///
/// Design Spec:
///   - "Me" (isMine=true):  primaryLight bg, white text,
///     rounded TL(12), TR(12), BL(12) — sharp bottom-right.
///   - "Other" (isMine=false): surface bg, onSurface text, outline border,
///     rounded TL(12), TR(12), BR(12) — sharp bottom-left.
///   - Timestamp caption aligned bottom-right.
class MessageBubble extends StatelessWidget {
  final String message;
  final String timestamp;
  final bool isMine;

  const MessageBubble({
    super.key,
    required this.message,
    required this.timestamp,
    required this.isMine,
  });

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: isMine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.75,
        ),
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: isMine ? AppColors.primaryLight : AppColors.surface,
          border: isMine
              ? null
              : Border.all(color: AppColors.outline),
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(12),
            topRight: const Radius.circular(12),
            bottomLeft: Radius.circular(isMine ? 12 : 0),
            bottomRight: Radius.circular(isMine ? 0 : 12),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              message,
              style: AppTypography.bodyMedium.copyWith(
                color: isMine ? Colors.white : AppColors.onSurface,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              timestamp,
              style: AppTypography.caption.copyWith(
                color: isMine
                    ? Colors.white.withValues(alpha: 0.7)
                    : AppColors.textTertiary,
                fontSize: 10,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
