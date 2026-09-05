// Shown once a session's phase is "closed" — pulls the consolidated
// groups + action items from GET /sessions/{id}/summary (populated by
// agents/consolidator.py on close) rather than re-deriving anything from
// Liveblocks, which the board has already disconnected from by then.
import { useEffect, useState, type FormEvent } from "react";
import {
  api,
  ApiError,
  type IntegrationProvider,
  type Session,
  type SessionSummary,
} from "../../shared/api/client";
import { DynamicWatermark } from "../../shared/components/atoms/DynamicWatermark";

function describeError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Unexpected error";
}

export function SessionSummaryScreen({ session }: { session: Session }) {
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Jira/Azure DevOps only need a project key from the UI — the actual
  // credentials (JIRA_API_TOKEN, AZURE_DEVOPS_PAT, ...) live server-side as
  // env vars (see apps/api/config.py), shared by the whole deployment.
  const [provider, setProvider] = useState<IntegrationProvider>("jira");
  const [projectKey, setProjectKey] = useState("");
  const [connectingIntegration, setConnectingIntegration] = useState(false);
  const [integrationMessage, setIntegrationMessage] = useState<string | null>(null);

  const [creatingActionItemFor, setCreatingActionItemFor] = useState<string | null>(null);
  const [exportingId, setExportingId] = useState<string | null>(null);
  const [exportingAll, setExportingAll] = useState(false);
  const [exportMessages, setExportMessages] = useState<Record<string, string>>({});

  function refreshSummary() {
    return api.getSessionSummary(session.id).then(setSummary);
  }

  useEffect(() => {
    refreshSummary().catch((err) => setError(describeError(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.id]);

  async function handleConnectIntegration(event: FormEvent) {
    event.preventDefault();
    setIntegrationMessage(null);
    setConnectingIntegration(true);
    try {
      await api.connectIntegration(session.team_id, provider, projectKey);
      setIntegrationMessage(`Connected to ${provider === "jira" ? "Jira" : "Azure DevOps"} project "${projectKey}".`);
    } catch (err) {
      setIntegrationMessage(describeError(err));
    } finally {
      setConnectingIntegration(false);
    }
  }

  async function handleCreateActionItem(groupId: string, title: string) {
    setCreatingActionItemFor(groupId);
    setError(null);
    try {
      await api.createActionItem(session.id, groupId, title, title);
      await refreshSummary();
    } catch (err) {
      setError(describeError(err));
    } finally {
      setCreatingActionItemFor(null);
    }
  }

  async function handleExport(actionItemIds: string[], busyKey: string) {
    if (busyKey === "*") setExportingAll(true);
    else setExportingId(busyKey);
    setError(null);
    try {
      const { results } = await api.exportActionItems(session.id, actionItemIds);
      setExportMessages((prev) => {
        const next = { ...prev };
        for (const result of results) {
          next[result.action_item_id] =
            result.status === "created"
              ? `Exported — ${result.external_ref}`
              : result.status === "skipped"
                ? "Already exported"
                : `Failed: ${result.detail}`;
        }
        return next;
      });
      await refreshSummary();
    } catch (err) {
      setError(describeError(err));
    } finally {
      setExportingAll(false);
      setExportingId(null);
    }
  }

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
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => void handleCreateActionItem(group.id, group.text || group.label)}
                          disabled={creatingActionItemFor === group.id}
                        >
                          {creatingActionItemFor === group.id ? "Adding…" : "+ Action item"}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}

            <h3>Action items</h3>
            {summary.action_items.length === 0 ? (
              <p className="meta">
                No action items yet — click "+ Action item" on a note above to add one.
              </p>
            ) : (
              <>
                <ul className="action-item-list">
                  {summary.action_items.map((item) => (
                    <li key={item.id}>
                      <strong>{item.title}</strong>
                      {item.assignee && <span className="meta"> — {item.assignee}</span>}{" "}
                      {item.exported ? (
                        <span className="meta">— exported ({item.external_ref})</span>
                      ) : (
                        <button
                          type="button"
                          className="secondary icon-btn"
                          onClick={() => void handleExport([item.id], item.id)}
                          disabled={exportingId === item.id || exportingAll}
                        >
                          {exportingId === item.id ? "Exporting…" : "Export"}
                        </button>
                      )}
                      {exportMessages[item.id] && <p className="meta">{exportMessages[item.id]}</p>}
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={() => void handleExport([], "*")}
                  disabled={exportingAll || summary.action_items.every((item) => item.exported)}
                >
                  {exportingAll ? "Exporting all…" : "Export all pending"}
                </button>
              </>
            )}

            <h3>Connect Jira / Azure DevOps</h3>
            <form className="field-row" onSubmit={(event) => void handleConnectIntegration(event)}>
              <select
                className="phase-select"
                value={provider}
                onChange={(event) => setProvider(event.target.value as IntegrationProvider)}
              >
                <option value="jira">Jira</option>
                <option value="azure_devops">Azure DevOps</option>
              </select>
              <input
                value={projectKey}
                onChange={(event) => setProjectKey(event.target.value)}
                placeholder="Project key (e.g. RETRO)"
                required
              />
              <button type="submit" className="secondary" disabled={connectingIntegration}>
                {connectingIntegration ? "Connecting…" : "Connect"}
              </button>
            </form>
            {integrationMessage && <p className="meta">{integrationMessage}</p>}
          </div>
        </div>
      )}
    </section>
  );
}
