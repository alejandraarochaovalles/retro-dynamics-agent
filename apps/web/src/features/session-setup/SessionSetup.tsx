import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type DynamicProposal, type Session, type Team } from "../../shared/api/client";
import { BoardScreen } from "../board/BoardScreen";
import { SessionSummaryScreen } from "../summary/SessionSummaryScreen";

type BackendStatus = "checking" | "online" | "offline";

function describeError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Unexpected error";
}

export function SessionSetup() {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [participantName, setParticipantName] = useState("");
  const [team, setTeam] = useState<Team | null>(null);
  const [teamName, setTeamName] = useState("");
  const [sessionTitle, setSessionTitle] = useState("");
  const [session, setSession] = useState<Session | null>(null);
  const [joinCode, setJoinCode] = useState("");
  const [proposals, setProposals] = useState<DynamicProposal[] | null>(null);
  const [generatingProposals, setGeneratingProposals] = useState(false);
  const [creatingSession, setCreatingSession] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then(() => setBackendStatus("online"))
      .catch(() => setBackendStatus("offline"));
  }, []);

  async function handleCreateTeam(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      setTeam(await api.createTeam(teamName));
    } catch (err) {
      setError(describeError(err));
    }
  }

  // Generates candidate dynamics without creating a session yet — the
  // creator picks one in handleChooseDynamic below. Split out of the form
  // handler so "show different dynamics" can call it directly too.
  async function generateProposals() {
    if (!team) return;
    setError(null);
    setGeneratingProposals(true);
    try {
      const context = `${sessionTitle || "general retro"} — team: ${team.name}`;
      const { proposals } = await api.generateDynamics(context);
      setProposals(proposals);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setGeneratingProposals(false);
    }
  }

  function handleGenerateProposals(event: FormEvent) {
    event.preventDefault();
    void generateProposals();
  }

  async function handleChooseDynamic(dynamic: DynamicProposal) {
    if (!team || !participantName) return;
    setError(null);
    setCreatingSession(true);
    try {
      setSession(await api.createSession(team.id, sessionTitle, participantName, dynamic));
    } catch (err) {
      setError(describeError(err));
    } finally {
      setCreatingSession(false);
    }
  }

  async function handleJoinSession(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      setSession(await api.joinSession(joinCode, participantName));
    } catch (err) {
      setError(describeError(err));
    }
  }

  async function handleStartSession() {
    if (!session) return;
    setError(null);
    try {
      setSession(await api.startSession(session.id, participantName));
    } catch (err) {
      setError(describeError(err));
    }
  }

  if (session?.phase === "active") {
    return (
      <BoardScreen session={session} participantName={participantName} onSessionClosed={setSession} />
    );
  }

  if (session?.phase === "closed") {
    return <SessionSummaryScreen session={session} />;
  }

  return (
    <section className="stack">
      <p>
        <span className={`badge ${backendStatus}`}>Backend {backendStatus}</span>
        {backendStatus === "offline" && (
          <span className="meta"> — start it with `uvicorn main:app --reload` in apps/api</span>
        )}
      </p>

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}

      {!session && (
        <div className="card">
          <input
            value={participantName}
            onChange={(event) => setParticipantName(event.target.value)}
            placeholder="Your name"
            required
          />
        </div>
      )}

      {session ? (
        <div className="card">
          <h2>
            {session.dynamic && (
              <span className="dynamic-icon inline" aria-hidden="true">
                {session.dynamic.icon}
              </span>
            )}
            {session.title}
          </h2>
          <p className="join-code">
            Join code: <code>{session.join_code}</code>
          </p>
          <p className="meta">Phase: {session.phase}</p>
          {session.phase === "lobby" &&
            (!session.created_by || participantName === session.created_by ? (
              <button type="button" onClick={handleStartSession}>
                Start session
              </button>
            ) : (
              <p className="meta">Waiting for {session.created_by} to start the session…</p>
            ))}
        </div>
      ) : (
        <>
          {!team ? (
            <form className="card" onSubmit={handleCreateTeam}>
              <h2>Create a team</h2>
              <input
                value={teamName}
                onChange={(event) => setTeamName(event.target.value)}
                placeholder="Team name"
                required
              />
              <button type="submit" disabled={backendStatus !== "online"}>
                Create team
              </button>
            </form>
          ) : !proposals ? (
            <form className="card" onSubmit={handleGenerateProposals}>
              <h2>Start a retro for {team.name}</h2>
              <input
                value={sessionTitle}
                onChange={(event) => setSessionTitle(event.target.value)}
                placeholder="Session title"
                required
              />
              <button type="submit" disabled={generatingProposals}>
                {generatingProposals ? "Generating dynamics…" : "Generate dynamics"}
              </button>
            </form>
          ) : (
            <div className="card">
              <h2>Pick a dynamic{sessionTitle && ` for "${sessionTitle}"`}</h2>
              <div className="dynamic-options">
                {proposals.map((proposal) => (
                  <div key={proposal.name} className="dynamic-option">
                    <span className="dynamic-icon" aria-hidden="true">
                      {proposal.icon}
                    </span>
                    <h3>{proposal.name}</h3>
                    <p className="meta">{proposal.description}</p>
                    <p className="meta">Phases: {proposal.phases.join(" → ")}</p>
                    <button
                      type="button"
                      onClick={() => handleChooseDynamic(proposal)}
                      disabled={creatingSession || !participantName}
                    >
                      {creatingSession ? "Creating…" : "Use this dynamic"}
                    </button>
                  </div>
                ))}
              </div>
              <button
                type="button"
                className="secondary"
                onClick={() => void generateProposals()}
                disabled={generatingProposals}
              >
                {generatingProposals ? "Generating…" : "Show different dynamics"}
              </button>
            </div>
          )}

          <form className="card" onSubmit={handleJoinSession}>
            <h2>Or join an existing session</h2>
            <input
              value={joinCode}
              onChange={(event) => setJoinCode(event.target.value.toUpperCase())}
              placeholder="Join code"
              required
            />
            <button
              type="submit"
              className="secondary"
              disabled={backendStatus !== "online" || !participantName}
            >
              Join
            </button>
          </form>
        </>
      )}
    </section>
  );
}
