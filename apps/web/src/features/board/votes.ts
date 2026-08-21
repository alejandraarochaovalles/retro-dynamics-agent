// Pure vote-tally logic for the board's toggleable voting (ADR-0004).
// Kept independent of Liveblocks' LiveMap/LiveList types (plain
// Record<participant, noteId[]> in, plain values out) so it's unit
// -testable without a live room — Canvas.tsx's useMutation callbacks are
// the only place that touch the real LiveMap/LiveList.
export type VotesByParticipant = Record<string, string[]>;

export function countVotes(votes: VotesByParticipant, noteId: string): number {
  let count = 0;
  for (const noteIds of Object.values(votes)) {
    if (noteIds.includes(noteId)) count++;
  }
  return count;
}

export function hasVoted(votes: VotesByParticipant, participant: string, noteId: string): boolean {
  return votes[participant]?.includes(noteId) ?? false;
}

/** Given one participant's current vote list, returns their next vote list
 * after toggling `noteId` — add it if absent, remove it if present. */
export function toggleVote(currentVotes: string[], noteId: string): string[] {
  return currentVotes.includes(noteId)
    ? currentVotes.filter((id) => id !== noteId)
    : [...currentVotes, noteId];
}
