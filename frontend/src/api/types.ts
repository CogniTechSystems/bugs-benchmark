export type DownloadStatus = "queued" | "downloading" | "ready" | "failed";
export type RuntimeKind = "managed" | "external";
export type DeploymentStatus = "stopped" | "starting" | "running" | "failed";
export type SessionStatus = "idle" | "running" | "error";
export type MessageRole = "user" | "assistant" | "tool";
export type Difficulty = "easy" | "medium" | "hard";
export type JobStatus = "active" | "scoring" | "completed" | "failed" | "cancelled";
export type FindingOutcome = "matched" | "superseded" | "false_positive";
export type FixStatus = "verified" | "failed" | "not_applicable";

export interface HubModel {
  repo_id: string;
  downloads: number;
  likes: number;
  pipeline_tag: string | null;
  tags: string[];
}

export interface RepositoryFile {
  path: string;
  size_bytes: number | null;
}

export interface LanguageModel {
  id: number;
  repo_id: string;
  revision: string;
  allow_patterns: string[] | null;
  local_path: string;
  status: DownloadStatus;
  error: string | null;
  total_bytes: number | null;
  downloaded_bytes: number;
  completed_at: string | null;
  created_at: string;
}

export interface ModelDownloadRequest {
  repo_id: string;
  revision: string;
  allow_patterns: string[] | null;
  register_only?: boolean;
}

export interface RuntimeWrite {
  name: string;
  description: string;
  kind: RuntimeKind;
  command_template: string | null;
  base_url: string | null;
  health_path: string;
  startup_timeout_seconds: number;
}

export interface Runtime extends RuntimeWrite {
  id: number;
  created_at: string;
  updated_at: string;
}

export interface DeploymentWrite {
  name: string;
  model_id: number;
  runtime_id: number;
  model_file: string | null;
  served_model_name: string | null;
  launch_args: string;
  temperature: number;
  top_p: number;
  max_tokens: number;
  request_timeout_seconds: number;
}

export interface Deployment extends DeploymentWrite {
  id: number;
  model_repo_id: string;
  runtime_name: string;
  status: DeploymentStatus;
  port: number | null;
  pid: number | null;
  error: string | null;
  started_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeploymentLog {
  id: number;
  line: string;
  created_at: string;
}

export interface StoredToolCall {
  id: string;
  name: string;
  arguments: string;
}

export interface ChatMessage {
  id: number;
  role: MessageRole;
  content: string | null;
  reasoning: string | null;
  tool_calls: StoredToolCall[] | null;
  tool_call_id: string | null;
  tool_name: string | null;
  job_id: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  latency_ms: number | null;
  created_at: string;
}

export interface SessionSummary {
  id: number;
  title: string;
  deployment_id: number;
  deployment_name: string;
  status: SessionStatus;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface Draft {
  reasoning: string;
  content: string;
}

export interface SessionDetail extends SessionSummary {
  messages: ChatMessage[];
  active_job: JobSummary | null;
  draft: Draft | null;
}

export interface BugHunt {
  id: number;
  slug: string;
  title: string;
  difficulty: Difficulty;
  language: string;
  summary: string;
  bug_count: number;
  max_points: number;
  time_budget_seconds: number;
}

export interface JobSummary {
  id: number;
  bug_hunt_slug: string;
  bug_hunt_title: string;
  difficulty: Difficulty;
  session_id: number;
  model_id: number;
  model_repo_id: string;
  runtime_name: string;
  deployment_name: string;
  status: JobStatus;
  started_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
  working_seconds: number | null;
  llm_calls: number;
  tool_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  findings_count: number;
  final_score: number | null;
  error: string | null;
}

export interface Finding {
  id: number;
  file_path: string;
  line: number;
  description: string;
  original: string;
  replacement: string;
  outcome: FindingOutcome | null;
  matched_bug_key: string | null;
  fix_status: FixStatus | null;
  fix_details: string | null;
  created_at: string;
}

export interface BugResult {
  bug_key: string;
  title: string;
  points: number;
  found: boolean;
  fix_verified: boolean;
  finding_id: number | null;
}

export interface Score {
  bugs_total: number;
  bugs_found: number;
  fixes_verified: number;
  false_positives: number;
  points_earned: number;
  points_possible: number;
  precision: number;
  recall: number;
  accuracy_score: number;
  time_factor: number;
  final_score: number;
  created_at: string;
}

export interface JobDetail extends JobSummary {
  settings_snapshot: Record<string, unknown>;
  agent_summary: string | null;
  findings: Finding[];
  bug_results: BugResult[];
  score: Score | null;
}

export interface LeaderboardEntry {
  model_id: number;
  model_repo_id: string;
  runtime_id: number;
  runtime_name: string;
  jobs: number;
  average_final_score: number;
  best_final_score: number;
  average_accuracy: number;
  average_working_seconds: number;
  bugs_found: number;
  bugs_total: number;
  fixes_verified: number;
  false_positives: number;
}
