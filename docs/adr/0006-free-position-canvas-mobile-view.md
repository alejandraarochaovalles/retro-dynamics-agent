# 0006 — Free-position canvas with mobile list view

**Status**: Accepted (design) — desktop canvas built; mobile view is a documented follow-up, not yet implemented.

## Context
The team joins retros from a mix of devices — some from a phone, others from a computer. The board chosen is free-position (Miro-style canvas, see ADR 0002), but precise finger dragging is the interaction that translates worst to touch.

## Decision
The data model is the same across all devices (a note's `x`/`y` always exists, regardless of how it was created), but the **interaction** changes by breakpoint:
- **Desktop**: full canvas, freely draggable notes, other people's cursors live (built — see `features/board/Canvas.tsx`).
- **Mobile (< 768px)**: list view by default (vertical feed), with an optional read-only "Map" toggle. Creating a note is done via a floating button + bottom sheet, which assigns it an automatic position on the shared canvas so it still has real coordinates for anyone viewing on desktop. In the grouping phase, the lasso/rectangle is replaced by checkboxes in the list.

## Consequences
- No separate branch of the data model or the API contract is needed — it's purely an interaction-layer decision in the frontend; a note created from the mobile list view is indistinguishable, server-side, from one dragged into place on desktop.
- The `StickyNote` component is designed around a `variant` prop (`canvas | list | chip`) so the different renderings share the same vote/author/text logic without duplicating it. **Current status**: only `variant: "canvas"` is implemented (`shared/components/organisms/StickyNote.tsx`'s type only allows `"canvas"` today) — `list` and `chip` are typed into the design but the components don't exist yet. See `shared/components/organisms/README.md` for the up-to-date built-vs-planned list, and `features/board/README.md` for the explicit scope note that this pass is desktop-canvas-only.
