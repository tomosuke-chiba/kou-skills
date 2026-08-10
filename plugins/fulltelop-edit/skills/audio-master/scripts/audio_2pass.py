#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audio_2pass.py — 2 パス loudnorm で確実に -14LUFS。線形ゲイン+軽コンプ+真ピークリミッター。"""
import argparse, json, re, subprocess, sys
from pathlib import Path

FFMPEG = "ffmpeg"


def measure_lufs(input_file, target_i=-14.0, target_tp=-1.0):
    """1パス目: integrated LUFS を測定"""
    cmd = [FFMPEG, "-hide_banner", "-i", input_file,
           "-af", f"loudnorm=I={target_i}:TP={target_tp}:print_format=json",
           "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    j = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not j:
        sys.stderr.write("loudnorm measurement failed:\n" + r.stderr[-2000:] + "\n")
        sys.exit(2)
    meas = json.loads(j.group(0))
    return {
        "input_i": float(meas["input_i"]),
        "input_tp": float(meas["input_tp"]),
        "input_lra": float(meas["input_lra"]),
        "input_thresh": float(meas["input_thresh"]),
        "target_offset": float(meas["target_offset"]),
    }


def apply_master(input_file, output_file, gain_db, mode="seion",
                 compressor=True, denoise=False, denoise_nr=6):
    af_parts = []
    if denoise:
        af_parts.append(f"afftdn=nr={denoise_nr}:nf=-25")
    if mode == "seion":
        if compressor:
            af_parts.append("acompressor=threshold=-18dB:ratio=2.5:attack=10:release=200:makeup=1")
        af_parts.append(f"volume={gain_db:.2f}dB")
        af_parts.append("alimiter=level=false:limit=0.84")
    elif mode == "muka":
        # 無加工: フェードのみ（必要なら呼び出し側でフィルタ追加）
        pass
    af = ",".join(af_parts) if af_parts else "anull"

    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-i", input_file, "-af", af,
           "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
           "-movflags", "+faststart", output_file]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(f"ffmpeg apply failed: {r.stderr[-1500:]}\n")
        sys.exit(3)


def verify_lufs(output_file):
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", output_file,
                        "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    vals = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", r.stderr)
    return float(vals[-1]) if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--target-i", type=float, default=-14.0)
    ap.add_argument("--target-tp", type=float, default=-1.0)
    ap.add_argument("--limiter-correction", type=float, default=0.6,
                    help="リミッター減衰分の補正 dB（既定 +0.6）")
    ap.add_argument("--mode", default="seion", choices=["seion", "muka"])
    ap.add_argument("--denoise", action="store_true")
    ap.add_argument("--denoise-nr", type=int, default=6)
    ap.add_argument("--no-compressor", action="store_true")
    args = ap.parse_args()

    print("=== 1パス目: 測定中 ===")
    meas = measure_lufs(args.input, args.target_i, args.target_tp)
    print(f"  input_i={meas['input_i']:.2f} LUFS  TP={meas['input_tp']:.2f}  LRA={meas['input_lra']:.2f}")
    gain = args.target_i - meas["input_i"] + args.limiter_correction
    print(f"  → gain {gain:+.2f}dB を適用")

    print("=== 2パス目: 適用中 ===")
    apply_master(args.input, args.output, gain, args.mode,
                 compressor=not args.no_compressor,
                 denoise=args.denoise, denoise_nr=args.denoise_nr)

    out_lufs = verify_lufs(args.output)
    print(f"=== 検証 ===")
    print(f"  integrated={out_lufs}LUFS (目標 {args.target_i})")
    if abs((out_lufs or -999) - args.target_i) > 1.0:
        sys.stderr.write(f"⚠️  目標から外れています。--limiter-correction を調整してください\n")
        sys.exit(4)
    print("  ✅ OK")


if __name__ == "__main__":
    main()
