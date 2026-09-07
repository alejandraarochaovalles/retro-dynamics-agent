import { useMutation, useOthers, useStorage } from "@liveblocks/react/suspense";
import { useState } from "react";
import { api, type DynamicProposal, type NoteInput, type Session } from "../../shared/api/client";
import { countVotes } from "./votes";

// Per your call: anyone in the session can advance phases — no
// facilitator/role concept to build. phaseIndex lives in Storage (not
// Presence) so it's durable across everyone disconnecting and back.
export function PhaseTopBar({
  sessionId,
  dynamic,
  participantName,
  createdBy,
  joinCode,
  onClosed,
}: {
  sessionId: string;
  dynamic: DynamicProposal;
  participantName: string;
  createdBy: string | null;
  joinCode: string;
  onClosed: (session: Session) => void;
}) {
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const phaseIndex = useStorage((root) => root.phaseIndex.value) ?? 0;
  const notes = useStorage((root) => root.notes) ?? [];
  const votesMap = useStorage((root) => root.votes);
  const others = useOthers();

  const lastIndex = dynamic.phases.length - 1;
  const isFirstPhase = phaseIndex <= 0;
  const isLastPhase = phaseIndex >= lastIndex;
  const currentPhase = dynamic.phases[phaseIndex];
  const explanation =
    dynamic.phase_descriptions?.[currentPhase] ?? "No explanation was generated for this phase.";
  // Legacy sessions (created before created_by existed) stay open to
  // anyone closing them — same fallback as the backend's _ensure_creator.
  const canClose = !createdBy || participantName === createdBy;

  const advancePhase = useMutation(({ storage }) => {
    const phase = storage.get("phaseIndex");
    const next = Math.min(phase.get("value") + 1, dynamic.phases.length - 1);
    phase.set("value", next);
  }, [dynamic.phases.length]);

  // Anyone can also step back — same "no facilitator role" call as
  // advancePhase above (phaseIndex lives in shared Storage either way).
  const goBackPhase = useMutation(({ storage }) => {
    const phase = storage.get("phaseIndex");
    const prev = Math.max(phase.get("value") - 1, 0);
    phase.set("value", prev);
  }, []);

  async function handleClose() {
    setClosing(true);
    setError(null);
    try {
      const votesByParticipant = Object.fromEntries(votesMap?.entries() ?? []) as Record<
        string,
        string[]
      >;
      const payload: NoteInput[] = notes.map((note) => ({
        id: note.id,
        author: note.author,
        text: note.text,
        x: note.x,
        y: note.y,
        votes: countVotes(votesByParticipant, note.id),
        phase: note.phase,
      }));
      const closed = await api.closeSession(sessionId, payload, participantName);
      onClosed(closed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not close the session");
    } finally {
      setClosing(false);
    }
  }

  return (
    <div className="phase-bar">
      <div className="phase-bar-row">
        <span className="dynamic-icon inline" aria-hidden="true">
          {dynamic.icon}
        </span>
        <span className="phase-name">{currentPhase}</span>
        <span className="meta">
          phase {phaseIndex + 1}/{dynamic.phases.length}
        </span>
        <span className="meta join-code">
          Join code: <code>{joinCode}</code>
        </span>
        <span className="meta">
          {others.length + 1} {others.length === 0 ? "person" : "people"} here
        </span>
        <div className="spacer">
          <button
            type="button"
            className="secondary"
            onClick={goBackPhase}
            disabled={isFirstPhase}
          >
            ← Back
          </button>
          {!isLastPhase && (
            <button type="button" onClick={advancePhase}>
              Next phase →
            </button>
          )}
          {isLastPhase && canClose && (
            <button type="button" onClick={handleClose} disabled={closing}>
              {closing ? "Closing…" : "Close session"}
            </button>
          )}
          {isLastPhase && !canClose && (
            <span className="meta">Waiting for {createdBy} to close the session…</span>
          )}
        </div>
      </div>
      <p className="phase-explanation">{explanation}</p>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
