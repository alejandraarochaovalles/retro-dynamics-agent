// Liveblocks auth wiring. Uses the function form of `authEndpoint`
// (see @liveblocks/core's ClientOptions) rather than a URL string,
// because our backend's /api/liveblocks/auth needs `participant_name` in
// the body — the URL-string form only ever POSTs `{ room }`. The callback
// receives just `room`, so participantName is captured via closure.
//
// Verified against the *installed* @liveblocks/core@2.24.4 type
// definitions (node_modules/@liveblocks/core/dist/index.d.ts): authEndpoint
// callback is `(room?: string) => Promise<{token: string} | {error, reason}>`.
import { api } from "../../shared/api/client";

export function makeAuthEndpoint(participantName: string) {
  return async (room?: string) => {
    if (!room) {
      return { error: "forbidden" as const, reason: "no room id provided" };
    }
    const result = await api.liveblocksAuth(room, participantName);
    if (!result.configured) {
      return {
        error: "forbidden" as const,
        reason: "LIVEBLOCKS_SECRET_KEY is not set on the backend",
      };
    }
    return { token: result.token };
  };
}

export function roomIdForSession(sessionId: string): string {
  return `session-${sessionId}`;
}
