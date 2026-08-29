class VoicePanel {
  constructor(micButton, inputField, onCommandDispatched) {
    this.micBtn = micButton;
    this.input = inputField;
    this.onCommandDispatched = onCommandDispatched;
    this.recognition = null;
    this.isListening = false;
    this.lastSpokenText = "";
    this.lastSpokenTime = 0;

    this._initSpeechRecognition();
  }

  _initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = false;
      this.recognition.interimResults = false;
      this.recognition.lang = 'en-US';

      this.recognition.onstart = () => {
        this.isListening = true;
        if (this.micBtn) this.micBtn.classList.add('listening');
      };

      this.recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (this.input) this.input.value = transcript;
        if (this.onCommandDispatched) this.onCommandDispatched(transcript);
      };

      this.recognition.onend = () => {
        this.isListening = false;
        if (this.micBtn) this.micBtn.classList.remove('listening');
      };

      this.recognition.onerror = () => {
        this.isListening = false;
        if (this.micBtn) this.micBtn.classList.remove('listening');
      };
    }
  }

  toggleListening() {
    if (!this.recognition) {
      alert("Speech recognition is not supported in this browser. You can type commands in the box.");
      return;
    }

    if (this.isListening) {
      this.recognition.stop();
    } else {
      this.recognition.start();
    }
  }

  speak(text, isPriority = false) {
    if (!text || !window.speechSynthesis) return;

    const now = Date.now();
    if (text === this.lastSpokenText && (now - this.lastSpokenTime < 2500) && !isPriority) {
      return; // Duplicate suppression
    }

    if (isPriority) {
      window.speechSynthesis.cancel();
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    this.lastSpokenText = text;
    this.lastSpokenTime = now;

    window.speechSynthesis.speak(utterance);
  }
}
