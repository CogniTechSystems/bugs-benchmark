import { useState } from "react";

import { api } from "../api/client";
import { Alert, Card, EmptyState, Field, PageHeader } from "../components/ui";
import { useResource } from "../hooks/useResource";
import { formatDuration, formatScore } from "../lib/format";

export function LeaderboardPage() {
  const [bugHunt, setBugHunt] = useState("");
  const hunts = useResource(api.bugHunts.list, "bug-hunts");
  const entries = useResource(
    () => api.leaderboard(bugHunt || undefined),
    `leaderboard-${bugHunt}`,
    10000,
  );

  return (
    <>
      <PageHeader title="Leaderboard" description="Model and runtime rankings" />
      <Card
        actions={
          <Field label="Bug hunt">
            <select value={bugHunt} onChange={(event) => setBugHunt(event.target.value)}>
              <option value="">All bug hunts</option>
              {(hunts.data ?? []).map((hunt) => (
                <option key={hunt.slug} value={hunt.slug}>
                  {hunt.title}
                </option>
              ))}
            </select>
          </Field>
        }
      >
        <Alert message={entries.error} />
        {entries.data?.length === 0 ? (
          <EmptyState>No completed bug hunts yet.</EmptyState>
        ) : (
          <table>
            <thead>
              <tr>
                <th className="numeric">Rank</th>
                <th>Model</th>
                <th>Runtime</th>
                <th className="numeric">Jobs</th>
                <th className="numeric">Average score</th>
                <th className="numeric">Best score</th>
                <th className="numeric">Accuracy</th>
                <th className="numeric">Bugs found</th>
                <th className="numeric">Fixes verified</th>
                <th className="numeric">False positives</th>
                <th className="numeric">Average working time</th>
              </tr>
            </thead>
            <tbody>
              {(entries.data ?? []).map((entry, index) => (
                <tr key={`${entry.model_id}-${entry.runtime_id}`}>
                  <td className="numeric">{index + 1}</td>
                  <td>{entry.model_repo_id}</td>
                  <td>{entry.runtime_name}</td>
                  <td className="numeric">{entry.jobs}</td>
                  <td className="numeric">
                    <strong>{formatScore(entry.average_final_score)}</strong>
                  </td>
                  <td className="numeric">{formatScore(entry.best_final_score)}</td>
                  <td className="numeric">{formatScore(entry.average_accuracy)}</td>
                  <td className="numeric">
                    {entry.bugs_found} / {entry.bugs_total}
                  </td>
                  <td className="numeric">{entry.fixes_verified}</td>
                  <td className="numeric">{entry.false_positives}</td>
                  <td className="numeric">{formatDuration(entry.average_working_seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
