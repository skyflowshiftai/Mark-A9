document.addEventListener('DOMContentLoaded', () => {
  const heroOverlay = document.getElementById('hero-start-overlay');
  const activeUI = document.getElementById('active-assistant-ui');
  const btnStartMark = document.getElementById('btn-start-mark');
  const videoEl = document.getElementById('user-video');
  const canvasEl = document.getElementById('user-canvas');
  const ctx = canvasEl.getContext('2d');
  const guidanceCard = document.getElementById('guidance-card');
  const guidanceText = document.getElementById('guidance-text');
  
  // Microphone Button & States
  const micCard = document.getElementById('mic-card');
  const btnTalkMic = document.getElementById('btn-talk-mic');
  const micIcon = document.getElementById('mic-icon');
  const micLabel = document.getElementById('mic-label');
  const micStatusSub = document.getElementById('mic-status-sub');
  
  // Conversation Transcript
  const transcriptYou = document.getElementById('transcript-you');
  const transcriptMark = document.getElementById('transcript-mark');

  // Guardian & Session
  const guardianLinkBtn = document.getElementById('guardian-link-btn');
  const displaySessionId = document.getElementById('display-session-id');
  const btnUserSos = document.getElementById('btn-user-sos');

  // Session ID
  const sessionId = 'SESS-' + Math.random().toString(36).substring(2, 8).toUpperCase();
  if (displaySessionId) displaySessionId.textContent = sessionId;
  if (guardianLinkBtn) guardianLinkBtn.href = `/guardian?session=${sessionId}`;

  let ws = null;
  let isAiMode = true;
  let currentLanguage = 'te-IN';
  let micState = 'IDLE'; // IDLE | LISTENING | PROCESSING | SPEAKING | ERROR
  let speechRecognizer = null;
  let recognitionActive = false;
  let audioMutedForTTS = false;

  canvasEl.width = 640;
  canvasEl.height = 360;

  // ── State Visualizer ──
  function setMicState(state, text = '') {
    micState = state;
    if (!btnTalkMic || !micCard) return;

    btnTalkMic.className = `btn-talk-mic ${state}`;
    micCard.className = `mic-control-card ${state}`;

    if (state === 'IDLE') {
      micIcon.textContent = '🎙️';
      micLabel.textContent = 'TALK TO MARK';
      if (micStatusSub) micStatusSub.textContent = 'Tap button to talk with MARK';
    } else if (state === 'LISTENING') {
      micIcon.textContent = '🔴';
      micLabel.textContent = 'MARK is listening...';
      if (micStatusSub) micStatusSub.textContent = text || 'Speak your question or command now';
    } else if (state === 'PROCESSING') {
      micIcon.textContent = '◌';
      micLabel.textContent = 'MARK is thinking...';
      if (micStatusSub) micStatusSub.textContent = 'Checking live world state...';
    } else if (state === 'SPEAKING') {
      micIcon.textContent = '🔊';
      micLabel.textContent = 'MARK is speaking...';
      if (micStatusSub) micStatusSub.textContent = 'Tap mic to interrupt and talk';
    } else if (state === 'ERROR') {
      micIcon.textContent = '⚠️';
      micLabel.textContent = 'Mic unavailable';
      if (micStatusSub) micStatusSub.textContent = 'Microphone access is required to talk with MARK. Tap to retry.';
    }
  }

  // ── Speech Synthesis with Interrupt Support & Mic Loopback Prevention ──
  function playAudioAlert(text, priority = 'NORMAL', isInterrupt = false, onEndCallback = null) {
    if (!text) return;
    if (isInterrupt && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    if (window.speechSynthesis) {
      // Pause speech recognition while MARK speaks to prevent self-loopback
      audioMutedForTTS = true;
      if (speechRecognizer && recognitionActive) {
        try { speechRecognizer.abort(); } catch (e) {}
      }

      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = currentLanguage;
      utter.rate = priority === 'CRITICAL' ? 1.15 : 1.0;
      utter.pitch = 1.0;

      setMicState('SPEAKING');
      console.log(`[TTS] speaking: "${text}" (${priority})`);

      utter.onend = () => {
        audioMutedForTTS = false;
        if (micState === 'SPEAKING') {
          setMicState('IDLE');
        }
        if (onEndCallback) onEndCallback();
      };

      utter.onerror = () => {
        audioMutedForTTS = false;
        if (micState === 'SPEAKING') {
          setMicState('IDLE');
        }
      };

      window.speechSynthesis.speak(utter);
    } else {
      setMicState('IDLE');
    }
  }

  // ── START MARK Hero Button Handler ──
  if (btnStartMark) {
    btnStartMark.addEventListener('click', async () => {
      console.log("[MIC] START MARK button pressed");
      heroOverlay.style.display = 'none';
      activeUI.style.display = 'flex';

      // 1. Initial Greet in Telugu
      const greeting = "నమస్కారం సర్, నేను MARK. మీ కోసం సిద్ధంగా ఉన్నాను.";
      guidanceText.textContent = `"${greeting}"`;
      if (transcriptMark) transcriptMark.textContent = `"${greeting}"`;
      playAudioAlert(greeting, "NORMAL", true);

      // 2. Start Camera & Perception Stream
      await startCamera();
      connectWebSocket();

      // 3. Initialize Speech Recognizer
      setupSpeechRecognizer();
    });
  }

  // ── Dedicated Microphone Button Handler ──
  if (btnTalkMic) {
    btnTalkMic.addEventListener('click', () => {
      console.log("[MIC] Button pressed by user");

      // 1. Interrupt any active speech
      if (window.speechSynthesis && window.speechSynthesis.speaking) {
        console.log("[MIC] Interrupting active TTS");
        window.speechSynthesis.cancel();
        audioMutedForTTS = false;
      }

      if (micState === 'LISTENING') {
        if (speechRecognizer) speechRecognizer.stop();
      } else {
        startListeningSession();
      }
    });
  }

  // ── Singleton Speech Recognition Setup ──
  function setupSpeechRecognizer() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      console.warn("Web SpeechRecognition not supported in this browser.");
      setMicState('ERROR');
      return;
    }

    if (speechRecognizer) {
      try { speechRecognizer.abort(); } catch (e) {}
    }

    speechRecognizer = new SpeechRec();
    speechRecognizer.continuous = false; // Turn-based for interactive push-to-talk
    speechRecognizer.interimResults = true;
    speechRecognizer.lang = currentLanguage;

    speechRecognizer.onstart = () => {
      recognitionActive = true;
      setMicState('LISTENING');
      console.log("[STT] Listening started");
    };

    speechRecognizer.onresult = (event) => {
      // Ignore results if TTS was speaking and fired loopback
      if (audioMutedForTTS) return;

      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }

      if (interimTranscript && transcriptYou) {
        transcriptYou.textContent = `"${interimTranscript}..."`;
        setMicState('LISTENING', `Heard: "${interimTranscript}"`);
      }

      if (finalTranscript) {
        console.log(`[STT] Transcript received: "${finalTranscript}"`);
        transcriptYou.textContent = `"${finalTranscript}"`;
        processUserVoiceQuery(finalTranscript);
      }
    };

    speechRecognizer.onerror = (e) => {
      console.warn("[STT] Speech Recognition Error:", e.error);
      recognitionActive = false;
      if (e.error === 'not-allowed') {
        setMicState('ERROR');
      } else if (micState === 'LISTENING') {
        setMicState('IDLE');
      }
    };

    speechRecognizer.onend = () => {
      recognitionActive = false;
      console.log("[STT] Listening ended");
      if (micState === 'LISTENING') {
        setMicState('IDLE');
      }
    };
  }

  function startListeningSession() {
    if (!speechRecognizer) {
      setupSpeechRecognizer();
    }
    if (!speechRecognizer) return;

    try {
      setMicState('LISTENING');
      speechRecognizer.start();
    } catch (e) {
      console.warn("Recognizer start error:", e);
      try {
        speechRecognizer.abort();
        setTimeout(() => speechRecognizer.start(), 150);
      } catch (err) {}
    }
  }

  async function processUserVoiceQuery(query) {
    setMicState('PROCESSING');
    console.log(`[AGENT] Transcript sent: "${query}"`);
    try {
      const res = await fetch('/api/conversation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          language: currentLanguage
        })
      });
      const data = await res.json();
      console.log("[AGENT] Response received:", data);
      
      if (data && data.speech) {
        guidanceText.textContent = `"${data.speech}"`;
        if (transcriptMark) transcriptMark.textContent = `"${data.speech}"`;

        // Handle System Actions from Voice
        if (data.action === "ENABLE_AI_MODE") isAiMode = true;
        else if (data.action === "DISABLE_AI_MODE") isAiMode = false;

        playAudioAlert(data.speech, data.priority || 'NORMAL', true);
      } else {
        setMicState('IDLE');
      }
    } catch (err) {
      console.error("[MARK Process Query Error]:", err);
      setMicState('IDLE');
    }
  }

  // ── Camera Streaming (Continuous Independent Loop) ──
  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 360 }, facingMode: 'environment' }
      });
      videoEl.srcObject = stream;
      try { await videoEl.play(); } catch(e) {}

      const bufCanvas = document.createElement('canvas');
      bufCanvas.width = 640;
      bufCanvas.height = 360;
      const bufCtx = bufCanvas.getContext('2d');

      setInterval(() => {
        if (!videoEl || videoEl.videoWidth === 0) return;
        bufCtx.drawImage(videoEl, 0, 0, 640, 360);
        const dataUrl = bufCanvas.toDataURL('image/jpeg', 0.65);
        const b64 = dataUrl.split(',')[1];

        if (b64 && ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: "frame",
            image: b64,
            session_id: sessionId,
            ai_mode: isAiMode,
            language: currentLanguage,
            timestamp: Date.now() / 1000.0
          }));
        }
      }, 100);
    } catch (e) {
      console.warn("[MARK User] Camera access error:", e);
    }
  }

  // ── WebSocket Client ──
  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host || 'localhost:5000'}/ws/stream`;
    ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "detection_update") {
          updateUserUI(payload);
        }
      } catch (e) {}
    };

    ws.onclose = () => {
      setTimeout(connectWebSocket, 2000);
    };
  }

  function updateUserUI(data) {
    if (!isAiMode) {
      ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
      guidanceText.textContent = "AI MODE PAUSED — Visual assistance standing by.";
      guidanceCard.className = "guidance-box";
      return;
    }

    // 1. Spoken message from event-based changes
    if (data.mark_message && data.mark_message !== "Path clear." && data.mark_message !== "AI MODE PAUSED") {
      guidanceText.textContent = `"${data.mark_message}"`;
    }

    // 2. Play only meaningful state changes (never spam repetitive guidance)
    if (data.voice_output && data.voice_output.should_speak && data.voice_output.spoken_message) {
      // Only speak if user is not currently interacting with the microphone
      if (micState === 'IDLE' || data.voice_output.priority === 'CRITICAL' || data.voice_output.interrupt_audio) {
        if (transcriptMark) transcriptMark.textContent = `"${data.voice_output.spoken_message}"`;
        playAudioAlert(data.voice_output.spoken_message, data.voice_output.priority, data.voice_output.interrupt_audio);
      }
    }

    const threat = data.highest_threat || 'SAFE';
    guidanceCard.className = `guidance-box ${threat}`;

    // 3. Render overlays
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
    const objects = data.objects || [];
    objects.forEach(obj => {
      const bbox = obj.norm_bbox || [0.2, 0.2, 0.6, 0.7];
      const x1 = bbox[0] * canvasEl.width;
      const y1 = bbox[1] * canvasEl.height;
      const x2 = bbox[2] * canvasEl.width;
      const y2 = bbox[3] * canvasEl.height;
      const w = Math.max(10, x2 - x1);
      const h = Math.max(10, y2 - y1);

      const name = (obj.recognized_name || obj.class_name || 'Object').toUpperCase();
      const objThreat = (obj.risk_level || 'LOW').toUpperCase();
      const trackId = obj.track_id || obj.id || 1;
      const conf = obj.confidence ? Math.round(obj.confidence * 100) : 85;
      const distStr = (obj.distance_info && obj.distance_info.distance_m) ? `${obj.distance_info.distance_m}m` : (obj.proximity || '2.0m');
      const motionStr = obj.motion_state || (obj.motion ? obj.motion.state : 'STATIONARY');

      let strokeColor = "#10b981";
      if (objThreat === "RED" || objThreat === "URGENT") strokeColor = "#ef4444";
      else if (objThreat === "YELLOW" || objThreat === "CAUTION") strokeColor = "#f59e0b";

      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 2.5;
      ctx.strokeRect(x1, y1, w, h);

      const label = `#0${trackId} ${name} (${conf}%) • ${distStr} • ${motionStr}`;
      ctx.font = "bold 11px 'JetBrains Mono', monospace";
      const tw = ctx.measureText(label).width;

      ctx.fillStyle = "rgba(0, 0, 0, 0.85)";
      ctx.fillRect(x1, Math.max(0, y1 - 20), tw + 12, 18);

      ctx.fillStyle = strokeColor;
      ctx.fillText(label, x1 + 5, Math.max(12, y1 - 6));
    });
  }

  // ── SOS Emergency Trigger ──
  if (btnUserSos) {
    btnUserSos.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/emergency/trigger', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source: "SOS_BUTTON" })
        });
        const data = await res.json();
        const emgMsg = "సర్, సహాయం కోసం వెంటనే అలర్ట్ చేస్తున్నాను.";
        guidanceText.textContent = `"${emgMsg}"`;
        if (transcriptMark) transcriptMark.textContent = `"${emgMsg}"`;
        playAudioAlert(emgMsg, "CRITICAL", true);
      } catch (err) {
        console.error("SOS trigger error:", err);
      }
    });
  }
});
