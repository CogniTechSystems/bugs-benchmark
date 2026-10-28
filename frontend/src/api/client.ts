import type {
  BugHunt,
  Deployment,
  DeploymentLog,
  DeploymentWrite,
  HubModel,
  JobDetail,
  JobSummary,
  LanguageModel,
  LeaderboardEntry,
  ModelDownloadRequest,
  RepositoryFile,
  Runtime,
  RuntimeWrite,
  SessionDetail,
  SessionSummary,
} from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
}

function describeError(body: unknown, fallback: string): string {
  if (typeof body !== "object" || body === null || !("detail" in body)) {
    return fallback;
  }
  const { detail } = body as { detail: unknown };
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return (detail as ValidationIssue[])
      .map((issue) => `${issue.loc.slice(1).join(".") || "request"}: ${issue.msg}`)
      .join("; ");
  }
  return fallback;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw new ApiError(response.status, describeError(payload, response.statusText));
  }
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function query(parameters: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(parameters)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  hub: {
    search: (searchText: string, limit = 25) =>
      request<HubModel[]>("GET", `/hub/search${query({ query: searchText, limit })}`),
    files: (repoId: string, revision: string) =>
      request<RepositoryFile[]>("GET", `/hub/files${query({ repo_id: repoId, revision })}`),
  },
  models: {
    list: () => request<LanguageModel[]>("GET", "/models"),
    download: (payload: ModelDownloadRequest) => request<LanguageModel>("POST", "/models", payload),
    files: (id: number) => request<RepositoryFile[]>("GET", `/models/${id}/files`),
    remove: (id: number) => request<undefined>("DELETE", `/models/${id}`),
  },
  runtimes: {
    list: () => request<Runtime[]>("GET", "/runtimes"),
    create: (payload: RuntimeWrite) => request<Runtime>("POST", "/runtimes", payload),
    update: (id: number, payload: RuntimeWrite) =>
      request<Runtime>("PUT", `/runtimes/${id}`, payload),
    remove: (id: number) => request<undefined>("DELETE", `/runtimes/${id}`),
  },
  deployments: {
    list: () => request<Deployment[]>("GET", "/deployments"),
    create: (payload: DeploymentWrite) => request<Deployment>("POST", "/deployments", payload),
    update: (id: number, payload: DeploymentWrite) =>
      request<Deployment>("PUT", `/deployments/${id}`, payload),
    remove: (id: number) => request<undefined>("DELETE", `/deployments/${id}`),
    start: (id: number) => request<Deployment>("POST", `/deployments/${id}/start`),
    stop: (id: number) => request<Deployment>("POST", `/deployments/${id}/stop`),
    logs: (id: number, afterId = 0) =>
      request<DeploymentLog[]>("GET", `/deployments/${id}/logs${query({ after_id: afterId })}`),
  },
  sessions: {
    list: () => request<SessionSummary[]>("GET", "/sessions"),
    create: (deploymentId: number) =>
      request<SessionDetail>("POST", "/sessions", { deployment_id: deploymentId }),
    get: (id: number) => request<SessionDetail>("GET", `/sessions/${id}`),
    send: (id: number, content: string) =>
      request<SessionDetail>("POST", `/sessions/${id}/messages`, { content }),
    cancel: (id: number) => request<undefined>("POST", `/sessions/${id}/cancel`),
  },
  bugHunts: {
    list: () => request<BugHunt[]>("GET", "/bug-hunts"),
    reload: () => request<BugHunt[]>("POST", "/bug-hunts/reload"),
  },
  jobs: {
    list: (filters: { model_id?: number; bug_hunt?: string; status?: string } = {}) =>
      request<JobSummary[]>("GET", `/jobs${query(filters)}`),
    get: (id: number) => request<JobDetail>("GET", `/jobs/${id}`),
    finish: (id: number) => request<JobDetail>("POST", `/jobs/${id}/finish`),
    cancel: (id: number) => request<JobDetail>("POST", `/jobs/${id}/cancel`),
    rescore: (id: number) => request<JobDetail>("POST", `/jobs/${id}/rescore`),
  },
  leaderboard: (bugHunt?: string) =>
    request<LeaderboardEntry[]>("GET", `/leaderboard${query({ bug_hunt: bugHunt })}`),
};
