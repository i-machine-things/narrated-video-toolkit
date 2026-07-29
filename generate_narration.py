#!/usr/bin/env python3
"""Generates narration WAVs for build_video.py's SCENES using VibeVoice,
cloning Allan's voice from a reference clip. Run inside the vibevoice venv."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_video import SCENES, OUT

from vibevoice.modular.modeling_vibevoice_inference import VibeVoiceForConditionalGenerationInference
from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor
import soundfile as sf
import numpy as np

MODEL_ID = "microsoft/VibeVoice-1.5B"
VOICE_REF = os.path.expanduser("~/voice_samples/my_voice_ref3.wav")

os.makedirs(OUT, exist_ok=True)


def main():
    print("Loading VibeVoice model...")
    processor = VibeVoiceProcessor.from_pretrained(MODEL_ID)
    model = VibeVoiceForConditionalGenerationInference.from_pretrained(MODEL_ID, torch_dtype="float32")
    model.eval()
    print("Model loaded.")

    for idx, scene in enumerate(SCENES):
        wav_path = os.path.join(OUT, f"narr_{idx:02d}.wav")
        text = f"Speaker 1: {scene['narration']}"

        inputs = processor(text=[text], voice_samples=[[VOICE_REF]], return_tensors="pt")
        out = model.generate(**inputs, tokenizer=processor.tokenizer, cfg_scale=1.3, max_new_tokens=None)
        speech = out.speech_outputs[0]
        if hasattr(speech, "cpu"):
            speech = speech.cpu().numpy()
        speech = np.asarray(speech).squeeze()
        sf.write(wav_path, speech, 24000)
        print(f"scene {idx} ({scene['id']}): {wav_path}")

    print("ALL_NARRATION_DONE")


if __name__ == "__main__":
    main()
