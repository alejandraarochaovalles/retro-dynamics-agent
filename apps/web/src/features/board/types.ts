// Liveblocks Presence (ephemeral) and Storage (durable, CRDT) shapes for
// the board room. See docs/adr/0002 and docs/adr/0004 for the reasoning
// (Liveblocks over Supabase Realtime; votes as a LiveMap keyed by
// participant so each person only ever writes their own entry).
import type { LiveList, LiveMap, LiveObject } from "@liveblocks/client";

export type NoteData = {
  id: string;
  author: string;
  text: string;
  x: number;
  y: number;
  // Which phase (a DynamicProposal.phases id) this note was written during
  // — stamped once at creation in Canvas.tsx's addNote, from the phase
  // that's current at that moment (not live-updated if the board moves on).
  phase: string;
};

export type BoardPresence = {
  name: string;
  cursor: { x: number; y: number } | null;
};

export type BoardStorage = {
  notes: LiveList<LiveObject<NoteData>>;
  votes: LiveMap<string, LiveList<string>>;
  phaseIndex: LiveObject<{ value: number }>;
};

// Declaration merging into Liveblocks' own `Liveblocks` interface (see
// @liveblocks/core's ExtendableTypes/DP/DS) — this is what makes every
// generic hook (useStorage, useMutation, useMyPresence, useOthers,
// RoomProvider) type-check against BoardPresence/BoardStorage app-wide,
// without passing generics at every call site.
declare global {
  interface Liveblocks {
    Presence: BoardPresence;
    Storage: BoardStorage;
  }
}
