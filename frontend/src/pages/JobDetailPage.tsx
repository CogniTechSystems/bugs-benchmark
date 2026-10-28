import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { Finding, JobDetail } from "../api/types";
import { Markdown } from "../components/Markdown";
import { Alert, Card, EmptyState, PageHeader, Stat, StatusBadge } from "../components/ui";
import { useAction, useResource } from "../hooks/useResource";
import {
  formatDateTime,
  formatDuration,
  formatNumber,
  formatPercent,
  formatScore,
} from "../lib/format";

const IN_PROGRESS = new Set(["active", "scoring"]);

export function JobDetailPage() {
  const jobId = Number(useParams().jobId);
  const [polling, setPolling] = useState(true);
  const job = useResource(() => api.jobs.get(jobId), `job-${jobId}`, polling ? 3000 : undefined);
  const action = useAction();
  const status = job.data?.status;

  useEffect(() => {
    setPolling(status === undefined || IN_PROGRESS.has(status));
  }, [status]);

  if (!job.data) {
    return job.error ? <Alert message={job.error} /> : <EmptyState>Loading…</EmptyState>;
  }
  const data = job.data;
  const refreshAfter = (operation: () => Promise<unknown>) =>
    action.run(async () => {
      await operation();
      await job.refresh();
    });

  return (
    <>
      <PageHeader
        title={`Job #${data.id} · ${data.bug_hunt_title}`}
        description={
          <>
            {data.model_repo_id} on {data.runtime_name} ({data.deployment_name}) ·{" "}
            <Link to={`/chat/${data.session_id}`}>View session</Link>
          </>
        }
        actions={
          <>
            <StatusBadge status={data.status} />
            {data.status === "active" && (
              <button
                type="button"
                onClick={() => void refreshAfter(() => api.jobs.finish(data.id))}
              >
                Finish and score
              </button>
            )}
            {!IN_PROGRESS.has(data.status) && data.finished_at && (
              <button
                type="button"
                className="secondary"
                disabled={action.pending}
                onClick={() => void refreshAfter(() => api.jobs.rescore(data.id))}
              >
                Rescore
              </button>
            )}
          </>
        }
      />
      <Alert message={action.error ?? data.error} />
      <ScoreSummary job={data} />
      <BugResults job={data} />
      <Findings findings={data.findings} />
      <Card title="Run details">
        <dl className="details">
          <dt>Started</dt>
          <dd>{formatDateTime(data.started_at)}</dd>
          <dt>Finished</dt>
          <dd>{formatDateTime(data.finished_at)}</dd>
          <dt>Agent summary</dt>
          <dd>{data.agent_summary ? <Markdown>{data.agent_summary}</Markdown> : "-"}</dd>
          {Object.entries(data.settings_snapshot).map(([key, value]) => (
            <FragmentRow key={key} label={key.replace(/_/g, " ")} value={value} />
          ))}
        </dl>
      </Card>
    </>
  );
}

function FragmentRow({ label, value }: { label: string; value: unknown }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>
        <code>{value === null || value === "" ? "-" : String(value)}</code>
      </dd>
    </>
  );
}

function ScoreSummary({ job }: { job: JobDetail }) {
  const score = job.score;
  return (
    <div className="stats">
      <Stat label="Final score" value={formatScore(score?.final_score)} detail="out of 100" />
      <Stat
        label="Accuracy"
        value={formatScore(score?.accuracy_score)}
        detail={score ? `${score.points_earned} of ${score.points_possible} points` : undefined}
      />
      <Stat
        label="Bugs found"
        value={score ? `${score.bugs_found} / ${score.bugs_total}` : "-"}
        detail={score ? `precision ${formatPercent(score.precision)}` : undefined}
      />
      <Stat label="Fixes verified" value={score ? score.fixes_verified : "-"} />
      <Stat label="False positives" value={score ? score.false_positives : "-"} />
      <Stat
        label="Working time"
        value={formatDuration(job.working_seconds)}
        detail={
          score
            ? `time factor ${score.time_factor.toFixed(2)} · wall clock ${formatDuration(job.duration_seconds)}`
            : undefined
        }
      />
      <Stat
        label="Model calls"
        value={job.llm_calls}
        detail={`${formatNumber(job.prompt_tokens + job.completion_tokens)} tokens`}
      />
      <Stat label="Tool calls" value={job.tool_calls} />
    </div>
  );
}

function BugResults({ job }: { job: JobDetail }) {
  if (job.bug_results.length === 0) {
    return null;
  }
  return (
    <Card title="Expected bugs">
      <table>
        <thead>
          <tr>
            <th>Bug</th>
            <th className="numeric">Points</th>
            <th>Found</th>
            <th>Fix</th>
            <th>Finding</th>
          </tr>
        </thead>
        <tbody>
          {job.bug_results.map((result) => (
            <tr key={result.bug_key}>
              <td>
                {result.title}
                <div className="muted small">
                  <code>{result.bug_key}</code>
                </div>
              </td>
              <td className="numeric">{result.points}</td>
              <td>
                <StatusBadge status={result.found ? "matched" : "failed"} />
              </td>
              <td>
                {result.found && (
                  <StatusBadge status={result.fix_verified ? "verified" : "failed"} />
                )}
              </td>
              <td>
                {result.finding_id ? (
                  <a href={`#finding-${result.finding_id}`}>#{result.finding_id}</a>
                ) : (
                  "-"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function Findings({ findings }: { findings: Finding[] }) {
  return (
    <Card title="Findings">
      {findings.length === 0 && <EmptyState>The agent has not reported any findings.</EmptyState>}
      {findings.map((finding) => (
        <article key={finding.id} id={`finding-${finding.id}`} className="finding">
          <header>
            <code>
              #{finding.id} {finding.file_path}:{finding.line}
            </code>
            {finding.outcome && <StatusBadge status={finding.outcome} />}
            {finding.fix_status && <StatusBadge status={finding.fix_status} />}
            {finding.matched_bug_key && (
              <span className="muted small">{finding.matched_bug_key}</span>
            )}
          </header>
          <Markdown>{finding.description}</Markdown>
          <div className="diff">
            <pre className="code code-removed">{finding.original}</pre>
            <pre className="code code-added">{finding.replacement}</pre>
          </div>
          {finding.fix_details && <p className="muted small">{finding.fix_details}</p>}
        </article>
      ))}
    </Card>
  );
}
