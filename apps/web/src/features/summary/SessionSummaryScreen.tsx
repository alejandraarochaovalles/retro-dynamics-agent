// Shown once a session's phase is "closed" — pulls the consolidated
// groups + action items from GET /sessions/{id}/summary (populated by
// agents/consolidator.py on close) rather than re-deriving anything from
// Liveblocks, which the board has already disconnected from by then.
import { useEffect, useState } from "react";
import { api, ApiError, type Session, type SessionSummary } from "../../shared/api/client";
import { DynamicWatermark } from "../../shared/components/atoms/DynamicWatermark";

function describeError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Unexpected error";
}

export function SessionSummaryScreen({ session }: { session: Session }) {
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSessionSummary(session.id)
      .then(setSummary)
      .catch((err) => setError(describeError(err)));
  }, [session.id]);

  const groups = summary?.groups ?? [];

  // Divided by phase (the dynamic's own phase order first, then any phase
  // id that only shows up on notes — e.g. "unknown" for notes written
  // before this field existed), highest-voted first within each phase —
  // same ranking as GET /sessions/{id}/votes-summary
  // (agents/consolidator.py's rank_by_votes), just grouped here too.
  const dynamicPhases = session.dynamic?.phases ?? [];
  const notePhases = Array.from(new Set(groups.map((g) => g.phase)));
  const phaseOrder = [...dynamicPhases, ...notePhases.filter((p) => !dynamicPhases.includes(p))];
  const phaseSections = phaseOrder
    .map((phase) => ({
      phase,
      notes: groups.filter((g) => g.phase === phase).sort((a, b) => b.votes - a.votes),
    }))
    .filter((section) => section.notes.length > 0);

  return (
    <section className="stack">
      <div className="card">
        <h2>
          {session.dynamic && (
            <span className="dynamic-icon inline" aria-hidden="true">
              {session.dynamic.icon}
            </span>
          )}
          {session.title}
        </h2>
        <p className="meta">
          {session.dynamic?.name ?? "Retro"} — closed
          {session.closed_at && ` on ${new Date(session.closed_at).toLocaleString()}`}
        </p>
      </div>

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}

      {!summary && !error && <p className="meta">Loading summary…</p>}

      {summary && (
        <div className="card note-board">
          {session.dynamic && <DynamicWatermark icon={session.dynamic.icon} />}
          <div className="note-board-content">
            <h3>What the team put ({groups.length})</h3>
            {phaseSections.length === 0 ? (
              <p className="meta">No notes were added during this session.</p>
            ) : (
              phaseSections.map(({ phase, notes }) => (
                <div key={phase} className="phase-section">
                  <span className="phase-name">{phase}</span>
                  <div className="summary-grid">
                    {notes.map((group) => (
                      <div key={group.id} className="summary-note">
                        <p>{group.text || group.label}</p>
                        <div className="sticky-footer">
                          <span>{group.author}</span>
                          <span>★ {group.votes}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}

            {summary.action_items.length > 0 && (
              <>
                <h3>Action items</h3>
                <ul className="action-item-list">
                  {summary.action_items.map((item) => (
                    <li key={item.id}>
                      <strong>{item.title}</strong>
                      {item.assignee && <span className="meta"> — {item.assignee}</span>}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
