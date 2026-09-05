# board

Live board screen (free-position canvas). Built so far — **desktop canvas
core only**:

- `BoardScreen.tsx` — mounts `LiveblocksProvider` + `RoomProvider` (see
  `types.ts` for the Presence/Storage shapes and the `declare global`
  augmentation that types every Liveblocks hook app-wide) and a
  `ClientSideSuspense` boundary. Its fallback reads `useStatus()` to tell
  the difference between "still connecting" and "disconnected/reconnecting"
  — the latter is shown as an explicit warning, since corporate networks/VPNs
  that block WebSocket traffic (Zscaler/Blue Coat-style proxies) otherwise
  leave the user staring at "Connecting…" forever with no explanation.
- `Canvas.tsx` — sticky notes, live drag (position updates on every
  pointermove, not just on release — see `StickyNote.tsx`'s comment on
  why), toggleable voting (ADR-0004), live cursors via Presence.
- `PhaseTopBar.tsx` — steps through `session.dynamic.phases` (from
  `dynamics/generate`, see `SessionSetup.tsx`), phase advance is
  open to anyone in the room (no facilitator role), "Close session" on
  the last phase syncs Storage → Postgres via the existing
  `POST /sessions/{id}/close`.
- `votes.ts` — pure vote-tally logic, unit-tested independent of
  Liveblocks (`votes.test.ts`).
- `liveblocksClient.ts` — the `authEndpoint` callback wiring; see its
  comment for why it has to be a function, not a URL string.

**Not built yet** (deliberately out of scope for this pass, see
ADR-0006):

- Mobile list view (`< 768px` breakpoint) — `StickyNote`'s `list`/`chip`
  variants don't exist, only `canvas`.
- Lasso/rectangle grouping — the consolidation screen after `close`
  (`/sessions/{id}/groups` etc.) has no frontend yet at all.
- Live phase-sync for participants who joined *before* the session was
  started: the coarse session `phase` (lobby/active/...) lives in
  Postgres, not Liveblocks, and isn't polled — a joiner sitting in the
  lobby won't see the screen flip to the board until they rejoin.

**Verification**: `npm run verify:board` (`scripts/verify-board-sync.mjs`
at the web package root) opens two independent Liveblocks connections and
proves a note/vote/phase-change from one is observed by the other —
requires `apps/api` running with a real `LIVEBLOCKS_SECRET_KEY`. Without
one, this feature is typed-correct (`tsc --noEmit` passes against the
real `@liveblocks/*` type definitions) and unit-tested (`votes.ts`), but
its actual real-time sync has **not** been run live — see the root
README's persistence/contract sections for how the rest of this app was
verified live, for contrast.

See [docs/adr/0002](../../../../docs/adr/0002-liveblocks-vs-supabase-realtime.md)
and [docs/adr/0006](../../../../docs/adr/0006-free-position-canvas-mobile-view.md).
