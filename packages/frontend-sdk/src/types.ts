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
  appId: string;
  projectId?: string;
  spaceId?: string;
  title: string;
  goal: string;
  status: string;
  currentFocus?: string | null;
  currentObjective?: string | null;
  branchId?: string;
  pauseRequested?: boolean;
  activeSnapshotId?: string | null;
  resumeMessage?: string | null;
  lastSafeStopAt?: string | null;
  createdAt: string;
  updatedAt?: string;
  [key: string]: unknown;
}

export interface SpaceRecord {
  id: string;
  projectId: string;
  spaceType: string;
  status: string;
  ownerSubject?: string | null;
  createdAt: string;
  [key: string]: unknown;
}

export interface SpaceMountRecord {
  id: string;
  projectId: string;
  hostSpaceId: string;
  mountedSpaceId: string;
  mountMode: string;
  status: string;
  createdAt: string;
  createdBy?: { type: string; id: string };
  [key: string]: unknown;
}

export interface PermissionTupleRecord {
  id: string;
  projectId: string;
  subject: string;
  relation: string;
  resource: string;
  condition?: Record<string, unknown> | null;
  effect: string;
  createdAt: string;
  createdBy?: { type: string; id: string };
  [key: string]: unknown;
}

export interface AgentRunRecord {
  id: string;
  appId: string;
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
  appId: string;
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
  appId: string;
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
  promptCompileArtifactId?: string | null;
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

export interface AssetRecord {
  id: string;
  projectId: string;
  spaceId: string;
  branchId: string;
  ownerNodeId?: string | null;
  mediaType: string;
  role: string;
  storageKey: string;
  checksum: string;
  sourceRef?: { type: string; locator: string } | null;
  durationMs?: number | null;
  width?: number | null;
  height?: number | null;
  createdAt: string;
  createdBy: { type: string; id: string };
  [key: string]: unknown;
}

export interface AssetSegmentRecord {
  id: string;
  assetId: string;
  ordinal: number;
  startOffset: number;
  endOffset: number;
  textExcerpt?: string | null;
  summary?: string | null;
  embeddingId?: string | null;
  createdAt: string;
  [key: string]: unknown;
}

export interface AssetEmbeddingRecord {
  id: string;
  ownerKind: string;
  ownerId: string;
  model: string;
  dimension: number;
  vectorRef: { type: string; locator: string };
  createdAt: string;
  [key: string]: unknown;
}

export interface DatasetVersionRecord {
  id: string;
  datasetName: string;
  version: string;
  sourceFilter: Record<string, unknown>;
  storageKey: string;
  rowCount: number;
  createdAt: string;
  [key: string]: unknown;
}

export interface ModelArtifactRecord {
  id: string;
  baseModel: string;
  tuningMethod: string;
  datasetVersionId: string;
  metricsRef?: { type: string; locator: string } | null;
  storageKey: string;
  status: string;
  createdAt: string;
  [key: string]: unknown;
}

export interface PromptProfileDefinition {
  id: string;
  name: string;
  version: string;
  runScope: string;
  systemRole: string;
  kernelTruth: string;
  behaviorGuidelines: string;
  toolPolicy: string;
  memoryPolicy: string;
  evidencePolicy: string;
  outputContract: string;
  selfEvolution?: string | null;
  fewShotRefs: string[];
  sourceAppId?: string | null;
  sourceModuleId?: string | null;
}

export interface SeedTemplateDefinition {
  id: string;
  name: string;
  version: string;
  domain: string;
  scenario: string;
  identityOverlay: string;
  contextOverlay: string;
  executionBias: string;
  toolPolicyOverlay?: string | null;
  outputStyle?: string | null;
  retrievalHints: Record<string, unknown>;
  selectionRules: Record<string, unknown>;
  fewShotRefs: string[];
  sourceAppId?: string | null;
  sourceModuleId?: string | null;
}

export interface ApplicationManifestSummary {
  appId: string;
  displayName: string;
  version: string;
  manifestPath: string;
  owner?: string | null;
  description?: string | null;
  defaultLoad: boolean;
  moduleDependencies: string[];
  capabilityModuleIds: string[];
  sceneModuleIds: string[];
  defaultPromptProfileId?: string | null;
  subagentPromptProfileId?: string | null;
  defaultSeedTemplateId?: string | null;
  promptProfileFiles: string[];
  seedTemplateFiles: string[];
  configDefaultsRef?: { type: string; locator: string } | null;
  frontendEntryRoute?: string | null;
  dashboardRef?: { type: string; locator: string } | null;
}

export interface ApplicationConfigBinding {
  appId: string;
  active: boolean;
  importantConfig: Record<string, unknown>;
  updatedAt: string;
}

export interface MCPWorkspaceOption {
  label: string;
  value: string;
  source: string;
}

export interface MCPServerDefinition {
  id: string;
  displayName: string;
  description?: string | null;
  transport: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  cwd?: string | null;
  enabled: boolean;
  keepAlive: boolean;
  toolPrefix: string;
  origin: string;
  sourcePath?: string | null;
  timeoutMs: number;
}

export interface MCPToolBinding {
  serverId: string;
  serverDisplayName: string;
  remoteToolName: string;
  exposedName: string;
  description?: string | null;
  inputSchema: Record<string, unknown>;
}

export interface MCPSyncedServer {
  id: string;
  displayName: string;
  status: string;
  error?: string | null;
  tools: MCPToolBinding[];
  toolCount: number;
  lastSyncedAt?: string | null;
  sourcePath?: string | null;
  origin?: string | null;
}

export interface MCPBridgeState {
  generatedAt: string;
  projectWorkspace: string;
  workspaceOptions: MCPWorkspaceOption[];
  servers: MCPServerDefinition[];
  syncedServers: MCPSyncedServer[];
  tools: MCPToolBinding[];
  availableImports: MCPServerDefinition[];
}

export interface PromptCompileArtifactRecord {
  id: string;
  appId: string;
  projectId: string;
  taskId?: string | null;
  agentRunId?: string | null;
  modelInvocationId?: string | null;
  promptProfileVersionId: string;
  seedTemplateVersionId?: string | null;
  runType: string;
  taskType: string;
  scenario?: string | null;
  registeredTools: Array<Record<string, unknown>>;
  systemSections: Record<string, string>;
  userSections: Record<string, string>;
  compiledMessagesRef: { type: string; locator: string };
  contentHash: string;
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

export interface TaskRuntimeControlSummary {
  pauseRequested: boolean;
  activeSnapshotId?: string | null;
  lastSafeStopAt?: string | null;
  snapshotCount: number;
  restorableSnapshotCount: number;
  consumedSnapshotCount: number;
  resumeStatus: string;
  canResume: boolean;
  canRequestPause: boolean;
  recommendedResumeToken?: string | null;
  recommendedResumeMessage?: string | null;
  latestSnapshot?: SnapshotRecord | null;
  latestRestorableSnapshot?: SnapshotRecord | null;
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
    sharedSpaces: number;
    spaceMounts: number;
    permissionTuples: number;
    pausedTasks: number;
    restorableSnapshots: number;
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
  runtimeControl: TaskRuntimeControlSummary;
  routeDecisions: RouteDecisionRecord[];
  modelInvocations: ModelInvocationRecord[];
}

export interface TaskControlActionResponse {
  status: string;
  task: TaskSummaryRecord;
  queue?: string;
  queueDepth?: number;
  workItem?: Record<string, unknown>;
  outboxRecord?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface NodeDetailResponse {
  node: NodeSummaryRecord;
  versions: NodeVersionRecord[];
  annotations: SourceAnnotationRecord[];
  outgoingEdges: EdgeRecord[];
  incomingEdges: EdgeRecord[];
}