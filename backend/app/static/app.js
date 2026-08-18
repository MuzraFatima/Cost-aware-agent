// API Server configurations
const API_BASE = "/api/v1";

// Global state variables
let activeLogIdForFeedback = null;
let costSavingsChartInstance = null;
let tierDistributionChartInstance = null;

// Initial Setup on DOM Content Loaded
document.addEventListener("DOMContentLoaded", () => {
  initializeDashboard();
});

async function initializeDashboard() {
  await fetchSummary();
  await fetchPolicies();
  await fetchLogs();
}

// Tab Switching Mechanism
function switchTab(event, panelId) {
  // Deactivate all tabs and panels
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.remove("active"));
  
  // Activate selected tab and panel
  event.currentTarget.classList.add("active");
  document.getElementById(panelId).classList.add("active");
  
  // Refresh relevant data when opening certain tabs
  if (panelId === 'tab-analytics') {
    fetchSummary();
    fetchLogs(); // logs needed to build chart histories
  } else if (panelId === 'tab-policies') {
    fetchPolicies();
  } else if (panelId === 'tab-logs') {
    fetchLogs();
  }
}

// Fetch Metrics Summary
async function fetchSummary() {
  try {
    const res = await fetch(`${API_BASE}/analytics/summary`);
    const data = await res.json();
    
    document.getElementById("kpi-requests").innerText = data.total_requests.toLocaleString();
    document.getElementById("kpi-cost").innerText = `$${data.total_cost_spent.toFixed(5)}`;
    document.getElementById("kpi-savings").innerText = `$${data.cost_saved_vs_frontier_only.toFixed(5)}`;
    document.getElementById("kpi-latency").innerText = `${data.average_latency_ms} ms`;
    document.getElementById("kpi-confidence").innerText = data.average_confidence.toFixed(2);
    document.getElementById("kpi-escalation").innerText = `${(data.escalation_rate * 100).toFixed(1)}%`;
    
    updateDistributionChart(data.tier_distribution);
  } catch (error) {
    console.error("Error fetching summary stats:", error);
  }
}

// Fetch Active Routing Policies and render controls
async function fetchPolicies() {
  try {
    const res = await fetch(`${API_BASE}/config/policies`);
    const policies = await res.json();
    
    const sliderContainer = document.getElementById("policy-slider-list");
    sliderContainer.innerHTML = "";
    
    policies.forEach(policy => {
      const row = document.createElement("div");
      row.className = "policy-row";
      row.innerHTML = `
        <div class="policy-info">
          <div class="policy-domain">${policy.domain}</div>
          <p>Minimum threshold confidence score</p>
        </div>
        <div class="slider-container">
          <input type="range" min="0.0" max="1.0" step="0.05" class="policy-slider" 
                 value="${policy.min_confidence_threshold}" 
                 oninput="updateSliderValue(this)"
                 onchange="savePolicyThreshold('${policy.domain}', this.value)">
          <div class="threshold-val" id="val-${policy.domain}">${policy.min_confidence_threshold.toFixed(2)}</div>
        </div>
      `;
      sliderContainer.appendChild(row);
    });
  } catch (error) {
    console.error("Error fetching policies:", error);
  }
}

// Update local slider text label
function updateSliderValue(sliderElement) {
  const valueElement = sliderElement.nextElementSibling;
  valueElement.innerText = parseFloat(sliderElement.value).toFixed(2);
}

// Send updated threshold to database
async function savePolicyThreshold(domain, thresholdValue) {
  try {
    const res = await fetch(`${API_BASE}/config/policies`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain: domain,
        min_confidence_threshold: parseFloat(thresholdValue)
      })
    });
    const result = await res.json();
    console.log("Policy updated:", result);
    fetchSummary(); // refresh summary
  } catch (error) {
    console.error("Error updating policy threshold:", error);
  }
}

// Fetch routing logs and populate Table & Charts
async function fetchLogs() {
  try {
    const res = await fetch(`${API_BASE}/analytics/logs?limit=50`);
    const logs = await res.json();
    
    const tbody = document.getElementById("logs-table-body");
    tbody.innerHTML = "";
    
    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--color-text-muted);">No records found. Run a prompt in the Sandbox first!</td></tr>`;
      updateSavingsChart([]);
      return;
    }
    
    logs.forEach(log => {
      const dateStr = new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      
      // Build escalation path badge string
      const pathBadges = (log.escalation_path || [log.final_tier]).map(t =>
        `<span class="tier-pill t${t}">T${t}</span>`
      ).join(" <span style='color:var(--color-text-muted)'>→</span> ");

      const row = document.createElement("tr");
      row.onclick = () => toggleRowDetails(log.id);
      row.id = `row-${log.id}`;
      row.innerHTML = `
        <td>${dateStr}</td>
        <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(log.prompt)}</td>
        <td><span class="tier-pill t${log.final_tier}">Tier ${log.final_tier}</span></td>
        <td>${pathBadges}</td>
        <td>$${log.total_cost.toFixed(5)}</td>
        <td>${log.total_latency_ms} ms</td>
        <td style="max-width: 200px; font-size: 0.78rem; color: var(--color-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(log.routing_reason || '')}">${escapeHtml(log.routing_reason || '—')}</td>
        <td>${log.eval_score !== null ? (log.eval_score === 1.0 ? '<i class="fa-solid fa-thumbs-up" style="color: var(--color-success)"></i>' : '<i class="fa-solid fa-thumbs-down" style="color: var(--color-error)"></i>') : '<span style="color: var(--color-text-muted)">-</span>'}</td>
      `;
      tbody.appendChild(row);
      
      // Detail row (collapsed by default)
      const detailRow = document.createElement("tr");
      detailRow.id = `detail-${log.id}`;
      detailRow.className = "log-expanded-row";
      detailRow.style.display = "none";
      
      let stepTraceHtml = "";
      log.steps.forEach((step, idx) => {
        const isLastStep = idx === log.steps.length - 1;
        const stepStatusColor = isLastStep ? "var(--color-success)" : "var(--color-warning)";
        const stepStatusLabel = isLastStep ? "✓ Accepted" : "↑ Escalated";
        stepTraceHtml += `
          <div class="step-trace-item">
            <span><strong>Step ${idx + 1}: Tier ${step.tier}</strong> (${step.model_name})</span>
            <span style="display:flex; gap:0.75rem; align-items:center;">
              Conf: <strong>${step.confidence_score.toFixed(3)}</strong>
              | Cost: $${step.cost.toFixed(5)}
              | Latency: ${step.latency_ms}ms
              | Tokens: ${step.tokens_input}↑/${step.tokens_output}↓
              <span style="color:${stepStatusColor}; font-weight:700;">${stepStatusLabel}</span>
            </span>
          </div>
        `;
      });
      
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
    
    updateSavingsChart(logs);
  } catch (error) {
    console.error("Error fetching logs:", error);
  }
}

// Collapsible Table Rows helper
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
  
  if (!promptText.trim()) {
    alert("Please enter a prompt first.");
    return;
  }
  
  // Set UI to loading state
  const visualizerContainer = document.getElementById("visualizer-list");
  visualizerContainer.innerHTML = `
    <div class="cascade-step active">
      <div class="step-badge">1</div>
      <div class="step-details">
        <div class="step-model">Router Gateway (Preprocessing)</div>
        <div class="step-meta">Analyzing query complexity and active thresholds...</div>
      </div>
      <div class="step-status running">Running</div>
    </div>
  `;
  
  document.getElementById("result-placeholder").style.display = "none";
  document.getElementById("result-text").innerText = "Invoking router, running confidence cascades...";
  document.getElementById("result-feedback-container").style.display = "none";
  
  try {
    const res = await fetch(`${API_BASE}/router/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: promptText,
        domain: domain,
        expected_format: format || null
      })
    });
    const result = await res.json();
    
    activeLogIdForFeedback = result.id;
    
    // Clear initial loading step
    visualizerContainer.innerHTML = "";
    
    // Animate and display each step of cascade
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

    // Populate Sandbox Result Summary panel
    const lastStep = result.usage.routing_path[result.usage.routing_path.length - 1];
    const escalationPath = result.usage.routing_path.map(s => `Tier ${s.tier}`).join(" → ");
    const routingReason = result.usage.routing_path.length === 1
      ? `Resolved at Tier ${result.final_tier} — confidence threshold met on first attempt`
      : `Escalated through ${escalationPath} — lower tiers did not meet confidence threshold`;

    document.getElementById("ss-tier").innerHTML = `<span class="tier-pill t${result.final_tier}">Tier ${result.final_tier}</span>`;
    document.getElementById("ss-confidence").innerText = lastStep ? lastStep.confidence_score.toFixed(3) : "—";
    document.getElementById("ss-threshold").innerText = result.threshold_used.toFixed(2);
    document.getElementById("ss-cost").innerText = `$${result.usage.total_cost_usd.toFixed(6)}`;
    document.getElementById("ss-latency").innerText = `${result.usage.total_latency_ms} ms`;
    document.getElementById("ss-path").innerText = escalationPath;
    document.getElementById("ss-reason").innerText = routingReason;
    document.getElementById("sandbox-result-summary").style.display = "block";
    
    // Set output text
    document.getElementById("result-text").innerText = result.text;
    
    // Enable rating feedback UI
    document.getElementById("result-feedback-container").style.display = "flex";
    
    // Reset feedback buttons selection
    document.querySelectorAll(".feedback-btn").forEach(btn => btn.classList.remove("selected"));
    
    // Trigger summaries updates in background
    fetchSummary();
  } catch (error) {
    console.error("Error submitting sandbox run:", error);
    document.getElementById("result-text").innerText = "Routing execution error. See console details.";
    visualizerContainer.innerHTML = `<div style="color: var(--color-error); padding: 1rem;"><i class="fa-solid fa-triangle-exclamation"></i> Error running completions router gateway.</div>`;
  }
}

// Submit sandbox feedback review
async function submitSandboxFeedback(scoreValue) {
  if (!activeLogIdForFeedback) return;
  
  // Add selected styling to buttons
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
    const result = await res.json();
    console.log("Feedback submitted successfully:", result);
    
    // Refresh policy rules and metrics
    await fetchSummary();
    await fetchPolicies();
  } catch (error) {
    console.error("Error submitting feedback:", error);
  }
}

// Chart.js Area Chart for Cost Savings Over Time
function updateSavingsChart(logs) {
  const ctx = document.getElementById("costSavingsChart").getContext("2d");
  
  if (costSavingsChartInstance) {
    costSavingsChartInstance.destroy();
  }
  
  // Reconstruct time timeline from oldest logs to newest
  const sortedLogs = [...logs].reverse();
  
  let labels = [];
  let actualCostData = [];
  let frontierCostData = [];
  
  let cumulativeActual = 0.0;
  let cumulativeFrontier = 0.0;
  
  sortedLogs.forEach((log, index) => {
    cumulativeActual += log.total_cost;
    // Frontier estimation ($0.005 per call)
    cumulativeFrontier += 0.005;
    
    const dateStr = new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    labels.push(`Run ${index + 1} (${dateStr})`);
    actualCostData.push(cumulativeActual);
    frontierCostData.push(cumulativeFrontier);
  });
  
  costSavingsChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Actual Spent Cost ($)",
          data: actualCostData,
          borderColor: "#6366f1",
          backgroundColor: "rgba(99, 102, 241, 0.1)",
          fill: true,
          tension: 0.3
        },
        {
          label: "Frontier Model Direct Call ($)",
          data: frontierCostData,
          borderColor: "#06b6d4",
          backgroundColor: "rgba(6, 182, 212, 0.05)",
          fill: true,
          borderDash: [5, 5],
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#9ca3af" } }
      },
      scales: {
        x: { ticks: { color: "#9ca3af" }, grid: { display: false } },
        y: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } }
      }
    }
  });
}

// Chart.js Doughnut Chart for Tier Distributions
function updateDistributionChart(distributions) {
  const ctx = document.getElementById("tierDistributionChart").getContext("2d");
  
  if (tierDistributionChartInstance) {
    tierDistributionChartInstance.destroy();
  }
  
  const values = [
    distributions.tier_1 * 100,
    distributions.tier_2 * 100,
    distributions.tier_3 * 100,
    distributions.tier_4 * 100
  ];
  
  tierDistributionChartInstance = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Tier 1: Cheap Direct", "Tier 2: RAG / Search", "Tier 3: Frontier Single", "Tier 4: Consensus & Verify"],
      datasets: [{
        data: values,
        backgroundColor: [
          "rgba(59, 130, 246, 0.75)",
          "rgba(6, 182, 212, 0.75)",
          "rgba(139, 92, 246, 0.75)",
          "rgba(245, 158, 11, 0.75)"
        ],
        borderColor: "#111827",
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#9ca3af" } }
      }
    }
  });
}

// Helper to escape HTML tags
function escapeHtml(unsafe) {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
