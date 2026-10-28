import { Link } from "react-router-dom";

import { api } from "../api/client";
import { Alert, Card, EmptyState, PageHeader, StatusBadge } from "../components/ui";
import { useAction, useResource } from "../hooks/useResource";
import { formatDateTime, formatDuration, formatScore } from "../lib/format";

export function BugHuntsPage() {
  const hunts = useResource(api.bugHunts.list, "bug-hunts");
  const jobs = useResource(() => api.jobs.list(), "jobs", 5000);
  const reload = useAction();

  return (
    <>
      <PageHeader
        title="Bug hunts"
        description="Challenge catalogue and jobs"
        actions={
          <button
            type="button"
            className="secondary"
            disabled={reload.pending}
            onClick={() =>
              void reload.run(async () => {
                await api.bugHunts.reload();
                await hunts.refresh();
              })
            }
          >
            Reload catalogue
          </button>
        }
      />
      <Alert message={hunts.error ?? reload.error} />
      <Card title="Catalogue">
        <table>
          <thead>
            <tr>
              <th>Bug hunt</th>
              <th>Slug</th>
              <th>Difficulty</th>
              <th className="numeric">Bugs</th>
              <th className="numeric">Points</th>
              <th className="numeric">Time budget</th>
            </tr>
          </thead>
          <tbody>
            {(hunts.data ?? []).map((hunt) => (
              <tr key={hunt.id}>
                <td>
                  <strong>{hunt.title}</strong>
                  <div className="muted small">{hunt.summary}</div>
                </td>
                <td>
                  <code>{hunt.slug}</code>
                </td>
                <td>
                  <StatusBadge status={hunt.difficulty} />
                </td>
                <td className="numeric">{hunt.bug_count}</td>
                <td className="numeric">{hunt.max_points}</td>
                <td className="numeric">{formatDuration(hunt.time_budget_seconds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Jobs">
        <Alert message={jobs.error} />
        {jobs.data?.length === 0 ? (
          <EmptyState>No bug hunts have been run yet.</EmptyState>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>Bug hunt</th>
                <th>Model</th>
                <th>Runtime</th>
                <th>Status</th>
                <th className="numeric">Findings</th>
                <th className="numeric">Working time</th>
                <th className="numeric">Score</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {(jobs.data ?? []).map((job) => (
                <tr key={job.id}>
                  <td>
                    <Link to={`/jobs/${job.id}`}>#{job.id}</Link>
                  </td>
                  <td>{job.bug_hunt_title}</td>
                  <td>{job.model_repo_id}</td>
                  <td>{job.runtime_name}</td>
                  <td>
                    <StatusBadge status={job.status} />
                  </td>
                  <td className="numeric">{job.findings_count}</td>
                  <td className="numeric">
                    {formatDuration(job.working_seconds ?? job.duration_seconds)}
                  </td>
                  <td className="numeric">{formatScore(job.final_score)}</td>
                  <td>{formatDateTime(job.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
