// API Server configurations
const API_BASE = "/api/v1";

// Global state variables
let activeLogIdForFeedback = null;
let costSavingsChartInstance = null;
let tierDistributionChartInstance = null;
let domainDistributionChartInstance = null;
let allLogsData = [];
let activeCalibrationWeights = {};

// Initial Setup on DOM Content Loaded
document.addEventListener("DOMContentLoaded", () => {
  initializeDashboard();
});

async function initializeDashboard() {
  checkProviderStatus();
  await fetchSummary();
  await fetchPolicies();
  await fetchCalibrationWeights();
  await fetchLogs();
}

// Check Gateway Provider Live Status
async function checkProviderStatus() {
  const badge = document.getElementById("provider-status-badge");
  const textEl = document.getElementById("provider-status-text");
  if (!badge || !textEl) return;

  try {
    const res = await fetch(`${API_BASE}/agents/registry`);
    const data = await res.json();
    const isLive = data.agent_pool && data.agent_pool.some(a => a.status === "live");

    if (isLive) {
      badge.className = "provider-status-badge live";
      textEl.innerText = "Groq Live API Connected";
    } else {
      badge.className = "provider-status-badge mock";
      textEl.innerText = "Mock Mode Fallback";
    }
  } catch (err) {
    badge.className = "provider-status-badge mock";
    textEl.innerText = "Offline / Standby";
  }
}

// Tab Switching Mechanism
function switchTab(event, panelId) {
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.remove("active"));
  
  event.currentTarget.classList.add("active");
  document.getElementById(panelId).classList.add("active");
  
  if (panelId === 'tab-analytics') {
    fetchSummary();
    fetchLogs();
  } else if (panelId === 'tab-rag') {
    fetchKnowledgeBaseDocuments();
  } else if (panelId === 'tab-agents') {
    fetchAgentRegistry();
  } else if (panelId === 'tab-policies') {
    fetchPolicies();
    fetchCalibrationWeights();
    fetchSummary();
  } else if (panelId === 'tab-logs') {
    fetchLogs();
  }
}

// Quick Prompt Presets
function applyPreset(type) {
  const promptEl = document.getElementById("sandbox-prompt");
  const domainEl = document.getElementById("sandbox-domain");
  const formatEl = document.getElementById("sandbox-format");

  if (!promptEl || !domainEl || !formatEl) return;

  if (type === 'coding') {
    promptEl.value = "Write a Python function to implement quicksort with type annotations and docstring.";
    domainEl.value = "coding";
    formatEl.value = "python";
  } else if (type === 'math') {
    promptEl.value = "Solve the expression 345 * 28 + sqrt(144) step by step.";
    domainEl.value = "math";
    formatEl.value = "";
  } else if (type === 'rag') {
    promptEl.value = "What are the minimum confidence thresholds and pricing details documented in the knowledge base?";
    domainEl.value = "general";
    formatEl.value = "";
  } else if (type === 'analysis') {
    promptEl.value = "Parse and analyze latency percentiles and error rates from server log lines.";
    domainEl.value = "analysis";
    formatEl.value = "";
  } else if (type === 'escalation') {
    promptEl.value = "Output configuration JSON";
    domainEl.value = "general";
    formatEl.value = "json";
  }
}

// Copy Response Output
function copyOutputResponse() {
  const resultText = document.getElementById("result-text");
  const copyBtn = document.getElementById("copy-output-btn");
  if (!resultText || !resultText.innerText.trim()) return;

  navigator.clipboard.writeText(resultText.innerText).then(() => {
    if (copyBtn) {
      const originalHtml = copyBtn.innerHTML;
      copyBtn.innerHTML = `<i class="fa-solid fa-check"></i> Copied!`;
      copyBtn.style.color = "var(--color-success)";
      setTimeout(() => {
        copyBtn.innerHTML = originalHtml;
        copyBtn.style.color = "";
      }, 2000);
    }
  }).catch(err => {
    console.error("Clipboard copy error:", err);
  });
}

// Fetch Metrics & Budget Summary
async function fetchSummary() {
  try {
    const res = await fetch(`${API_BASE}/analytics/summary`);
    const data = await res.json();
    
    document.getElementById("kpi-requests").innerText = (data.total_requests || 0).toLocaleString();
    document.getElementById("kpi-cost").innerText = `$${(data.daily_spent_usd || data.total_cost_spent || 0).toFixed(5)}`;
    
    if (document.getElementById("kpi-daily-limit")) {
      document.getElementById("kpi-daily-limit").innerText = `Daily limit: $${(data.daily_budget_usd || 10.0).toFixed(2)}`;
    }
    if (document.getElementById("kpi-monthly-spent")) {
      document.getElementById("kpi-monthly-spent").innerText = `$${(data.monthly_spent_usd || 0).toFixed(5)}`;
    }
    if (document.getElementById("kpi-monthly-limit")) {
      document.getElementById("kpi-monthly-limit").innerText = `Monthly limit: $${(data.monthly_budget_usd || 100.0).toFixed(2)}`;
    }

    const pressureEl = document.getElementById("kpi-budget-pressure");
    const pressureDescEl = document.getElementById("kpi-pressure-desc");
    if (pressureEl) {
      const score = data.budget_pressure_score || 0;
      pressureEl.innerText = `${score} / 100`;
      if (score >= 80) {
        pressureEl.style.color = "var(--color-error)";
        if (pressureDescEl) pressureDescEl.innerText = "High pressure (auto-downgrade active)";
      } else if (score >= 50) {
        pressureEl.style.color = "var(--color-warning)";
        if (pressureDescEl) pressureDescEl.innerText = "Moderate pressure (cost-optimized)";
      } else {
        pressureEl.style.color = "var(--color-success)";
        if (pressureDescEl) pressureDescEl.innerText = "Low pressure (normal routing)";
      }
    }

    if (document.getElementById("kpi-cost-per-req")) {
      document.getElementById("kpi-cost-per-req").innerText = `$${(data.avg_cost_per_request_usd || 0).toFixed(5)}`;
    }

    document.getElementById("kpi-savings").innerText = `$${(data.cost_saved_vs_frontier_only || 0).toFixed(5)}`;
    document.getElementById("kpi-latency").innerText = `${data.average_latency_ms || 0} ms`;
    document.getElementById("kpi-escalation").innerText = `${((data.escalation_rate || 0) * 100).toFixed(1)}%`;
    
    // Set Budget inputs if in policy tab
    const dailyInp = document.getElementById("cfg-daily-budget");
    const monthlyInp = document.getElementById("cfg-monthly-budget");
    if (dailyInp && !dailyInp.getAttribute("data-user-modified")) {
      dailyInp.value = (data.daily_budget_usd || 10.0).toFixed(1);
    }
    if (monthlyInp && !monthlyInp.getAttribute("data-user-modified")) {
      monthlyInp.value = (data.monthly_budget_usd || 100.0).toFixed(1);
    }

    updateDistributionChart(data.tier_distribution || {tier_1:1, tier_2:0, tier_3:0, tier_4:0});
  } catch (error) {
    console.error("Error fetching summary stats:", error);
  }
}

// Save Budget Limits
async function saveBudgetLimits() {
  const dailyVal = parseFloat(document.getElementById("cfg-daily-budget").value);
  const monthlyVal = parseFloat(document.getElementById("cfg-monthly-budget").value);
  
  if (isNaN(dailyVal) || dailyVal <= 0 || isNaN(monthlyVal) || monthlyVal <= 0) {
    alert("Please enter valid positive numbers for budget limits.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/analytics/budget`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        daily_budget_usd: dailyVal,
        monthly_budget_usd: monthlyVal
      })
    });
    const updated = await res.json();
    alert(`Budget limits updated! Daily: $${updated.daily_budget_usd.toFixed(2)}, Monthly: $${updated.monthly_budget_usd.toFixed(2)}`);
    fetchSummary();
  } catch (error) {
    console.error("Error updating budget limits:", error);
    alert("Failed to update budget limits.");
  }
}

// Confidence Calibration Management
async function fetchCalibrationWeights() {
  const container = document.getElementById("calibration-cards-container");
  if (!container) return;

  try {
    const res = await fetch(`${API_BASE}/evaluator/calibration`);
    const data = await res.json();
    activeCalibrationWeights = data.domain_weights || {};

    container.innerHTML = "";
    const domains = Object.keys(activeCalibrationWeights);

    domains.forEach(domain => {
      const weights = activeCalibrationWeights[domain];
      const card = document.createElement("div");
      card.className = "calibration-card";
      
      let icon = "fa-layer-group";
      if (domain === "coding") icon = "fa-code";
      else if (domain === "math") icon = "fa-calculator";
      else if (domain === "rag" || domain === "research") icon = "fa-book-bookmark";
      else if (domain === "analysis") icon = "fa-chart-pie";

      card.innerHTML = `
        <div class="calibration-card-header">
          <div class="calibration-card-title">
            <i class="fa-solid ${icon}"></i> ${domain} Domain
          </div>
        </div>
        ${Object.keys(weights).map(dim => {
          const valPct = Math.round(weights[dim] * 100);
          return `
            <div class="weight-slider-group">
              <div class="weight-slider-label">
                <span style="text-transform: capitalize;">${dim}</span>
                <span id="label-${domain}-${dim}">${valPct}%</span>
              </div>
              <input type="range" class="weight-slider" id="slider-${domain}-${dim}" 
                min="0" max="100" value="${valPct}" 
                oninput="onWeightSliderChange('${domain}', '${dim}', this.value)">
            </div>
          `;
        }).join("")}
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Error fetching calibration weights:", err);
  }
}

function onWeightSliderChange(domain, dimension, val) {
  const label = document.getElementById(`label-${domain}-${dimension}`);
  if (label) label.innerText = `${val}%`;
  if (!activeCalibrationWeights[domain]) activeCalibrationWeights[domain] = {};
  activeCalibrationWeights[domain][dimension] = parseFloat(val) / 100.0;
}

async function saveCalibrationWeights() {
  try {
    for (const domain of Object.keys(activeCalibrationWeights)) {
      const weights = activeCalibrationWeights[domain];
      await fetch(`${API_BASE}/evaluator/calibration`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain, weights })
      });
    }
    alert("Domain confidence calibration weights successfully saved!");
    fetchCalibrationWeights();
  } catch (err) {
    console.error("Error saving calibration weights:", err);
    alert("Failed to save calibration weights.");
  }
}

// Fetch Routing Policies & Sliders
async function fetchPolicies() {
  try {
    const res = await fetch(`${API_BASE}/config/policies`);
    const policies = await res.json();
    
    const sliderList = document.getElementById("policy-slider-list");
    sliderList.innerHTML = "";
    
    policies.forEach(policy => {
      const card = document.createElement("div");
      card.className = "policy-card";
      
      const domainNormalized = policy.domain.charAt(0).toUpperCase() + policy.domain.slice(1);
      
      card.innerHTML = `
        <div class="policy-header">
          <div class="policy-title">${domainNormalized} Domain Policy</div>
          <div class="policy-threshold" id="val-${policy.domain}">
            ${(policy.min_confidence_threshold * 100).toFixed(0)}%
          </div>
        </div>
        <div class="slider-container">
          <input 
            type="range" 
            class="slider-input" 
            min="0.4" 
            max="0.99" 
            step="0.01" 
            value="${policy.min_confidence_threshold}"
            id="slider-${policy.domain}"
            oninput="handleSliderChange('${policy.domain}', this.value)"
          >
        </div>
      `;
      sliderList.appendChild(card);
    });
  } catch (error) {
    console.error("Error fetching routing policies:", error);
  }
}

function handleSliderChange(domain, value) {
  document.getElementById(`val-${domain}`).innerText = `${(parseFloat(value) * 100).toFixed(0)}%`;
  debounce(() => savePolicy(domain, parseFloat(value)), 500)();
}

async function savePolicy(domain, threshold) {
  try {
    await fetch(`${API_BASE}/config/policies/${domain}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ min_confidence_threshold: threshold })
    });
  } catch (error) {
    console.error(`Error saving policy for ${domain}:`, error);
  }
}

let timeoutId = null;
function debounce(func, delay) {
  return function(...args) {
    if (timeoutId) clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };
}

// Fetch and Display Logs Table
async function fetchLogs() {
  try {
    const res = await fetch(`${API_BASE}/analytics/logs?limit=50`);
    allLogsData = await res.json();
    filterLogsTable();
    updateSavingsChart(allLogsData);
    updateDomainDistributionChart(allLogsData);
  } catch (error) {
    console.error("Error fetching logs:", error);
  }
}

// Search and Filter Logs
function filterLogsTable() {
  const tbody = document.getElementById("logs-table-body");
  if (!tbody) return;

  const searchInput = document.getElementById("logs-search-input");
  const tierFilter = document.getElementById("logs-tier-filter");

  const query = searchInput ? searchInput.value.toLowerCase().trim() : "";
  const selectedTier = tierFilter ? tierFilter.value : "all";

  const filtered = allLogsData.filter(log => {
    const matchesQuery = !query || 
      log.prompt.toLowerCase().includes(query) || 
      (log.response && log.response.toLowerCase().includes(query)) ||
      (log.routing_reason && log.routing_reason.toLowerCase().includes(query));

    const matchesTier = selectedTier === "all" || log.final_tier === parseInt(selectedTier);
    return matchesQuery && matchesTier;
  });

  tbody.innerHTML = "";
  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--color-text-muted); padding: 2rem;">No matching logs found.</td></tr>`;
    return;
  }

  filtered.forEach(log => {
    const dateObj = new Date(log.created_at);
    const dateStr = dateObj.toLocaleDateString() + " " + dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    let feedbackBadge = `<span style="color: var(--color-text-muted); font-size: 0.8rem;">—</span>`;
    if (log.eval_score !== null && log.eval_score !== undefined) {
      if (log.eval_score >= 0.8) {
        feedbackBadge = `<span style="color: var(--color-success); font-weight:600;"><i class="fa-solid fa-thumbs-up"></i> High</span>`;
      } else {
        feedbackBadge = `<span style="color: var(--color-error); font-weight:600;"><i class="fa-solid fa-thumbs-down"></i> Low</span>`;
      }
    }
    
    const escalationPath = log.escalation_path && log.escalation_path.length > 0 
      ? log.escalation_path.map(t => `T${t}`).join(" → ") 
      : `T${log.final_tier}`;

    const mainRow = document.createElement("tr");
    mainRow.setAttribute("onclick", `toggleRowDetails('${log.id}')`);
    mainRow.innerHTML = `
      <td>${dateStr}</td>
      <td title="${escapeHtml(log.prompt)}" style="max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
        ${escapeHtml(log.prompt)}
      </td>
      <td><span class="tier-pill t${log.final_tier}">Tier ${log.final_tier}</span></td>
      <td><span style="font-weight: 600; font-size: 0.85rem;">${escalationPath}</span></td>
      <td>$${log.total_cost.toFixed(5)}</td>
      <td>${log.total_latency_ms} ms</td>
      <td title="${escapeHtml(log.routing_reason || '')}" style="max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.8rem; color: var(--color-text-muted);">
        ${escapeHtml(log.routing_reason || '—')}
      </td>
      <td>${feedbackBadge}</td>
    `;
    tbody.appendChild(mainRow);
    
    const detailRow = document.createElement("tr");
    detailRow.id = `detail-${log.id}`;
    detailRow.className = "log-expanded-row";
    detailRow.style.display = "none";
    
    let stepTraceHtml = `<div style="color: var(--color-text-muted); font-size: 0.8rem;">No step details available.</div>`;
    if (log.steps && log.steps.length > 0) {
      stepTraceHtml = log.steps.map((s, idx) => {
        const isLastStep = idx === log.steps.length - 1;
        const stepStatusLabel = isLastStep ? "✓ Accepted" : "↑ Escalated";
        return `
          <div class="step-trace-item">
            <div>
              <strong>Tier ${s.tier} (${escapeHtml(s.model_name)})</strong>
              <div style="font-size: 0.75rem; color: var(--color-text-muted);">
                Conf: ${s.confidence_score.toFixed(2)} | Cost: $${s.cost.toFixed(5)} | Latency: ${s.latency_ms}ms
              </div>
            </div>
            <div style="font-size: 0.75rem; font-weight: 600; color: ${isLastStep ? 'var(--color-success)' : 'var(--color-warning)'};">
              ${stepStatusLabel}
            </div>
          </div>
        `;
      }).join("");
    }
    
    detailRow.innerHTML = `
      <td colspan="8">
        <div class="log-expanded-details">
          <div class="expanded-grid">
            <div class="expanded-item">
              <h4>Prompt Context</h4>
              <div class="expanded-text-block">${escapeHtml(log.prompt)}</div>
              
              <h4 style="margin-top: 1rem;">Response Output</h4>
              <div class="expanded-text-block">${escapeHtml(log.response || "")}</div>

              <h4 style="margin-top: 1rem;">Routing Reason</h4>
              <div class="expanded-text-block" style="font-style: italic; color: var(--color-text-muted);">${escapeHtml(log.routing_reason || '—')}</div>
            </div>
            <div class="expanded-item">
              <h4>Routing Cascade Trace</h4>
              <div class="step-trace-list">
                ${stepTraceHtml}
              </div>
              ${log.feedback_text ? `
                <h4 style="margin-top: 1rem;">User Review</h4>
                <div class="expanded-text-block" style="font-style: italic;">"${escapeHtml(log.feedback_text)}"</div>
              ` : ""}
            </div>
          </div>
        </div>
      </td>
    `;
    tbody.appendChild(detailRow);
  });
}

function toggleRowDetails(logId) {
  const detailRow = document.getElementById(`detail-${logId}`);
  if (detailRow.style.display === "none") {
    detailRow.style.display = "table-row";
  } else {
    detailRow.style.display = "none";
  }
}

// Sandbox Prompt Submission
async function submitSandboxPrompt() {
  const promptText = document.getElementById("sandbox-prompt").value;
  const domain = document.getElementById("sandbox-domain").value;
  const format = document.getElementById("sandbox-format").value;
  const budgetVal = parseFloat(document.getElementById("sandbox-budget").value);
  const budget_limit_usd = !isNaN(budgetVal) && budgetVal > 0 ? budgetVal : null;
  
  if (!promptText.trim()) {
    alert("Please enter a prompt first.");
    return;
  }
  
  const visualizerContainer = document.getElementById("visualizer-list");
  visualizerContainer.innerHTML = `
    <div class="cascade-step active">
      <div class="step-badge">1</div>
      <div class="step-details">
        <div class="step-model">Router Gateway (Preprocessing & Cost Estimation)</div>
        <div class="step-meta">Evaluating task type, pre-request estimated cost, and active budget pressure...</div>
      </div>
      <div class="step-status running">Running</div>
    </div>
  `;
  
  document.getElementById("result-placeholder").style.display = "none";
  document.getElementById("result-text").innerText = "Invoking router, checking cost & budget intelligence...";
  document.getElementById("result-feedback-container").style.display = "none";
  
  try {
    const res = await fetch(`${API_BASE}/router/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: promptText,
        domain: domain,
        expected_format: format || null,
        budget_limit_usd: budget_limit_usd
      })
    });

    const result = await res.json();
    activeLogIdForFeedback = result.id;
    visualizerContainer.innerHTML = "";
    
    result.usage.routing_path.forEach((step, idx) => {
      const stepRow = document.createElement("div");
      const isLast = idx === result.usage.routing_path.length - 1;
      const passed = step.confidence_score >= result.threshold_used;
      
      let stepClass = isLast && passed ? "success" : "failed";
      let statusText = isLast && passed ? "PASS (Accepted)" : "FAIL (Escalated)";
      
      stepRow.className = `cascade-step ${stepClass}`;
      stepRow.innerHTML = `
        <div class="step-badge">${idx + 1}</div>
        <div class="step-details">
          <div class="step-model">Tier ${step.tier}: ${step.model_name}</div>
          <div class="step-meta">Confidence Score: <strong>${step.confidence_score.toFixed(2)}</strong> (Threshold: ${result.threshold_used.toFixed(2)}) | Latency: ${step.latency_ms}ms | Cost: $${step.cost.toFixed(5)}</div>
        </div>
        <div class="step-status ${isLast && passed ? 'pass' : 'fail'}">${statusText}</div>
      `;
      visualizerContainer.appendChild(stepRow);
    });

    const lastStep = result.usage.routing_path[result.usage.routing_path.length - 1];
    const escalationPath = result.usage.routing_path.map(s => `Tier ${s.tier}`).join(" → ");
    const preCost = result.pre_request_estimated_cost_usd || result.usage.pre_request_estimated_cost_usd || 0;
    const pressureScore = result.budget_pressure_score !== undefined ? result.budget_pressure_score : (result.usage.budget_pressure_score || 0);

    document.getElementById("ss-tier").innerHTML = `<span class="tier-pill t${result.final_tier}">Tier ${result.final_tier}</span>`;
    document.getElementById("ss-confidence").innerText = lastStep ? lastStep.confidence_score.toFixed(3) : "—";
    document.getElementById("ss-precost").innerText = `$${preCost.toFixed(6)}`;
    document.getElementById("ss-cost").innerText = `$${result.usage.total_cost_usd.toFixed(6)}`;
    document.getElementById("ss-pressure").innerText = `${pressureScore} / 100`;
    document.getElementById("ss-latency").innerText = `${result.usage.total_latency_ms} ms`;
    document.getElementById("ss-path").innerText = escalationPath;
    document.getElementById("ss-reason").innerText = result.routing_reason || "—";
    
    // Render RAG Citations if present
    const ragContainer = document.getElementById("ss-rag-container");
    const ragSourcesEl = document.getElementById("ss-rag-sources");
    if (ragContainer && ragSourcesEl) {
      if (result.rag_used && result.sources && result.sources.length > 0) {
        ragContainer.style.display = "block";
        ragSourcesEl.innerHTML = result.sources.map(s => `
          <div style="margin-top: 0.3rem; padding: 0.3rem 0.5rem; background: rgba(255,255,255,0.03); border-radius: 4px;">
            <strong>📄 ${escapeHtml(s.document_name)}</strong> (Relevance: ${(s.similarity_score * 100).toFixed(0)}%)
            <div style="font-size: 0.75rem; color: var(--color-text-muted); margin-top: 0.1rem;">Chunk #${s.chunk_index}: "${escapeHtml(s.text_snippet.substring(0, 120))}..."</div>
          </div>
        `).join("");
      } else {
        ragContainer.style.display = "none";
      }
    }

    // Render Evaluator Breakdown if present
    const evalBadgesEl = document.getElementById("ss-eval-badges");
    const evalCritiqueEl = document.getElementById("ss-eval-critique");
    if (evalBadgesEl && result.evaluation) {
      const ev = result.evaluation;
      const sub = ev.sub_scores || {};
      const synColor = (sub.syntactic >= 0.8) ? "#10b981" : ((sub.syntactic >= 0.5) ? "#f59e0b" : "#ef4444");
      const semColor = (sub.semantic >= 0.8) ? "#10b981" : ((sub.semantic >= 0.5) ? "#f59e0b" : "#ef4444");
      const hedColor = (sub.hedging >= 0.8) ? "#10b981" : ((sub.hedging >= 0.5) ? "#f59e0b" : "#ef4444");
      const facColor = (sub.factuality >= 0.8) ? "#10b981" : ((sub.factuality >= 0.5) ? "#f59e0b" : "#ef4444");
      const verdictColor = ev.verdict === "ACCEPTED" ? "#10b981" : "#f59e0b";

      evalBadgesEl.innerHTML = `
        <span style="background: rgba(255,255,255,0.06); padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">
          Syntactic: <strong style="color: ${synColor};">${(sub.syntactic !== undefined ? sub.syntactic : 1.0).toFixed(2)}</strong>
        </span>
        <span style="background: rgba(255,255,255,0.06); padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">
          Semantic: <strong style="color: ${semColor};">${(sub.semantic !== undefined ? sub.semantic : 1.0).toFixed(2)}</strong>
        </span>
        <span style="background: rgba(255,255,255,0.06); padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">
          Hedging: <strong style="color: ${hedColor};">${(sub.hedging !== undefined ? sub.hedging : 1.0).toFixed(2)}</strong>
        </span>
        <span style="background: rgba(255,255,255,0.06); padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">
          Factuality: <strong style="color: ${facColor};">${(sub.factuality !== undefined ? sub.factuality : 1.0).toFixed(2)}</strong>
        </span>
        <span style="background: rgba(255,255,255,0.06); padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">
          Verdict: <strong style="color: ${verdictColor};">${escapeHtml(ev.verdict)}</strong>
        </span>
      `;

      if (ev.critique) {
        evalCritiqueEl.style.display = "block";
        evalCritiqueEl.innerHTML = `<strong>Escalation Critique:</strong> ${escapeHtml(ev.critique)}`;
      } else {
        evalCritiqueEl.style.display = "none";
      }
    }

    document.getElementById("sandbox-result-summary").style.display = "block";
    document.getElementById("result-text").innerText = result.text;
    document.getElementById("result-feedback-container").style.display = "flex";
    document.querySelectorAll(".feedback-btn").forEach(btn => btn.classList.remove("selected"));
    
    fetchSummary();
  } catch (error) {
    console.error("Error submitting sandbox run:", error);
    document.getElementById("result-text").innerText = "Routing execution error. See console details.";
    visualizerContainer.innerHTML = `<div style="color: var(--color-error); padding: 1rem;"><i class="fa-solid fa-triangle-exclamation"></i> Error running completions router gateway.</div>`;
  }
}

// RAG Knowledge Base Documents Management
async function fetchKnowledgeBaseDocuments() {
  try {
    const res = await fetch(`${API_BASE}/rag/documents`);
    const data = await res.json();
    
    const tbody = document.getElementById("rag-docs-table-body");
    if (!tbody) return;
    tbody.innerHTML = "";
    
    if (!data.documents || data.documents.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--color-text-muted); padding: 2rem;">No documents ingested yet. Upload a PDF, TXT, or MD file above!</td></tr>`;
      return;
    }
    
    data.documents.forEach(doc => {
      const dateObj = new Date(doc.created_at);
      const dateStr = dateObj.toLocaleDateString() + " " + dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const sizeKb = (doc.file_size / 1024).toFixed(1);
      
      const row = document.createElement("tr");
      row.innerHTML = `
        <td><strong>${escapeHtml(doc.filename)}</strong></td>
        <td><span style="font-size: 0.8rem; color: var(--color-text-muted);">${escapeHtml(doc.file_type)}</span></td>
        <td>${sizeKb} KB</td>
        <td><span class="tier-pill t2">${doc.chunk_count} chunks</span></td>
        <td style="font-size: 0.8rem; color: var(--color-text-muted);">${dateStr}</td>
        <td>
          <button class="action-btn" style="background: rgba(239, 68, 68, 0.2); color: var(--color-error); border: 1px solid rgba(239, 68, 68, 0.4); padding: 0.3rem 0.6rem; font-size: 0.8rem;" onclick="deleteKnowledgeDocument('${doc.id}')">
            <i class="fa-solid fa-trash"></i> Delete
          </button>
        </td>
      `;
      tbody.appendChild(row);
    });
  } catch (error) {
    console.error("Error fetching knowledge base documents:", error);
  }
}

async function uploadKnowledgeDocument() {
  const fileInput = document.getElementById("rag-file-input");
  const statusEl = document.getElementById("rag-upload-status");
  
  if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
    alert("Please select a file to ingest first.");
    return;
  }
  
  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);
  
  if (statusEl) {
    statusEl.style.display = "block";
    statusEl.style.color = "var(--color-warning)";
    statusEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Ingesting '${escapeHtml(file.name)}', extracting text & generating vector embeddings...`;
  }
  
  try {
    const res = await fetch(`${API_BASE}/rag/documents/upload`, {
      method: "POST",
      body: formData
    });
    
    const result = await res.json();
    if (res.ok) {
      if (statusEl) {
        statusEl.style.color = "var(--color-success)";
        statusEl.innerHTML = `<i class="fa-solid fa-circle-check"></i> Successfully ingested '${escapeHtml(file.name)}' into vector index (${result.document.chunk_count} chunks).`;
      }
      fileInput.value = "";
      fetchKnowledgeBaseDocuments();
    } else {
      if (statusEl) {
        statusEl.style.color = "var(--color-error)";
        statusEl.innerText = `Ingestion failed: ${result.detail || 'Unknown error'}`;
      }
    }
  } catch (error) {
    console.error("Error uploading knowledge base document:", error);
    if (statusEl) {
      statusEl.style.color = "var(--color-error)";
      statusEl.innerText = `Network or upload exception occurred.`;
    }
  }
}

async function deleteKnowledgeDocument(docId) {
  if (!confirm("Are you sure you want to delete this document from the knowledge base?")) return;
  
  try {
    const res = await fetch(`${API_BASE}/rag/documents/${docId}`, { method: "DELETE" });
    if (res.ok) {
      fetchKnowledgeBaseDocuments();
    } else {
      alert("Failed to delete document.");
    }
  } catch (error) {
    console.error("Error deleting document:", error);
  }
}

// Multi-Agent System Registry Management
async function fetchAgentRegistry() {
  const container = document.getElementById("agents-grid");
  if (!container) return;
  
  try {
    const res = await fetch(`${API_BASE}/agents/registry`);
    const data = await res.json();
    
    container.innerHTML = "";
    data.agent_pool.forEach(agent => {
      const card = document.createElement("div");
      card.className = "kpi-card";
      card.style.display = "flex";
      card.style.flexDirection = "column";
      card.style.justifyContent = "space-between";
      
      let iconClass = "fa-robot";
      if (agent.specialization === "coding") iconClass = "fa-code";
      else if (agent.specialization === "research") iconClass = "fa-compass-drafting";
      else if (agent.specialization === "analysis") iconClass = "fa-chart-line";
      else if (agent.specialization === "rag") iconClass = "fa-book-bookmark";
      else if (agent.specialization === "consensus") iconClass = "fa-users";
      
      card.innerHTML = `
        <div>
          <div class="kpi-header" style="margin-bottom: 0.75rem;">
            <span style="font-weight: 700; font-size: 1rem; color: var(--color-text-main);">${escapeHtml(agent.name)}</span>
            <div class="kpi-icon" style="background: rgba(99, 102, 241, 0.15); color: var(--color-primary);">
              <i class="fa-solid ${iconClass}"></i>
            </div>
          </div>
          <div style="display: flex; gap: 0.5rem; margin-bottom: 0.75rem;">
            <span class="tier-pill t${agent.tier}">Tier ${agent.tier}</span>
            <span style="background: rgba(255,255,255,0.06); padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; color: var(--color-text-muted); font-weight: 600; text-transform: uppercase;">${escapeHtml(agent.specialization)}</span>
          </div>
          <p style="font-size: 0.85rem; color: var(--color-text-muted); line-height: 1.4; margin-bottom: 1rem;">${escapeHtml(agent.description)}</p>
        </div>
        <div style="font-size: 0.8rem; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 0.75rem; color: var(--color-text-muted); display:flex; justify-content:space-between;">
          <span>Model: <strong>${escapeHtml(agent.model_name)}</strong></span>
          <span>${escapeHtml(agent.cost_tier)}</span>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (error) {
    console.error("Error fetching agent registry:", error);
  }
}

async function submitSandboxFeedback(scoreValue) {
  if (!activeLogIdForFeedback) return;
  
  document.querySelectorAll(".feedback-btn").forEach(btn => btn.classList.remove("selected"));
  if (scoreValue === 1.0) {
    document.querySelector(".feedback-btn.up").classList.add("selected");
  } else {
    document.querySelector(".feedback-btn.down").classList.add("selected");
  }
  
  try {
    const res = await fetch(`${API_BASE}/router/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        routing_log_id: activeLogIdForFeedback,
        score: scoreValue,
        feedback_text: scoreValue === 1.0 ? "Passed sandbox inspection" : "Failed confidence expectations"
      })
    });
    if (res.ok) {
      fetchPolicies();
    }
  } catch (error) {
    console.error("Error submitting feedback:", error);
  }
}

function updateDistributionChart(tierDistribution) {
  const ctx = document.getElementById("tierDistributionChart");
  if (!ctx) return;
  
  const labels = ["Tier 1 (Cheap)", "Tier 2 (RAG)", "Tier 3 (Frontier)", "Tier 4 (Consensus)"];
  const dataValues = [
    tierDistribution.tier_1 || 0,
    tierDistribution.tier_2 || 0,
    tierDistribution.tier_3 || 0,
    tierDistribution.tier_4 || 0
  ];
  
  if (tierDistributionChartInstance) {
    tierDistributionChartInstance.data.datasets[0].data = dataValues;
    tierDistributionChartInstance.update();
  } else {
    tierDistributionChartInstance = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{
          data: dataValues,
          backgroundColor: ["#10b981", "#06b6d4", "#6366f1", "#a855f7"],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { color: "#94a3b8" } }
        }
      }
    });
  }
}

function updateDomainDistributionChart(logs) {
  const ctx = document.getElementById("domainDistributionChart");
  if (!ctx) return;

  const domainCounts = { "General": 0, "Coding": 0, "Math": 0, "RAG / Research": 0, "Analysis": 0 };
  logs.forEach(l => {
    const text = (l.prompt + " " + (l.routing_reason || "")).toLowerCase();
    if (text.includes("code") || text.includes("python") || text.includes("function")) domainCounts["Coding"]++;
    else if (text.includes("math") || text.includes("solve") || text.includes("calc")) domainCounts["Math"]++;
    else if (text.includes("rag") || text.includes("knowledge") || text.includes("chunk")) domainCounts["RAG / Research"]++;
    else if (text.includes("analysis") || text.includes("log") || text.includes("metric")) domainCounts["Analysis"]++;
    else domainCounts["General"]++;
  });

  const labels = Object.keys(domainCounts);
  const dataValues = Object.values(domainCounts);

  if (domainDistributionChartInstance) {
    domainDistributionChartInstance.data.datasets[0].data = dataValues;
    domainDistributionChartInstance.update();
  } else {
    domainDistributionChartInstance = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{
          data: dataValues,
          backgroundColor: ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { color: "#94a3b8" } }
        }
      }
    });
  }
}

function updateSavingsChart(logs) {
  const ctx = document.getElementById("costSavingsChart");
  if (!ctx) return;
  
  const sortedLogs = [...logs].reverse();
  const labels = sortedLogs.map((l, i) => `#${i + 1}`);
  let cumulativeActual = 0;
  
  const actualCosts = sortedLogs.map(l => {
    cumulativeActual += l.total_cost;
    return cumulativeActual;
  });
  
  if (costSavingsChartInstance) {
    costSavingsChartInstance.data.labels = labels;
    costSavingsChartInstance.data.datasets[0].data = actualCosts;
    costSavingsChartInstance.update();
  } else {
    costSavingsChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Cumulative Actual Cost ($)",
            data: actualCosts,
            borderColor: "#6366f1",
            backgroundColor: "rgba(99, 102, 241, 0.1)",
            fill: true,
            tension: 0.3
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: "#64748b" }, grid: { display: false } },
          y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } }
        },
        plugins: {
          legend: { position: "bottom", labels: { color: "#94a3b8" } }
        }
      }
    });
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
