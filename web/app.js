const ui = {
  serverState: document.querySelector("#serverState"),
  voiceTopState: document.querySelector("#voiceTopState"),
  visionTopState: document.querySelector("#visionTopState"),
  privacyTopState: document.querySelector("#privacyTopState"),
  systemClock: document.querySelector("#systemClock"),
  stopControl: document.querySelector("#stopControl"),
  dockStop: document.querySelector("#dockStop"),
  commandForm: document.querySelector("#commandForm"),
  commandInput: document.querySelector("#commandInput"),
  voiceButton: document.querySelector("#voiceButton"),
  wakeToggle: document.querySelector("#wakeToggle"),
  activeMode: document.querySelector("#activeMode"),
  liveOperation: document.querySelector("#liveOperation"),
  messages: document.querySelector("#messages"),
  conversation: document.querySelector("#conversation"),
  projectSelect: document.querySelector("#projectSelect"),
  modeSelect: document.querySelector("#modeSelect"),
  privateToggle: document.querySelector("#privateToggle"),
  agentsView: document.querySelector("#agentsView"),
  planView: document.querySelector("#planView"),
  riskBadge: document.querySelector("#riskBadge"),
  tasksView: document.querySelector("#tasksView"),
  systemView: document.querySelector("#systemView"),
  capabilitiesView: document.querySelector("#capabilitiesView"),
  memoryForm: document.querySelector("#memoryForm"),
  memoryInput: document.querySelector("#memoryInput"),
  memoryView: document.querySelector("#memoryView"),
  memoryMode: document.querySelector("#memoryMode"),
  memoryCategory: document.querySelector("#memoryCategory"),
  memorySubject: document.querySelector("#memorySubject"),
  memoryEnvironment: document.querySelector("#memoryEnvironment"),
  memorySensitivity: document.querySelector("#memorySensitivity"),
  memoryExpiry: document.querySelector("#memoryExpiry"),
  memoryDecisionFields: document.querySelector("#memoryDecisionFields"),
  memoryDecisionAlternatives: document.querySelector("#memoryDecisionAlternatives"),
  memoryDecisionEvidence: document.querySelector("#memoryDecisionEvidence"),
  memoryDecisionAssumptions: document.querySelector("#memoryDecisionAssumptions"),
  memoryDecisionRisks: document.querySelector("#memoryDecisionRisks"),
  memoryDecisionReason: document.querySelector("#memoryDecisionReason"),
  memoryDecisionOutcome: document.querySelector("#memoryDecisionOutcome"),
  memoryMetrics: document.querySelector("#memoryMetrics"),
  memoryExport: document.querySelector("#memoryExport"),
  memoryFilterForm: document.querySelector("#memoryFilterForm"),
  memorySearch: document.querySelector("#memorySearch"),
  memoryCategoryFilter: document.querySelector("#memoryCategoryFilter"),
  memoryStatusFilter: document.querySelector("#memoryStatusFilter"),
  memorySensitivityFilter: document.querySelector("#memorySensitivityFilter"),
  memoryCategories: document.querySelector("#memoryCategories"),
  memoryConflicts: document.querySelector("#memoryConflicts"),
  memoryEditDialog: document.querySelector("#memoryEditDialog"),
  memoryEditForm: document.querySelector("#memoryEditForm"),
  memoryEditId: document.querySelector("#memoryEditId"),
  memoryEditContent: document.querySelector("#memoryEditContent"),
  memoryEditSubject: document.querySelector("#memoryEditSubject"),
  memoryEditEnvironment: document.querySelector("#memoryEditEnvironment"),
  memoryEditSensitivity: document.querySelector("#memoryEditSensitivity"),
  memoryEditExpiry: document.querySelector("#memoryEditExpiry"),
  memoryEditReason: document.querySelector("#memoryEditReason"),
  memoryHistoryDialog: document.querySelector("#memoryHistoryDialog"),
  memoryHistoryView: document.querySelector("#memoryHistoryView"),
  approvalsView: document.querySelector("#approvalsView"),
  auditView: document.querySelector("#auditView"),
  voiceTurnsView: document.querySelector("#voiceTurnsView"),
  eventsView: document.querySelector("#eventsView"),
  watchForm: document.querySelector("#watchForm"),
  watchMetric: document.querySelector("#watchMetric"),
  watchOperator: document.querySelector("#watchOperator"),
  watchThreshold: document.querySelector("#watchThreshold"),
  watchInterval: document.querySelector("#watchInterval"),
  watchesView: document.querySelector("#watchesView"),
  watchAlertsView: document.querySelector("#watchAlertsView"),
  browserMetrics: document.querySelector("#browserMetrics"),
  browserNavigateForm: document.querySelector("#browserNavigateForm"),
  browserUrl: document.querySelector("#browserUrl"),
  browserInspect: document.querySelector("#browserInspect"),
  browserFillForm: document.querySelector("#browserFillForm"),
  browserFieldName: document.querySelector("#browserFieldName"),
  browserFieldValue: document.querySelector("#browserFieldValue"),
  browserClickForm: document.querySelector("#browserClickForm"),
  browserControlName: document.querySelector("#browserControlName"),
  browserMissionForm: document.querySelector("#browserMissionForm"),
  browserMissionUrl: document.querySelector("#browserMissionUrl"),
  browserMissionField: document.querySelector("#browserMissionField"),
  browserMissionValue: document.querySelector("#browserMissionValue"),
  browserMissionControl: document.querySelector("#browserMissionControl"),
  browserStateView: document.querySelector("#browserStateView"),
  browserStateShow: document.querySelector("#browserStateShow"),
  browserStateContinue: document.querySelector("#browserStateContinue"),
  browserPageView: document.querySelector("#browserPageView"),
  integrationsView: document.querySelector("#integrationsView"),
  decisionForm: document.querySelector("#decisionForm"),
  decisionObjective: document.querySelector("#decisionObjective"),
  decisionOptionA: document.querySelector("#decisionOptionA"),
  decisionOptionB: document.querySelector("#decisionOptionB"),
  decisionCriterion: document.querySelector("#decisionCriterion"),
  decisionWeight: document.querySelector("#decisionWeight"),
  decisionScoreA: document.querySelector("#decisionScoreA"),
  decisionScoreB: document.querySelector("#decisionScoreB"),
  decisionCouncil: document.querySelector("#decisionCouncil"),
  decisionUnknowns: document.querySelector("#decisionUnknowns"),
  decisionMetrics: document.querySelector("#decisionMetrics"),
  decisionConfidence: document.querySelector("#decisionConfidence"),
  decisionRecommendation: document.querySelector("#decisionRecommendation"),
  decisionEvidence: document.querySelector("#decisionEvidence"),
  decisionCases: document.querySelector("#decisionCases"),
  decisionOutcomeForm: document.querySelector("#decisionOutcomeForm"),
  decisionOutcomeCase: document.querySelector("#decisionOutcomeCase"),
  decisionOutcomeSuccess: document.querySelector("#decisionOutcomeSuccess"),
  decisionOutcomeSummary: document.querySelector("#decisionOutcomeSummary"),
  decisionExpectedSummary: document.querySelector("#decisionExpectedSummary"),
  decisionDifferenceSummary: document.querySelector("#decisionDifferenceSummary"),
  decisionRootCause: document.querySelector("#decisionRootCause"),
  decisionLesson: document.querySelector("#decisionLesson"),
  decisionConfidenceUpdate: document.querySelector("#decisionConfidenceUpdate"),
  decisionLearning: document.querySelector("#decisionLearning"),
  projectsWorkspace: document.querySelector("#projectsWorkspace"),
  researchForm: document.querySelector("#researchForm"),
  researchInput: document.querySelector("#researchInput"),
  researchMetrics: document.querySelector("#researchMetrics"),
  researchMap: document.querySelector("#researchMap"),
  researchCampaigns: document.querySelector("#researchCampaigns"),
  researchSources: document.querySelector("#researchSources"),
  engineeringMetrics: document.querySelector("#engineeringMetrics"),
  engineeringProjectName: document.querySelector("#engineeringProjectName"),
  repositoryMap: document.querySelector("#repositoryMap"),
  engineeringRuns: document.querySelector("#engineeringRuns"),
  engineeringComponents: document.querySelector("#engineeringComponents"),
  engineeringRisks: document.querySelector("#engineeringRisks"),
  projectRootForm: document.querySelector("#projectRootForm"),
  projectRootInput: document.querySelector("#projectRootInput"),
  projectRootButton: document.querySelector("#projectRootButton"),
  projectRootState: document.querySelector("#projectRootState"),
  runProjectTests: document.querySelector("#runProjectTests"),
  repairProjectTest: document.querySelector("#repairProjectTest"),
  codexProjectMission: document.querySelector("#codexProjectMission"),
  versionControlState: document.querySelector("#versionControlState"),
  documentForm: document.querySelector("#documentForm"),
  documentInput: document.querySelector("#documentInput"),
  documentFormats: document.querySelector("#documentFormats"),
  documentRuns: document.querySelector("#documentRuns"),
  dailyDate: document.querySelector("#dailyDate"),
  dailyObjective: document.querySelector("#dailyObjective"),
  dailySupporting: document.querySelector("#dailySupporting"),
  dailyFirstAction: document.querySelector("#dailyFirstAction"),
  dailyPriorities: document.querySelector("#dailyPriorities"),
  dailySchedule: document.querySelector("#dailySchedule"),
  dailySystems: document.querySelector("#dailySystems"),
  dailyRisks: document.querySelector("#dailyRisks"),
  attentionMetrics: document.querySelector("#attentionMetrics"),
  dailyAttention: document.querySelector("#dailyAttention"),
  dailyOpportunities: document.querySelector("#dailyOpportunities"),
  operationsQueryForm: document.querySelector("#operationsQueryForm"),
  operationsQueryInput: document.querySelector("#operationsQueryInput"),
  operationsGraph: document.querySelector("#operationsGraph"),
  worldModelMetrics: document.querySelector("#worldModelMetrics"),
  worldActionForm: document.querySelector("#worldActionForm"),
  worldActionSelect: document.querySelector("#worldActionSelect"),
  worldAlternativeSelect: document.querySelector("#worldAlternativeSelect"),
  worldSimulation: document.querySelector("#worldSimulation"),
  predictiveMetrics: document.querySelector("#predictiveMetrics"),
  predictiveSignals: document.querySelector("#predictiveSignals"),
  eveningDebrief: document.querySelector("#eveningDebrief"),
  missionObjective: document.querySelector("#missionObjective"),
  missionState: document.querySelector("#missionState"),
  missionRisk: document.querySelector("#missionRisk"),
  missionVerification: document.querySelector("#missionVerification"),
  contextObjective: document.querySelector("#contextObjective"),
  contextAgent: document.querySelector("#contextAgent"),
  contextPermission: document.querySelector("#contextPermission"),
  contextNext: document.querySelector("#contextNext"),
  coreStateLabel: document.querySelector("#coreStateLabel"),
  coreStateDetail: document.querySelector("#coreStateDetail"),
  voiceReadout: document.querySelector("#voiceReadout"),
  responseRouteReadout: document.querySelector("#responseRouteReadout"),
  coreFps: document.querySelector("#coreFps"),
  coreContext: document.querySelector("#coreContext"),
  coreQuality: document.querySelector("#coreQuality"),
  coreProjection: document.querySelector("#coreProjection"),
  coreInspector: document.querySelector("#coreInspector"),
  coreMemoryMetric: document.querySelector("#coreMemoryMetric"),
  coreReasoningMetric: document.querySelector("#coreReasoningMetric"),
  coreKnowledgeMetric: document.querySelector("#coreKnowledgeMetric"),
  coreAgentMetric: document.querySelector("#coreAgentMetric"),
  coreVoiceMetric: document.querySelector("#coreVoiceMetric"),
  coreMissionMetric: document.querySelector("#coreMissionMetric"),
  commandMachineName: document.querySelector("#commandMachineName"),
  commandCpuGauge: document.querySelector("#commandCpuGauge"),
  commandCpuUsage: document.querySelector("#commandCpuUsage"),
  commandCpuBar: document.querySelector("#commandCpuBar"),
  commandCpuDetail: document.querySelector("#commandCpuDetail"),
  commandRamGauge: document.querySelector("#commandRamGauge"),
  commandRamUsage: document.querySelector("#commandRamUsage"),
  commandRamBar: document.querySelector("#commandRamBar"),
  commandRamDetail: document.querySelector("#commandRamDetail"),
  commandGpuGauge: document.querySelector("#commandGpuGauge"),
  commandGpuUsage: document.querySelector("#commandGpuUsage"),
  commandGpuBar: document.querySelector("#commandGpuBar"),
  commandGpuDetail: document.querySelector("#commandGpuDetail"),
  commandDiskGauge: document.querySelector("#commandDiskGauge"),
  commandDiskPercent: document.querySelector("#commandDiskPercent"),
  commandDiskGaugeDetail: document.querySelector("#commandDiskGaugeDetail"),
  commandDiskBar: document.querySelector("#commandDiskBar"),
  commandDiskUsage: document.querySelector("#commandDiskUsage"),
  commandUptime: document.querySelector("#commandUptime"),
  commandPower: document.querySelector("#commandPower"),
  commandPlatform: document.querySelector("#commandPlatform"),
  commandProcesses: document.querySelector("#commandProcesses"),
  commandAgentCount: document.querySelector("#commandAgentCount"),
  commandTaskCount: document.querySelector("#commandTaskCount"),
  commandApprovalCount: document.querySelector("#commandApprovalCount"),
  commandAgentList: document.querySelector("#commandAgentList"),
  commandEngineList: document.querySelector("#commandEngineList"),
  commandCpuTrace: document.querySelector("#commandCpuTrace"),
  commandRamTrace: document.querySelector("#commandRamTrace"),
  commandGpuTrace: document.querySelector("#commandGpuTrace"),
  commandMissionObjective: document.querySelector("#commandMissionObjective"),
  commandMissionState: document.querySelector("#commandMissionState"),
  commandMissionRisk: document.querySelector("#commandMissionRisk"),
  commandMissionVerification: document.querySelector("#commandMissionVerification"),
  commandTimeline: document.querySelector("#commandTimeline"),
  openCommandSearch: document.querySelector("#openCommandSearch"),
  toggleFocusMode: document.querySelector("#toggleFocusMode"),
  commandPalette: document.querySelector("#commandPalette"),
  commandPaletteInput: document.querySelector("#commandPaletteInput"),
  commandPaletteResults: document.querySelector("#commandPaletteResults"),
  bootSequence: document.querySelector("#bootSequence"),
  skipBoot: document.querySelector("#skipBoot"),
  deviceTrustState: document.querySelector("#deviceTrustState"),
  deviceTrustDetail: document.querySelector("#deviceTrustDetail"),
  deviceIpcState: document.querySelector("#deviceIpcState"),
  cloudRouterState: document.querySelector("#cloudRouterState"),
};

let controlStopped = false;
let activeCoreState = "dormant";
let audioContext = null;
const conversationId = "auris-primary";
let wakeModeActive = false;
let lastVoiceStatus = {};
let voiceStatusRequestActive = false;
let statusRequestActive = false;
let operationalRefresh = null;
let csrfToken = "";
let projectsCache = [];
let memoryCache = new Map();
let latestAgents = [];
let latestWorldSnapshotId = "";
const backgroundCodingTasks = new Set();
let workspaceRequestGeneration = 0;
const telemetryHistory = { cpu: [], memory: [], gpu: [] };

const coreCanvas = document.querySelector("#aurisCore");
let coreVisual = createInertCore();
coreCanvas.addEventListener("auris-render-metrics", (event) => {
  ui.coreFps.textContent = `${event.detail.fps} FPS // ${event.detail.nodes} NODES // ${event.detail.links || 0} LINKS`;
  ui.coreProjection.textContent = event.detail.projection || "3D";
  coreCanvas.dataset.pixelCheck = event.detail.nonblank ? "nonblank" : "pending";
});
coreCanvas.addEventListener("auris-core-hover", (event) => renderCoreInspector(event.detail));
coreCanvas.addEventListener("auris-core-focus", (event) => {
  renderCoreInspector(event.detail, true);
  const focusName = event.detail?.name || "";
  document.querySelectorAll("[data-core-focus]").forEach((button) => {
    button.classList.toggle("active", button.dataset.coreFocus === focusName);
  });
});

ui.commandForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const command = ui.commandInput.value.trim();
  if (!command) return;
  ui.commandInput.value = "";
  addTranscript("user", "DEVANSH", command);
  await runCommand(command);
});

ui.voiceButton.addEventListener("click", listenForCommand);
ui.wakeToggle.addEventListener("change", toggleWakeMode);
ui.stopControl.addEventListener("click", toggleEmergencyStop);
ui.dockStop.addEventListener("click", toggleEmergencyStop);
ui.openCommandSearch.addEventListener("click", openCommandPalette);
ui.toggleFocusMode.addEventListener("click", toggleNeuralFocus);
ui.skipBoot.addEventListener("click", dismissBootSequence);
ui.commandPaletteInput.addEventListener("input", renderCommandPalette);
ui.memoryForm.addEventListener("submit", saveMemory);
ui.memoryCategory.addEventListener("change", syncMemoryDecisionFields);
ui.memoryFilterForm.addEventListener("submit", async (event) => { event.preventDefault(); await loadMemories(); });
ui.memoryExport.addEventListener("click", exportMemories);
ui.memoryEditForm.addEventListener("submit", saveMemoryCorrection);
ui.modeSelect.addEventListener("change", syncSessionControls);
ui.privateToggle.addEventListener("change", syncSessionControls);
ui.projectSelect.addEventListener("change", async () => {
  syncProjectContext();
  await Promise.all([loadMemories(), loadAdvancedWorkspaces(), loadDecisions(), loadBrowserStatus()]);
});
ui.projectRootForm.addEventListener("submit", saveProjectRoot);
ui.codexProjectMission.addEventListener("click", () => {
  if (window.matchMedia("(max-width: 640px)").matches) setWorkspace("command");
  ui.commandInput.value = "Use Codex to implement  in this project";
  ui.commandInput.focus();
  ui.commandInput.setSelectionRange(23, 23);
});
ui.researchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const topic = ui.researchInput.value.trim();
  if (!topic) return;
  ui.researchInput.value = "";
  await runCommand(`AURIS, research ${topic}`);
});
ui.documentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const filename = ui.documentInput.value.trim();
  if (!filename) return;
  ui.documentInput.value = "";
  await runCommand(`AURIS, summarize document ${filename}`);
});
ui.operationsQueryForm.addEventListener("submit", loadOperationsQuery);
ui.worldActionForm.addEventListener("submit", simulateWorldAction);
ui.decisionForm.addEventListener("submit", analyseDecision);
ui.decisionOutcomeForm.addEventListener("submit", recordDecisionOutcome);
ui.watchForm.addEventListener("submit", createProactiveWatch);
ui.browserNavigateForm.addEventListener("submit", navigateBrowser);
ui.browserInspect.addEventListener("click", () => runBrowserDirective("AURIS, inspect the current browser page"));
ui.browserFillForm.addEventListener("submit", prepareBrowserFill);
ui.browserClickForm.addEventListener("submit", prepareBrowserClick);
ui.browserMissionForm.addEventListener("submit", prepareBrowserMission);
ui.browserStateShow.addEventListener("click", () => runBrowserDirective("AURIS, show active browser mission"));
ui.browserStateContinue.addEventListener("click", () => runBrowserDirective("AURIS, continue browser mission"));

document.querySelector("#refreshStatus").addEventListener("click", loadStatus);
document.querySelector("#refreshTasks").addEventListener("click", loadTasks);
document.querySelector("#refreshApprovals").addEventListener("click", loadApprovals);
document.querySelector("#refreshAudit").addEventListener("click", loadAudit);
document.querySelector("#refreshEvents").addEventListener("click", loadEvents);
document.querySelector("#refreshIntegrations").addEventListener("click", loadIntegrations);
document.querySelector("#refreshDecisions").addEventListener("click", loadDecisions);
document.querySelector("#refreshWorkspaces").addEventListener("click", loadAdvancedWorkspaces);
document.querySelector("#refreshBrowser").addEventListener("click", loadBrowserStatus);

document.addEventListener("click", (event) => {
  const qualityButton = event.target.closest("button[data-quality]");
  if (qualityButton) setVisualQuality(qualityButton.dataset.quality);

  const coreViewButton = event.target.closest("button[data-core-view]");
  if (coreViewButton) setCoreViewMode(coreViewButton.dataset.coreView);

  const coreFocusButton = event.target.closest("button[data-core-focus]");
  if (coreFocusButton) coreVisual.focusCluster(coreFocusButton.dataset.coreFocus);

  const paletteItem = event.target.closest("button[data-palette-view], button[data-palette-command]");
  if (paletteItem) activatePaletteItem(paletteItem);

  const nav = event.target.closest("[data-view]");
  if (nav && !nav.disabled) setWorkspace(nav.dataset.view);

  const target = event.target.closest("[data-view-target]");
  if (target) setWorkspace(target.dataset.viewTarget);

  const quick = event.target.closest("[data-command]");
  if (quick) {
    const command = quick.dataset.command;
    addTranscript("user", "DEVANSH", command);
    runCommand(command);
  }

  const approval = event.target.closest("button[data-approval]");
  if (approval) decideApproval(approval.dataset.approval, approval.dataset.action);

  const memory = event.target.closest("button[data-memory-action]");
  if (memory) {
    const memoryId = memory.dataset.memory;
    if (memory.dataset.memoryAction === "delete") removeMemory(memoryId);
    if (memory.dataset.memoryAction === "correct") openMemoryCorrection(memoryId);
    if (memory.dataset.memoryAction === "history") openMemoryHistory(memoryId);
  }

  const conflict = event.target.closest("button[data-memory-conflict]");
  if (conflict) resolveConflict(conflict.dataset.memoryConflict, conflict.dataset.memoryChoice);

  const category = event.target.closest("input[data-memory-category]");
  if (category) toggleMemoryCategory(category.dataset.memoryCategory, category.checked);

  const dialogClose = event.target.closest("button[data-dialog-close]");
  if (dialogClose) document.querySelector(`#${CSS.escape(dialogClose.dataset.dialogClose)}`)?.close();

  const scheduledEvent = event.target.closest("button[data-event]");
  if (scheduledEvent) cancelEvent(scheduledEvent.dataset.event);

  const watchAction = event.target.closest("button[data-watch-action]");
  if (watchAction) changeProactiveWatch(watchAction.dataset.watch, watchAction.dataset.watchAction);

  const project = event.target.closest("button[data-project]");
  if (project) {
    ui.projectSelect.value = project.dataset.project;
    syncProjectContext();
    loadMemories();
    loadAdvancedWorkspaces();
  }

  const openProject = event.target.closest("button[data-open-project]");
  if (openProject) {
    ui.projectSelect.value = openProject.dataset.openProject;
    syncProjectContext();
    loadMemories();
    addTranscript("user", "DEVANSH", "AURIS, open this project");
    runCommand("AURIS, open this project");
  }
});

window.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    openCommandPalette();
  }
  if (event.key === "Escape" && document.body.classList.contains("neural-focus")) {
    toggleNeuralFocus(false);
  }
});

async function runCommand(command, voiceTurnId = null) {
  if (controlStopped && !/resume/i.test(command)) {
    addTranscript("warning", "AURIS", "The emergency stop is active. Resume AURIS before issuing a new operation.");
    return;
  }

  const screenCommand = isScreenCommand(command);
  const deviceIntent = screenCommand || /\b(open|navigate|inspect|fill|click|launch|start|run|close|quit|exit|terminate|focus|switch to|minimize|minimise|maximize|maximise|restore|volume|mute|unmute|track|play media|pause media|list files|show files|create|make|append|rename|copy|move|recycle)\b/i.test(command);
  if (screenCommand) {
    ui.visionTopState.innerHTML = "<i></i>VISION ACTIVE";
    ui.visionTopState.className = "signal listening";
  }
  setCoreState(deviceIntent ? "executing" : "planning");
  ui.responseRouteReadout.textContent = deviceIntent ? "DEVICE" : "ROUTING";
  setOperation(
    deviceIntent ? "WINDOWS AGENT" : "SUPERVISOR",
    deviceIntent
      ? "Resolving and executing Windows device action..."
      : "Building and policy-checking the mission graph..."
  );

  try {
    const data = await fetchJson("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command,
        project_id: ui.projectSelect.value || null,
        mode: ui.modeSelect.value,
        private: isPrivate(),
        conversation_id: conversationId,
        voice_turn_id: voiceTurnId,
      }),
    });

    renderPlan(data.plan, data.workflow, data.result.verification_report);
    if (data.plan.context_resolution) {
      addTranscript("system", "APP CONTEXT", `${data.plan.context_resolution.resolved_command} // VERIFIED PRIOR TASK ${shortId(data.plan.context_resolution.source_task_id)}`);
    }
    if (data.system_status) renderSystem(data.system_status);
    if (data.result.control) renderControlState(data.result.control);

    const blocked = ["blocked", "failed", "partially_completed", "interrupted"].includes(data.plan.state);
    addTranscript(blocked ? "warning" : "auris", "AURIS", data.result.message);
    if (data.result.generated_project?.project_id) {
      await loadProjects();
      ui.projectSelect.value = data.result.generated_project.project_id;
      syncProjectContext();
    }
    if (data.result.background) backgroundCodingTasks.add(data.plan.task_id);
    if (data.result.intelligence) {
      renderNeuralRoute(data.result.intelligence);
      const intelligence = data.result.intelligence;
      addTranscript(
        "system",
        "NEURAL ROUTE",
        `${String(intelligence.route || "quality").toUpperCase()} // ${intelligence.model || intelligence.provider} // ${intelligence.duration_ms ?? 0} MS`,
      );
    }
    if (data.result.device_action?.items?.length) {
      addTranscript("system", "DEVICE RESULT", data.result.device_action.items.slice(0, 15).join("  |  "));
    }
    if (data.result.device_action?.command_fabric) {
      const fabric = data.result.device_action.command_fabric;
      addTranscript("verification", "DEVICE FABRIC", `${shortId(fabric.command_id)} // ${fabric.permission_scope} // SIGNATURE ${fabric.signature_verified ? "VERIFIED" : "REJECTED"} // NONCE ${fabric.nonce_claimed ? "CLAIMED" : "REJECTED"}`);
    }
    if (data.result.device_actions?.length > 1) {
      addTranscript(
        "verification",
        "DEVICE SEQUENCE",
        data.result.device_actions.map((item, index) => `${index + 1}/${data.result.device_actions.length} ${item.action?.label || "ACTION"} // ${item.ok ? "VERIFIED" : "FAILED"}`).join("  |  "),
      );
    }
    if (data.result.project_action) {
      const projectAction = data.result.project_action;
      addTranscript("system", "PROJECT WINDOW", `${projectAction.project_name} // ${projectAction.application || "WINDOWS"} // ${projectAction.observed_path ? "EXACT ROOT OBSERVED" : "NOT OBSERVED"}`);
      if (projectAction.command_fabric) {
        const fabric = projectAction.command_fabric;
        addTranscript("verification", "DEVICE FABRIC", `${shortId(fabric.command_id)} // ${fabric.permission_scope} // SIGNATURE ${fabric.signature_verified ? "VERIFIED" : "REJECTED"} // NONCE ${fabric.nonce_claimed ? "CLAIMED" : "REJECTED"}`);
      }
    }
    if (data.result.file_action?.items?.length) {
      addTranscript("system", "FILE RESULTS", data.result.file_action.items.slice(0, 12).map((item) => item.path).join("  |  "));
    }
    if (data.result.research_action) {
      const research = data.result.research_action;
      const ledger = research.coverage_ledger || {};
      if (research.sources?.length) {
        addTranscript("system", "RESEARCH SOURCES", research.sources.map((source) => `[${source.source_id}] ${source.title} // ${source.url}`).join("  |  "));
      }
      if (research.claims?.length) {
        addTranscript("system", "CLAIM EVIDENCE", research.claims.map((claim) => `${claim.claim_id} ${String(claim.status).toUpperCase()} // ${claim.source_ids.join("+")}`).join("  |  "));
      }
      addTranscript("verification", "RESEARCH COVERAGE", `${String(research.mode || "rapid").toUpperCase()} // ${ledger.sources_processed || 0} SOURCES // ${ledger.branch_coverage_percent || 0}% BRANCHES // ${ledger.counterevidence_queries || 0} COUNTER QUERIES // ${research.definition_of_done_met ? "DEFINITION OF DONE MET" : "PARTIAL"}`);
    }
    if (data.result.document_action?.document) {
      const document = data.result.document_action.document;
      addTranscript("system", "DOCUMENT", `${document.name} // ${document.format} // ${document.bytes_read} bytes // read only`);
    }
    if (data.result.artifact_action?.artifact) {
      const work = data.result.artifact_action;
      const artifact = work.artifact;
      const checkCount = artifact.checks?.filter((check) => check.passed).length || 0;
      addTranscript(
        "system",
        "WORK PRODUCT",
        `${String(artifact.kind || work.operation || "artifact").replaceAll("_", " ").toUpperCase()} // ${artifact.path} // ${artifact.files?.length || artifact.paragraphs || 0} ITEMS`,
      );
      addTranscript(
        work.ok ? "verification" : "warning",
        "ARTIFACT VERIFICATION",
        `${work.ok ? "VERIFIED" : "FAILED"} // ${checkCount}/${artifact.checks?.length || 0} CHECKS // ${artifact.sha256 || artifact.manifest_sha256 || "NO HASH"}${artifact.generated_code_executed === false ? " // CODE NOT EXECUTED" : ""}`,
      );
    }
    if (data.result.coding_action) {
      const coding = data.result.coding_action;
      addTranscript("system", "CODING CHECK", `${coding.operation} // ${coding.exit_code ?? "read only"} // ${coding.duration_ms} ms`);
      if (coding.proposal) {
        const proposal = coding.proposal;
        const codexProposal = proposal.engine === "codex_cli";
        addTranscript("system", codexProposal ? "SIGNED CODEX PROPOSAL" : "SIGNED REPAIR PROPOSAL", `${shortId(proposal.proposal_id)} // ${String(proposal.isolation_kind || "isolated").replaceAll("_", " ").toUpperCase()} // ${proposal.files?.length || 0} FILES // +${proposal.diff_stats?.added_lines || 0} -${proposal.diff_stats?.removed_lines || 0} // APPROVAL REQUIRED`);
        addTranscript(
          "verification",
          codexProposal ? "CODEX VALIDATION" : "REPAIR TEST GATE",
          codexProposal
            ? `${proposal.validation?.passed_checks || 0}/${proposal.validation?.total_checks || 0} STATIC CHECKS // TEST EXECUTION SANDBOX ONLY // SOURCE UNCHANGED`
            : `TARGETED ${proposal.verified_targeted?.passed ? "PASSED" : "FAILED"} // COMPLETE ${proposal.verified_full?.passed ? "PASSED" : "FAILED"} // SOURCE UNCHANGED`,
        );
      } else if (coding.operation === "apply_repair") {
        addTranscript("verification", "REPAIR APPLICATION", `${shortId(coding.proposal_id)} // ${coding.ok ? "APPLIED AND VERIFIED" : coding.rolled_back ? "FAILED AND ROLLED BACK" : "BLOCKED"}`);
      } else if (coding.operation === "apply_codex_workspace_change") {
        addTranscript("verification", "CODEX APPLICATION", `${shortId(coding.proposal_id)} // ${coding.ok ? "APPLIED AND VERIFIED" : coding.rolled_back ? "FAILED AND ROLLED BACK" : "BLOCKED"}`);
      }
    }
    if (data.result.event) {
      addTranscript("system", "EVENT ENGINE", `${data.result.event.title} // ${formatTime(data.result.event.due_at)} // scheduled`);
    }
    if (data.result.browser_action) {
      renderBrowserResult(data.result.browser_action);
      const browser = data.result.browser_action;
      addTranscript(
        browser.ok ? "verification" : "warning",
        "BROWSER WORKER",
        `${String(browser.action?.kind || "browser").toUpperCase()} // ${browser.page?.title || browser.page?.url || "NO VERIFIED PAGE"} // ${browser.command_fabric?.signature_verified ? "SIGNATURE VERIFIED" : "NO FABRIC EVIDENCE"}`,
      );
    }
    if (data.result.proactive_action) {
      const proactive = data.result.proactive_action;
      const watch = proactive.watch;
      addTranscript(
        "system",
        "PROACTIVE ENGINE",
        watch
          ? `${String(proactive.operation).toUpperCase()} // ${String(watch.metric).replaceAll("_", " ").toUpperCase()} // ADVISORY ONLY // NO AUTO ACTION`
          : `${String(proactive.operation).toUpperCase()} // ${proactive.watches?.length || 0} WATCHES`,
      );
    }
    if (data.result.communications_action?.items?.length) {
      const operation = data.result.communications_action.operation;
      const items = data.result.communications_action.items.slice(0, 12).map((item) => {
        if (operation === "calendar") {
          return `${item.subject} // ${formatTime(item.start_at)} // ${item.location || "no location"}`;
        }
        if (operation === "search_contacts") {
          return `${item.name || "Unnamed contact"} // ${item.company || "no company"} // ${item.email || item.mobile_phone || item.business_phone || "no contact detail"}`;
        }
        return `${item.subject} // ${item.sender} // ${formatTime(item.received_at)}${item.preview ? ` // ${item.preview}` : ""}`;
      });
      const label = operation === "calendar" ? "CALENDAR" : operation === "search_contacts" ? "CONTACTS" : "EMAIL RESULTS";
      addTranscript("system", label, items.join("  |  "));
    }
    if (data.result.verification) {
      addTranscript("verification", "VERIFICATION", data.result.verification);
    }

    setCoreState(blocked ? "warning" : data.result.background ? "executing" : data.plan.state === "awaiting_approval" ? "approval" : "completed");
    setOperation(data.plan.state.toUpperCase(), `Mission ${shortId(data.plan.task_id)} // ${data.result.verification || "Result recorded"}`);
    const verificationLabel = taskVerificationLabel({ ...data.plan, result: data.result });
    ui.missionVerification.textContent = verificationLabel;
    ui.commandMissionVerification.textContent = verificationLabel;
    if (!data.result.background) playTone(blocked ? "warning" : "complete");
    await speakResponse(data.result.message, voiceTurnId);
    void refreshOperationalData();
    window.setTimeout(() => {
      if (!data.result.background && !controlStopped && activeCoreState !== "listening") setCoreState("dormant");
    }, 2400);
  } catch (error) {
    addTranscript("warning", "AURIS", error.message);
    setCoreState("warning");
    setOperation("OPERATION HALTED", error.message);
    playTone("warning");
    await loadStatus();
  } finally {
    if (screenCommand) {
      ui.visionTopState.innerHTML = "<i></i>VISION IDLE";
      ui.visionTopState.className = "signal";
    }
  }
}

function isScreenCommand(command) {
  return /(?:what(?:'s| is).*screen|describe.*screen|read.*screen|inspect.*screen|analy[sz]e.*screen|look at.*screen|what can you see)/i.test(command);
}

async function listenForCommand() {
  if (controlStopped) return;
  ui.voiceButton.disabled = true;
  ui.voiceButton.classList.add("listening");
  ui.voiceButton.innerHTML = "<span></span>LISTENING";
  ui.voiceTopState.className = "signal listening";
  ui.voiceTopState.innerHTML = "<i></i>VOICE LISTENING";
  setCoreState("listening");
  setOperation("VOICE INPUT", "Listening through the Windows microphone. Speak now...");
  playTone("listen");

  try {
    const data = await fetchJson("/api/voice/listen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ timeout_seconds: 9, private: isPrivate() }),
    });
    const transcript = data.voice.text.trim();
    ui.commandInput.value = transcript;
    setCoreState("understanding");
    setOperation("VOICE TRANSCRIPT", `${transcript} // ${data.voice.input_provider || "LOCAL SPEECH"}`);
    addTranscript("user", "DEVANSH // VOICE", transcript);
    await runCommand(transcript, data.voice.turn_id || null);
  } catch (error) {
    addTranscript("warning", "VOICE SYSTEM", error.message);
    setCoreState("warning");
    setOperation("VOICE INPUT", error.message);
  } finally {
    ui.voiceButton.disabled = controlStopped;
    ui.voiceButton.classList.remove("listening");
    ui.voiceButton.innerHTML = "<span></span>LISTEN";
    renderVoiceState(lastVoiceStatus);
  }
}

async function toggleWakeMode() {
  const requested = Boolean(ui.wakeToggle.checked) && !controlStopped;
  ui.wakeToggle.disabled = true;
  try {
    const data = await fetchJson("/api/voice/background", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: requested }),
    });
    lastVoiceStatus = data.voice;
    renderVoiceState(lastVoiceStatus);
    setOperation(
      requested ? "BACKGROUND VOICE" : "VOICE STANDBY",
      requested
        ? "AURIS is listening locally for its wake phrase, even when this dashboard is closed."
        : "Background wake listening is disabled. Push-to-talk remains available."
    );
  } catch (error) {
    ui.wakeToggle.checked = wakeModeActive;
    addTranscript("warning", "VOICE SYSTEM", error.message);
  } finally {
    ui.wakeToggle.disabled = controlStopped;
  }
}

async function speakResponse(text, voiceTurnId = null) {
  try {
    await fetchJson("/api/voice/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, rate: 0, voice_turn_id: voiceTurnId }),
    });
  } catch (error) {
    addTranscript("warning", "VOICE SYSTEM", `AURIS voice output was unavailable: ${error.message}`);
  }
}

async function loadStatus() {
  if (statusRequestActive) return;
  statusRequestActive = true;
  try {
    const data = await fetchJson("/api/status");
    const status = data.status;
    controlStopped = status.control.stopped;
    renderControlState(status.control);
    renderSystem(status.device, status.device_trust, status.local_ipc, status.cloud_channel, status.model);
    renderModelStandby(status.model);
    renderAgents(status.agents);
    renderCommandTelemetry(status);
    lastVoiceStatus = status.voice || {};
    renderVoiceState(lastVoiceStatus);
    renderVoiceTurns(lastVoiceStatus.recent_turns || []);
    if (status.capability_registry) renderCapabilities(status.capability_registry);
    if (!controlStopped && activeCoreState === "warning") setCoreState("dormant");
  } catch (error) {
    ui.serverState.className = "signal critical";
    ui.serverState.innerHTML = "<i></i>AURIS OFFLINE";
    setCoreState("critical");
  } finally {
    statusRequestActive = false;
  }
}

async function loadVoiceStatus() {
  if (voiceStatusRequestActive || document.hidden) return;
  voiceStatusRequestActive = true;
  try {
    const data = await fetchJson("/api/voice/status");
    lastVoiceStatus = data.voice || {};
    renderVoiceState(lastVoiceStatus);
    renderVoiceTurns(lastVoiceStatus.recent_turns || []);
  } catch (_error) {
    // The full status refresh owns offline presentation and recovery.
  } finally {
    voiceStatusRequestActive = false;
  }
}

let voiceTurnSignature = "";
function renderVoiceTurns(turns) {
  const signature = JSON.stringify(turns);
  if (signature === voiceTurnSignature) return;
  voiceTurnSignature = signature;
  const opened = new Set([...ui.voiceTurnsView.querySelectorAll("details[open]")].map((item) => item.dataset.turn));
  const ms = (value) => value == null ? "--" : `${Math.round(value)} ms`;
  ui.voiceTurnsView.innerHTML = turns.length ? turns.map((turn) => `
    <details data-turn="${escapeHtml(turn.turn_id)}" ${opened.has(turn.turn_id) ? "open" : ""} class="voice-turn ${turn.failure_stage ? "voice-turn-failed" : ""}">
      <summary><span>${escapeHtml(turn.source.replaceAll("_", " ").toUpperCase())}</span><strong>${escapeHtml(turn.heard || "Speech not understood")}</strong><b>${escapeHtml(turn.outcome.replaceAll("_", " ").toUpperCase())}</b></summary>
      <dl class="voice-turn-metrics">
        <div><dt>CAPTURE</dt><dd>${ms(turn.capture_ms)}</dd></div>
        <div><dt>DECODE</dt><dd>${ms(turn.decode_ms)}</dd></div>
        <div><dt>COMMAND</dt><dd>${ms(turn.command_ms)}</dd></div>
        <div><dt>TTS TO AUDIO</dt><dd>${ms(turn.first_audio_ms)}</dd></div>
        <div><dt>RECOGNITION TO AUDIO</dt><dd>${ms(turn.recognition_to_audio_ms)}</dd></div>
      </dl>
      <div class="voice-turn-evidence"><span>INPUT // ${escapeHtml(turn.input_provider)}</span>${turn.signal_state ? `<span>SIGNAL // ${escapeHtml(turn.signal_state).replaceAll("_", " ").toUpperCase()} // ${turn.peak_dbfs == null ? "--" : `${Number(turn.peak_dbfs).toFixed(1)} dBFS`}</span>` : ""}${turn.error_code ? `<span>INPUT ISSUE // ${escapeHtml(turn.error_code)}</span>` : ""}<span>TASK // ${escapeHtml(turn.task_type || "NOT DISPATCHED")}</span><span>VERIFICATION // ${escapeHtml(turn.verification)}</span><span>SPEECH // ${escapeHtml(turn.speech_state)}</span>${turn.failure_stage ? `<span>FAILED AT // ${escapeHtml(turn.failure_stage)}</span>` : ""}${turn.miss_count > 1 ? `<span>BACKGROUND MISSES // ${turn.miss_count}</span>` : ""}${turn.decoder_score != null ? `<span>DECODER SCORE // ${Number(turn.decoder_score).toFixed(2)} // UNCALIBRATED</span>` : ""}${turn.actions.map((action) => `<span>ACTION // ${escapeHtml(action.kind)} // ${action.ok ? "OBSERVED" : "FAILED"} // ${action.signed && action.nonce_claimed ? "SIGNED RECEIPT" : "NO SIGNED RECEIPT"}</span>`).join("")}</div>
    </details>`).join("") : '<p class="empty-state">No recent voice input.</p>';
}

async function loadProjects() {
  const data = await fetchJson("/api/projects");
  const selected = ui.projectSelect.value || "auris-one";
  projectsCache = data.projects;
  ui.projectSelect.innerHTML = projectsCache.map((project) =>
    `<option value="${escapeHtml(project.project_id)}">${escapeHtml(project.name)}</option>`
  ).join("");
  ui.projectSelect.value = projectsCache.some((project) => project.project_id === selected) ? selected : "auris-one";
  syncProjectContext();
}

function syncProjectContext() {
  const project = projectsCache.find((item) => item.project_id === ui.projectSelect.value);
  const fixedRoot = project?.project_id === "auris-one";
  const managedRoot = /[\\/]Documents[\\/]AURIS Work[\\/]Projects[\\/]/i.test(project?.root_path || "");
  const codexTrusted = fixedRoot || managedRoot;
  ui.projectRootInput.value = project?.root_path || "";
  ui.projectRootInput.readOnly = fixedRoot;
  ui.projectRootButton.disabled = fixedRoot;
  ui.projectRootButton.textContent = fixedRoot ? "SYSTEM ROOT" : "REGISTER ROOT";
  ui.projectRootState.textContent = project?.root_path ? "REGISTERED" : "NOT REGISTERED";
  ui.engineeringProjectName.textContent = project?.name || "Selected project";
  ui.coreContext.textContent = (project?.name || "AURIS ONE").toUpperCase();
  ui.coreContext.title = project?.name || "AURIS ONE";
  ui.runProjectTests.disabled = !fixedRoot;
  ui.runProjectTests.title = fixedRoot ? "Run the trusted AURIS test profile" : "Project-code execution is not trusted for this root";
  ui.repairProjectTest.disabled = !fixedRoot;
  ui.repairProjectTest.title = fixedRoot ? "Reproduce and prepare a supervised signed repair" : "Repair execution is not trusted for this root";
  ui.codexProjectMission.disabled = !codexTrusted;
  ui.codexProjectMission.title = codexTrusted
    ? "Describe a feature for Codex to implement in an isolated workspace"
    : "Codex execution is currently limited to AURIS and AURIS-managed project roots";
}

async function saveProjectRoot(event) {
  event.preventDefault();
  const project = projectsCache.find((item) => item.project_id === ui.projectSelect.value);
  if (!project || project.project_id === "auris-one") return;
  const rootPath = ui.projectRootInput.value.trim();
  try {
    await fetchJson("/api/projects/root", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: project.project_id, root_path: rootPath }),
    });
    addTranscript("verification", "PROJECT ROOT", rootPath ? `${project.name} // REGISTERED` : `${project.name} // DISCONNECTED`);
    await loadProjects();
    await Promise.all([loadAdvancedWorkspaces(), loadAudit()]);
  } catch (error) {
    addTranscript("warning", "PROJECT ROOT", error.message);
  }
}

async function loadConversationHistory() {
  if (isPrivate()) return;
  const data = await fetchJson(`/api/conversations/${encodeURIComponent(conversationId)}/messages?limit=24`);
  data.messages.forEach((message) => {
    const kind = message.role === "user" ? "user" : "auris";
    const label = message.role === "user" ? "DEVANSH // HISTORY" : "AURIS // HISTORY";
    addTranscript(kind, label, message.content);
  });
}

async function loadCapabilities() {
  const data = await fetchJson("/api/capabilities");
  renderCapabilities(data.registry);
}

let capabilitySignature = "";
function renderCapabilities(registry) {
  const entries = registry?.capabilities || [];
  const signature = JSON.stringify(entries);
  if (signature === capabilitySignature) return;
  capabilitySignature = signature;
  const opened = new Set([...ui.capabilitiesView.querySelectorAll("details[open]")].map((item) => item.dataset.capability));
  ui.capabilitiesView.innerHTML = entries.map((item) => `
    <details class="capability-item" data-capability="${escapeHtml(item.id)}" ${opened.has(item.id) ? "open" : ""}>
      <summary><strong>${escapeHtml(item.label)}</strong><span class="capability-state ${escapeHtml(item.state)}">${escapeHtml(item.state).replaceAll("_", " ").toUpperCase()}</span></summary>
      <p>${escapeHtml(item.scope)}</p>
      <small>${escapeHtml(item.reason)}</small>
      <dl><dt>ADAPTER</dt><dd>${escapeHtml(item.adapter)}</dd><dt>AUTHORITY</dt><dd>${item.required_permissions.map(escapeHtml).join(" // ")}</dd><dt>VERIFIER</dt><dd>${escapeHtml(item.verifier)}</dd><dt>RECORDED EVIDENCE</dt><dd>${escapeHtml(item.acceptance?.scope || "See capability audit; current runtime acceptance is not implied.")}</dd></dl>
      ${item.limitations.map((limit) => `<p class="capability-limit">${escapeHtml(limit)}</p>`).join("")}
    </details>`).join("");
}

async function loadTasks() {
  const [data, workflowData] = await Promise.all([
    fetchJson("/api/tasks?limit=18"),
    fetchJson("/api/workflows?limit=50"),
  ]);
  const workflows = new Map(workflowData.workflows.map((workflow) => [workflow.task_id, workflow]));
  let codingFinished = false;
  for (const task of data.tasks) {
    if (task.result?.background && task.state === "running") {
      backgroundCodingTasks.add(task.task_id);
    }
    if (!backgroundCodingTasks.has(task.task_id) || ["created", "planning", "running", "verifying", "recovering"].includes(task.state)) continue;
    backgroundCodingTasks.delete(task.task_id);
    codingFinished = true;
    addTranscript(task.state === "failed" ? "warning" : "auris", "CODEX MISSION", task.result?.message || task.state.replaceAll("_", " "));
    if (task.result?.verification) addTranscript("verification", "CODING EVIDENCE", task.result.verification);
    const proposal = task.result?.coding_action?.proposal;
    if (task.result?.generated_project?.project_id) {
      await loadProjects();
      ui.projectSelect.value = task.result.generated_project.project_id;
      syncProjectContext();
    }
    if (proposal) addTranscript("system", "DIFF AWAITING APPROVAL", `${proposal.files?.length || 0} FILES // +${proposal.diff_stats?.added_lines || 0} -${proposal.diff_stats?.removed_lines || 0} // SOURCE UNCHANGED`);
    if (!controlStopped) setCoreState(task.state === "awaiting_approval" ? "approval" : task.state === "failed" ? "warning" : "completed");
  }
  if (codingFinished) await Promise.all([loadApprovals(), loadAdvancedWorkspaces()]);
  ui.tasksView.innerHTML = data.tasks.length ? data.tasks.map((task) => `
    <article class="stream-item">
      <strong>${escapeHtml(task.objective)}</strong>
      <small>${escapeHtml(task.task_type)} // ${escapeHtml(task.risk_level)} // ${escapeHtml(task.state)}</small>
      ${workflows.has(task.task_id) ? `<small>ATTEMPTS ${workflows.get(task.task_id).attempts}/${workflows.get(task.task_id).max_attempts} // RECOVERIES ${workflows.get(task.task_id).recovery_count}</small>` : ""}
      ${task.result?.verification ? `<p>${escapeHtml(task.result.verification)}</p>` : ""}
      ${task.result?.verification_report ? `<span class="verification-status ${escapeHtml(task.result.verification_report.status)}">${escapeHtml(taskVerificationLabel(task))}</span>` : ""}
    </article>`).join("") : empty("No missions recorded.");

  const activeStates = new Set(["created", "planning", "running", "verifying", "recovering", "awaiting_approval", "partially_completed"]);
  const activeTask = data.tasks.find((task) => activeStates.has(task.state));
  const contextualTask = activeTask || data.tasks[0] || null;
  if (contextualTask) {
    const verification = taskVerificationLabel(contextualTask);
    ui.commandMissionObjective.textContent = contextualTask.objective;
    ui.commandMissionState.textContent = contextualTask.state.replaceAll("_", " ").toUpperCase();
    ui.commandMissionRisk.textContent = contextualTask.risk_level.replaceAll("_", " ").toUpperCase();
    ui.commandMissionVerification.textContent = verification.replaceAll("_", " ").toUpperCase();
  } else {
    ui.commandMissionObjective.textContent = "No mission recorded";
    ui.commandMissionState.textContent = "STANDBY";
    ui.commandMissionRisk.textContent = "NONE";
    ui.commandMissionVerification.textContent = "READY";
  }
}

function taskVerificationLabel(task) {
  if (task.state === "awaiting_approval") return "AWAITING APPROVAL";
  if (task.state === "partially_completed") return "PARTIAL";
  if (["created", "planning", "running", "verifying", "recovering"].includes(task.state)) return "PENDING";
  if (task.state !== "completed") return "NOT CONFIRMED";
  if (task.task_type === "general_assistance") return "REPLY GENERATED";
  return (task.result?.verification_report?.status || "NOT VERIFIED").replaceAll("_", " ").toUpperCase();
}

async function loadApprovals() {
  const data = await fetchJson("/api/approvals?status=pending");
  ui.approvalsView.innerHTML = data.approvals.length ? data.approvals.map((approval) => `
    <article class="approval-card">
      <header><span>AUTHORISATION REQUIRED</span><span>${escapeHtml(approval.risk_level).toUpperCase()}</span></header>
      <strong>${escapeHtml(approval.proposed_action)}</strong>
      <p>TARGET // ${escapeHtml(approval.target)}<br>DATA // ${escapeHtml(approval.data_summary)}<br>REVERSIBLE // ${approval.reversible ? "YES" : "NO"}</p>
      ${approval.repair_proposal ? `<div class="approval-repair-evidence"><span>${approval.repair_proposal.engine === "codex_cli" ? "SIGNED CODEX PROPOSAL" : "SIGNED REPAIR PROPOSAL"} // ${escapeHtml(shortId(approval.repair_proposal.proposal_id))}</span><strong>${escapeHtml(approval.repair_proposal.diagnosis)}</strong><small>${escapeHtml(approval.repair_proposal.isolation_kind).replaceAll("_", " ").toUpperCase()} // ${approval.repair_proposal.files.length} FILES // +${approval.repair_proposal.diff_stats.added_lines || 0} -${approval.repair_proposal.diff_stats.removed_lines || 0} // ${approval.repair_proposal.engine === "codex_cli" ? `${approval.repair_proposal.validation?.passed_checks || 0}/${approval.repair_proposal.validation?.total_checks || 0} STATIC CHECKS${approval.repair_proposal.verified_full?.passed ? " // COMPLETE TESTS PASS" : ""}` : "TARGETED PASS // COMPLETE PASS"}</small><details><summary>REVIEW EXACT DIFF</summary><pre>${escapeHtml(approval.repair_proposal.diff)}</pre></details></div>` : ""}
      <div class="card-actions">
        <button class="reject" type="button" data-approval="${escapeHtml(approval.approval_id)}" data-action="reject">REJECT</button>
        <button class="approve" type="button" data-approval="${escapeHtml(approval.approval_id)}" data-action="approve">APPROVE ONCE</button>
      </div>
    </article>`).join("") : empty("No operation is awaiting authorisation.");
}

async function loadMemories() {
  if (isPrivate()) {
    memoryCache = new Map();
    ui.coreMemoryMetric.textContent = "PRIVATE // DISABLED";
    ui.memoryMetrics.innerHTML = "";
    ui.memoryCategories.innerHTML = "";
    ui.memoryConflicts.innerHTML = "";
    ui.memoryView.innerHTML = empty("Persistent memory is disabled in this private session.");
    return;
  }
  const query = new URLSearchParams({
    project_id: ui.projectSelect.value || "",
    q: ui.memorySearch.value.trim(),
    category: ui.memoryCategoryFilter.value,
    status: ui.memoryStatusFilter.value,
    sensitivity: ui.memorySensitivityFilter.value,
    limit: "200",
  });
  const data = await fetchJson(`/api/memories?${query.toString()}`);
  memoryCache = new Map(data.memories.map((memory) => [memory.memory_id, memory]));
  ui.coreMemoryMetric.textContent = `${data.summary.current || 0} CURRENT`;
  ui.memoryMetrics.innerHTML = [
    ["CURRENT", data.summary.current],
    ["STALE", data.summary.stale],
    ["EXPIRED", data.summary.expired],
    ["CONFLICTS", data.summary.unresolved_conflicts],
    ["DISABLED", data.summary.disabled_categories],
  ].map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join("");
  if (ui.memoryCategoryFilter.options.length === 1) {
    ui.memoryCategoryFilter.insertAdjacentHTML(
      "beforeend",
      Object.keys(data.categories).map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category.replaceAll("_", " ").toUpperCase())}</option>`).join("")
    );
  }
  ui.memoryCategories.innerHTML = Object.entries(data.categories).map(([category, enabled]) => `
    <label class="${enabled ? "enabled" : "disabled"}"><input type="checkbox" data-memory-category="${escapeHtml(category)}" ${enabled ? "checked" : ""} /><span>${escapeHtml(category).toUpperCase()}</span></label>
  `).join("");
  ui.memoryConflicts.innerHTML = data.conflicts.length ? data.conflicts.map((conflict) => {
    const left = conflict.memory;
    const right = conflict.conflicting_memory;
    const analysis = conflict.analysis || {};
    const contextual = left.environment && right.environment && left.environment !== right.environment;
    const signal = (memory) => {
      const markers = [];
      if (analysis.more_recent_memory_id === memory.memory_id) markers.push("NEWER");
      if (analysis.higher_confidence_memory_id === memory.memory_id) markers.push("HIGHER CONFIDENCE");
      if ((analysis.user_confirmed_memory_ids || []).includes(memory.memory_id)) markers.push("USER CONFIRMED");
      return markers.length ? ` // ${markers.join(" // ")}` : "";
    };
    return `<article class="memory-conflict-item">
      <header><span>UNRESOLVED // ${escapeHtml(conflict.subject_key).toUpperCase()}</span><small>${escapeHtml(formatTime(conflict.created_at))}</small></header>
      <div class="memory-conflict-choice"><p>${escapeHtml(left.content)}</p><small>${escapeHtml(left.environment || "NO ENVIRONMENT").toUpperCase()} // ${escapeHtml(left.source_type).toUpperCase()} // ${Math.round(Number(left.confidence_score || 0) * 100)}%${escapeHtml(signal(left))}</small><button type="button" data-memory-conflict="${escapeHtml(conflict.conflict_id)}" data-memory-choice="${escapeHtml(left.memory_id)}">USE THIS</button></div>
      <div class="memory-conflict-choice"><p>${escapeHtml(right.content)}</p><small>${escapeHtml(right.environment || "NO ENVIRONMENT").toUpperCase()} // ${escapeHtml(right.source_type).toUpperCase()} // ${Math.round(Number(right.confidence_score || 0) * 100)}%${escapeHtml(signal(right))}</small><button type="button" data-memory-conflict="${escapeHtml(conflict.conflict_id)}" data-memory-choice="${escapeHtml(right.memory_id)}">USE THIS</button></div>
      ${contextual ? `<button class="contextual-choice" type="button" data-memory-conflict="${escapeHtml(conflict.conflict_id)}" data-memory-choice="both">KEEP CONTEXTUAL</button>` : ""}
    </article>`;
  }).join("") : "";
  ui.memoryView.innerHTML = data.memories.length ? data.memories.map((memory) => `
    <article class="memory-card state-${escapeHtml(memory.temporal_state)} ${memory.requires_resolution ? "requires-resolution" : ""} ${memory.category_enabled ? "" : "category-disabled"}">
      <header><span>${escapeHtml(memory.category).toUpperCase()} // ${escapeHtml(memory.status).toUpperCase()}</span><span>${escapeHtml(memory.temporal_state).toUpperCase()}</span></header>
      <strong>${escapeHtml(memory.content)}</strong>
      <small>SUBJECT // ${escapeHtml(memory.subject_key || "UNSPECIFIED")}<br>CONTEXT // ${escapeHtml(memory.environment || "GLOBAL")}<br>SOURCE // ${escapeHtml(memory.source_type)} // ${Math.round(Number(memory.confidence_score || 0) * 100)}%<br>SENSITIVITY // ${escapeHtml(memory.sensitivity)}<br>VERIFIED // ${escapeHtml(formatTime(memory.verified_at))}${memory.expires_at ? `<br>EXPIRES // ${escapeHtml(formatTime(memory.expires_at))}` : ""}</small>
      <div class="card-actions">
        <button type="button" data-memory-action="history" data-memory="${escapeHtml(memory.memory_id)}">HISTORY</button>
        ${["active", "conflicted"].includes(memory.status) ? `<button type="button" data-memory-action="correct" data-memory="${escapeHtml(memory.memory_id)}">CORRECT</button>` : ""}
        <button class="delete" type="button" data-memory-action="delete" data-memory="${escapeHtml(memory.memory_id)}">DELETE</button>
      </div>
    </article>`).join("") : empty("No persistent memories in this workspace.");
}

async function loadAudit() {
  const data = await fetchJson("/api/audit?limit=30");
  const events = [...data.events];
  ui.commandTimeline.innerHTML = events.length ? events.slice(0, 7).map((event) => `
    <article><time>${escapeHtml(new Date(event.timestamp).toLocaleTimeString("en-GB", { hour12: false }))}</time><span>${escapeHtml(event.event_type).replaceAll(".", " // ").toUpperCase()}</span></article>
  `).join("") : "<p>No operational events recorded.</p>";
  ui.auditView.innerHTML = events.length ? events.reverse().map((event) => {
    const details = JSON.stringify(event.payload || {}).slice(0, 180);
    return `<div class="audit-row"><span>${escapeHtml(formatTime(event.timestamp))}</span><strong>${escapeHtml(event.event_type)}</strong><span>${escapeHtml(details)}</span></div>`;
  }).join("") : empty("No audit events recorded.");
}

async function loadEvents() {
  const projectId = ui.projectSelect.value || "auris-one";
  const [data, proactiveData] = await Promise.all([
    fetchJson("/api/events?limit=100"),
    fetchJson(`/api/watches?project_id=${encodeURIComponent(projectId)}&private=${isPrivate()}`),
  ]);
  ui.eventsView.innerHTML = data.events.length ? data.events.map((event) => `
    <article class="approval-card">
      <header><span>${escapeHtml(event.status).toUpperCase()}</span><span>${escapeHtml(formatTime(event.due_at))}</span></header>
      <strong>${escapeHtml(event.title)}</strong>
      <p>${escapeHtml(event.event_id)}</p>
      ${event.status === "scheduled" ? `<footer><button type="button" data-event="${escapeHtml(event.event_id)}">CANCEL</button></footer>` : ""}
    </article>`).join("") : empty("No reminders scheduled.");
  const proactive = proactiveData.proactive;
  ui.watchesView.innerHTML = proactive.watches.length ? proactive.watches.map((watch) => {
    const relation = watch.operator === "gte" ? "AT OR ABOVE" : "AT OR BELOW";
    const state = watch.enabled ? (watch.condition_active ? "TRIGGERED" : "MONITORING") : "DISABLED";
    return `<article class="approval-card">
      <header><span>${escapeHtml(state)}</span><span>${escapeHtml(String(watch.interval_seconds / 60))} MIN</span></header>
      <strong>${escapeHtml(watch.metric.replaceAll("_", " ").toUpperCase())}</strong>
      <p>${relation} ${escapeHtml(watch.threshold)} // LAST ${watch.last_value === null ? "AWAITING SAMPLE" : escapeHtml(watch.last_value)}</p>
      <footer><button type="button" data-watch="${escapeHtml(watch.watch_id)}" data-watch-action="${watch.enabled ? "disable" : "enable"}">${watch.enabled ? "DISABLE" : "ENABLE"}</button><button class="delete" type="button" data-watch="${escapeHtml(watch.watch_id)}" data-watch-action="delete">DELETE</button></footer>
    </article>`;
  }).join("") : empty(isPrivate() ? "Watches are suppressed in Private Session." : "No proactive watches configured.");
  ui.watchAlertsView.innerHTML = proactive.alerts.length ? proactive.alerts.map((alert) => `
    <article class="approval-card"><header><span>${escapeHtml(alert.classification).toUpperCase()}</span><span>${escapeHtml(formatTime(alert.delivered_at))}</span></header><strong>${escapeHtml(alert.metric.replaceAll("_", " ").toUpperCase())}</strong><p>OBSERVED ${escapeHtml(alert.observed_value)} // THRESHOLD ${escapeHtml(alert.threshold)} // ADVISORY ONLY</p></article>
  `).join("") : empty("No threshold transitions recorded.");
}

async function createProactiveWatch(event) {
  event.preventDefault();
  if (isPrivate()) {
    addTranscript("warning", "AURIS", "Private Session cannot create durable watches.");
    return;
  }
  try {
    await fetchJson("/api/watches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: ui.projectSelect.value || "auris-one",
        metric: ui.watchMetric.value,
        operator: ui.watchOperator.value,
        threshold: Number(ui.watchThreshold.value),
        interval_seconds: Number(ui.watchInterval.value),
        cooldown_seconds: 3600,
        private: false,
      }),
    });
    addTranscript("auris", "AURIS", "Proactive watch recorded. I will alert on a threshold transition and take no automatic action.");
    await loadEvents();
  } catch (error) {
    addTranscript("warning", "AURIS", error.message);
  }
}

async function changeProactiveWatch(watchId, action) {
  try {
    if (action === "delete") {
      await fetchJson(`/api/watches/${encodeURIComponent(watchId)}`, { method: "DELETE" });
    } else {
      await fetchJson(`/api/watches/${encodeURIComponent(watchId)}/state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: action === "enable" }),
      });
    }
    await loadEvents();
  } catch (error) {
    addTranscript("warning", "AURIS", error.message);
  }
}

async function loadIntegrations() {
  const data = await fetchJson("/api/integrations");
  ui.integrationsView.innerHTML = Object.entries(data.integrations).map(([name, integration]) => {
    const state = String(integration.state || "unknown").replaceAll("_", " ").toUpperCase();
    const permissions = (integration.permissions || []).map((item) => String(item).replaceAll("_", " ").toUpperCase()).join(" // ");
    const outlookAction = name === "outlook" && integration.available && !integration.connected
      ? `<button type="button" data-command="AURIS, open Outlook (classic)">OPEN OUTLOOK</button>`
      : "";
    return `
      <article class="integration-card ${integration.connected ? "connected" : "disconnected"}">
        <header><span>${escapeHtml(name).toUpperCase()}</span><strong>${integration.connected ? "CONNECTED" : state}</strong></header>
        <dl>
          <div><dt>MODE</dt><dd>${escapeHtml(integration.mode || (name === "outlook" ? "LOCAL PROFILE" : "NOT CONNECTED"))}</dd></div>
          <div><dt>PERMISSIONS</dt><dd>${escapeHtml(permissions || "NONE")}</dd></div>
          ${integration.root_count !== undefined ? `<div><dt>ROOTS</dt><dd>${escapeHtml(integration.root_count)}</dd></div>` : ""}
        </dl>
        ${outlookAction}
      </article>`;
  }).join("");
}

async function loadBrowserStatus() {
  const projectId = encodeURIComponent(ui.projectSelect.value || "auris-one");
  const privateMode = isPrivate() ? "true" : "false";
  const [data, stateData] = await Promise.all([
    fetchJson("/api/browser/status"),
    fetchJson(`/api/application-state?project_id=${projectId}&private=${privateMode}`),
  ]);
  const browser = data.browser;
  ui.browserMetrics.innerHTML = `
    <div><span>RUNTIME</span><strong>${browser.runtime_available ? "READY" : "NOT CONNECTED"}</strong></div>
    <div><span>WORKER</span><strong>${browser.connected ? "ONLINE" : "STANDBY"}</strong></div>
    <div><span>PROVIDER</span><strong>${escapeHtml(String(browser.provider || "playwright_edge")).replaceAll("_", " ").toUpperCase()}</strong></div>
    <div><span>PROFILE</span><strong>ISOLATED</strong></div>`;
  renderBrowserApplicationState(stateData.application_state);
}

function renderBrowserApplicationState(dashboard) {
  const active = dashboard?.active;
  ui.browserStateContinue.disabled = !active || active.status !== "resumable" || !active.checkpoint?.safe_to_retry || Boolean(dashboard?.private_mode);
  if (dashboard?.private_mode) {
    ui.browserStateView.innerHTML = empty("Application checkpoints are hidden in Private Session.");
    return;
  }
  if (!active) {
    ui.browserStateView.innerHTML = empty("No interrupted browser mission in this project.");
    return;
  }
  const checkpoint = active.checkpoint || {};
  const completed = (active.completed || []).map((step) => `<li><span>STEP ${String(step.index).padStart(2, "0")}</span><strong>${escapeHtml(String(step.kind || "step")).toUpperCase()} // VERIFIED</strong></li>`).join("");
  const remaining = (active.remaining || []).map((step) => `<li><span>STEP ${String(step.index).padStart(2, "0")}</span><strong>${escapeHtml(String(step.kind || "step")).toUpperCase()} // ${escapeHtml(step.target || "approved target")}</strong></li>`).join("");
  const disposition = active.status === "resumable"
    ? "SAFE TO RETRY FROM INITIAL NAVIGATION AFTER APPROVAL"
    : "MANUAL REVIEW REQUIRED // FINAL CONTROL WILL NOT REPLAY";
  ui.browserStateView.innerHTML = `
    <dl>
      <div><dt>STATUS</dt><dd>${escapeHtml(String(active.status)).replaceAll("_", " ").toUpperCase()}</dd></div>
      <div><dt>PROGRESS</dt><dd>${checkpoint.completed_steps || 0} / ${checkpoint.total_steps || 0} VERIFIED</dd></div>
      <div><dt>POLICY</dt><dd>${disposition}</dd></div>
    </dl>
    ${completed ? `<h3>COMPLETED</h3><ul>${completed}</ul>` : ""}
    ${remaining ? `<h3>REMAINING</h3><ul>${remaining}</ul>` : ""}`;
}

async function navigateBrowser(event) {
  event.preventDefault();
  const target = ui.browserUrl.value.trim();
  if (target) await runBrowserDirective(`AURIS, navigate to ${target}`);
}

async function prepareBrowserFill(event) {
  event.preventDefault();
  const name = browserQuoted(ui.browserFieldName.value.trim());
  const value = browserQuoted(ui.browserFieldValue.value.trim());
  if (name && value) await runBrowserDirective(`AURIS, fill ${name} with ${value} in the browser`);
}

async function prepareBrowserClick(event) {
  event.preventDefault();
  const name = browserQuoted(ui.browserControlName.value.trim());
  if (name) await runBrowserDirective(`AURIS, click ${name} in the browser`);
}

async function prepareBrowserMission(event) {
  event.preventDefault();
  const values = [
    ui.browserMissionUrl.value.trim(),
    ui.browserMissionField.value.trim(),
    ui.browserMissionValue.value.trim(),
    ui.browserMissionControl.value.trim(),
  ].map(browserMissionQuoted);
  if (values.every(Boolean)) {
    await runBrowserDirective(`AURIS, run browser mission open ${values[0]} then fill ${values[1]} with ${values[2]} then click ${values[3]}`);
    ui.browserMissionValue.value = "";
  }
}

async function runBrowserDirective(command) {
  if (isPrivate()) {
    addTranscript("warning", "AURIS", "Private Session does not use the persistent isolated browser profile.");
    return;
  }
  addTranscript("user", "DEVANSH", command);
  await runCommand(command);
}

function renderBrowserResult(browser) {
  const page = browser.page || {};
  const headings = (page.headings || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const controls = (page.controls || []).map((item) => `<li><span>${escapeHtml(item.role).toUpperCase()}</span><strong>${escapeHtml(item.name)}</strong></li>`).join("");
  const checkpoints = (browser.steps || []).map((item) => `<li><span>STEP ${String(item.index).padStart(2, "0")} // ${escapeHtml(String(item.kind || "step")).toUpperCase()}</span><strong>${item.ok ? "VERIFIED" : "FAILED"}</strong></li>`).join("");
  ui.browserPageView.innerHTML = `
    <dl><div><dt>TITLE</dt><dd>${escapeHtml(page.title || "Unavailable")}</dd></div><div><dt>URL</dt><dd>${escapeHtml(page.url || "Unavailable")}</dd></div><div><dt>TRUST</dt><dd>UNTRUSTED WEB CONTENT</dd></div></dl>
    ${checkpoints ? `<h3>MISSION CHECKPOINTS</h3><ul>${checkpoints}</ul>` : ""}
    ${headings ? `<h3>HEADINGS</h3><ul>${headings}</ul>` : ""}
    ${controls ? `<h3>VISIBLE CONTROLS</h3><ul>${controls}</ul>` : empty("No visible named controls observed.")}`;
}

function browserQuoted(value) {
  if (!value) return "";
  if (!value.includes('"')) return `"${value}"`;
  if (!value.includes("'")) return `'${value}'`;
  addTranscript("warning", "BROWSER WORKER", "Field and control values cannot contain both quote styles in this bounded command grammar.");
  return "";
}

function browserMissionQuoted(value) {
  if (!value) return "";
  if (!value.includes('"')) return `"${value}"`;
  addTranscript("warning", "BROWSER WORKER", "Mission fields cannot contain double quotes in this bounded command grammar.");
  return "";
}

async function loadAdvancedWorkspaces() {
  const generation = ++workspaceRequestGeneration;
  const projectId = ui.projectSelect.value || "auris-one";
  const data = await fetchJson(`/api/workspaces?project_id=${encodeURIComponent(projectId)}`);
  if (generation !== workspaceRequestGeneration || projectId !== (ui.projectSelect.value || "auris-one")) return;
  renderDailyWorkspace(data.workspaces.daily, data.workspaces.operations);
  renderProjectWorkspace(data.workspaces.projects);
  renderResearchWorkspace(data.workspaces.research);
  renderEngineeringWorkspace(data.workspaces.engineering);
  ui.engineeringMetrics.dataset.projectId = projectId;
  renderDocumentWorkspace(data.workspaces.documents);
  await Promise.all([loadWorldModel(), loadPredictiveIntelligence()]);
}

async function loadPredictiveIntelligence() {
  const params = new URLSearchParams({
    project_id: ui.projectSelect.value || "auris-one",
    private: String(isPrivate()),
  });
  const data = await fetchJson(`/api/predictions?${params}`);
  const intelligence = data.predictive_intelligence || {};
  const forecasts = intelligence.forecasts || [];
  const failure = forecasts.find((item) => item.metric === "mission_failure_probability");
  ui.predictiveMetrics.innerHTML = [
    `${forecasts.length} SIGNALS`,
    failure?.sample_sufficient ? `${Math.round(failure.probability * 100)}% OBSERVED FAILURE` : "FAILURE RATE WITHHELD",
    `${failure?.sample_size || 0}/${failure?.minimum_sample_size || 20} OUTCOMES`,
    "ADVISORY ONLY",
  ].map((item) => `<span>${escapeHtml(item)}</span>`).join("");
  ui.predictiveSignals.innerHTML = forecasts.length ? forecasts.map((forecast) => `
    <article class="predictive-signal attention-${escapeHtml(forecast.classification || "low")}">
      <header><span>${escapeHtml(forecast.metric).replaceAll("_", " ").toUpperCase()}</span><b>${forecast.probability == null ? escapeHtml(forecast.score) : `${Math.round(forecast.probability * 100)}%`}</b></header>
      <p>${escapeHtml(forecast.method)}</p>
      <small>${escapeHtml(forecast.classification).replaceAll("_", " ").toUpperCase()} // SAMPLE ${escapeHtml(forecast.sample_size)} // ${escapeHtml(forecast.uncertainty)}</small>
    </article>`).join("") : empty(intelligence.message || "No project forecast is available.");
}

async function loadWorldModel() {
  const params = new URLSearchParams({
    project_id: ui.projectSelect.value || "auris-one",
    private: String(isPrivate()),
  });
  const data = await fetchJson(`/api/world-model?${params}`);
  const model = data.world_model || {};
  latestWorldSnapshotId = model.snapshot_id || "";
  ui.worldModelMetrics.innerHTML = [
    `${model.entities?.length || 0} ENTITIES`,
    `${model.relationships?.length || 0} RELATIONS`,
    `${model.events?.length || 0} EVENTS`,
    `${model.possible_actions?.length || 0} ACTIONS`,
  ].map((item) => `<span>${escapeHtml(item)}</span>`).join("");
  const actions = (model.possible_actions || []).slice(0, 60);
  ui.worldActionSelect.innerHTML = actions.map((action) => `<option value="${escapeHtml(action.action_id)}">${escapeHtml(action.label)} // ${escapeHtml(action.risk_level).replaceAll("_", " ").toUpperCase()}</option>`).join("");
  ui.worldAlternativeSelect.innerHTML = `<option value="">NO ALTERNATIVE // COMPARE WITH NO ACTION</option>${actions.map((action) => `<option value="${escapeHtml(action.action_id)}">${escapeHtml(action.label)}</option>`).join("")}`;
  ui.worldActionForm.querySelectorAll("select, button").forEach((control) => {
    control.disabled = !actions.length || model.private_mode;
  });
  ui.worldSimulation.innerHTML = model.private_mode
    ? empty(model.message || "World-model state is suppressed in Private Session.")
    : `<div class="epistemic-state"><span>SNAPSHOT</span><strong>${escapeHtml((model.snapshot_id || "unavailable").toUpperCase())}</strong></div><p>STRUCTURED OPERATIONAL MODEL // ${model.learned_model ? "LEARNED" : "DETERMINISTIC"} // ${escapeHtml(model.provenance || "UNKNOWN").toUpperCase()}</p>`;
}

async function simulateWorldAction(event) {
  event.preventDefault();
  if (!latestWorldSnapshotId || !ui.worldActionSelect.value || isPrivate()) return;
  const data = await fetchJson("/api/world-model/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      snapshot_id: latestWorldSnapshotId,
      action_id: ui.worldActionSelect.value,
      alternative_action_id: ui.worldAlternativeSelect.value === ui.worldActionSelect.value ? null : (ui.worldAlternativeSelect.value || null),
      project_id: ui.projectSelect.value || "auris-one",
      private: false,
    }),
  });
  const simulation = data.simulation;
  const causal = data.causal_analysis || {};
  ui.worldSimulation.innerHTML = `
    <div class="world-transition"><span>${escapeHtml(simulation.before.state).replaceAll("_", " ").toUpperCase()}</span><b>SIMULATED</b><strong>${escapeHtml(simulation.after.state).replaceAll("_", " ").toUpperCase()}</strong></div>
    <p>${escapeHtml(simulation.target.label)} // ${escapeHtml(simulation.confidence).replaceAll("_", " ").toUpperCase()}</p>
    <div class="causal-readout"><span>${escapeHtml(causal.intervention?.notation || "INTERVENTION UNAVAILABLE")}</span><b>${escapeHtml(causal.causal_graph?.scope || "UNKNOWN SCOPE").toUpperCase()}</b><strong>DOWNSTREAM ${escapeHtml(causal.identifiability?.downstream_outcomes || "UNKNOWN").replaceAll("_", " ").toUpperCase()}</strong></div>
    <small>MEDIATORS // ${escapeHtml((causal.mediators || []).join(" -> ").replaceAll("_", " ").toUpperCase())}</small>
    <small>CONFOUNDERS // ${escapeHtml((causal.confounders || []).join(" // ").toUpperCase())}</small>
    ${(simulation.unknowns || []).map((item) => `<small>${escapeHtml(item)}</small>`).join("")}
    <div class="decision-calibration-warning">ADVISORY ONLY // EXECUTED FALSE // ORDINARY POLICY AND APPROVAL STILL APPLY</div>`;
}

async function analyseDecision(event) {
  event.preventDefault();
  const criterion = ui.decisionCriterion.value.trim();
  const decision = {
    objective: ui.decisionObjective.value.trim(),
    criteria: [{ name: criterion, weight: Number(ui.decisionWeight.value) }],
    options: [
      { name: ui.decisionOptionA.value.trim(), scores: { [criterion]: Number(ui.decisionScoreA.value) }, score_source: "User-entered Decision Lab score" },
      { name: ui.decisionOptionB.value.trim(), scores: { [criterion]: Number(ui.decisionScoreB.value) }, score_source: "User-entered Decision Lab score" },
    ],
    unknowns: memoryLines(ui.decisionUnknowns.value),
  };
  const data = await fetchJson("/api/decisions/analyse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision,
      project_id: ui.projectSelect.value || "auris-one",
      private: isPrivate(),
      council: {
        requested: ui.decisionCouncil.value === "true",
        complexity: 0.8,
        risk: "medium",
        max_calls: 5,
        token_budget: 1400,
      },
    }),
  });
  renderDecisionAnalysis(data.analysis);
  await loadDecisions();
}

async function loadDecisions() {
  const params = new URLSearchParams({
    project_id: ui.projectSelect.value || "auris-one",
    private: String(isPrivate()),
    limit: "50",
  });
  const data = await fetchJson(`/api/decisions?${params}`);
  const calibration = data.calibration || {};
  const learning = data.outcome_learning || {};
  ui.decisionMetrics.innerHTML = metricCells([
    ["CASES", data.decisions.length],
    ["OUTCOMES", calibration.outcomes_recorded || 0],
    ["FORECASTS", calibration.probabilistic_forecasts_scored || 0],
    ["CALIBRATION", calibration.calibrated ? "MEASURED" : "INSUFFICIENT DATA"],
  ]);
  renderDecisionCases(data.decisions, calibration);
  renderDecisionLearning(learning);
}

function renderDecisionLearning(learning = {}) {
  const performance = learning.option_performance || [];
  const lessons = learning.recent_lessons || [];
  ui.decisionLearning.innerHTML = `
    <div class="epistemic-state"><span>OBSERVATIONS</span><strong>${escapeHtml(learning.observations || 0)}</strong></div>
    ${performance.map((item) => `<div class="decision-evidence-row"><b>${escapeHtml(item.option)}</b><p>${item.sample_sufficient ? `${Math.round(item.observed_success_rate * 100)}% OBSERVED SUCCESS` : `RATE WITHHELD // ${item.observations}/${learning.minimum_option_sample_size || 5} OBSERVATIONS`}</p></div>`).join("")}
    ${lessons.map((item) => `<div class="decision-missing"><span>LESSON</span><p>${escapeHtml(item)}</p></div>`).join("") || `<div class="decision-complete">NO OUTCOME LESSONS RECORDED</div>`}
    <div class="decision-calibration-warning">${escapeHtml(learning.warning || "Outcome feedback never changes security policy automatically.")}</div>`;
}

function renderDecisionAnalysis(analysis = {}) {
  const recommendation = analysis.recommendation || {};
  ui.decisionConfidence.textContent = `${String(analysis.confidence || "unassessed").toUpperCase()} CONFIDENCE`;
  ui.decisionRecommendation.innerHTML = `
    <div class="decision-primary ${recommendation.status === "supported" ? "supported" : "inconclusive"}">
      <span>${escapeHtml(String(recommendation.status || "inconclusive").toUpperCase())}</span>
      <strong>${escapeHtml(recommendation.option || "RECOMMENDATION WITHHELD")}</strong>
      <p>${escapeHtml(recommendation.reason || "No decision analysis has run.")}</p>
    </div>
    ${(analysis.options || []).map((option) => `<div class="decision-option"><span>${escapeHtml(option.name)}</span><b>${option.weighted_score == null ? "UNSCORED" : escapeHtml(option.weighted_score.toFixed(2))}</b><small>${Math.round((option.score_coverage || 0) * 100)}% CRITERIA COVERAGE</small></div>`).join("")}`;
  const missing = analysis.missing_evidence || [];
  const hypotheses = analysis.hypotheses || [];
  const council = analysis.model_council || {};
  ui.decisionEvidence.innerHTML = `
    <div class="epistemic-state"><span>STATUS</span><strong>${escapeHtml(String(analysis.epistemic_status || "unknown").toUpperCase())}</strong></div>
    ${hypotheses.map((item) => `<div class="decision-evidence-row"><b>${escapeHtml(item.id)} // ${escapeHtml(item.status).toUpperCase()}</b><p>${escapeHtml(item.statement)}</p><small>${item.evidence_ids.length} EVIDENCE ITEMS // ${item.counterevidence_present ? "COUNTEREVIDENCE PRESENT" : "COUNTEREVIDENCE MISSING"}</small></div>`).join("")}
    <div class="decision-evidence-row"><b>MODEL COUNCIL // ${escapeHtml(String(council.state || "not connected").replaceAll("_", " ").toUpperCase())}</b><p>${escapeHtml(council.reason || "No council review requested.")}</p><small>${council.independent_models ? "DISTINCT MODELS" : "ROLE SEPARATION ONLY"}</small></div>
    ${missing.map((item) => `<div class="decision-missing"><span>REQUIRED</span><p>${escapeHtml(item)}</p></div>`).join("") || `<div class="decision-complete">NO DECLARED EVIDENCE GAP</div>`}`;
}

function renderDecisionCases(decisions, calibration) {
  ui.decisionOutcomeCase.innerHTML = decisions.map((item) => `<option value="${escapeHtml(item.case_id)}">${escapeHtml(item.objective)}</option>`).join("");
  ui.decisionOutcomeForm.querySelectorAll("input, select, button").forEach((control) => { control.disabled = !decisions.length || isPrivate(); });
  ui.decisionCases.innerHTML = decisions.length ? decisions.map((item) => {
    const recommendation = item.analysis.recommendation || {};
    return `<article class="stream-item decision-case">
      <strong>${escapeHtml(item.objective)}</strong>
      <small>${escapeHtml(item.status).toUpperCase()} // ${escapeHtml(item.analysis.confidence).toUpperCase()} CONFIDENCE // ${item.outcomes.length} OUTCOME${item.outcomes.length === 1 ? "" : "S"}</small>
      <p>${recommendation.option ? `SUPPORTED OPTION: ${escapeHtml(recommendation.option)}` : escapeHtml(recommendation.reason || "RECOMMENDATION WITHHELD")}</p>
    </article>`;
  }).join("") : empty(isPrivate() ? "Decision history is suppressed in Private Session." : "No decision cases recorded for this project.");
  if (!calibration.calibrated && decisions.length) {
    ui.decisionCases.insertAdjacentHTML("afterbegin", `<div class="decision-calibration-warning">${escapeHtml(calibration.warning)}</div>`);
  }
}

async function recordDecisionOutcome(event) {
  event.preventDefault();
  const caseId = ui.decisionOutcomeCase.value;
  if (!caseId || isPrivate()) return;
  await fetchJson(`/api/decisions/${encodeURIComponent(caseId)}/outcomes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actual_success: ui.decisionOutcomeSuccess.value === "true",
      actual_summary: ui.decisionOutcomeSummary.value.trim(),
      expected_summary: ui.decisionExpectedSummary.value.trim(),
      difference_summary: ui.decisionDifferenceSummary.value.trim(),
      root_cause: ui.decisionRootCause.value.trim(),
      lesson: ui.decisionLesson.value.trim(),
      confidence_update: ui.decisionConfidenceUpdate.value,
    }),
  });
  [ui.decisionOutcomeSummary, ui.decisionExpectedSummary, ui.decisionDifferenceSummary, ui.decisionRootCause, ui.decisionLesson].forEach((field) => { field.value = ""; });
  ui.decisionConfidenceUpdate.value = "unchanged";
  await loadDecisions();
}

function renderDailyWorkspace(daily, operations = {}) {
  ui.dailyDate.textContent = `${daily.local_date} // ${daily.location}`;
  ui.dailyObjective.textContent = daily.primary_objective;
  ui.dailySupporting.innerHTML = (daily.supporting_objectives || []).map((objective, index) => `<span>0${index + 2} // ${escapeHtml(objective)}</span>`).join("");
  ui.dailyFirstAction.textContent = daily.suggested_first_action;
  ui.dailyPriorities.innerHTML = daily.priorities.map((priority) => `
    <div class="priority-item"><b>${escapeHtml(priority.level)}</b><strong>${escapeHtml(priority.title)}</strong>${priority.due_at ? `<small>${escapeHtml(formatTime(priority.due_at))}</small>` : ""}</div>`).join("");
  ui.dailySchedule.innerHTML = daily.schedule.length ? daily.schedule.map((event) => `
    <article class="stream-item"><strong>${escapeHtml(event.title)}</strong><small>${escapeHtml(formatTime(event.due_at))} // ${escapeHtml(event.status).toUpperCase()}</small></article>`).join("") : empty("No AURIS reminders are scheduled.");
  const systemRows = Object.entries(daily.active_systems || {}).flatMap(([label, value]) => {
    if (value && typeof value === "object") return Object.entries(value).map(([subLabel, subValue]) => [`${label} ${subLabel}`, subValue]);
    return [[label, value]];
  });
  ui.dailySystems.innerHTML = systemRows.map(([label, value]) => `
    <div class="telemetry-row"><span>${escapeHtml(label).replaceAll("_", " ").toUpperCase()}</span><div>${escapeHtml(value ?? "N/A").replaceAll("_", " ").toUpperCase()}</div></div>`).join("");
  ui.dailyRisks.innerHTML = daily.risks.map((risk) => `
    <article class="stream-item attention-${escapeHtml(risk.level).toLowerCase()}"><strong>${escapeHtml(risk.level).toUpperCase()}</strong><p>${escapeHtml(risk.title)}</p><small>${escapeHtml(risk.delivery || "NEXT BRIEFING")}</small></article>`).join("") || empty("No local risk signal is supported by current evidence.");
  renderOperationsIntelligence(operations);
}

function renderOperationsIntelligence(operations = {}) {
  const attention = operations.attention || { items: [], opportunities: [], counts: {}, delivery_counts: {} };
  const levels = ["CRITICAL", "URGENT", "IMPORTANT", "NOTIFY", "BRIEFING", "LOG"];
  ui.attentionMetrics.innerHTML = levels.map((level) => `
    <div class="attention-metric attention-${level.toLowerCase()}"><span>${escapeHtml(level)}</span><strong>${escapeHtml(attention.counts?.[level] || 0)}</strong></div>`).join("");
  ui.dailyAttention.innerHTML = (attention.risks || []).slice(0, 8).map(renderAttentionSignal).join("") || empty("No operational risk is supported by current evidence.");
  ui.dailyOpportunities.innerHTML = (attention.opportunities || []).slice(0, 6).map(renderAttentionSignal).join("") || empty("No evidence-backed opportunity is currently available.");
  renderOperationsGraph(operations.graph || { nodes: [], edges: [], matched_node_ids: [], coverage: {} });
  renderEveningDebrief(operations.evening || {});
}

function renderAttentionSignal(signal) {
  const factorText = Object.entries(signal.factors || {}).map(([name, value]) => `${name.replaceAll("_", " ")} ${value}`).join(" // ");
  return `<article class="attention-signal attention-${escapeHtml(signal.level || "LOG").toLowerCase()}">
    <header><span>${escapeHtml(signal.level || "LOG")} // ${escapeHtml(signal.delivery || "LOG ONLY")}</span><b>${escapeHtml(signal.score ?? 0)}</b></header>
    <strong>${escapeHtml(signal.title)}</strong>
    <p>${escapeHtml(signal.detail || "")}</p>
    <small>${escapeHtml(factorText.toUpperCase())}</small>
  </article>`;
}

function renderOperationsGraph(graph) {
  const matched = new Set(graph.matched_node_ids || []);
  const typeCounts = (graph.nodes || []).reduce((counts, node) => {
    counts[node.type] = (counts[node.type] || 0) + 1;
    return counts;
  }, {});
  const summary = `<div class="graph-summary"><span>${graph.nodes?.length || 0} NODES</span><span>${graph.edges?.length || 0} LINKS</span><span>${graph.truncated ? "BOUNDED VIEW" : "COMPLETE VIEW"}</span></div>`;
  ui.coreKnowledgeMetric.textContent = `${graph.nodes?.length || 0} NODES // ${graph.edges?.length || 0} LINKS`;
  const types = `<div class="graph-types">${Object.entries(typeCounts).slice(0, 10).map(([type, count]) => `<span>${escapeHtml(type).replaceAll("_", " ").toUpperCase()} <b>${count}</b></span>`).join("")}</div>`;
  const nodes = (graph.nodes || []).slice(0, 18).map((node) => `<div class="graph-node ${matched.has(node.id) ? "matched" : ""}"><i></i><span><b>${escapeHtml(node.type).toUpperCase()}</b><strong>${escapeHtml(node.label)}</strong><small>${escapeHtml(node.status).replaceAll("_", " ").toUpperCase()} // ${escapeHtml(node.provenance || "REAL")}</small></span></div>`).join("");
  const privateMessage = graph.private_mode ? `<div class="graph-private">${escapeHtml(graph.message)}</div>` : "";
  ui.operationsGraph.innerHTML = summary + types + privateMessage + (nodes ? `<div class="graph-node-list">${nodes}</div>` : empty(graph.query ? "No durable relationship matched this trace." : "No graph evidence is available in this context."));
}

function renderEveningDebrief(evening) {
  const rows = [
    ["COMPLETED", (evening.completed || []).length, (evening.completed || []).map((item) => item.objective)],
    ["INCOMPLETE", (evening.incomplete || []).length, (evening.incomplete || []).map((item) => item.objective)],
    ["DECISIONS", (evening.decisions || []).length, (evening.decisions || []).map((item) => item.subject)],
    ["TOMORROW", (evening.tomorrow_preparation || []).length, (evening.tomorrow_preparation || []).map((item) => item.title)],
    ["RISKS", (evening.outstanding_risks || []).length, (evening.outstanding_risks || []).map((item) => item.title)],
  ];
  ui.eveningDebrief.innerHTML = rows.map(([label, count, items]) => `<section class="debrief-row"><header><span>${label}</span><b>${count}</b></header>${items.slice(0, 3).map((item) => `<p>${escapeHtml(item)}</p>`).join("") || `<small>NO RECORDED EVIDENCE</small>`}</section>`).join("");
}

async function loadOperationsQuery(event) {
  event.preventDefault();
  const query = ui.operationsQueryInput.value.trim();
  const params = new URLSearchParams({
    project_id: ui.projectSelect.value || "auris-one",
    q: query,
    private: String(isPrivate()),
    focus: String(document.body.classList.contains("neural-focus")),
  });
  const data = await fetchJson(`/api/anticipation?${params}`);
  renderOperationsGraph(data.operations.graph);
  ui.dailyAttention.innerHTML = (data.operations.attention.risks || []).slice(0, 8).map(renderAttentionSignal).join("") || empty("No operational risk is supported by current evidence.");
}

function renderProjectWorkspace(projects) {
  ui.projectsWorkspace.innerHTML = projects.items.map((project) => `
    <article class="project-item ${project.project_id === ui.projectSelect.value ? "selected" : ""}">
      <header><span>${escapeHtml(project.project_id).toUpperCase()}</span><b>${project.active_tasks ? "ACTIVE" : project.root_connected ? "ROOT LINKED" : "STANDBY"}</b></header>
      <h2>${escapeHtml(project.name)}</h2><p>${escapeHtml(project.description)}</p>
      <dl><div><dt>TASKS</dt><dd>${project.task_count}</dd></div><div><dt>COMPLETED</dt><dd>${project.completed_tasks}</dd></div><div><dt>MEMORIES</dt><dd>${project.memory_count}</dd></div><div><dt>EVENTS</dt><dd>${project.scheduled_events}</dd></div></dl>
      <div class="project-actions"><button type="button" data-project="${escapeHtml(project.project_id)}">SET ACTIVE CONTEXT</button>${project.root_connected ? `<button type="button" data-open-project="${escapeHtml(project.project_id)}">OPEN PROJECT</button>` : ""}</div>
    </article>`).join("");
}

function renderResearchWorkspace(research) {
  ui.researchMetrics.innerHTML = metricCells([
    ["CAMPAIGNS", research.metrics.campaigns],
    ["SOURCES", research.metrics.sources_processed],
    ["CLAIMS", research.metrics.claims],
    ["VERIFIED", research.metrics.verified],
  ]);
  const latest = research.campaigns[0];
  const latestClaims = latest ? research.claims.filter((claim) => claim.task_id === latest.task_id).slice(0, 8) : [];
  ui.researchMap.innerHTML = latest ? `
    <div class="research-topic"><span>${escapeHtml(latest.mode).toUpperCase()} MISSION // ${latest.branch_coverage_percent}% BRANCH COVERAGE</span><strong>${escapeHtml(latest.topic)}</strong></div>
    <div class="research-links">${latestClaims.map((claim) => `<div class="research-node ${escapeHtml(claim.status)}"><b>${escapeHtml(claim.claim_id)}</b><span>${escapeHtml(claim.claim)}<small>${escapeHtml(claim.status).toUpperCase()} // ${claim.source_ids.map(escapeHtml).join(" + ")}</small></span></div>`).join("") || empty("No validated claim nodes for this campaign.")}</div>
    <div class="coverage-ledger">${research.coverage_dimensions.map((item) => `<span class="${escapeHtml(item.state)}">${escapeHtml(item.name).replaceAll("_", " ").toUpperCase()} // ${escapeHtml(item.state).replaceAll("_", " ").toUpperCase()}</span>`).join("")}</div>` : empty("Run a research mission to create an evidence map.");
  ui.researchCampaigns.innerHTML = research.campaigns.length ? research.campaigns.map((campaign) => `
    <article class="stream-item ${campaign.definition_of_done_met ? "alert-green" : "alert-amber"}"><strong>${escapeHtml(campaign.topic)}</strong><small>${escapeHtml(campaign.mode).toUpperCase()} // ${campaign.query_count} QUERIES // ${campaign.source_count} SOURCES // ${campaign.claim_count} CLAIMS</small><p>${campaign.branch_coverage_percent}% BRANCH COVERAGE // ${campaign.counterevidence_count} COUNTEREVIDENCE QUERIES // ${campaign.duplicate_count} DUPLICATES RESOLVED // ${campaign.definition_of_done_met ? "VERIFIED COMPLETE" : "PARTIAL"}</p></article>`).join("") : empty("No research campaigns recorded.");
  ui.researchSources.innerHTML = research.sources.length ? research.sources.map((source) => `
    <a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer"><span>${escapeHtml(source.source_id)}</span><strong>${escapeHtml(source.title)}</strong><small>${escapeHtml(source.publisher || "SOURCE")} // ${escapeHtml(source.source_type).toUpperCase()}${source.primary ? " // PRIMARY" : ""}</small></a>`).join("") : empty("No preserved evidence links.");
}

function renderEngineeringWorkspace(engineering) {
  const metrics = engineering.metrics;
  const repository = engineering.repository;
  const codingEngine = engineering.coding_engine || {};
  ui.engineeringProjectName.textContent = repository.name || "Selected project";
  ui.engineeringMetrics.innerHTML = metricCells([
    ["FILES", repository.file_count],
    ["TEXT LINES", repository.text_line_count],
    ["TEST FILES", metrics.test_files],
    ["SIGNALS", metrics.review_signals],
    ["CODEX", codingEngine.ready ? "READY" : codingEngine.available ? "SIGN IN" : "OFFLINE"],
  ]);
  const maximum = Math.max(1, ...repository.extensions.map((item) => item.count));
  ui.repositoryMap.innerHTML = repository.extensions.length ? repository.extensions.map((item) => `
    <div class="repository-row"><span>${escapeHtml(item.extension)}</span><i><b class="fill-${Math.max(10, Math.ceil(item.count / maximum * 10) * 10)}"></b></i><strong>${item.count}</strong></div>`).join("")
    : empty(repository.analysis_error || "Register a local root for the selected project.");
  ui.engineeringRuns.innerHTML = engineering.recent_runs.length ? engineering.recent_runs.map((run) => `
    <article class="stream-item engineering-run ${run.rolled_back ? "alert-amber" : ""}">
      <strong>${escapeHtml(run.objective)}</strong>
      <small>${escapeHtml(run.operation || "PLANNING").toUpperCase()} // ${escapeHtml(run.state).toUpperCase()}${run.test_count != null ? ` // ${run.test_count} TESTS` : ""}${run.snapshot_id ? ` // ${escapeHtml(run.snapshot_id)}` : ""}${run.proposal_id ? ` // ${escapeHtml(shortId(run.proposal_id))}` : ""}</small>
      ${run.proposal_id ? `<p>${escapeHtml(run.isolation_kind || "SIGNED PROPOSAL").replaceAll("_", " ").toUpperCase()} // ${run.files.length} FILES // +${run.diff_stats.added_lines || 0} -${run.diff_stats.removed_lines || 0} // TARGETED ${run.targeted_passed ? "PASS" : "N/A"} // COMPLETE ${run.full_passed ? "PASS" : "N/A"}${run.rolled_back ? " // EXACT ROLLBACK" : ""}</p>` : ""}
      ${run.diagnosis ? `<p class="repair-diagnosis">${escapeHtml(run.diagnosis)}</p>` : ""}
      ${run.diff ? `<details class="repair-diff"><summary>REVIEW SIGNED DIFF</summary><pre>${escapeHtml(run.diff)}</pre></details>` : ""}
    </article>`).join("") : empty("No engineering checks recorded.");
  const instructionRows = repository.instructions.map((item) => `<div class="analysis-item instruction"><span>INSTRUCTION</span><strong>${escapeHtml(item)}</strong></div>`).join("");
  const manifestRows = repository.manifest_details.map((item) => `<div class="analysis-item manifest"><span>MANIFEST // ${escapeHtml(item.parse_state).toUpperCase()}</span><strong>${escapeHtml(item.path)}</strong><small>${item.runtime ? `${escapeHtml(item.runtime)} // ` : ""}${item.dependency_count ?? 0} DEPENDENCIES</small></div>`).join("");
  const componentRows = repository.components.map((item) => `<div class="analysis-item"><span>${escapeHtml(item.kind).replaceAll("_", " ").toUpperCase()}</span><strong>${escapeHtml(item.name)}</strong><small>${item.file_count} FILES // ${item.text_line_count} LINES</small></div>`).join("");
  ui.engineeringComponents.innerHTML = instructionRows + manifestRows + componentRows || empty("No architecture snapshot is available.");
  ui.engineeringRisks.innerHTML = repository.risks.length ? repository.risks.map((risk) => `
    <div class="analysis-item signal-${escapeHtml(risk.severity)}"><span>${escapeHtml(risk.code)}</span><strong>${escapeHtml(risk.message)}</strong></div>`).join("") : `<div class="analysis-item clear"><span>REVIEW</span><strong>No bounded review signals detected.</strong></div>`;
  ui.projectRootState.textContent = repository.root_connected ? `REGISTERED // ${repository.snapshot_id || "READY"}` : "NOT REGISTERED";
  ui.versionControlState.textContent = repository.version_control.replaceAll("_", " ").toUpperCase();
}

function renderDocumentWorkspace(documents) {
  const processed = new Map(documents.formats_processed.map((item) => [item.format, item.count]));
  ui.documentFormats.innerHTML = documents.supported_read_formats.map((format) => `
    <div><strong>${escapeHtml(format)}</strong><small>${processed.get(format) || 0} PROCESSED</small></div>`).join("");
  ui.documentRuns.innerHTML = documents.recent.length ? documents.recent.map((run) => `
    <article class="stream-item"><strong>${escapeHtml(run.name || run.objective)}</strong><small>${escapeHtml(run.format || "FILE SEARCH")} // ${escapeHtml(run.state).toUpperCase()}${run.bytes_read ? ` // ${run.bytes_read} BYTES` : ""}</small></article>`).join("") : empty("No document operations recorded.");
}

function metricCells(items) {
  return items.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
}

async function cancelEvent(eventId) {
  await fetchJson(`/api/events/${encodeURIComponent(eventId)}`, { method: "DELETE" });
  await Promise.all([loadEvents(), loadAudit()]);
}

async function saveMemory(event) {
  event.preventDefault();
  if (isPrivate()) return;
  const content = ui.memoryInput.value.trim();
  if (!content) return;
  const structuredData = ui.memoryCategory.value === "decision" ? {
    decision: content,
    alternatives: memoryLines(ui.memoryDecisionAlternatives.value),
    evidence: memoryLines(ui.memoryDecisionEvidence.value),
    assumptions: memoryLines(ui.memoryDecisionAssumptions.value),
    risks: memoryLines(ui.memoryDecisionRisks.value),
    reason: ui.memoryDecisionReason.value.trim(),
    outcome: ui.memoryDecisionOutcome.value.trim() || null,
  } : {};
  try {
    const data = await fetchJson("/api/memories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content,
        category: ui.memoryCategory.value,
        subject_key: ui.memorySubject.value.trim() || null,
        environment: ui.memoryEnvironment.value.trim() || null,
        sensitivity: ui.memorySensitivity.value,
        structured_data: structuredData,
        valid_until: localDateTimeToIso(ui.memoryExpiry.value),
        confidence_score: 1,
        project_id: ui.projectSelect.value || null,
      }),
    });
    ui.memoryForm.reset();
    syncMemoryDecisionFields();
    addTranscript(
      data.requires_resolution ? "warning" : "verification",
      "MEMORY",
      data.requires_resolution ? "Contradiction preserved for explicit resolution." : data.duplicate ? "Duplicate assertion not stored." : "Typed memory stored with temporal history."
    );
    await Promise.all([loadMemories(), loadAudit()]);
  } catch (error) {
    addTranscript("warning", "MEMORY", error.message);
  }
}

function memoryLines(value) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean).slice(0, 20);
}

function syncMemoryDecisionFields() {
  ui.memoryDecisionFields.hidden = ui.memoryCategory.value !== "decision";
}

async function removeMemory(memoryId) {
  if (!window.confirm("Delete this memory, its version history, and related conflicts?")) return;
  try {
    await fetchJson(`/api/memories/${encodeURIComponent(memoryId)}`, { method: "DELETE" });
    await Promise.all([loadMemories(), loadAudit()]);
  } catch (error) {
    addTranscript("warning", "MEMORY", error.message);
  }
}

function openMemoryCorrection(memoryId) {
  const memory = memoryCache.get(memoryId);
  if (!memory) return;
  ui.memoryEditId.value = memory.memory_id;
  ui.memoryEditContent.value = memory.content;
  ui.memoryEditSubject.value = memory.subject_key || "";
  ui.memoryEditEnvironment.value = memory.environment || "";
  ui.memoryEditSensitivity.value = memory.sensitivity;
  ui.memoryEditExpiry.value = isoToLocalDateTime(memory.expires_at);
  ui.memoryEditReason.value = "";
  ui.memoryEditDialog.showModal();
}

async function saveMemoryCorrection(event) {
  event.preventDefault();
  try {
    await fetchJson(`/api/memories/${encodeURIComponent(ui.memoryEditId.value)}/correct`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: ui.memoryEditContent.value.trim(),
        subject_key: ui.memoryEditSubject.value.trim() || null,
        environment: ui.memoryEditEnvironment.value.trim() || null,
        sensitivity: ui.memoryEditSensitivity.value,
        valid_until: localDateTimeToIso(ui.memoryEditExpiry.value),
        reason: ui.memoryEditReason.value.trim(),
        project_id: ui.projectSelect.value || null,
        confidence_score: 1,
      }),
    });
    ui.memoryEditDialog.close();
    await Promise.all([loadMemories(), loadAudit()]);
  } catch (error) {
    addTranscript("warning", "MEMORY", error.message);
  }
}

async function openMemoryHistory(memoryId) {
  try {
    const data = await fetchJson(`/api/memories/${encodeURIComponent(memoryId)}/history`);
    const history = data.history;
    ui.memoryHistoryView.innerHTML = history.versions.map((version) => `
      <article><header><span>V${version.version_number} // ${escapeHtml(version.operation).toUpperCase()}</span><time>${escapeHtml(formatTime(version.created_at))}</time></header><p>${escapeHtml(version.snapshot.content)}</p><small>${escapeHtml(version.reason)} // ${escapeHtml(version.actor)}</small></article>
    `).join("") || empty("No version history is available.");
    ui.memoryHistoryDialog.showModal();
  } catch (error) {
    addTranscript("warning", "MEMORY", error.message);
  }
}

async function resolveConflict(conflictId, choice) {
  try {
    await fetchJson(`/api/memory/conflicts/${encodeURIComponent(conflictId)}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(choice === "both" ? { keep_both: true } : { chosen_memory_id: choice }),
    });
    await Promise.all([loadMemories(), loadAudit()]);
  } catch (error) {
    addTranscript("warning", "MEMORY", error.message);
  }
}

async function toggleMemoryCategory(category, enabled) {
  try {
    await fetchJson(`/api/memory/categories/${encodeURIComponent(category)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    await Promise.all([loadMemories(), loadAudit()]);
  } catch (error) {
    addTranscript("warning", "MEMORY", error.message);
    await loadMemories();
  }
}

async function exportMemories() {
  if (isPrivate()) return;
  try {
    const data = await fetchJson(`/api/memories/export?project_id=${encodeURIComponent(ui.projectSelect.value || "")}`);
    const blob = new Blob([JSON.stringify(data.archive, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `auris-memory-${ui.projectSelect.value || "all"}-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    await loadAudit();
  } catch (error) {
    addTranscript("warning", "MEMORY", error.message);
  }
}

async function decideApproval(approvalId, action) {
  const data = await fetchJson(`/api/approvals/${encodeURIComponent(approvalId)}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scope: "once" }),
  });
  const result = data.task?.result;
  if (result?.message) addTranscript(action === "approve" ? "auris" : "warning", "AURIS", result.message);
  if (result?.interaction_action) {
    const interaction = result.interaction_action;
    addTranscript(
      interaction.observed || interaction.input_units_emitted ? "verification" : "warning",
      "WINDOWS INTERACTION",
      `${interaction.application || "WINDOWS"} // ${interaction.control_name || `${interaction.characters || 0} CHARACTERS`} // ${interaction.observation || "INPUT ACCEPTED"}`
    );
    if (interaction.command_fabric) {
      const fabric = interaction.command_fabric;
      addTranscript("verification", "DEVICE FABRIC", `${shortId(fabric.command_id)} // ${fabric.permission_scope} // SIGNATURE ${fabric.signature_verified ? "VERIFIED" : "REJECTED"} // NONCE ${fabric.nonce_claimed ? "CLAIMED" : "REJECTED"}`);
    }
  }
  if (result?.browser_action) {
    renderBrowserResult(result.browser_action);
    const fabric = result.browser_action.command_fabric;
    addTranscript(
      result.browser_action.ok ? "verification" : "warning",
      "BROWSER WORKER",
      `${String(result.browser_action.action?.kind || "browser").toUpperCase()} // ${result.browser_action.page?.title || result.browser_action.page?.url || "NO VERIFIED PAGE CHANGE"}${fabric ? ` // SIGNATURE ${fabric.signature_verified ? "VERIFIED" : "REJECTED"} // NONCE ${fabric.nonce_claimed ? "CLAIMED" : "REJECTED"}` : ""}`,
    );
  }
  setCoreState(action === "approve" ? "completed" : "warning");
  await refreshOperationalData();
}

async function toggleEmergencyStop() {
  const endpoint = controlStopped ? "/api/control/resume" : "/api/control/stop";
  const data = await fetchJson(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: controlStopped ? "Resumed from command centre" : "Emergency stop from command centre" }),
  });
  renderControlState(data.control);
  await Promise.all([loadAudit(), loadTasks()]);
}

function renderControlState(control) {
  controlStopped = Boolean(control.stopped);
  const executeButton = ui.commandForm.querySelector(".execute-control");
  ui.commandInput.disabled = controlStopped;
  ui.voiceButton.disabled = controlStopped;
  executeButton.disabled = controlStopped;

  if (controlStopped) {
    ui.wakeToggle.disabled = true;
    ui.voiceTopState.className = "signal critical";
    ui.voiceTopState.innerHTML = "<i></i>VOICE PAUSED";
    ui.serverState.className = "signal critical";
    ui.serverState.innerHTML = "<i></i>CORE STOPPED";
    ui.stopControl.textContent = "RESUME AURIS";
    ui.stopControl.classList.add("resume");
    ui.dockStop.textContent = "RESUME";
    setCoreState("critical");
    setOperation("EMERGENCY STOP", control.reason || "All new operations are blocked.");
  } else {
    ui.wakeToggle.disabled = false;
    ui.serverState.className = "signal online";
    ui.serverState.innerHTML = "<i></i>AURIS ONLINE";
    ui.stopControl.textContent = "EMERGENCY STOP";
    ui.stopControl.classList.remove("resume");
    ui.dockStop.textContent = "STOP";
  }
}

function renderVoiceState(voice) {
  const enabled = Boolean(voice?.background_enabled);
  const online = Boolean(voice?.background_daemon_online);
  const speaking = Boolean(voice?.speaking);
  const processing = voice?.background_state === "processing" || voice?.input_phase === "interpreting_speech";
  const capturing = Boolean(voice?.input_capture_active);
  const partial = String(voice?.input_partial_transcript || "").trim();
  const audioLevel = Math.max(0, Math.min(100, Number(voice?.input_audio_level || 0)));
  const neuralProvider = voice?.provider === "local_kokoro" || voice?.provider === "local_piper";
  const neuralReady = neuralProvider && Boolean(voice?.neural_worker_online);
  const observation = voice?.input_observation || {};
  const inputIssue = observation.age_seconds != null && observation.age_seconds <= 30 && (["no_frames", "overflow"].includes(observation.signal_state) || (observation.signal_state === "weak_signal" && observation.mode === "command"));
  const dbfs = voice?.input_dbfs;
  const levelText = dbfs == null ? `LEVEL ${Math.round(audioLevel)}` : `${Number(dbfs).toFixed(1)} dBFS`;
  wakeModeActive = enabled;
  ui.wakeToggle.checked = enabled;
  ui.voiceReadout.textContent = `${neuralReady ? "VALE" : neuralProvider ? "WARMING" : "SAPI"}${capturing ? ` // ${levelText}` : ""}`;
  ui.voiceTopState.title = inputIssue ? String(voice?.last_input_error || "Check the microphone input and level.") : String(voice?.input_microphone || "");
  if (ui.coreVoiceMetric) {
    ui.coreVoiceMetric.textContent = controlStopped
      ? "VOICE PAUSED"
      : inputIssue
        ? "CHECK MICROPHONE"
      : capturing
        ? levelText
        : speaking
          ? "SPEAKING"
          : enabled && online
            ? "WAKE ARMED"
            : neuralReady
              ? "VALE READY"
              : enabled
                ? "VOICE STARTING"
                : "VOICE STANDBY";
  }
  if (controlStopped) {
    ui.voiceTopState.className = "signal critical";
    ui.voiceTopState.innerHTML = "<i></i>VOICE PAUSED";
  } else if (inputIssue && !speaking && !processing) {
    ui.voiceTopState.className = "signal warning";
    ui.voiceTopState.innerHTML = `<i></i>${observation.signal_state === "weak_signal" ? "MIC INPUT TOO QUIET" : "CHECK MICROPHONE"}`;
  } else if (processing) {
    ui.voiceTopState.className = "signal online";
    ui.voiceTopState.innerHTML = "<i></i>INTERPRETING COMMAND";
    if (!["critical", "approval"].includes(activeCoreState)) setCoreState("planning");
  } else if (capturing && speaking) {
    ui.voiceTopState.className = "signal listening";
    ui.voiceTopState.innerHTML = "<i></i>BARGE-IN LISTENING";
  } else if (capturing) {
    ui.voiceTopState.className = "signal listening";
    ui.voiceTopState.innerHTML = `<i></i>MIC ${escapeHtml(levelText)}`;
  } else if (speaking) {
    ui.voiceTopState.className = "signal online";
    ui.voiceTopState.innerHTML = `<i></i>${escapeHtml(voice?.sentiment || "neutral").toUpperCase()} DELIVERY`;
    if (!["critical", "approval"].includes(activeCoreState)) setCoreState("speaking");
  } else if (enabled && online) {
    ui.voiceTopState.className = "signal listening";
    ui.voiceTopState.innerHTML = "<i></i>WAKE WORD ARMED";
  } else if (enabled) {
    ui.voiceTopState.className = "signal";
    ui.voiceTopState.innerHTML = "<i></i>WAKE STARTING";
  } else {
    ui.voiceTopState.className = "signal";
    ui.voiceTopState.innerHTML = "<i></i>VOICE STANDBY";
  }
  if (capturing && !processing) {
    if (activeCoreState === "dormant" || activeCoreState === "listening") setCoreState("listening");
    if (partial) setOperation("LIVE VOICE", partial);
  } else if (["listening", "speaking"].includes(activeCoreState)) {
    setCoreState("dormant");
  }
}

function renderPlan(plan, workflow = null, verificationReport = null) {
  const risk = plan.risk_level.replaceAll("_", " ").toUpperCase();
  const checkpoints = new Map((workflow?.checkpoints || []).map((checkpoint) => [checkpoint.step_id, checkpoint]));
  const workflowSummary = workflow
    ? `<div><span>ATTEMPTS</span><b>${workflow.attempts}/${workflow.max_attempts} // RECOVERIES ${workflow.recovery_count}</b></div>`
    : "";
  const verificationView = verificationReport ? `
    <section class="verification-report">
      <header><span>DETERMINISTIC VERIFICATION</span><b class="${escapeHtml(verificationReport.status)}">${escapeHtml(verificationReport.status).replaceAll("_", " ").toUpperCase()}</b></header>
      ${verificationReport.checks.map((check) => `<div class="verification-check ${check.passed ? "passed" : "failed"}"><i></i><strong>${escapeHtml(check.name).replaceAll("_", " ")}</strong><small>${escapeHtml(check.evidence)}</small></div>`).join("")}
    </section>` : "";
  ui.riskBadge.textContent = risk;
  ui.riskBadge.className = `risk-badge ${plan.risk_level}`;
  ui.planView.innerHTML = `
    <div class="plan-summary">
      <div><span>OBJECTIVE</span><b>${escapeHtml(plan.objective)}</b></div>
      <div><span>STATE</span><b>${escapeHtml(plan.state)}</b></div>
      <div><span>AGENTS</span><b>${plan.required_agents.map(escapeHtml).join(" // ")}</b></div>
      ${workflowSummary}
    </div>
    ${plan.steps.map((step, index) => {
      const checkpoint = checkpoints.get(step.step_id);
      const checkpointState = checkpoint?.state || (plan.state === "awaiting_approval" && index === 1 ? "awaiting_approval" : "pending");
      return `<article class="plan-step checkpoint-${escapeHtml(checkpointState)}"><b>${String(index + 1).padStart(2, "0")}</b><strong>${escapeHtml(step.title)}</strong><small>${escapeHtml(step.agent)} // ${escapeHtml(step.success_condition)}</small><span>${escapeHtml(checkpointState).replaceAll("_", " ").toUpperCase()}${checkpoint?.attempts ? ` // ATTEMPT ${checkpoint.attempts}` : ""}</span></article>`;
    }).join("")}
    ${verificationView}`;

  ui.missionObjective.textContent = plan.objective;
  ui.missionState.textContent = plan.state.replaceAll("_", " ").toUpperCase();
  ui.missionRisk.textContent = risk;
  ui.commandMissionObjective.textContent = plan.objective;
  ui.commandMissionState.textContent = plan.state.replaceAll("_", " ").toUpperCase();
  ui.commandMissionRisk.textContent = risk;
  ui.commandMissionVerification.textContent = verificationReport?.status
    ? verificationReport.status.replaceAll("_", " ").toUpperCase()
    : plan.state === "awaiting_approval" ? "AWAITING APPROVAL" : "PENDING";
  ui.contextObjective.textContent = plan.objective;
  ui.contextAgent.textContent = plan.required_agents[0]?.replaceAll("_", " ") || "Supervisor";
  ui.contextPermission.textContent = risk;
  ui.contextNext.textContent = plan.steps[1]?.title || plan.approval_points[0] || "Report result";
}

function renderSystem(status, trust = null, ipc = null, cloud = null, model = null) {
  const rows = [
    ["MACHINE", status.machine],
    ["PLATFORM", status.platform],
    ["RUNTIME", `Python ${status.python}`],
    ["LOGICAL CPU", status.cpu_count],
    ["DISK", `${status.disk.free_gb} GB free / ${status.disk.total_gb} GB`],
    ["WORKSPACE", status.cwd],
  ];
  if (trust) {
    rows.push(
      ["DEVICE ID", shortId(trust.device_id)],
      ["COMMAND FABRIC", trust.transport.replaceAll("_", " ").toUpperCase()],
      ["KEY STORAGE", trust.key_storage.replaceAll("_", " ").toUpperCase()],
      ["SIGNING KEY", trust.key_fingerprint.slice(0, 16).toUpperCase()],
      ["CERTIFICATE", trust.certificate_state.replaceAll("_", " ").toUpperCase()],
      ["REMOTE CHANNEL", trust.remote_channel.replaceAll("_", " ").toUpperCase()],
    );
    ui.deviceTrustState.textContent = trust.revoked ? "REVOKED" : "TRUSTED LOCAL";
    const pipeState = ipc?.connected ? "pipe online" : "HTTP recovery path";
    ui.deviceTrustDetail.textContent = `${trust.permissions.length} typed permissions // ${pipeState} // replay defence active`;
  }
  if (ipc) {
    rows.push(["NATIVE IPC", `${ipc.transport.replaceAll("_", " ").toUpperCase()} // ${ipc.connected ? "ONLINE" : "FALLBACK"}`]);
    ui.deviceIpcState.textContent = ipc.connected
      ? "AUTHENTICATED PIPE // SIGNED COMMANDS"
      : "HTTP RECOVERY // SIGNED COMMANDS";
  }
  if (cloud) {
    rows.push(
      ["OUTBOUND CHANNEL", `${cloud.transport.replaceAll("_", " ").toUpperCase()} // ${cloud.connected ? "CONNECTED" : "OFFLINE"}`],
      ["REMOTE EXECUTION", cloud.execution.replaceAll("_", " ").toUpperCase()],
      ["MUTUAL TLS", cloud.mtls.replaceAll("_", " ").toUpperCase()],
    );
    ui.cloudRouterState.textContent = cloud.connected
      ? "CONNECTED"
      : cloud.configured ? "CONFIGURED // OFFLINE" : "NOT CONNECTED";
  }
  if (model) {
    rows.push(
      ["QUALITY MODEL", `${model.name} // ${model.warm ? "WARM" : model.priming ? "PRIMING" : "STANDBY"}`],
      ["FAST MODEL", `${model.fast?.name || "NOT CONFIGURED"} // ${model.fast?.warm ? "WARM" : model.fast?.priming ? "PRIMING" : model.fast?.connected ? "READY" : "OFFLINE"}`],
    );
  }
  ui.systemView.innerHTML = rows.map(([label, value]) => `<div class="telemetry-row"><span>${escapeHtml(label)}</span><div>${escapeHtml(value)}</div></div>`).join("");
}

function renderNeuralRoute(intelligence) {
  const route = String(intelligence?.route || "quality").toUpperCase();
  const duration = Number(intelligence?.duration_ms);
  ui.responseRouteReadout.textContent = Number.isFinite(duration) ? `${route} ${duration}MS` : route;
  ui.responseRouteReadout.title = `${intelligence?.model || intelligence?.provider || "AURIS"} response route`;
}

function renderModelStandby(model) {
  if (!model || !ui.responseRouteReadout) return;
  const qualityReady = Boolean(model.warm);
  const fastReady = Boolean(model.fast?.warm);
  if (qualityReady && fastReady) ui.responseRouteReadout.textContent = "DUAL WARM";
  else if (fastReady) ui.responseRouteReadout.textContent = "FAST WARM";
  else if (model.priming || model.fast?.priming) ui.responseRouteReadout.textContent = "WARMING";
  else ui.responseRouteReadout.textContent = "STANDBY";
}

function renderAgents(agents) {
  latestAgents = agents;
  ui.agentsView.innerHTML = agents.map((agent) => `
    <div class="agent-row ${escapeHtml(agent.status)}"><i></i><span>${escapeHtml(agent.name)}</span><small>${escapeHtml(agent.status).toUpperCase()}</small></div>`
  ).join("");
  ui.commandAgentList.innerHTML = agents.slice(0, 8).map((agent, index) => `
    <div class="command-agent ${escapeHtml(agent.status)}"><i></i><span>${String(index + 1).padStart(2, "0")} // ${escapeHtml(agent.name).toUpperCase()}</span><b>${escapeHtml(agent.status).replaceAll("_", " ").toUpperCase()}</b></div>
  `).join("");
  ui.commandEngineList.innerHTML = agents.length ? agents.slice(0, 6).map((agent) => `
    <div class="engine-status ${escapeHtml(agent.status)}"><i></i><span>${escapeHtml(agent.name).replaceAll("_", " ").toUpperCase()}</span><b>${escapeHtml(agent.status).replaceAll("_", " ").toUpperCase()}</b></div>
  `).join("") : "<p>No agent fabric reported.</p>";
  coreVisual.setAgents(agents);
  const online = agents.filter((agent) => agent.status === "online").length;
  ui.coreAgentMetric.textContent = `${online} / ${agents.length} ONLINE`;
}

function renderCommandTelemetry(status) {
  const device = status.device || {};
  const cpu = device.cpu || {};
  const memory = device.memory || {};
  const gpu = device.gpu || {};
  const disk = device.disk || {};
  const cpuUsage = finitePercent(cpu.utilization_percent);
  const memoryUsage = finitePercent(memory.utilization_percent);
  const gpuUsage = finitePercent(gpu.utilization_percent);
  const diskUsage = finitePercent(
    disk.utilization_percent ?? (Number(disk.total_gb) > 0 ? (Number(disk.used_gb) / Number(disk.total_gb)) * 100 : null),
  );
  ui.commandMachineName.textContent = device.machine || "EDGE NODE";
  ui.commandCpuUsage.textContent = cpuUsage === null ? "N/A" : `${cpuUsage}%`;
  ui.commandCpuBar.style.width = `${cpuUsage || 0}%`;
  setRadialGauge(ui.commandCpuGauge, cpuUsage, "CPU");
  ui.commandCpuDetail.textContent = cpu.model ? `${cpu.model} // ${device.cpu_count || "?"} THREADS` : `${device.cpu_count || "?"} LOGICAL THREADS`;
  ui.commandRamUsage.textContent = memoryUsage === null ? "N/A" : `${memoryUsage}%`;
  ui.commandRamBar.style.width = `${memoryUsage || 0}%`;
  setRadialGauge(ui.commandRamGauge, memoryUsage, "MEMORY");
  ui.commandRamDetail.textContent = memory.total_gb !== undefined ? `${memory.used_gb} GB ACTIVE // ${memory.total_gb} GB TOTAL` : "Memory telemetry unavailable";
  ui.commandGpuUsage.textContent = gpuUsage === null ? "N/A" : `${gpuUsage}%`;
  ui.commandGpuBar.style.width = `${gpuUsage || 0}%`;
  setRadialGauge(ui.commandGpuGauge, gpuUsage, "GPU");
  ui.commandGpuDetail.textContent = gpu.name ? `${gpu.name} // ${gpu.memory_used_mb || 0}/${gpu.memory_total_mb || 0} MB` : "No GPU telemetry reported";
  ui.commandDiskPercent.textContent = diskUsage === null ? "N/A" : `${diskUsage}%`;
  ui.commandDiskBar.style.width = `${diskUsage || 0}%`;
  ui.commandDiskGaugeDetail.textContent = disk.total_gb !== undefined ? `${disk.used_gb} GB USED // ${disk.total_gb} GB TOTAL` : "Storage telemetry unavailable";
  setRadialGauge(ui.commandDiskGauge, diskUsage, "STORAGE");
  ui.commandDiskUsage.textContent = disk.total_gb !== undefined ? `${disk.used_gb} / ${disk.total_gb} GB` : "UNAVAILABLE";
  ui.commandUptime.textContent = device.uptime_seconds !== undefined ? formatDuration(device.uptime_seconds) : "UNAVAILABLE";
  ui.commandPower.textContent = device.power?.ac_line === true ? "AC POWER" : device.power?.battery_percent !== null && device.power?.battery_percent !== undefined ? `${device.power.battery_percent}% BATTERY` : "UNAVAILABLE";
  ui.commandPlatform.textContent = String(device.platform || "UNAVAILABLE").split("-").slice(0, 2).join(" ");
  ui.commandProcesses.innerHTML = (device.top_processes || []).slice(0, 6).map((process, index) => `<span>${String(index + 1).padStart(2, "0")} // ${escapeHtml(process)}</span>`).join("") || "No process names reported.";
  ui.commandAgentCount.textContent = String((status.agents || []).filter((agent) => agent.status === "online").length).padStart(2, "0");
  ui.commandTaskCount.textContent = String(status.metrics?.active_tasks || 0).padStart(2, "0");
  ui.commandApprovalCount.textContent = String(status.metrics?.pending_approvals || 0).padStart(2, "0");
  ui.coreMissionMetric.textContent = `${status.metrics?.active_tasks || 0} ACTIVE`;
  appendTelemetrySample("cpu", cpuUsage);
  appendTelemetrySample("memory", memoryUsage);
  appendTelemetrySample("gpu", gpuUsage);
  renderTelemetryHistory();
}

function setRadialGauge(element, value, label) {
  if (!element) return;
  const available = value !== null;
  element.style.setProperty("--meter", `${available ? value : 0}%`);
  element.classList.toggle("unavailable", !available);
  element.setAttribute("aria-label", available ? `${label} ${value} percent` : `${label} telemetry unavailable`);
}

function appendTelemetrySample(channel, value) {
  const samples = telemetryHistory[channel];
  if (!samples) return;
  samples.push(value);
  if (samples.length > 28) samples.shift();
}

function telemetryPoints(samples, width = 200, height = 64) {
  if (!samples.length || samples.every((value) => value === null)) return "";
  const lastIndex = Math.max(1, samples.length - 1);
  return samples
    .map((value, index) => value === null ? null : `${((index / lastIndex) * width).toFixed(1)},${(height - (value / 100) * height).toFixed(1)}`)
    .filter(Boolean)
    .join(" ");
}

function renderTelemetryHistory() {
  ui.commandCpuTrace.setAttribute("points", telemetryPoints(telemetryHistory.cpu));
  ui.commandRamTrace.setAttribute("points", telemetryPoints(telemetryHistory.memory));
  ui.commandGpuTrace.setAttribute("points", telemetryPoints(telemetryHistory.gpu));
}

function finitePercent(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : null;
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  return `${days ? `${days}D ` : ""}${String(hours).padStart(2, "0")}H ${String(minutes).padStart(2, "0")}M`;
}

function syncSessionControls() {
  const privateMode = isPrivate();
  ui.activeMode.textContent = ui.modeSelect.value.toUpperCase();
  ui.memoryMode.textContent = privateMode ? "MEMORY DISABLED" : "PERSISTENT";
  ui.memoryForm.querySelectorAll("input, select, textarea, button").forEach((control) => { control.disabled = privateMode; });
  ui.memoryFilterForm.querySelectorAll("input, select, button").forEach((control) => { control.disabled = privateMode; });
  ui.memoryExport.disabled = privateMode;
  ui.privacyTopState.innerHTML = privateMode ? "<i></i>PRIVACY PRIVATE" : "<i></i>PRIVACY STANDARD";
  ui.privacyTopState.className = privateMode ? "signal listening" : "signal";
  loadMemories();
  loadBrowserStatus();
}

function setWorkspace(name) {
  if (name !== "command" && document.body.classList.contains("neural-focus")) toggleNeuralFocus(false);
  document.body.dataset.workspace = name;
  document.querySelectorAll("[data-view-panel]").forEach((panel) => panel.classList.toggle("active", panel.dataset.viewPanel === name));
  document.querySelectorAll("[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
}

function setVisualQuality(quality) {
  if (!['eco', 'balanced', 'cinematic'].includes(quality)) return;
  coreVisual.setQuality(quality);
  ui.coreQuality.textContent = quality.toUpperCase();
  document.querySelectorAll("button[data-quality]").forEach((button) => button.classList.toggle("active", button.dataset.quality === quality));
  try { window.localStorage.setItem("auris-neural-quality", quality); } catch (_error) { /* Local preference is optional. */ }
}

function setCoreViewMode(mode) {
  if (!["3d", "2d", "schematic"].includes(mode)) return;
  coreVisual.setViewMode(mode);
  coreCanvas.dataset.viewMode = mode;
  ui.coreProjection.textContent = mode.toUpperCase();
  document.querySelectorAll("button[data-core-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.coreView === mode);
  });
  try { window.localStorage.setItem("auris-core-view", mode); } catch (_error) { /* Local preference is optional. */ }
}

function renderCoreInspector(detail, focused = false) {
  const data = detail || { name: "field", label: "NEURAL FIELD", active: true };
  const phase = focused ? "FOCUSED" : detail ? "OBSERVED" : "AMBIENT";
  ui.coreInspector.dataset.visible = detail ? "true" : "false";
  ui.coreInspector.innerHTML = `
    <span>${escapeHtml(data.label)}</span>
    <strong>${escapeHtml(data.name).toUpperCase()} // ${phase}</strong>
    <dl>
      <div><dt>STATUS</dt><dd>${data.active === false ? "STANDBY" : "LIVE"}</dd></div>
      <div><dt>ACTIVITY</dt><dd>${phase}</dd></div>
      <div><dt>SIGNAL</dt><dd>LOCAL</dd></div>
    </dl>`;
}

function toggleNeuralFocus(force) {
  const enabled = typeof force === "boolean" ? force : !document.body.classList.contains("neural-focus");
  document.body.classList.toggle("neural-focus", enabled);
  ui.toggleFocusMode.textContent = enabled ? "RESTORE" : "FOCUS";
  coreVisual.setFocus(enabled);
}

function openCommandPalette() {
  if (!ui.commandPalette.open) ui.commandPalette.showModal();
  ui.commandPaletteInput.value = "";
  renderCommandPalette();
  window.setTimeout(() => ui.commandPaletteInput.focus(), 30);
}

async function renderCommandPalette() {
  const query = ui.commandPaletteInput.value.trim().toLowerCase();
  const workspaces = ["command", "daily", "missions", "projects", "research", "engineering", "documents", "devices", "memory", "decisions", "approvals", "activity", "events", "browser", "integrations"];
  const commands = ["Open Notepad", "Open Calculator", "Open Documents", "List files in Documents", "Describe my screen", "Show system health", "Prepare my daily briefing", "Analyse this project", "Run the tests"];
  const results = [];
  workspaces.filter((item) => !query || item.includes(query)).slice(0, 6).forEach((item) => results.push(`<button type="button" data-palette-view="${escapeHtml(item)}"><span>WORKSPACE</span><strong>${escapeHtml(item).toUpperCase()}</strong><small>OPEN SUBSYSTEM</small></button>`));
  commands.filter((item) => !query || item.toLowerCase().includes(query)).slice(0, 5).forEach((item) => results.push(`<button type="button" data-palette-command="AURIS, ${escapeHtml(item.toLowerCase())}"><span>COMMAND</span><strong>${escapeHtml(item)}</strong><small>LOAD DIRECTIVE</small></button>`));
  projectsCache.filter((item) => !query || item.name.toLowerCase().includes(query)).slice(0, 3).forEach((item) => results.push(`<button type="button" data-palette-view="projects"><span>PROJECT</span><strong>${escapeHtml(item.name)}</strong><small>${item.root_path ? "REGISTERED ROOT" : "NO LOCAL ROOT"}</small></button>`));
  latestAgents.filter((item) => !query || item.name.toLowerCase().includes(query)).slice(0, 3).forEach((item) => results.push(`<button type="button" data-palette-view="missions"><span>AGENT</span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.status).replaceAll("_", " ").toUpperCase()}</small></button>`));
  if (query) {
    results.push(`<button type="button" data-palette-command="AURIS, search memory for ${escapeHtml(ui.commandPaletteInput.value.trim())}"><span>MEMORY</span><strong>Search temporal memory</strong><small>${escapeHtml(ui.commandPaletteInput.value.trim())}</small></button>`);
    results.push(`<button type="button" data-palette-command="AURIS, find files named ${escapeHtml(ui.commandPaletteInput.value.trim())}"><span>FILES</span><strong>Search approved folders</strong><small>${escapeHtml(ui.commandPaletteInput.value.trim())}</small></button>`);
  }
  ui.commandPaletteResults.innerHTML = results.join("") || empty("No matching AURIS operation.");
  if (!query || isPrivate()) return;
  try {
    const data = await fetchJson(`/api/memories?q=${encodeURIComponent(query)}&limit=4`);
    if (ui.commandPaletteInput.value.trim().toLowerCase() !== query) return;
    const memoryResults = data.memories.map((memory) => `<button type="button" data-palette-view="memory"><span>MEMORY</span><strong>${escapeHtml(memory.content)}</strong><small>${escapeHtml(memory.category).toUpperCase()} // ${escapeHtml(memory.temporal_state).toUpperCase()}</small></button>`).join("");
    if (memoryResults) ui.commandPaletteResults.insertAdjacentHTML("beforeend", memoryResults);
  } catch (_error) {
    // Universal search keeps local workspace and command results available.
  }
}

function activatePaletteItem(item) {
  if (item.dataset.paletteView) setWorkspace(item.dataset.paletteView);
  if (item.dataset.paletteCommand) {
    ui.commandInput.value = item.dataset.paletteCommand;
    ui.commandInput.focus();
  }
  ui.commandPalette.close();
}

function dismissBootSequence() {
  ui.bootSequence.classList.add("complete");
  try { window.sessionStorage.setItem("auris-boot-complete", "true"); } catch (_error) { /* Session state is optional. */ }
  window.setTimeout(() => { ui.bootSequence.hidden = true; }, 650);
}

function setCoreState(state) {
  activeCoreState = state;
  coreVisual.setState(state);
  const labels = {
    dormant: ["READY", wakeModeActive ? "WAKE WORD ARMED" : "AWAITING DIRECTIVE"],
    listening: ["LISTENING", "WINDOWS MICROPHONE ACTIVE"],
    understanding: ["UNDERSTANDING", "INTERPRETING VOICE INPUT"],
    planning: ["PLANNING", "CONSTRUCTING MISSION GRAPH"],
    executing: ["EXECUTING", "DEVICE CHANNEL ACTIVE"],
    speaking: ["SPEAKING", "NEURAL VOICE OUTPUT ACTIVE"],
    approval: ["AWAITING", "AUTHORISATION REQUIRED"],
    completed: ["VERIFIED", "MISSION COMPLETE"],
    warning: ["WARNING", "RESULT REQUIRES ATTENTION"],
    critical: ["STOPPED", "OPERATIONS BLOCKED"],
  };
  const [label, detail] = labels[state] || labels.dormant;
  ui.coreStateLabel.textContent = label;
  ui.coreStateDetail.textContent = detail;
  ui.coreReasoningMetric.textContent = label;
}

function setOperation(label, detail) {
  ui.liveOperation.innerHTML = `<i></i><span>${escapeHtml(label)}</span> ${escapeHtml(detail)}`;
}

function addTranscript(kind, label, text) {
  const classNames = {
    user: "user-entry",
    auris: "auris-entry",
    verification: "verification-entry",
    warning: "warning-entry",
    system: "verification-entry",
  };
  const node = document.createElement("article");
  node.className = `transcript-entry ${classNames[kind] || "auris-entry"}`;
  node.innerHTML = `<header><time>${escapeHtml(currentTime())}</time><span>${escapeHtml(label)}</span></header><p>${escapeHtml(text)}</p>`;
  ui.messages.appendChild(node);
  ui.conversation.scrollTop = ui.conversation.scrollHeight;
}

function playTone(kind) {
  try {
    audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    const frequencies = { listen: 660, complete: 520, warning: 220 };
    oscillator.frequency.value = frequencies[kind] || 440;
    oscillator.type = "sine";
    gain.gain.setValueAtTime(0.025, audioContext.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.14);
    oscillator.connect(gain).connect(audioContext.destination);
    oscillator.start();
    oscillator.stop(audioContext.currentTime + 0.15);
  } catch (error) {
    return;
  }
}

function refreshOperationalData() {
  if (operationalRefresh) return operationalRefresh;
  operationalRefresh = Promise.allSettled([
    loadStatus(),
    loadTasks(),
    loadApprovals(),
    loadMemories(),
    loadAudit(),
    loadCapabilities(),
    loadEvents(),
    loadIntegrations(),
    loadAdvancedWorkspaces(),
    loadDecisions(),
    loadBrowserStatus(),
  ]).then((results) => results.filter((result) => result.status === "rejected").length)
    .finally(() => { operationalRefresh = null; });
  return operationalRefresh;
}

async function fetchJson(url, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  if (!["GET", "HEAD"].includes(method) && csrfToken) headers.set("X-AURIS-CSRF", csrfToken);
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), method === "GET" ? 20000 : 240000);
  try {
    const response = await fetch(url, { ...options, headers, credentials: "same-origin", signal: options.signal || controller.signal });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || data.voice?.error || "AURIS request failed.");
    return data;
  } finally {
    window.clearTimeout(timer);
  }
}

function isPrivate() { return ui.privateToggle.checked || ui.modeSelect.value === "private"; }
function empty(text) { return `<div class="empty-state">${escapeHtml(text)}</div>`; }
function shortId(value) { return String(value).split("-")[0].toUpperCase(); }
function formatTime(value) { return value ? new Date(value).toLocaleString("en-GB") : ""; }
function localDateTimeToIso(value) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}
function isoToLocalDateTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  const local = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}
function currentTime() { return new Date().toLocaleTimeString("en-GB", { hour12: false }); }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[char]); }

function createInertCore() {
  return {
    start() {},
    setState() {},
    setAgents() {},
    setQuality() {},
    setFocus() {},
    setViewMode() {},
    focusCluster() {},
    destroy() {},
  };
}

async function initializeNeuralVisual() {
  try {
    const neuralModule = await import("/neural-core.js?v=0.8.34.0");
    const enhancedCore = neuralModule.createAurisNeuralCore(coreCanvas);
    if (coreCanvas.dataset.renderer === "unavailable") {
      coreVisual = createCoreVisual(coreCanvas);
      coreCanvas.dataset.renderer = "canvas-2d-fallback";
    } else {
      coreVisual = enhancedCore;
    }
  } catch (_error) {
    coreVisual = createCoreVisual(coreCanvas);
    coreCanvas.dataset.renderer = coreCanvas.dataset.renderer || "canvas-2d-fallback";
    addTranscript(
      "warning",
      "VISUAL CORE",
      "The advanced renderer is unavailable. Backend commands and the resilient display remain operational.",
    );
  }
  coreVisual.setState(activeCoreState);
  coreVisual.setAgents(latestAgents);
  const selectedQuality = document.querySelector("button[data-quality].active")?.dataset.quality || "balanced";
  coreVisual.setQuality(selectedQuality);
  const selectedView = document.querySelector("button[data-core-view].active")?.dataset.coreView || "3d";
  coreVisual.setViewMode(selectedView);
  coreVisual.start();
}

function createCoreVisual(canvas) {
  const context = canvas.getContext("2d");
  if (!context) return createInertCore();
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let state = "dormant";
  let frame = 0;

  const stateColours = {
    dormant: "#ffb13b",
    listening: "#ffd66b",
    understanding: "#ffedb0",
    planning: "#ffc34f",
    executing: "#ff8a31",
    speaking: "#ffd889",
    approval: "#ff8a31",
    completed: "#57e7a5",
    warning: "#ffb85c",
    critical: "#ff5268",
  };

  function draw(timestamp) {
    const rect = canvas.getBoundingClientRect();
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(rect.width * ratio));
    const height = Math.max(1, Math.floor(rect.height * ratio));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }

    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, rect.width, rect.height);
    const cx = rect.width / 2;
    const cy = rect.height / 2 - 5;
    const radius = Math.min(rect.width, rect.height) * 0.24;
    const colour = stateColours[state] || stateColours.dormant;
    const motion = reducedMotion ? 0 : timestamp * (state === "dormant" ? 0.00008 : 0.00022);
    const pulse = reducedMotion ? 0.5 : (Math.sin(timestamp * 0.0022) + 1) / 2;

    context.save();
    context.translate(cx, cy);
    context.strokeStyle = "rgba(132,203,230,0.11)";
    context.lineWidth = 1;
    for (let ring = 1; ring <= 4; ring += 1) {
      context.beginPath();
      context.arc(0, 0, radius * (0.55 + ring * 0.24), 0, Math.PI * 2);
      context.stroke();
    }

    context.strokeStyle = colour;
    context.shadowColor = colour;
    context.shadowBlur = state === "critical" ? 4 : 10;
    context.lineWidth = 1.4;
    for (let ring = 0; ring < 3; ring += 1) {
      const ringRadius = radius * (0.72 + ring * 0.31);
      const segments = 9 + ring * 3;
      for (let segment = 0; segment < segments; segment += 1) {
        if ((segment + ring) % 4 === 0) continue;
        const start = motion * (ring % 2 ? -1 : 1) + (segment / segments) * Math.PI * 2;
        const length = (Math.PI * 2 / segments) * 0.58;
        context.globalAlpha = 0.32 + ring * 0.12 + pulse * 0.12;
        context.beginPath();
        context.arc(0, 0, ringRadius, start, start + length);
        context.stroke();
      }
    }

    const nodes = state === "planning" ? 10 : state === "listening" ? 14 : 7;
    for (let index = 0; index < nodes; index += 1) {
      const angle = motion * 2 + (index / nodes) * Math.PI * 2;
      const distance = radius * (1.35 + (index % 3) * 0.22);
      const x = Math.cos(angle) * distance;
      const y = Math.sin(angle) * distance;
      context.globalAlpha = 0.28 + (index % 3) * 0.18;
      context.beginPath();
      context.moveTo(Math.cos(angle) * radius * 1.05, Math.sin(angle) * radius * 1.05);
      context.lineTo(x, y);
      context.stroke();
      context.fillStyle = colour;
      context.fillRect(x - 1.5, y - 1.5, 3, 3);
    }

    context.globalAlpha = 0.85;
    context.fillStyle = colour;
    context.shadowBlur = 18;
    context.beginPath();
    context.arc(0, 0, radius * (0.12 + pulse * 0.025), 0, Math.PI * 2);
    context.fill();
    context.globalAlpha = 0.15;
    context.beginPath();
    context.arc(0, 0, radius * (0.30 + pulse * 0.04), 0, Math.PI * 2);
    context.fill();
    context.restore();

    frame = window.requestAnimationFrame(draw);
  }

  return {
    start() { if (!frame) frame = window.requestAnimationFrame(draw); },
    setState(nextState) { state = nextState; },
    setAgents() {},
    setQuality() {},
    setFocus() {},
    setViewMode(mode) { canvas.dataset.viewMode = mode; },
    focusCluster(name) {
      canvas.dispatchEvent(new CustomEvent("auris-core-focus", {
        detail: name ? { name, label: `${name.toUpperCase()} SUBSYSTEM`, active: true } : null,
      }));
    },
    destroy() { if (frame) window.cancelAnimationFrame(frame); frame = 0; },
  };
}

async function initialize() {
  let preferredQuality = "balanced";
  let preferredCoreView = "3d";
  try {
    preferredQuality = window.localStorage.getItem("auris-neural-quality") || "balanced";
    preferredCoreView = window.localStorage.getItem("auris-core-view") || "3d";
  } catch (_error) {
    // Local display preferences are optional.
  }
  setVisualQuality(preferredQuality);
  setCoreViewMode(preferredCoreView);
  let bootSeen = false;
  try { bootSeen = window.sessionStorage.getItem("auris-boot-complete") === "true"; } catch (_error) { /* Session state is optional. */ }
  const bootDelay = bootSeen || window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 350 : 2800;
  window.setTimeout(dismissBootSequence, bootDelay);
  window.setInterval(() => { ui.systemClock.textContent = currentTime(); }, 1000);
  ui.systemClock.textContent = currentTime();
  try {
    const session = await fetchJson("/api/session");
    csrfToken = session.session.csrf_token;
    ui.serverState.className = "signal online";
    ui.serverState.innerHTML = "<i></i>AURIS BACKEND ONLINE";
    void initializeNeuralVisual();
    try {
      await fetchJson("/api/client/ready", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ui_version: "0.8.34.0",
          renderer: coreCanvas.dataset.renderer || "initialising",
        }),
      });
      document.body.dataset.backend = "online";
    } catch (error) {
      document.body.dataset.backend = "degraded";
      addTranscript(
        "warning",
        "BACKEND",
        `The readiness audit is unavailable (${error.message}); authenticated commands remain operational.`,
      );
    }
    void Promise.allSettled([loadProjects(), loadConversationHistory()]);
    void refreshOperationalData().then((optionalFailures) => {
      if (optionalFailures) addTranscript("warning", "BACKEND", `${optionalFailures} workspace channels unavailable.`);
    });
    syncSessionControls();
    setCoreState(controlStopped ? "critical" : "dormant");
    window.setInterval(loadVoiceStatus, 600);
    window.setInterval(loadStatus, 2500);
    window.setInterval(loadEvents, 15000);
    window.setInterval(loadAudit, 7500);
    window.setInterval(() => { loadTasks().catch(() => {}); }, 3000);
  } catch (error) {
    document.body.dataset.backend = "offline";
    addTranscript("warning", "SYSTEM", `AURIS initialization failed: ${error.message}`);
    setCoreState("critical");
  }
}

initialize();
