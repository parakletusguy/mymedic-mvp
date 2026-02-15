import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';

/// Available states for a time‐slot chip.
enum SlotState { available, selected, disabled }

/// A selectable time‐slot chip for the booking calendar grid.
///
/// Design Spec:
///   - Height 48, horizontally flexible
///   - Default: outlined, white bg
///   - Selected: primaryLight bg, white text
///   - Disabled: grey200 bg, grey400 text
class TimeSlotChip extends StatelessWidget {
  final String label;
  final SlotState state;
  final VoidCallback? onTap;

  const TimeSlotChip({
    super.key,
    required this.label,
    this.state = SlotState.available,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final bool isSelected = state == SlotState.selected;
    final bool isDisabled = state == SlotState.disabled;

    return GestureDetector(
      onTap: isDisabled ? null : onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeInOut,
        height: 48,
        alignment: Alignment.center,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        decoration: BoxDecoration(
          color: isSelected
              ? AppColors.primaryLight
              : isDisabled
                  ? const Color(0xFFEEEEEE)
                  : AppColors.surface,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(
            color: isSelected
                ? AppColors.primaryLight
                : isDisabled
                    ? const Color(0xFFE0E0E0)
                    : AppColors.outline,
          ),
        ),
        child: Text(
          label,
          style: AppTypography.bodyMedium.copyWith(
            color: isSelected
                ? Colors.white
                : isDisabled
                    ? const Color(0xFFBDBDBD)
                    : AppColors.onSurface,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
      ),
    );
  }
}
