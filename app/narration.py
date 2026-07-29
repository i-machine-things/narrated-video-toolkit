"""VibeVoice narration generation, loaded once and reused across jobs."""
import os
from typing import Callable, Optional

import numpy as np
import soundfile as sf

from vibevoice.modular.modeling_vibevoice_inference import VibeVoiceForConditionalGenerationInference
from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor

MODEL_ID = os.environ.get("VIBEVOICE_MODEL_ID", "microsoft/VibeVoice-1.5B")
CFG_SCALE = 1.3

_model = None
_processor = None


def load_model():
    global _model, _processor
    if _model is None:
        _processor = VibeVoiceProcessor.from_pretrained(MODEL_ID)
        _model = VibeVoiceForConditionalGenerationInference.from_pretrained(MODEL_ID, torch_dtype="float32")
        _model.eval()
    return _model, _processor


def generate_narration(
    scene_texts: list[str],
    reference_audio_path: str,
    out_dir: str,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> list[str]:
    model, processor = load_model()
    total = len(scene_texts)
    wav_paths = []
    for idx, text in enumerate(scene_texts):
        wav_path = os.path.join(out_dir, f"narr_{idx:02d}.wav")
        prompt = f"Speaker 1: {text}"
        inputs = processor(text=[prompt], voice_samples=[[reference_audio_path]], return_tensors="pt")
        out = model.generate(**inputs, tokenizer=processor.tokenizer, cfg_scale=CFG_SCALE, max_new_tokens=None)
        speech = out.speech_outputs[0]
        if hasattr(speech, "cpu"):
            speech = speech.cpu().numpy()
        speech = np.asarray(speech).squeeze()
        sf.write(wav_path, speech, 24000)
        wav_paths.append(wav_path)
        if progress_cb:
            progress_cb(idx + 1, total)
    return wav_paths
