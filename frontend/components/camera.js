class CameraManager {
  constructor(videoElement, canvasElement, onFrameEncoded) {
    this.video = videoElement;
    this.canvas = canvasElement;
    this.ctx = canvasElement.getContext('2d');
    this.onFrameEncoded = onFrameEncoded;
    this.stream = null;
    this.intervalId = null;
    this.isActive = false;
    
    // Virtual frame buffer canvas for downscaling
    this.bufferCanvas = document.createElement('canvas');
    this.bufferCanvas.width = 640;
    this.bufferCanvas.height = 360;
    this.bufferCtx = this.bufferCanvas.getContext('2d');
  }

  async start() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "environment" },
        audio: false
      });
      this.video.srcObject = this.stream;
      await this.video.play();
      this.isActive = true;

      // Start frame capture loop at ~10 FPS (100ms)
      this.intervalId = setInterval(() => this._captureFrame(), 100);
      return true;
    } catch (err) {
      console.warn("[CameraManager] Camera access error:", err);
      this.isActive = false;
      return false;
    }
  }

  stop() {
    if (this.intervalId) clearInterval(this.intervalId);
    if (this.stream) {
      this.stream.getTracks().forEach(t => t.stop());
      this.stream = null;
    }
    this.isActive = false;
  }

  _captureFrame() {
    if (!this.isActive || !this.video || this.video.videoWidth === 0) return;

    this.bufferCtx.drawImage(this.video, 0, 0, 640, 360);
    const dataUrl = this.bufferCanvas.toDataURL('image/jpeg', 0.65);
    const base64 = dataUrl.split(',')[1];

    if (base64 && this.onFrameEncoded) {
      this.onFrameEncoded(base64);
    }
  }

  renderDetections(tracks) {
    if (!this.ctx || !this.canvas) return;

    const w = this.canvas.width = this.video.videoWidth || 640;
    const h = this.canvas.height = this.video.videoHeight || 360;
    this.ctx.clearRect(0, 0, w, h);

    if (!tracks || tracks.length === 0) return;

    tracks.forEach(track => {
      const [nx1, ny1, nx2, ny2] = track.norm_box || [0, 0, 0, 0];
      const x1 = nx1 * w;
      const y1 = ny1 * h;
      const bw = (nx2 - nx1) * w;
      const bh = (ny2 - ny1) * h;

      let color = "#00e676"; // Green
      if (track.risk_level === "CRITICAL" || track.risk_level === "HIGH") {
        color = "#ef4444"; // Red
      } else if (track.risk_level === "MEDIUM") {
        color = "#f59e0b"; // Amber
      }

      // Draw bounding box
      this.ctx.strokeStyle = color;
      this.ctx.lineWidth = 2.5;
      this.ctx.strokeRect(x1, y1, bw, bh);

      // Label background & text
      const label = `${track.class_name.toUpperCase()} #${track.track_id} • ${track.distance_m}m`;
      this.ctx.font = "bold 11px 'JetBrains Mono', monospace";
      const textWidth = this.ctx.measureText(label).width;

      this.ctx.fillStyle = "rgba(0, 0, 0, 0.85)";
      this.ctx.fillRect(x1, Math.max(0, y1 - 22), textWidth + 12, 20);

      this.ctx.fillStyle = color;
      this.ctx.fillText(label, x1 + 6, Math.max(14, y1 - 8));
    });
  }
}
