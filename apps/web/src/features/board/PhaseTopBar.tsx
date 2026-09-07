import { useMutation, useOthers, useStorage, useSyncStatus } from "@liveblocks/react/suspense";
import { useEffect, useRef, useState } from "react";
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
  // Storage (not Presence) so it's durable and reaches everyone, including
  // participants who reconnect right as the facilitator closes — flipped by
  // handleClose below once the backend confirms the close.
  const closedFlag = useStorage((root) => root.closed?.value) ?? false;
  const syncStatus = useSyncStatus();

  const markClosed = useMutation(({ storage }) => {
    storage.get("closed").set("value", true);
  }, []);

  const lastIndex = dynamic.phases.length - 1;
  const isFirstPhase = phaseIndex <= 0;
  const isLastPhase = phaseIndex >= lastIndex;
  const currentPhase = dynamic.phases[phaseIndex];
  const explanation =
    dynamic.phase_descriptions?.[currentPhase] ?? "No explanation was generated for this phase.";
  // Legacy sessions (created before created_by existed) stay open to
  // anyone closing them — same fallback as the backend's _ensure_creator.
  const canClose = !createdBy || participantName === createdBy;

  // Only the facilitator gets `closed` back directly from api.closeSession
  // in handleClose. Everyone else has no other signal that the session
  // closed server-side, so they pick it up here and fetch the now-closed
  // session themselves to move to the summary screen.
  const handledRemoteClose = useRef(false);
  useEffect(() => {
    if (!closedFlag || canClose || handledRemoteClose.current) return;
    handledRemoteClose.current = true;
    api
      .getSession(sessionId)
      .then(onClosed)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load the closed session"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [closedFlag]);

  // markClosed() above sends its storage write over Liveblocks' async
  // connection — calling onClosed(closed) right away would unmount this
  // component (BoardScreen only renders while session.phase === "active"),
  // tearing down the room and risking the write never reaching the server
  // before the socket closes, so other participants' closedFlag never flips.
  // Wait for useSyncStatus to confirm the write went through; the timeout
  // is a safety net (backend close already succeeded either way) in case
  // sync never settles, e.g. a flaky connection.
  const pendingCloseRef = useRef<Session | null>(null);
  const closeTimeoutRef = useRef<number | null>(null);

  function finalizeClose(closed: Session) {
    if (!pendingCloseRef.current) return;
    if (closeTimeoutRef.current !== null) {
      window.clearTimeout(closeTimeoutRef.current);
      closeTimeoutRef.current = null;
    }
    pendingCloseRef.current = null;
    onClosed(closed);
  }

  useEffect(() => {
    if (pendingCloseRef.current && syncStatus === "synchronized") {
      finalizeClose(pendingCloseRef.current);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [syncStatus]);

  useEffect(() => {
    return () => {
      if (closeTimeoutRef.current !== null) window.clearTimeout(closeTimeoutRef.current);
    };
  }, []);

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
      markClosed();
      pendingCloseRef.current = closed;
      closeTimeoutRef.current = window.setTimeout(() => finalizeClose(closed), 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not close the session");
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
