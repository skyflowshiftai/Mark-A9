class AlertPanel {
  constructor(statusElement, chainContainerElement) {
    this.statusElement = statusElement;
    this.chainContainer = chainContainerElement;
  }

  update(decision, scene) {
    if (!decision) return;

    // Update Status Pill
    if (this.statusElement) {
      const isClear = scene?.forward_clear ?? true;
      const pathState = scene?.path_state || "CLEAR";
      const statusClass = isClear ? "accent-green" : "accent-red";
      
      this.statusElement.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
          <div>
            <span class="label-tag">FORWARD PATH STATE</span>
            <div style="font-size: 16px; font-weight: 800; font-family: var(--font-mono); color: var(--${statusClass}); margin-top: 2px;">
              ● ${pathState} ${isClear ? "— SAFE TO WALK" : "— OBSTRUCTION DETECTED"}
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
              ${scene?.path_message || "Path is unobstructed."}
            </div>
          </div>
          <div class="status-pill" style="border-color: var(--${statusClass});">
            ${decision.decision_state || "SILENCE"}
          </div>
        </div>
      `;
    }

    // Update Reasoning Chain (5 Nodes)
    if (this.chainContainer && decision.reasoning_chain) {
      const chain = decision.reasoning_chain;
      this.chainContainer.innerHTML = `
        <div class="chain-node">
          <div class="node-label">01 • Perception</div>
          <div class="node-value">${chain.perception || "Open space"}</div>
        </div>
        <div class="chain-node">
          <div class="node-label">02 • Context</div>
          <div class="node-value">${chain.context || "Unobstructed corridor"}</div>
        </div>
        <div class="chain-node">
          <div class="node-label">03 • Risk</div>
          <div class="node-value">${chain.risk || "Low (Safe)"}</div>
        </div>
        <div class="chain-node">
          <div class="node-label">04 • Decision</div>
          <div class="node-value">${chain.decision || "Remain silent"}</div>
        </div>
        <div class="chain-node">
          <div class="node-label">05 • Voice Output</div>
          <div class="node-value" style="color: var(--accent-green); font-weight: 700; font-style: italic;">
            "${decision.voice_message || decision.active_message || "— (Silent)"}"
          </div>
        </div>
      `;
    }
  }
}
