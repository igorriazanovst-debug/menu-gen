part of 'diary_bloc.dart';

abstract class DiaryState extends Equatable {
  const DiaryState();
  @override
  List<Object?> get props => [];
}

class DiaryInitial extends DiaryState {
  const DiaryInitial();
}

class DiaryLoading extends DiaryState {
  const DiaryLoading();
}

class DiaryLoaded extends DiaryState {
  final String date;
  final int? memberId;
  final List<DiaryEntry> entries;
  final DiaryDayStats stats;
  final int waterMl; // DIARY_V2

  const DiaryLoaded({
    required this.date,
    required this.memberId,
    required this.entries,
    required this.stats,
    this.waterMl = 0,
  });

  /// Planned entries (came from menu import, may or may not be eaten yet).
  List<DiaryEntry> get plannedEntries =>
      entries.where((e) => e.isPlanned).toList();

  /// Manual / actual-only entries (no plan attached).
  List<DiaryEntry> get manualEntries =>
      entries.where((e) => !e.isPlanned).toList();

  DiaryLoaded copyWith({
    String? date,
    int? memberId,
    List<DiaryEntry>? entries,
    DiaryDayStats? stats,
    int? waterMl,
  }) {
    return DiaryLoaded(
      date: date ?? this.date,
      memberId: memberId ?? this.memberId,
      entries: entries ?? this.entries,
      stats: stats ?? this.stats,
      waterMl: waterMl ?? this.waterMl,
    );
  }

  @override
  List<Object?> get props => [date, memberId, entries, stats, waterMl];
}

/// MG-606: backend denied access with 403 from IsFamilyPremiumOrReadOnly.
///
/// `isWrite=false` → user has no premium history at all (full lock).
/// `isWrite=true`  → user is in read-only-after-expiry mode (writes blocked).
class DiaryPremiumLocked extends DiaryState {
  final String message;
  final bool isWrite;
  const DiaryPremiumLocked({required this.message, required this.isWrite});
  @override
  List<Object?> get props => [message, isWrite];
}

class DiaryError extends DiaryState {
  final String message;
  const DiaryError({required this.message});
  @override
  List<Object?> get props => [message];
}
