# Narrated Video Toolkit

Pipeline for generating narrated, animated training videos (slides + Ken Burns motion + TTS narration) rendered on a beefy remote sandbox instead of a weak local machine. Built for a sample ITAR/EAR export-control training video; the pipeline itself is reusable for any similar narrated-slide video by swapping out the `SCENES` list in `build_video.py`.

## How it fits together

1. **Sandbox** (`sandbox-setup/`): an isolated Docker container on a home server (TrueNAS SCALE, in the original case), reachable only over LAN via key-only SSH, with no access to anything else on the host. This is where all the heavy lifting (TTS model inference, ffmpeg encoding) happens.
2. **`generate_narration.py`**: run inside the sandbox's `vibevoice` venv. Loads VibeVoice-1.5B, clones a voice from a reference clip (`my_voice_ref3.wav`), and generates one narration WAV per scene defined in `build_video.py`'s `SCENES` list.
3. **`build_video.py`**: run on the sandbox with system Python (needs Pillow + ffmpeg). Renders one animated slide per scene, pairs it with the matching pre-generated narration WAV, applies a Ken Burns zoom + fade transition per scene, and concatenates everything into the final MP4.
4. **`narration_progress_widget.py`**: run locally (needs `python3-tk`). A small always-on-top Tkinter window that polls the sandbox over SSH every 20s and shows a progress bar while narration generation (the slow part) runs in the background.

## Sandbox setup

See `sandbox-setup/docker-compose.yaml` — paste into TrueNAS SCALE's "Custom App" → "Install via YAML" dialog (or adapt for any Docker host). It's a **Debian bookworm-slim** container (not Alpine — see gotchas below) that bootstraps `openssh-server` + a `claude` user with key-only auth on every start, then execs `sshd -D`. No host paths are mounted, so the container has zero visibility into anything else on the host.

Generate your own keypair rather than reusing the one baked into the example YAML:
```
ssh-keygen -t ed25519 -f ~/.ssh/sandbox_key -N "" -C "sandbox"
```
and swap the `PUBLIC_KEY` env var for your own public key before deploying.

Once the container is up:
```
ssh -i ~/.ssh/sandbox_key -p 2222 claude@<host>
sudo apt-get install -y ffmpeg python3 python3-pip python3-venv python3-pil fonts-noto-core
```

### Per-model virtualenvs

Each TTS engine has a **separate venv** on the sandbox — do not install them into the same environment. They have incompatible pinned `transformers` versions and stepping on each other's deps repeatedly broke things during development:

| venv | engine | key pin |
|---|---|---|
| `~/venvs/xtts` | Coqui XTTS-v2 | `transformers==4.57.1` (newer versions removed an internal fn XTTS needs) |
| `~/venvs/chatterbox` | Resemble AI Chatterbox | `transformers==5.2.0` |
| `~/venvs/vibevoice` | Microsoft VibeVoice-1.5B | needs Pillow added too, so `generate_narration.py` can `import build_video` for the `SCENES` list |

`sandbox-setup/req_*.txt` are frozen pip requirements for each venv as of the last working build — use `pip install -r req_xtts.txt` etc. to reproduce an environment quickly instead of re-solving versions from scratch.

Torch/torchaudio/torchcodec should be installed from the CPU wheel index, not the default index (no GPU on the sandbox):
```
pip install torch torchaudio torchcodec --index-url https://download.pytorch.org/whl/cpu
```

## Usage

```bash
# 1. On the sandbox, generate narration (slow — VibeVoice is diffusion-based,
#    expect minutes per scene depending on scene length, not seconds):
source ~/venvs/vibevoice/bin/activate
python3 generate_narration.py     # reads SCENES from build_video.py, writes out/narr_NN.wav

# 2. Then render the video (fast — mostly ffmpeg + Pillow, seconds per scene):
python3 build_video.py            # reads out/narr_NN.wav, writes out/*.mp4 slides + final concat

# 3. Locally, watch progress while step 1 runs:
python3 narration_progress_widget.py
```

`generate_narration.py` and `build_video.py` are split deliberately because they need different Python environments (VibeVoice's venv vs. system Python with Pillow/ffmpeg) — don't try to merge them without solving that dependency separation first.

## Model choices tried (evaluate before assuming VibeVoice is always right)

Tried in this rough order, each an actual step up:
1. **espeak-ng** — free, instant, sounds fully robotic.
2. **Piper** (`en_US-lessac-medium`) — clear but flat/monotone.
3. **Coqui XTTS-v2** — good prosody, ~58 built-in speaker voices, ~15s CPU synthesis per short sentence. **Gotcha:** hard ~250-character-per-sentence limit; a single run-on sentence past that silently truncates. Always sentence-check narration text before a full render.
4. **Chatterbox** (Resemble AI) — comparable quality to XTTS, supports voice cloning + an "exaggeration" knob.
5. **VibeVoice-1.5B** (Microsoft) — won the side-by-side comparison for naturalness, especially cloning a real reference voice. Much slower (diffusion-based; minutes per scene, not seconds) and needs `Speaker 1: ...` prefixed text format.

## Voice cloning notes

- Reference clips should be **≥20-30s**, clean, natural intonation (not monotone), consistent mic distance. A 6.5s clip works but clones noticeably worse than a 30s+ one.
- If the input recording is quiet, normalize before using it as a reference:
  ```
  ffmpeg -i in.flac -af "afftdn=nr=20:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=80" -ac 1 -ar 24000 ref.wav
  ```
  (`afftdn` denoises background hiss/static, `loudnorm` fixes level, `highpass` cuts low rumble.)
- **Never clone a real, identifiable person's voice without their consent** — that's a hard line, not just a style choice. Also don't clone real celebrities/public figures even for "just for fun" personal use, and don't rip copyrighted game/media audio to use as a cloning reference for a fictional character's voice actor performance.

## Pronunciation fixes

TTS engines guess acronym pronunciation and often guess wrong. Fix it in the narration text itself (the on-screen slide text/title can keep the normal acronym spelling — only the spoken narration string needs the phonetic hint):
- Spell-out-by-letter acronyms: insert periods between letters, e.g. `D.D.T.C.` — forces individual letter names.
- Acronyms meant to be read as a word: spell it phonetically, e.g. `ITAR` → `I-TAR` (this project settled on `I-TAR` and `EE-A-R` after a few rounds of trial and error with VibeVoice specifically — different engines may need slightly different spellings, always verify per engine/voice).

## Timing

Videos in the 5-15 minute range are the target — don't over-tune narration pacing/padding to hit an exact stated runtime like "5 minutes", anything in that band is fine.
