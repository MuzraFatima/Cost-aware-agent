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
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.remove("active"));
  
  event.currentTarget.classList.add("active");
  document.getElementById(panelId).classList.add("active");
  
  if (panelId === 'tab-analytics') {
    fetchSummary();
    fetchLogs();
  } else if (panelId === 'tab-policies') {
    fetchPolicies();
    fetchSummary();
  } else if (panelId === 'tab-logs') {
    fetchLogs();
  }
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
    document.getElementById("kpi-confidence").innerText = (data.average_confidence || 0).toFixed(2);
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

function updateSliderValue(sliderElement) {
  const valueElement = sliderElement.nextElementSibling;
  valueElement.innerText = parseFloat(sliderElement.value).toFixed(2);
}

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
    if (res.ok) {
      fetchPolicies();
    }
  } catch (error) {
    console.error("Error updating policy threshold:", error);
  }
}

// Fetch Log Traces
async function fetchLogs() {
  try {
    const res = await fetch(`${API_BASE}/analytics/logs?limit=50`);
    const logs = await res.json();
    
    const tbody = document.getElementById("logs-table-body");
    tbody.innerHTML = "";
    
    if (!logs || logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--color-text-muted); padding: 2rem;">No logs recorded yet. Run queries in Sandbox!</td></tr>`;
      return;
    }
    
    logs.forEach(log => {
      const dateObj = new Date(log.created_at);
      const timeStr = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      const escalationPath = log.escalation_path && log.escalation_path.length > 0 ? log.escalation_path.map(t => `T${t}`).join(" → ") : `T${log.final_tier}`;

      const row = document.createElement("tr");
      row.onclick = () => toggleRowDetails(log.id);
      row.style.cursor = "pointer";
      
      row.innerHTML = `
        <td style="white-space: nowrap; font-size: 0.82rem; color: var(--color-text-muted);">${timeStr}</td>
        <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(log.prompt)}</td>
        <td><span class="tier-pill t${log.final_tier}">Tier ${log.final_tier}</span></td>
        <td><span style="font-weight: 600; font-size: 0.85rem;">${escalationPath}</span></td>
        <td style="font-family: monospace;">$${log.total_cost.toFixed(5)}</td>
        <td>${log.total_latency_ms} ms</td>
        <td style="max-width: 200px; font-size: 0.78rem; color: var(--color-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(log.routing_reason || '')}">${escapeHtml(log.routing_reason || '—')}</td>
        <td>${log.eval_score !== null ? (log.eval_score === 1.0 ? '<i class="fa-solid fa-thumbs-up" style="color: var(--color-success)"></i>' : '<i class="fa-solid fa-thumbs-down" style="color: var(--color-error)"></i>') : '<span style="color: var(--color-text-muted)">-</span>'}</td>
      `;
      tbody.appendChild(row);
      
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
    const res = await fetch(`${API_BASE}/router/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: promptText,
        messages: [{ role: "user", content: promptText }],
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
