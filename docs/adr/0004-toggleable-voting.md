# 0004 — Toggleable voting

**Status**: Accepted · related: [0002](0002-liveblocks-vs-supabase-realtime.md)

## Context
During the voting phase, each participant votes on the notes that matter most to them. It had to be decided whether clicking toggles the vote (vote/unvote) or is one-directional (once voted, it can't be undone) — and, separately, whether votes are capped per participant or unlimited.

## Decision
Clicking toggles the vote, and voting is uncapped: a participant can vote for as many notes as they want, change their mind, and remove a vote to give it to another one, as long as the voting phase is still active. `StickyNote.tsx` renders this as a star toggle (`☆`/`★` + live count) with `aria-pressed` reflecting the participant's own vote state.

## Consequences
- **Data model**: live votes are stored in Liveblocks Storage as `LiveMap<participantName, LiveList<noteId>>` (`Canvas.tsx`'s `toggleNoteVote` mutation) — each participant writes only their own entry, avoiding write conflicts between people voting at the same time. The vote count per note is derived by counting how many participants' lists contain that note's id (`features/board/votes.ts`'s pure `countVotes`/`hasVoted` helpers, unit-tested independent of any Liveblocks types), rather than kept as a separate mutable counter that could drift.
- When syncing to Postgres on session close, only the final, already-resolved vote count per note is persisted (`Note.votes` / `Group.votes` in `models.py`) — there's no need to reconcile historical additions/removals, and no per-participant vote record survives the sync; the tally is intentionally the only thing that outlives the live session.
- Extends conceptually to a future `GroupContainer` (grouping several notes into one theme before voting): undoing a grouping shouldn't delete votes already registered on the group, only empty its membership, so an insight's vote history survives regrouping. **This part is design intent, not yet built** — today's board only ever votes on individual notes; `agents/consolidator.py`'s grouping only happens server-side, after close, and is currently a naive 1:1 (each note becomes its own group) rather than a live, votable clustering UI. See `shared/components/organisms/README.md` for what's actually built vs. planned for `GroupContainer`.
