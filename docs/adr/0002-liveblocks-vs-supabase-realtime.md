# 0002 — Liveblocks instead of Supabase Realtime

**Status**: Accepted · related: [0001](0001-separate-frontend-backend.md), [0004](0004-toggleable-voting.md)

## Context
The board needs real-time sync between participants: creating notes, moving them, grouping them, and voting. Postgres (via Supabase) had already been chosen as the persistent database, which made Supabase Realtime the "free" candidate in terms of integration (same vendor, Postgres Changes streams every new row with no extra sync code).

## Options considered
- **Supabase Realtime**: a single vendor, zero extra sync, but row-level "last-write-wins" conflict resolution — no automatic merge for concurrent edits. Every drag would mean writing to Postgres on each `pointermove`, which is both too slow for 60fps dragging and too much write volume for a free-tier database.
- **Liveblocks**: its own CRDT-based storage (`LiveList`, `LiveMap`, `LiveObject`), presence and cursors out of the box, built specifically for Figma/Miro-style collaborative canvases — but requires an explicit sync step to Postgres when the session closes, since it isn't the system of record.

## Decision
The board is **free-position** (Miro-style canvas, not fixed Trello-style columns). With free dragging and live cursors, the conflict of two people moving the same note at the same time is real and frequent — exactly the problem Liveblocks solves with CRDTs and Supabase Realtime doesn't. Liveblocks is chosen despite the extra cost of having to manually sync to Postgres when the session closes.

## Consequences
- Better simultaneous-drag experience, no last-write-wins glitches: a note's position updates in Liveblocks Storage on every `pointermove`, not just on release (see `StickyNote.tsx`'s comment on `onMove`), so every participant sees the drag live rather than a jump on drop.
- Presence (cursors, who's connected) is solved out of the box via Liveblocks' `useOthers`/`useMyPresence` — no custom "who's online" channel to build.
- Adds an explicit sync step at session close: `POST /sessions/{id}/close` receives the final notes (author, text, position, vote count, and which dynamic phase each was written in) from the frontend and persists them. **Correction from the original design**: this doesn't land in separate `card`/`group`/`vote` tables — `db_models.py` keeps `notes` and `groups` as JSON columns directly on the `sessions` row instead, since they're produced wholesale by `agents/consolidator.py` in one shot and read back wholesale, never queried note-by-note. Only `action_items` got a real table, because those need per-row CRUD and concurrent export. Votes themselves are never persisted per-participant; only the resolved count per note survives the sync.
- Two vendors to maintain instead of one (Liveblocks + Supabase/Postgres), each with its own auth story — the backend mints short-lived Liveblocks tokens per participant via `routes/liveblocks_auth.py` rather than exposing the Liveblocks secret key to the browser.
- The sync path is covered by `apps/web/scripts/verify-board-sync.mjs`, which drives two Liveblocks clients directly (no browser) to prove a note/vote/phase change made by one is observed by the other — this is the sync guarantee this ADR actually rests on, checked without relying on a UI test.
