#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""transcribe.py — 16kHz WAV を word 単位で文字起こし。mlx_whisper → faster-whisper の順でフォールバック。"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path


def try_mlx_whisper_module(wav, model_name):
    try:
        import mlx_whisper  # noqa: F401
    except ImportError:
        return None
    try:
        from mlx_whisper import transcribe as mx_transcribe
        return mx_transcribe(str(wav), path_or_hf_repo=model_name, word_timestamps=True, language="ja")
    except Exception as e:
        sys.stderr.write(f"mlx_whisper module error: {e}\n")
        return None


def try_mlx_whisper_cli(wav, model_name, out_dir):
    """mlx_whisper CLI を直接呼ぶフォールバック"""
    exe = shutil.which("mlx_whisper")
    if not exe:
        # ユーザー pip インストール先も検索
        candidates = [
            str(Path.home() / "Library/Python/3.9/bin/mlx_whisper"),
            str(Path.home() / "Library/Python/3.10/bin/mlx_whisper"),
            str(Path.home() / "Library/Python/3.11/bin/mlx_whisper"),
            str(Path.home() / "Library/Python/3.12/bin/mlx_whisper"),
        ]
        for c in candidates:
            if os.path.exists(c):
                exe = c
                break
    if not exe:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([exe, "--model", model_name, "--language", "ja",
                        "--word-timestamps", "True", "--output-format", "json",
                        "--output-dir", str(out_dir), str(wav)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(f"mlx_whisper CLI error: {r.stderr[-500:]}\n")
        return None
    # mlx_whisper は最初の "." までで切るので注意
    base = wav.name.split(".", 1)[0]
    jf = out_dir / (base + ".json")
    if not jf.exists():
        return None
    return json.loads(jf.read_text(encoding="utf-8"))


def try_faster_whisper(wav, model_name):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    # CPU でも動くが遅い。GPU があれば自動利用
    model = WhisperModel(model_name, device="auto", compute_type="default")
    segments_iter, info = model.transcribe(str(wav), language="ja", word_timestamps=True, vad_filter=False)
    segments = []
    for seg in segments_iter:
        words = []
        for w in seg.words or []:
            words.append({"start": float(w.start), "end": float(w.end), "word": w.word})
        segments.append({
            "start": float(seg.start), "end": float(seg.end),
            "text": seg.text, "words": words,
        })
    return {"language": info.language, "segments": segments}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", help="16kHz mono wav (or any audio ffmpeg can read)")
    ap.add_argument("--out", required=True, help="words.json output path")
    ap.add_argument("--model", default="mlx-community/whisper-large-v3-turbo",
                    help="model name (mlx_whisper id or faster-whisper id)")
    ap.add_argument("--engine", default="auto", choices=["auto", "mlx", "faster", "mlx_cli"])
    args = ap.parse_args()

    wav = Path(args.audio)
    if not wav.exists():
        sys.stderr.write(f"audio not found: {wav}\n")
        sys.exit(2)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    result = None
    used_engine = None
    fw_model = args.model.split("/")[-1].replace("whisper-", "") if "whisper-" in args.model else "large-v3"

    if args.engine in ("auto", "mlx"):
        result = try_mlx_whisper_module(wav, args.model)
        used_engine = "mlx_whisper (module)" if result else None

    if result is None and args.engine in ("auto", "mlx_cli"):
        result = try_mlx_whisper_cli(wav, args.model, out.parent / "_mlx")
        if result:
            used_engine = "mlx_whisper (cli)"

    if result is None and args.engine in ("auto", "faster"):
        result = try_faster_whisper(wav, fw_model)
        if result:
            used_engine = "faster_whisper"

    if result is None:
        sys.stderr.write("ERROR: no transcribe engine available. Install mlx-whisper (Mac) or faster-whisper.\n")
        sys.stderr.write("  Mac:     pip install mlx-whisper\n")
        sys.stderr.write("  Other:   pip install faster-whisper\n")
        sys.exit(3)

    # 正規化: segments[].words[] {start,end,word}
    normalized = {
        "engine": used_engine,
        "model": args.model,
        "language": result.get("language", "ja"),
        "segments": [],
    }
    for seg in result.get("segments", []):
        words = []
        for w in (seg.get("words") or []):
            ww = w.get("word") if isinstance(w.get("word"), str) else w.get("text", "")
            words.append({
                "start": float(w["start"]),
                "end": float(w["end"]),
                "word": (ww or "").strip(),
            })
        normalized["segments"].append({
            "start": float(seg.get("start", 0)),
            "end": float(seg.get("end", 0)),
            "text": (seg.get("text") or "").strip(),
            "words": words,
        })

    out.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    n_words = sum(len(s["words"]) for s in normalized["segments"])
    print(f"OK: {used_engine} → {out}  ({n_words} words, {len(normalized['segments'])} segments)")


if __name__ == "__main__":
    main()
