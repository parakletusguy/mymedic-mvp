import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';

/// A card displaying a healthcare professional's summary.
/// Used in search results, featured lists, and recommendations.
///
/// Design Spec:
///   - Elevation 2, 12px radius, 16px internal padding
///   - Avatar (radius 30) with optional verified badge overlay
///   - Name (H3), Specialty (BodyMedium, primaryLight), Star rating
///   - Chevron trailing icon for navigation affordance
class ProfessionalCard extends StatelessWidget {
  final String name;
  final String specialty;
  final String? imageUrl;
  final double rating;
  final int reviewCount;
  final bool isVerified;
  final VoidCallback? onTap;

  const ProfessionalCard({
    super.key,
    required this.name,
    required this.specialty,
    this.imageUrl,
    this.rating = 0.0,
    this.reviewCount = 0,
    this.isVerified = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              // ── Avatar with verified badge ──────────────────
              Stack(
                clipBehavior: Clip.none,
                children: [
                  CircleAvatar(
                    radius: 30,
                    backgroundColor: AppColors.shimmer,
                    backgroundImage:
                        imageUrl != null ? NetworkImage(imageUrl!) : null,
                    child: imageUrl == null
                        ? const Icon(Icons.person, color: AppColors.onSurfaceVar)
                        : null,
                  ),
                  if (isVerified)
                    Positioned(
                      bottom: -2,
                      right: -2,
                      child: Container(
                        padding: const EdgeInsets.all(2),
                        decoration: const BoxDecoration(
                          color: AppColors.surface,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.verified,
                          color: AppColors.secondary,
                          size: 16,
                        ),
                      ),
                    ),
                ],
              ),

              const SizedBox(width: 14),

              // ── Info column ─────────────────────────────────
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name, style: AppTypography.h3),
                    const SizedBox(height: 2),
                    Text(
                      specialty,
                      style: AppTypography.bodyMedium
                          .copyWith(color: AppColors.primaryLight),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        const Icon(Icons.star_rounded,
                            color: Color(0xFFFFC107), size: 16),
                        const SizedBox(width: 4),
                        Text(
                          '$rating',
                          style: AppTypography.bodyMedium
                              .copyWith(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          '($reviewCount)',
                          style: AppTypography.caption,
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              // ── Chevron ─────────────────────────────────────
              const Icon(Icons.chevron_right, color: AppColors.outline),
            ],
          ),
        ),
      ),
    );
  }
}
