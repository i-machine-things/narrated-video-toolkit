"""Cleans up user-uploaded reference audio before it's used for voice cloning."""
import subprocess


def prepare_reference_audio(input_path: str, output_path: str):
    """Denoise, loudness-normalize, and resample a reference clip so quiet/noisy
    uploads still clone well. Learned the hard way: a raw quiet/noisy recording
    clones noticeably worse and can carry background static into the output."""
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-af", "afftdn=nr=20:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=80",
        "-ac", "1", "-ar", "24000",
        output_path,
        "-loglevel", "error",
    ], check=True)
