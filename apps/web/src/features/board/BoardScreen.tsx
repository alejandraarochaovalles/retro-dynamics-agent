import { LiveList, LiveMap, LiveObject } from "@liveblocks/client";
import { ClientSideSuspense, LiveblocksProvider, RoomProvider, useStatus } from "@liveblocks/react/suspense";
import { useMemo } from "react";
import type { DynamicProposal, Session } from "../../shared/api/client";
import { Canvas } from "./Canvas";
import { makeAuthEndpoint, roomIdForSession } from "./liveblocksClient";
import { PhaseTopBar } from "./PhaseTopBar";
// Type-only, but still needed at compile time: this is what pulls
// types.ts's `declare global { interface Liveblocks {...} } }` into the
// program so every Liveblocks hook (here and in Canvas/PhaseTopBar) is
// typed against BoardPresence/BoardStorage without per-call generics.
import type { BoardPresence, BoardStorage } from "./types";

// Sessions created before the dynamics-generation step existed (or if
// generateDynamics ever fails) may have no `dynamic` — fall back rather
// than leaving the board with no phases to step through.
const FALLBACK_DYNAMIC: DynamicProposal = {
  name: "Start / Stop / Continue",
  description: "Fallback dynamic — no dynamic was attached to this session.",
  phases: ["start", "stop", "continue", "vote"],
  icon: "🧭",
  phase_descriptions: {
    start: "As a team, write things you should start doing.",
    stop: "As a team, write things you should stop doing.",
    continue: "As a team, write things that are working and should continue.",
    vote: "As a team, vote for the notes that matter most — everyone gets to pick their top ones.",
  },
};

// Shown while the Liveblocks room is still connecting/loading storage.
// Corporate networks and VPNs commonly block the WebSocket connection
// Liveblocks needs (proxies like Zscaler/Blue Coat terminate or drop
// `wss://` traffic), which otherwise leaves the user staring at "Connecting…"
// forever with no indication of what's wrong. useStatus() reads the room's
// connection state so we can tell them what's actually happening instead.
function ConnectingFallback() {
  const status = useStatus();

  if (status === "disconnected" || status === "reconnecting") {
    return (
      <p className="alert" role="alert">
        No pudimos conectar al tablero en tiempo real (estado: {status}). Esto
        suele pasar en redes corporativas o VPNs que bloquean conexiones
        WebSocket — probá con datos móviles u otra red antes de reportarlo
        como un error de la app.
      </p>
    );
  }

  return <p>Connecting to the board…</p>;
}

export function BoardScreen({
  session,
  participantName,
  onSessionClosed,
}: {
  session: Session;
  participantName: string;
  onSessionClosed: (session: Session) => void;
}) {
  const dynamic = session.dynamic ?? FALLBACK_DYNAMIC;

  // Memoized so LiveblocksProvider doesn't see a new `authEndpoint`
  // function identity (and reconnect) on every render.
  const authEndpoint = useMemo(() => makeAuthEndpoint(participantName), [participantName]);

  return (
    <LiveblocksProvider authEndpoint={authEndpoint}>
      <RoomProvider
        id={roomIdForSession(session.id)}
        initialPresence={{ name: participantName, cursor: null } satisfies BoardPresence}
        initialStorage={
          {
            notes: new LiveList([]),
            votes: new LiveMap(),
            phaseIndex: new LiveObject({ value: 0 }),
          } satisfies BoardStorage
        }
      >
        <ClientSideSuspense fallback={<ConnectingFallback />}>
          <PhaseTopBar
            sessionId={session.id}
            dynamic={dynamic}
            participantName={participantName}
            createdBy={session.created_by}
            onClosed={onSessionClosed}
          />
          <Canvas participantName={participantName} dynamic={dynamic} />
        </ClientSideSuspense>
      </RoomProvider>
    </LiveblocksProvider>
  );
}
