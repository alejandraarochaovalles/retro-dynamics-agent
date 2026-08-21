// `canvas` variant only for now — `list`/`chip` (mobile, ADR-0006) are a
// follow-up pass, see features/board/README.md.
//
// Position is fully controlled by the parent (x/y props, sourced from
// Liveblocks storage) rather than kept as local drag state: onMove fires
// on every pointermove while dragging, not just on release, so the note's
// position updates storage — and therefore every other participant's
// screen — continuously during the drag. That's the actual point of
// picking Liveblocks over last-write-wins sync (ADR-0002).
import { useRef, type PointerEvent as ReactPointerEvent } from "react";

export type StickyNoteProps = {
  id: string;
  author: string;
  text: string;
  x: number;
  y: number;
  phase: string;
  voteCount: number;
  hasVoted: boolean;
  variant: "canvas";
  onMove: (id: string, x: number, y: number) => void;
  onToggleVote: (id: string) => void;
};

export function StickyNote({
  id,
  author,
  text,
  x,
  y,
  phase,
  voteCount,
  hasVoted,
  onMove,
  onToggleVote,
}: StickyNoteProps) {
  // Pointer position minus note position at drag start, so the note
  // doesn't jump to re-center under the cursor on the first move.
  const dragOffset = useRef<{ dx: number; dy: number } | null>(null);

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragOffset.current = { dx: event.clientX - x, dy: event.clientY - y };
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    if (!dragOffset.current) return;
    onMove(id, event.clientX - dragOffset.current.dx, event.clientY - dragOffset.current.dy);
  }

  function handlePointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    event.currentTarget.releasePointerCapture(event.pointerId);
    dragOffset.current = null;
  }

  return (
    <div
      className="sticky-note"
      style={{ left: x, top: y }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      <span className="note-phase-tag">{phase}</span>
      <p>{text}</p>
      <div className="sticky-footer">
        <span>{author}</span>
        <button
          type="button"
          className="icon-btn"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={() => onToggleVote(id)}
          aria-pressed={hasVoted}
        >
          {hasVoted ? "★" : "☆"} {voteCount}
        </button>
      </div>
    </div>
  );
}
