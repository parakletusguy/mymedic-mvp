import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../repositories/booking_repository.dart';
import '../../payments/screens/payment_webview_screen.dart';
import '../../payments/repositories/payment_repository.dart';
import '../../../shared/widgets/time_slot_chip.dart';

class BookingScreen extends ConsumerStatefulWidget {
  final Map<String, dynamic> professional;

  const BookingScreen({super.key, required this.professional});

  @override
  ConsumerState<BookingScreen> createState() => _BookingScreenState();
}

class _BookingScreenState extends ConsumerState<BookingScreen> {
  DateTime _selectedDate = DateTime.now().add(const Duration(days: 1));
  Map<String, dynamic>? _selectedSlot;

  Future<void> _handleBooking() async {
    if (_selectedSlot == null) return;

    try {
      final repo = ref.read(bookingRepositoryProvider);
      final booking = await repo.bookAppointment(
        professionalId: widget.professional['user_id'],
        startTime: _selectedSlot!['start_time'],
        endTime: _selectedSlot!['end_time'],
      );

      if (mounted) {
        // Now navigate to payment initialization
        _initializePayment(booking['id']);
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString())),
      );
    }
  }

  Future<void> _initializePayment(String appointmentId) async {
    try {
      final payRepo = ref.read(paymentRepositoryProvider);
      final payment = await payRepo.initializePayment(appointmentId);
      
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(
            builder: (_) => PaymentWebviewScreen(
              checkoutUrl: payment['checkout_url'],
              appointmentId: appointmentId,
            ),
          ),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Payment initialization failed: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final dateStr = DateFormat('yyyy-MM-dd').format(_selectedDate);
    final slotsAsync = ref.watch(slotsProvider((profId: widget.professional['user_id'] as String, date: dateStr)));

    return Scaffold(
      appBar: AppBar(title: const Text('Select Time Slot')),
      body: Column(
        children: [
          CalendarDatePicker(
            initialDate: _selectedDate,
            firstDate: DateTime.now(),
            lastDate: DateTime.now().add(const Duration(days: 30)),
            onDateChanged: (date) {
              setState(() {
                _selectedDate = date;
                _selectedSlot = null;
              });
            },
          ),
          const Divider(),
          Expanded(
            child: slotsAsync.when(
              data: (slots) {
                if (slots.isEmpty) {
                  return const Center(child: Text('No slots available for this date.'));
                }
                return GridView.builder(
                  padding: const EdgeInsets.all(16),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 3,
                    childAspectRatio: 2.2,
                    crossAxisSpacing: 10,
                    mainAxisSpacing: 10,
                  ),
                  itemCount: slots.length,
                  itemBuilder: (context, index) {
                    final slot = slots[index];
                    final time = DateFormat('HH:mm').format(DateTime.parse(slot['start_time']).toLocal());
                    final isSelected = _selectedSlot == slot;

                    return TimeSlotChip(
                      label: time,
                      state: isSelected ? SlotState.selected : SlotState.available,
                      onTap: () => setState(() => _selectedSlot = slot),
                    );
                  },
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, st) => Center(child: Text('Error: $e')),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(20.0),
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _selectedSlot == null ? null : _handleBooking,
                child: const Text('Confirm & Pay'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

final futureSlotsProvider = FutureProvider.family<List<Map<String, dynamic>>, String>((ref, params) async {
  final parts = params.split('|'); // professionalId|date
  // Wait, Provider.family takes one argument. I'll use a string join.
  return []; // Placeholder for implementation logic below
});

// Correct implementation of family provider
final slotsProvider = FutureProvider.family<List<Map<String, dynamic>>, ({String profId, String date})>((ref, args) async {
  final repo = ref.watch(bookingRepositoryProvider);
  return await repo.getAvailableSlots(args.profId, args.date);
});
