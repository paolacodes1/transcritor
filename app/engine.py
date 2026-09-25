"""Transcription engine.

Apple Silicon Macs  -> mlx-whisper (fast, uses the Mac's GPU)
Intel Macs / others -> faster-whisper (CPU)

Audio/video is decoded with PyAV, so no separate ffmpeg install is needed.
"""
import os
import platform
import sys
import types

import numpy as np

SAMPLE_RATE = 16000
USE_MLX = sys.platform == "darwin" and platform.machine() == "arm64"

MLX_MODEL = os.environ.get("TRANSCRITOR_MLX_MODEL", "mlx-community/whisper-large-v3-turbo")
FW_MODEL = os.environ.get("TRANSCRITOR_FW_MODEL", "large-v3-turbo")


def load_audio(path):
    """Decode any audio/video file to 16 kHz mono float32."""
    import av

    chunks = []
    try:
        container = av.open(path)
    except Exception as e:  # unreadable / not a media file
        raise ValueError("NO_AUDIO") from e
    with container:
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise ValueError("NO_AUDIO")
        resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        raise ValueError("NO_AUDIO")
    return np.concatenate(chunks).astype(np.float32)


class Engine:
    def __init__(self):
        self._fw_model = None

    @property
    def backend(self):
        return "mlx" if USE_MLX else "faster-whisper"

    def download(self):
        """Fetch model weights ahead of time (used by the installer)."""
        if USE_MLX:
            from huggingface_hub import snapshot_download

            snapshot_download(MLX_MODEL)
        else:
            self._load_fw()

    def _load_fw(self):
        if self._fw_model is None:
            from faster_whisper import WhisperModel

            self._fw_model = WhisperModel(FW_MODEL, device="cpu", compute_type="int8")
        return self._fw_model

    def transcribe(self, path, language=None, prompt=None, on_progress=None):
        """Returns {"segments": [{"start","end","text"}], "language", "duration"}."""
        on_progress = on_progress or (lambda p: None)
        audio = load_audio(path)
        duration = len(audio) / SAMPLE_RATE
        language = language or None
        prompt = (prompt or "").strip() or None

        if USE_MLX:
            segments, lang = self._run_mlx(audio, language, prompt, on_progress)
        else:
            segments, lang = self._run_fw(audio, duration, language, prompt, on_progress)
        on_progress(1.0)
        return {"segments": segments, "language": lang, "duration": duration}

    def _run_mlx(self, audio, language, prompt, on_progress):
        import mlx_whisper

        tmod = sys.modules["mlx_whisper.transcribe"]

        class Bar:  # stands in for tqdm so we can report progress
            def __init__(self, total=None, **_):
                self.total = total or 1
                self.n = 0

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def update(self, k):
                self.n += k
                on_progress(min(self.n / self.total, 0.999))

        original = tmod.tqdm
        tmod.tqdm = types.SimpleNamespace(tqdm=Bar)
        try:
            result = mlx_whisper.transcribe(
                audio,
                path_or_hf_repo=MLX_MODEL,
                verbose=False,
                language=language,
                initial_prompt=prompt,
                condition_on_previous_text=False,
            )
        finally:
            tmod.tqdm = original
        segments = [
            {"start": float(s["start"]), "end": float(s["end"]), "text": s["text"].strip()}
            for s in result["segments"]
            if s["text"].strip()
        ]
        return segments, result.get("language")

    def _run_fw(self, audio, duration, language, prompt, on_progress):
        model = self._load_fw()
        seg_iter, info = model.transcribe(
            audio,
            language=language,
            initial_prompt=prompt,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        segments = []
        for s in seg_iter:
            text = s.text.strip()
            if text:
                segments.append({"start": float(s.start), "end": float(s.end), "text": text})
            if duration:
                on_progress(min(s.end / duration, 0.999))
        return segments, info.language


if __name__ == "__main__":
    if "--download" in sys.argv:
        Engine().download()
        print("OK")
