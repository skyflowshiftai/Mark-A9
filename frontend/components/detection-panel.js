class DetectionPanel {
  constructor(containerElement) {
    this.container = containerElement;
  }

  update(tracks) {
    if (!this.container) return;

    if (!tracks || tracks.length === 0) {
      this.container.innerHTML = `
        <div style="text-align: center; color: var(--text-muted); padding: 24px; font-family: var(--font-mono); font-size: 11px;">
          NO OBJECTS DETECTED IN PATH
        </div>
      `;
      return;
    }

    let html = '';
    tracks.forEach(track => {
      const riskClass = track.risk_level.toLowerCase();
      const directionIcon = track.movement_direction === "APPROACHING" ? "↘" : (track.movement_direction === "RECEDING" ? "↗" : "•");
      
      html += `
        <div class="track-item">
          <div class="track-info">
            <div class="track-name">
              ${track.class_name} #${track.track_id}
            </div>
            <div class="track-meta">
              ${track.sector} • ~${track.distance_m}m • ${directionIcon} ${track.movement_direction}
            </div>
          </div>
          <div class="track-badge ${riskClass}">
            ${track.risk_score}/100 ${track.risk_level}
          </div>
        </div>
      `;
    });

    this.container.innerHTML = html;
  }
}
