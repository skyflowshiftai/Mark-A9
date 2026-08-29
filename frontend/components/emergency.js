class EmergencyHandler {
  constructor(overlayElement, emergencyBtn, onTrigger, onResolve) {
    this.overlay = overlayElement;
    this.btn = emergencyBtn;
    this.onTrigger = onTrigger;
    this.onResolve = onResolve;
    this.isActive = false;

    if (this.btn) {
      this.btn.addEventListener('click', () => this.trigger());
    }
  }

  trigger(source = "MANUAL_BUTTON") {
    this.isActive = true;
    if (this.overlay) {
      this.overlay.classList.add('active');
    }
    if (this.onTrigger) {
      this.onTrigger(source);
    }
  }

  resolve() {
    this.isActive = false;
    if (this.overlay) {
      this.overlay.classList.remove('active');
    }
    if (this.onResolve) {
      this.onResolve();
    }
  }
}
