import pytest
from voice.voice_controller import VoiceController

def test_voice_agent_instruction_synthesis():
    vc = VoiceController()

    # 1. Person, front -> "Person ahead."
    cue_person = vc.generate_spoken_cue({
        "name": "person",
        "spatial_sector": "CENTER",
        "proximity": "MEDIUM",
        "risk_level": "LOW",
        "motion_state": "STATIONARY"
    })
    assert cue_person == "Person ahead."
    assert len(cue_person.split()) <= 5

    # 2. Chair, front, close -> "Chair ahead. Careful."
    cue_chair = vc.generate_spoken_cue({
        "name": "chair",
        "spatial_sector": "CENTER",
        "proximity": "NEAR",
        "risk_level": "CAUTION",
        "path_relevance": "HIGH",
        "motion_state": "STATIONARY"
    })
    assert "Chair" in cue_chair and ("Careful" in cue_chair or "ahead" in cue_chair)
    assert len(cue_chair.split()) <= 5

    # 3. Car approaching -> "Car approaching. Stop."
    cue_car = vc.generate_spoken_cue({
        "name": "car",
        "spatial_sector": "CENTER",
        "proximity": "NEAR",
        "risk_level": "URGENT",
        "approach_tendency": "CLOSING_IN",
        "motion_state": "APPROACHING"
    })
    assert "Car approaching. Stop." in cue_car or "Car ahead. Stop." in cue_car
    assert len(cue_car.split()) <= 5

    # 4. Step down -> "Step down. Stop."
    cue_step = vc.generate_spoken_cue({
        "name": "step",
        "spatial_sector": "CENTER",
        "proximity": "NEAR",
        "risk_level": "URGENT",
        "motion_state": "STATIONARY"
    })
    assert "Step down. Stop." in cue_step
    assert len(cue_step.split()) <= 5

    # 5. Dog approaching -> "Dog approaching. Careful."
    cue_dog = vc.generate_spoken_cue({
        "name": "dog",
        "spatial_sector": "CENTER",
        "proximity": "MEDIUM",
        "risk_level": "CAUTION",
        "motion_state": "APPROACHING"
    })
    assert cue_dog == "Dog approaching. Careful."
    assert len(cue_dog.split()) <= 5

    # 6. Silence on safe / distant path
    eval_none = vc.evaluate_voice_instruction(None)
    assert eval_none["should_speak"] is False
    assert eval_none["reason"] == "SILENCE_PATH_CLEAR"
