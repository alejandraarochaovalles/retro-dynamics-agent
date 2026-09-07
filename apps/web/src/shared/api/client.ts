// Thin fetch wrapper over apps/api. Types mirror apps/api/models.py — keep
// them in sync until packages/contracts/openapi.yaml formalizes
// components.schemas and codegen can take over.
export type Team = {
  id: string;
  name: string;
  integration: Record<string, unknown> | null;
  created_at: string;
};

export type SessionPhase = "lobby" | "active" | "consolidation" | "closed";

export type DynamicProposal = {
  name: string;
  description: string;
  phases: string[];
  icon: string;
  phase_descriptions: Record<string, string>;
};

export type Session = {
  id: string;
  team_id: string;
  title: string;
  join_code: string;
  phase: SessionPhase;
  dynamic: DynamicProposal | null;
  created_at: string;
  closed_at: string | null;
  created_by: string | null;
};

export type NoteInput = {
  id?: string;
  author: string;
  text: string;
  x: number;
  y: number;
  votes: number;
  phase: string;
};

export type Group = {
  id: string;
  label: string;
  note_ids: string[];
  votes: number;
  author: string;
  text: string;
  phase: string;
};

export type ActionItem = {
  id: string;
  group_id: string;
  title: string;
  description: string;
  assignee: string | null;
  exported: boolean;
  external_ref: string | null;
};

export type SessionSummary = {
  session_id: string;
  title: string;
  phase: SessionPhase;
  groups: Group[];
  action_items: ActionItem[];
};

export type IntegrationProvider = "jira" | "azure_devops";

export type ExportResult = {
  action_item_id: string;
  status: "created" | "skipped" | "failed";
  external_ref: string | null;
  detail: string | null;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, `Could not reach the API at ${API_URL} — is uvicorn running?`);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.detail ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  createTeam: (name: string) =>
    request<Team>("/api/teams", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  createSession: (teamId: string, title: string, createdBy: string, dynamic?: DynamicProposal) =>
    request<Session>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({
        team_id: teamId,
        title,
        dynamic: dynamic ?? null,
        created_by: createdBy,
      }),
    }),

  getSession: (id: string) => request<Session>(`/api/sessions/${id}`),

  startSession: (id: string, participantName: string) =>
    request<Session>(`/api/sessions/${id}/start`, {
      method: "POST",
      body: JSON.stringify({ participant_name: participantName }),
    }),

  joinSession: (joinCode: string, participantName: string) =>
    request<Session>("/api/sessions/join", {
      method: "POST",
      body: JSON.stringify({ join_code: joinCode, participant_name: participantName }),
    }),

  closeSession: (id: string, notes: NoteInput[], participantName: string) =>
    request<Session>(`/api/sessions/${id}/close`, {
      method: "POST",
      body: JSON.stringify({ notes, participant_name: participantName }),
    }),

  getSessionSummary: (id: string) => request<SessionSummary>(`/api/sessions/${id}/summary`),

  generateDynamics: (context: string, count = 3) =>
    request<{ proposals: DynamicProposal[]; source: "groq" | "fallback" }>(
      "/api/dynamics/generate",
      { method: "POST", body: JSON.stringify({ context, count }) }
    ),

  liveblocksAuth: (room: string, participantName: string) =>
    request<{ token: string; configured: boolean }>("/api/liveblocks/auth", {
      method: "POST",
      body: JSON.stringify({ room, participant_name: participantName }),
    }),

  connectIntegration: (teamId: string, provider: IntegrationProvider, projectKey: string) =>
    request<Team>(`/api/teams/${teamId}/integration`, {
      method: "POST",
      body: JSON.stringify({ provider, config: { project_key: projectKey } }),
    }),

  createActionItem: (sessionId: string, groupId: string, title: string, description = "") =>
    request<ActionItem>(`/api/sessions/${sessionId}/action-items`, {
      method: "POST",
      body: JSON.stringify({ group_id: groupId, title, description }),
    }),

  // Empty actionItemIds exports every not-yet-exported action item in the session.
  exportActionItems: (sessionId: string, actionItemIds: string[] = []) =>
    request<{ results: ExportResult[] }>(`/api/sessions/${sessionId}/export`, {
      method: "POST",
      body: JSON.stringify({ action_item_ids: actionItemIds }),
    }),

  // Not a fetch — the browser must navigate here so Atlassian's own consent
  // screen can render (see apps/api/routes/jira_oauth.py). session_id rides
  // along in the signed `state` param and comes back in the callback
  // redirect, since the frontend has no persistence of its own.
  jiraConnectUrl: (teamId: string, sessionId: string, projectKey: string) => {
    const params = new URLSearchParams({
      team_id: teamId,
      session_id: sessionId,
      project_key: projectKey,
    });
    return `${API_URL}/api/integrations/jira/connect?${params.toString()}`;
  },
};
