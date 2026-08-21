import { useMutation, useMyPresence, useOthers, useStorage } from "@liveblocks/react/suspense";
import { LiveList, LiveObject } from "@liveblocks/client";
import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { DynamicProposal } from "../../shared/api/client";
import { DynamicWatermark } from "../../shared/components/atoms/DynamicWatermark";
import { StickyNote } from "../../shared/components/organisms/StickyNote";
import { countVotes, hasVoted } from "./votes";

export function Canvas({
  participantName,
  dynamic,
}: {
  participantName: string;
  dynamic: DynamicProposal;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [draftText, setDraftText] = useState("");

  const notes = useStorage((root) => root.notes) ?? [];
  const votesMap = useStorage((root) => root.votes);
  const phaseIndex = useStorage((root) => root.phaseIndex.value) ?? 0;
  const [, updateMyPresence] = useMyPresence();
  const others = useOthers();

  // Whatever phase is current *right now*, for everyone in the room.
  const currentPhase = dynamic.phases[phaseIndex] ?? "unknown";

  // Which phase a *new* note gets stamped with — defaults to "now", but a
  // participant who's still catching up (someone else already advanced the
  // shared phaseIndex past where they are) can pick an earlier one instead
  // of silently getting their note mis-attributed to the current phase.
  // Only phases already visited (index <= phaseIndex) are offered — you
  // can't write a note for a phase that hasn't happened yet.
  const visitedPhases = dynamic.phases.slice(0, phaseIndex + 1);
  const [notePhase, setNotePhase] = useState(currentPhase);
  // Adjusted during render (React's documented pattern for state that
  // should reset when a prop/derived value changes — see
  // https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes)
  // rather than in a useEffect, which would commit the stale value for one
  // extra render first: snap back to "now" whenever the shared phase
  // advances, so an earlier pick only sticks until the next phase change.
  const [lastSeenPhase, setLastSeenPhase] = useState(currentPhase);
  if (currentPhase !== lastSeenPhase) {
    setLastSeenPhase(currentPhase);
    setNotePhase(currentPhase);
  }

  // useStorage's LiveMap read is a ReadonlyMap (see @liveblocks/core's
  // ToImmutable) — votes.ts's pure helpers take a plain Record, so it's
  // testable without any Liveblocks types.
  const votesByParticipant = Object.fromEntries(votesMap?.entries() ?? []) as Record<
    string,
    string[]
  >;

  const addNote = useMutation(({ storage }, text: string, phase: string) => {
    storage.get("notes").push(
      new LiveObject({
        id: crypto.randomUUID(),
        author: participantName,
        text,
        x: 40 + Math.random() * 200,
        y: 40 + Math.random() * 120,
        phase,
      })
    );
  }, [participantName]);

  // Fires on every pointermove during a drag, not just on release — see
  // StickyNote.tsx's comment on why that matters for this app.
  const moveNote = useMutation(({ storage }, id: string, x: number, y: number) => {
    const list = storage.get("notes");
    const index = list.findIndex((note) => note.get("id") === id);
    if (index !== -1) list.get(index)!.update({ x, y });
  }, []);

  const toggleNoteVote = useMutation(({ storage, self }, noteId: string) => {
    const votes = storage.get("votes");
    const participant = self.presence.name;
    const current = votes.get(participant)?.toArray() ?? [];
    const next = current.includes(noteId)
      ? current.filter((id) => id !== noteId)
      : [...current, noteId];
    votes.set(participant, new LiveList(next));
  }, []);

  function handleAddNote() {
    if (!draftText.trim()) return;
    addNote(draftText.trim(), notePhase);
    setDraftText("");
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const bounds = containerRef.current?.getBoundingClientRect();
    if (!bounds) return;
    updateMyPresence({
      cursor: { x: event.clientX - bounds.left, y: event.clientY - bounds.top },
    });
  }

  return (
    <div>
      <div className="composer">
        {visitedPhases.length > 1 && (
          <select
            className="phase-select"
            value={notePhase}
            onChange={(e) => setNotePhase(e.target.value)}
            aria-label="Which phase this note is for"
          >
            {visitedPhases.map((phase) => (
              <option key={phase} value={phase}>
                {phase}
                {phase === currentPhase ? " (now)" : ""}
              </option>
            ))}
          </select>
        )}
        <input
          value={draftText}
          onChange={(e) => setDraftText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAddNote()}
          placeholder="Write a note and press Enter"
        />
        <button type="button" onClick={handleAddNote}>
          Add note
        </button>
      </div>

      <div
        ref={containerRef}
        onPointerMove={handlePointerMove}
        onPointerLeave={() => updateMyPresence({ cursor: null })}
        className="board-surface"
      >
        <DynamicWatermark icon={dynamic.icon} />

        {notes.map((note) => (
          <StickyNote
            key={note.id}
            id={note.id}
            author={note.author}
            text={note.text}
            x={note.x}
            y={note.y}
            phase={note.phase}
            variant="canvas"
            voteCount={countVotes(votesByParticipant, note.id)}
            hasVoted={hasVoted(votesByParticipant, participantName, note.id)}
            onMove={moveNote}
            onToggleVote={toggleNoteVote}
          />
        ))}

        {others.map(
          (other) =>
            other.presence.cursor && (
              <div
                key={other.connectionId}
                className="cursor-flag"
                style={{ left: other.presence.cursor.x, top: other.presence.cursor.y }}
              >
                ▲ {other.presence.name}
              </div>
            )
        )}
      </div>
    </div>
  );
}
