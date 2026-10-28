import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, NavLink, useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import type {
  ChatMessage,
  Deployment,
  Draft,
  JobSummary,
  SessionDetail,
  StoredToolCall,
} from "../api/types";
import { Markdown } from "../components/Markdown";
import { Reasoning } from "../components/Reasoning";
import { Alert, EmptyState, StatusBadge } from "../components/ui";
import { useAction, useResource } from "../hooks/useResource";
import { formatDateTime, formatScore } from "../lib/format";

const SUGGESTED_PROMPTS = ["List the available bug hunts", "Run bug hunt inventory-ledger"];

export function ChatPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const sessions = useResource(api.sessions.list, "sessions", 5000);
  const deployments = useResource(api.deployments.list, "deployments", 10000);
  const selectedId = sessionId ? Number(sessionId) : undefined;

  return (
    <div className="chat-layout">
      <aside className="chat-sidebar">
        <NewSessionForm
          deployments={deployments.data ?? []}
          onCreated={(id) => {
            void sessions.refresh();
            navigate(`/chat/${id}`);
          }}
        />
        <Alert message={sessions.error} />
        <nav className="session-list">
          {(sessions.data ?? []).map((session) => (
            <NavLink key={session.id} to={`/chat/${session.id}`} className="session-link">
              <span className="session-title">{session.title}</span>
              <span className="session-meta">
                {session.deployment_name}
                {session.status !== "idle" && <StatusBadge status={session.status} />}
              </span>
            </NavLink>
          ))}
          {sessions.data?.length === 0 && <EmptyState>No sessions yet.</EmptyState>}
        </nav>
      </aside>
      {selectedId ? (
        <SessionView key={selectedId} sessionId={selectedId} onActivity={sessions.refresh} />
      ) : (
        <section className="chat-main">
          <EmptyState>Select a running deployment to start a session.</EmptyState>
        </section>
      )}
    </div>
  );
}

function NewSessionForm({
  deployments,
  onCreated,
}: {
  deployments: Deployment[];
  onCreated: (sessionId: number) => void;
}) {
  const [deploymentId, setDeploymentId] = useState<number>();
  const action = useAction();
  const running = deployments.filter((deployment) => deployment.status === "running");
  const selected = deploymentId ?? running[0]?.id;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (selected === undefined) {
      return;
    }
    await action.run(async () => onCreated((await api.sessions.create(selected)).id));
  };

  return (
    <form className="new-session" onSubmit={submit}>
      <select
        value={selected ?? ""}
        onChange={(event) => setDeploymentId(Number(event.target.value))}
        aria-label="Deployment"
      >
        {running.length === 0 && <option value="">No running deployments</option>}
        {running.map((deployment) => (
          <option key={deployment.id} value={deployment.id}>
            {deployment.name}
          </option>
        ))}
      </select>
      <button type="submit" disabled={selected === undefined || action.pending}>
        New session
      </button>
      <Alert message={action.error} />
      {running.length === 0 && (
        <p className="muted small">
          Start a deployment under <Link to="/admin/deployments">Deployments</Link> first.
        </p>
      )}
    </form>
  );
}

function SessionView({
  sessionId,
  onActivity,
}: {
  sessionId: number;
  onActivity: () => Promise<void>;
}) {
  const [polling, setPolling] = useState(false);
  const session = useResource(
    () => api.sessions.get(sessionId),
    `session-${sessionId}`,
    polling ? 1500 : undefined,
  );
  const status = session.data?.status;

  useEffect(() => {
    setPolling(status === "running");
    if (status !== undefined) {
      void onActivity();
    }
  }, [status, onActivity]);

  if (!session.data) {
    return session.error ? <Alert message={session.error} /> : <EmptyState>Loading…</EmptyState>;
  }

  const data = session.data;
  const latestJobId =
    data.active_job?.id ??
    [...data.messages].reverse().find((message) => message.job_id !== null)?.job_id;

  return (
    <div className="chat-workspace">
      <section className="chat-main">
        <div className="chat-header">
          <div>
            <h1>{data.title}</h1>
            <span className="muted small">
              {data.deployment_name} · started {formatDateTime(data.created_at)}
            </span>
          </div>
          <StatusBadge status={data.status} />
        </div>
        <MessageList
          messages={data.messages}
          running={data.status === "running"}
          draft={data.draft}
        />
        <Alert message={data.error} />
        <Composer
          session={data}
          onSent={async () => {
            setPolling(true);
            await session.refresh();
          }}
        />
      </section>
      <JobProgressPanel
        jobId={latestJobId ?? null}
        activeJob={data.active_job}
        messages={data.messages}
        sessionRunning={data.status === "running"}
        onChange={session.refresh}
      />
    </div>
  );
}

function JobProgressPanel({
  jobId,
  activeJob,
  messages,
  sessionRunning,
  onChange,
}: {
  jobId: number | null;
  activeJob: JobSummary | null;
  messages: ChatMessage[];
  sessionRunning: boolean;
  onChange: () => Promise<void>;
}) {
  if (jobId === null) {
    return (
      <aside className="job-panel" aria-label="Job progress">
        <h2>Job progress</h2>
        <p className="muted">No bug hunt in this session.</p>
      </aside>
    );
  }
  return (
    <JobProgressDetails
      key={jobId}
      jobId={jobId}
      activeJob={activeJob}
      messages={messages}
      sessionRunning={sessionRunning}
      onChange={onChange}
    />
  );
}

function JobProgressDetails({
  jobId,
  activeJob,
  messages,
  sessionRunning,
  onChange,
}: {
  jobId: number;
  activeJob: JobSummary | null;
  messages: ChatMessage[];
  sessionRunning: boolean;
  onChange: () => Promise<void>;
}) {
  const jobResource = useResource(() => api.jobs.get(jobId), `chat-job-${jobId}`);
  const refreshJob = jobResource.refresh;
  const action = useAction();
  const job = jobResource.data ?? activeJob;
  const status = job?.status;
  const recentActivity = messages
    .filter((message) => message.role === "tool" && message.job_id === jobId && message.tool_name)
    .slice(-3)
    .reverse();

  useEffect(() => {
    if (status === "active" || status === "scoring") {
      const timer = window.setInterval(() => void refreshJob(), 2500);
      return () => window.clearInterval(timer);
    }
    return undefined;
  }, [status, refreshJob]);

  const finish = () =>
    action.run(async () => {
      await api.jobs.finish(jobId);
      await refreshJob();
      await onChange();
    });
  const cancel = () =>
    action.run(async () => {
      await api.jobs.cancel(jobId);
      await refreshJob();
      await onChange();
    });

  return (
    <aside className="job-panel" aria-label="Job progress">
      <div className="job-panel-header">
        <div>
          <span className="eyebrow">Bug hunt</span>
          <h2>{job?.bug_hunt_title ?? `Job #${jobId}`}</h2>
        </div>
        {status && <StatusBadge status={status} />}
      </div>
      <span className="muted small">Job #{jobId}</span>
      <div className="job-steps" aria-label="Run stages">
        <div className="job-step done">
          <span className="job-step-mark" />
          Started
        </div>
        <div className={`job-step ${status === "active" ? "current" : "done"}`}>
          <span className="job-step-mark" />
          Investigation
        </div>
        <div
          className={`job-step ${status === "scoring" ? "current" : status === "completed" ? "done" : ""}`}
        >
          <span className="job-step-mark" />
          Scoring
        </div>
      </div>
      <div className="job-metrics">
        <div>
          <span>Findings</span>
          <strong>{job?.findings_count ?? "—"}</strong>
        </div>
        <div>
          <span>Tool calls</span>
          <strong>{job?.tool_calls ?? "—"}</strong>
        </div>
        <div>
          <span>Model calls</span>
          <strong>{job?.llm_calls ?? "—"}</strong>
        </div>
        {job?.final_score !== null && job?.final_score !== undefined && (
          <div>
            <span>Final score</span>
            <strong>{formatScore(job.final_score)}</strong>
          </div>
        )}
      </div>
      {jobResource.data && jobResource.data.findings.length > 0 && (
        <div className="job-findings">
          <h3>Findings</h3>
          {jobResource.data.findings
            .slice(-4)
            .reverse()
            .map((finding) => (
              <div className="job-finding" key={finding.id}>
                <span className="job-finding-path">
                  {finding.file_path}:{finding.line}
                </span>
                {finding.outcome && <StatusBadge status={finding.outcome} />}
              </div>
            ))}
        </div>
      )}
      {recentActivity.length > 0 && (
        <div className="job-activity">
          <h3>Recent activity</h3>
          {recentActivity.map((message) => (
            <div key={message.id}>{message.tool_name?.replace(/_/g, " ")}</div>
          ))}
        </div>
      )}
      {job?.error && <Alert message={job.error} />}
      <Alert message={jobResource.error ?? action.error} />
      <div className="job-panel-actions">
        <Link className="button-link" to={`/jobs/${jobId}`}>
          View job details
        </Link>
        {status === "active" && (
          <>
            <button type="button" onClick={finish} disabled={action.pending || sessionRunning}>
              Finish and score
            </button>
            <button type="button" className="secondary" onClick={cancel} disabled={action.pending}>
              Cancel job
            </button>
          </>
        )}
      </div>
    </aside>
  );
}

function MessageList({
  messages,
  running,
  draft,
}: {
  messages: ChatMessage[];
  running: boolean;
  draft: Draft | null;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const results = useMemo(() => {
    const byCallId = new Map<string, ChatMessage>();
    for (const message of messages) {
      if (message.role === "tool" && message.tool_call_id) {
        byCallId.set(message.tool_call_id, message);
      }
    }
    return byCallId;
  }, [messages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, running, draft?.content.length]);

  return (
    <div className="messages">
      {messages.length === 0 && <EmptyState>Send a message or choose a prompt below.</EmptyState>}
      {messages
        .filter((message) => message.role !== "tool")
        .map((message) =>
          message.role === "user" ? (
            <div key={message.id} className="message message-user">
              {message.content}
            </div>
          ) : (
            <AssistantMessage key={message.id} message={message} results={results} />
          ),
        )}
      {running && <DraftMessage draft={draft} />}
      <div ref={endRef} />
    </div>
  );
}

function DraftMessage({ draft }: { draft: Draft | null }) {
  if (!draft || (!draft.reasoning && !draft.content)) {
    return <div className="message message-pending">Running…</div>;
  }
  return (
    <div className="message message-assistant message-draft">
      {draft.reasoning && <Reasoning text={draft.reasoning} live />}
      {draft.content && <Markdown>{draft.content}</Markdown>}
      <div className="message-meta">Generating…</div>
    </div>
  );
}

function AssistantMessage({
  message,
  results,
}: {
  message: ChatMessage;
  results: Map<string, ChatMessage>;
}) {
  const details = [
    message.latency_ms !== null ? `${(message.latency_ms / 1000).toFixed(1)}s` : null,
    message.completion_tokens !== null ? `${message.completion_tokens} tokens` : null,
  ].filter(Boolean);

  return (
    <div className="message message-assistant">
      {message.reasoning && <Reasoning text={message.reasoning} />}
      {message.content && <Markdown>{message.content}</Markdown>}
      {message.tool_calls?.map((call) => (
        <ToolCallView key={call.id} call={call} result={results.get(call.id)} />
      ))}
      {details.length > 0 && <div className="message-meta">{details.join(" · ")}</div>}
    </div>
  );
}

function parseArguments(call: StoredToolCall): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(call.arguments || "{}");
    return typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function summariseCall(call: StoredToolCall, args: Record<string, unknown>): string {
  const target = args.slug ?? args.path ?? args.query ?? args.file_path;
  const line = args.line !== undefined ? `:${String(args.line)}` : "";
  return target !== undefined ? `${call.name} ${String(target)}${line}` : call.name;
}

function ToolCallView({ call, result }: { call: StoredToolCall; result?: ChatMessage }) {
  const args = parseArguments(call);
  const failed = result?.content?.startsWith("Error:") ?? false;
  const jobLink =
    result?.job_id && (call.name === "start_bug_hunt" || call.name === "finish_bug_hunt");

  return (
    <details className={`tool-call${failed ? " tool-call-failed" : ""}`}>
      <summary>
        <code>{summariseCall(call, args)}</code>
        {!result && <span className="muted small">running…</span>}
        {failed && <StatusBadge status="error" />}
        {jobLink && (
          <Link to={`/jobs/${result.job_id}`} onClick={(event) => event.stopPropagation()}>
            Job #{result.job_id}
          </Link>
        )}
      </summary>
      {call.name === "report_bug" ? (
        <div className="finding-preview">
          <Markdown>{String(args.description ?? "")}</Markdown>
          <pre className="code code-removed">{String(args.original ?? "")}</pre>
          <pre className="code code-added">{String(args.replacement ?? "")}</pre>
        </div>
      ) : (
        Object.keys(args).length > 0 && <pre className="code">{JSON.stringify(args, null, 2)}</pre>
      )}
      {result?.content && <pre className="code tool-result">{result.content}</pre>}
    </details>
  );
}

function Composer({ session, onSent }: { session: SessionDetail; onSent: () => Promise<void> }) {
  const [draft, setDraft] = useState("");
  const action = useAction();
  const running = session.status === "running";

  const send = async (content: string) => {
    const text = content.trim();
    if (!text || running) {
      return;
    }
    const sent = await action.run(() => api.sessions.send(session.id, text));
    if (sent) {
      setDraft("");
      await onSent();
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(draft);
    }
  };

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault();
        void send(draft);
      }}
    >
      {session.messages.length === 0 && (
        <div className="suggestions">
          {SUGGESTED_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="secondary"
              onClick={() => void send(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}
      <Alert message={action.error} />
      <div className="composer-row">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Message · Enter to send, Shift+Enter for a new line"
          rows={3}
          disabled={running}
        />
        {running ? (
          <button
            type="button"
            className="secondary"
            onClick={() => void api.sessions.cancel(session.id)}
          >
            Stop
          </button>
        ) : (
          <button type="submit" disabled={!draft.trim() || action.pending}>
            Send
          </button>
        )}
      </div>
    </form>
  );
}
