#!/usr/bin/env node
// Two-client, no-browser proof that the board's real-time sync actually
// works end-to-end — not just that the code compiles against Liveblocks'
// types. Opens two independent @liveblocks/client connections (as two
// different participants, same room) and proves each of storage's three
// pieces crosses the wire: a note created by A appears for B, a vote cast
// by B appears for A, a phase advanced by A appears for B. Same rigor as
// the Postgres restart-proof test in apps/api — verifying the codebase's
// actual claims instead of trusting that "the code looks right."
//
// Requires apps/api running with a REAL LIVEBLOCKS_SECRET_KEY (see
// .env.example) — this exercises the real backend auth handshake
// (routes/liveblocks_auth.py), not a Liveblocks key directly, so it
// proves the whole path production actually uses.
//
// Usage:
//   cd apps/api && source .venv/bin/activate
//   LIVEBLOCKS_SECRET_KEY=sk_... uvicorn main:app &
//   cd apps/web && node scripts/verify-board-sync.mjs
//
// Needs Node >= 22 (native fetch + WebSocket, no polyfills passed here).

import { createClient, LiveList, LiveObject, LiveMap } from "@liveblocks/client";

const API_URL = process.env.VITE_API_URL ?? "http://127.0.0.1:8000";
const ROOM = `verify-${Date.now()}`;

function makeClient(participantName) {
  return createClient({
    authEndpoint: async (room) => {
      const res = await fetch(`${API_URL}/api/liveblocks/auth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room, participant_name: participantName }),
      });
      const data = await res.json();
      if (!data.configured) {
        return { error: "forbidden", reason: "backend has no LIVEBLOCKS_SECRET_KEY set" };
      }
      return { token: data.token };
    },
  });
}

async function waitUntil(label, predicate, { timeoutMs = 10_000, intervalMs = 150 } = {}) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (predicate()) {
      console.log(`[ok] ${label}`);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(`[FAIL] timed out waiting for: ${label}`);
}

async function main() {
  const clientA = makeClient("Alice");
  const clientB = makeClient("Bob");

  const { room: roomA, leave: leaveA } = clientA.enterRoom(ROOM, {
    initialPresence: { name: "Alice", cursor: null },
    initialStorage: { notes: new LiveList([]), votes: new LiveMap(), phaseIndex: new LiveObject({ value: 0 }) },
  });
  const { room: roomB, leave: leaveB } = clientB.enterRoom(ROOM, {
    initialPresence: { name: "Bob", cursor: null },
  });

  try {
    const { root: rootA } = await roomA.getStorage();
    const { root: rootB } = await roomB.getStorage();
    console.log(`[ok] both clients connected to room ${ROOM}`);

    // A creates a note -> B must observe it.
    const noteId = "verify-note-1";
    rootA.get("notes").push(new LiveObject({ id: noteId, author: "Alice", text: "sync check", x: 0, y: 0 }));
    await waitUntil("B sees the note Alice created", () =>
      (roomB.getStorageSnapshot()?.get("notes").toArray() ?? []).some((n) => n.get("id") === noteId)
    );

    // B votes for it -> A must observe it (ADR-0004: own-entry LiveMap).
    rootB.get("votes").set("Bob", new LiveList([noteId]));
    await waitUntil(
      "A sees Bob's vote",
      () => (roomA.getStorageSnapshot()?.get("votes").get("Bob")?.toArray() ?? []).includes(noteId)
    );

    // A advances the phase -> B must observe it.
    rootA.get("phaseIndex").set("value", 1);
    await waitUntil(
      "B sees the phase Alice advanced",
      () => roomB.getStorageSnapshot()?.get("phaseIndex").get("value") === 1
    );

    console.log("\nAll board sync checks passed.");
  } finally {
    leaveA();
    leaveB();
  }
}

main().catch((err) => {
  console.error(err.message ?? err);
  process.exit(1);
});
