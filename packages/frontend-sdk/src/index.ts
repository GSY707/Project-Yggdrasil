export type ContributionKind = "panel" | "route" | "widget";

export interface PanelContribution {
  id: string;
  title: string;
  path: string;
  description?: string;
}

export interface RouteContribution {
  id: string;
  path: string;
  title: string;
}

export interface WidgetContribution {
  id: string;
  title: string;
  description?: string;
}

export interface FrontendContributionBundle {
  moduleId: string;
  panels?: PanelContribution[];
  routes?: RouteContribution[];
  widgets?: WidgetContribution[];
}

export interface ServiceHealthSnapshot {
  status: string;
  service: string;
  database?: Record<string, unknown>;
  redis?: Record<string, unknown>;
}

export interface TaskSummaryRecord {
  id: string;
  title: string;
  goal: string;
  status: string;
  currentFocus?: string | null;
  currentObjective?: string | null;
  branchId?: string;
  createdAt: string;
  updatedAt?: string;
  [key: string]: unknown;
}

export interface AgentRunRecord {
  id: string;
  taskId: string;
  status: string;
  runType: string;
  selectedModel: string;
  selectedProvider?: string | null;
  startedAt: string;
  endedAt?: string | null;
  [key: string]: unknown;
}

export interface SnapshotRecord {
  id: string;
  status: string;
  resumeToken?: string | null;
  resumeMessage?: string | null;
  createdAt: string;
  consumedAt?: string | null;
  [key: string]: unknown;
}

export interface RouteDecisionRecord {
  id: string;
  selectedModel: string;
  selectedProvider?: string | null;
  reason: string;
  routePolicyVersion: string;
  createdAt: string;
  [key: string]: unknown;
}

export interface ModelInvocationRecord {
  id: string;
  projectId: string;
  taskId?: string | null;
  agentRunId?: string | null;
  routeDecisionId?: string | null;
  requestedModel: string;
  requestedProvider?: string | null;
  resolvedModel: string;
  resolvedProvider?: string | null;
  invocationKind: string;
  status: string;
  traceId?: string | null;
  requestRef?: { type: string; locator: string } | null;
  responseRef?: { type: string; locator: string } | null;
  inputTokensUsed: number;
  outputTokensUsed: number;
  costUsed: number;
  latencyMs?: number | null;
  errorSummary?: string | null;
  startedAt: string;
  endedAt?: string | null;
  createdAt: string;
  [key: string]: unknown;
}

export interface LLMSummary {
  totalInvocations: number;
  liveInvocations: number;
  fallbackInvocations: number;
  failedInvocations: number;
  totalCostUsed: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  providerCounts: Record<string, number>;
  statusCounts: Record<string, number>;
}

export interface NodeSummaryRecord {
  id: string;
  title: string;
  content: string;
  nodeType: string;
  status: string;
  branchId: string;
  parentId?: string | null;
  importance?: number;
  updatedAt?: string;
  createdAt: string;
  [key: string]: unknown;
}

export interface NodeVersionRecord {
  id: string;
  versionNo: number;
  titleSnapshot: string;
  contentSnapshot: string;
  changeReason: string;
  createdAt: string;
  [key: string]: unknown;
}

export interface SourceAnnotationRecord {
  id: string;
  ownerKind: string;
  ownerId: string;
  sourceType: string;
  excerpt?: string | null;
  inferenceSummary?: string | null;
  confidence: number;
  createdAt: string;
  [key: string]: unknown;
}

export interface EdgeRecord {
  id: string;
  fromNodeId: string;
  toNodeId: string;
  relationType: string;
  reason: string;
  status: string;
  [key: string]: unknown;
}

export interface BranchRecord {
  id: string;
  name: string;
  status: string;
  baseBranchId?: string | null;
  headRef?: string | null;
  createdAt: string;
  [key: string]: unknown;
}

export interface PullRequestRecord {
  id: string;
  title: string;
  summary: string;
  status: string;
  sourceBranchId: string;
  targetBranchId: string;
  externalId?: string | null;
  externalUrl?: string | null;
  mergeCommitRef?: string | null;
  mergedAt?: string | null;
  createdAt: string;
  [key: string]: unknown;
}

export interface EvaluationCaseDefinition {
  id: string;
  title: string;
  scenario: string;
  tags: string[];
  difficulty: string;
}

export interface EvaluationSuiteRecord {
  id: string;
  name: string;
  domain: string;
  metricRefs: string[];
  createdAt: string;
  caseCount: number;
  cases: EvaluationCaseDefinition[];
  subjectKind: string;
  subjectRef: string;
}

export interface EvaluationRunRecord {
  id: string;
  suiteId: string;
  projectId: string;
  subjectKind: string;
  subjectRef: string;
  status: string;
  metricsRef?: { type: string; locator: string } | null;
  startedAt?: string | null;
  endedAt?: string | null;
  createdAt: string;
  metrics?: Record<string, unknown> | null;
}

export interface ObservabilityServiceSummary {
  serviceName: string;
  spanCount: number;
  errorCount: number;
  avgDurationMs: number;
  lastSeenAt?: string | null;
  counters: Record<string, number>;
  gauges: Record<string, number>;
}

export interface ObservabilityExporterStatus {
  configured: boolean;
  enabled: boolean;
  ready: boolean;
  detail?: string | null;
  transport?: string | null;
  host?: string | null;
  tracesEndpoint?: string | null;
  metricsEndpoint?: string | null;
}

export interface ObservabilitySummary {
  generatedAt: string;
  totalSpans: number;
  totalLogs: number;
  totalMetrics: number;
  serviceSummaries: ObservabilityServiceSummary[];
  exporters: {
    otel: ObservabilityExporterStatus;
    langfuse: ObservabilityExporterStatus;
  };
  llmSummary: LLMSummary;
  recentModelInvocations: ModelInvocationRecord[];
  recentSpans: Array<Record<string, unknown>>;
  recentLogs: Array<Record<string, unknown>>;
  metricSamples: Array<Record<string, unknown>>;
  health: ServiceHealthSnapshot;
}

export interface WorkbenchOverview {
  generatedAt: string;
  health: ServiceHealthSnapshot;
  cards: {
    tasks: number;
    nodes: number;
    branches: number;
    pullRequests: number;
    imports: number;
    retrievals: number;
    outboxPending: number;
    evaluationRuns: number;
    observabilityErrors: number;
    modelInvocations: number;
    llmFallbacks: number;
    llmCostUsed: number;
  };
  moduleSummary: {
    total: number;
    active: number;
    degraded: number;
    disabled: number;
  };
  llmSummary: LLMSummary;
  taskStatusCounts: Record<string, number>;
  pullRequestStatusCounts: Record<string, number>;
  importJobStatusCounts: Record<string, number>;
  outboxStatusCounts: Record<string, number>;
  recentTasks: TaskSummaryRecord[];
  recentPullRequests: PullRequestRecord[];
  recentImportJobs: Array<Record<string, unknown>>;
  recentModelInvocations: ModelInvocationRecord[];
  recentEvaluationRuns: EvaluationRunRecord[];
  evaluationSuites: EvaluationSuiteRecord[];
  observability: ObservabilitySummary;
}

export interface TaskDetailResponse {
  task: TaskSummaryRecord;
  agentRuns: AgentRunRecord[];
  snapshots: SnapshotRecord[];
  routeDecisions: RouteDecisionRecord[];
  modelInvocations: ModelInvocationRecord[];
}

export interface NodeDetailResponse {
  node: NodeSummaryRecord;
  versions: NodeVersionRecord[];
  annotations: SourceAnnotationRecord[];
  outgoingEdges: EdgeRecord[];
  incomingEdges: EdgeRecord[];
}