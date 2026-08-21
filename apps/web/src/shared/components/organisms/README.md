# organisms

Components with their own business logic, composed from atoms/molecules:

- `StickyNote` — individual note. **Built: `canvas` variant only** (see
  `features/board/Canvas.tsx`); `list`/`chip` (mobile, ADR-0006) not built yet.
- `GroupContainer` — note grouping, `canvas | panel` variants. Not built yet
  — there's no consolidation-screen frontend at all currently.
- `DynamicCard`, `PhaseEditorRow`, `ActionItemRow`, `GroupPanel`, `SessionListItem`, `IntegrationForm` — not built yet.

(`PhaseTopBar` ended up living in `features/board/` instead, since it's
board-specific orchestration — reading/advancing Liveblocks' `phaseIndex`
— rather than a reusable presentational piece.)

The props/state details for each one live documented alongside its implementation (JSDoc) once the file is created.
