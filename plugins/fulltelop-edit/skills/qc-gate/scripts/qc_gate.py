#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qc_gate — ショート編集の「品質改札」（MVP）

セッションが変わると品質がブレる問題を、機械チェックで強制的に止める小さな改札。
焼く前/書き出す前に必ず通す。FAILがあれば exit 1（納品ブロック）、WARNは要目視で記録。

設計の正本: 社内メモ（非公開）
しきい値の正本: ./thresholds.json（エージェントは上書きしない）

サブコマンド（MVP=Codex推奨の最小サブセット）:
  caption <校閲json>          テロップlint（幅px/cps/行頭NG/句読点/辞書未補正）
  audio   <video|audio>       音質事故（ピーククリップ/長すぎる無音/[整音時]LUFS）
  render  <video>             書き出し事故（解像度/fps/尺/音声有無/ビットレート）
  sync    <校閲json> <video>  テロップ↔発話のズレ（出力動画を再認識→全文difflib大域整列・独立データ）
                                個別ズレは要目視WARN／系統ズレ(中央値大)のみFAIL。mlx無ければVADにフォールバック
  spec    <spec.json>         経路宣言5項目が埋まっているか
  words   <words.json>        word文字起こしの実在とカバレッジ

共通オプション: --profile {vertical_reel|horizontal_lecture} --thresholds <path>
終了コード: 0=PASS / 1=FAIL（納品不可） / 2=BLOCKED（前提不足・要再生成）
"""
import argparse
import json
import os
import re
import subprocess
import shutil
import sys
import unicodedata
from pathlib import Path


def _find_exe(name, extra_candidates=()):
    """PATH 検索 + 既知のインストール先候補。配布物の可搬化のため。"""
    p = shutil.which(name)
    if p:
        return p
    for c in extra_candidates:
        if Path(c).exists():
            return c
    return None


FFMPEG = _find_exe("ffmpeg", ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]) or "ffmpeg"
FFPROBE = _find_exe("ffprobe", ["/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"]) or "ffprobe"
MLX = _find_exe("mlx_whisper", [
    str(Path.home() / "Library/Python/3.9/bin/mlx_whisper"),
    str(Path.home() / "Library/Python/3.10/bin/mlx_whisper"),
    str(Path.home() / "Library/Python/3.11/bin/mlx_whisper"),
    str(Path.home() / "Library/Python/3.12/bin/mlx_whisper"),
])
MLX_MODEL = "mlx-community/whisper-large-v3-turbo"
HERE = Path(__file__).resolve().parent
DEFAULT_THRESHOLDS = (HERE.parent / "thresholds.json") if (HERE.parent / "thresholds.json").exists() else (HERE / "thresholds.json")

# 語彙辞書の検索順: 環境変数 → プロジェクト直下 → ホーム → パッケージ同梱
def _find_vocab():
    env = os.environ.get("FULLTELOP_VOCAB")
    if env and Path(env).exists():
        return Path(env)
    cwd_v = Path.cwd() / "vocabulary.json"
    if cwd_v.exists():
        return cwd_v
    home_v = Path.home() / ".fulltelop" / "vocabulary.json"
    if home_v.exists():
        return home_v
    # パッケージ同梱の sample
    pkg_root = HERE.parent.parent.parent  # qc-gate/scripts/ → qc-gate/ → skills/ → root
    bundled = pkg_root / "assets" / "vocabulary.json"
    if bundled.exists():
        return bundled
    sample = pkg_root / "assets" / "vocabulary.sample.json"
    if sample.exists():
        return sample
    return None


VOCAB = _find_vocab()

# ---- 出力ヘルパ ----
OK, WARN, FAIL = "✅", "⚠️", "❌"


class Report:
    def __init__(self, name):
        self.name = name
        self.fails = []
        self.warns = []
        self.notes = []

    def fail(self, msg):
        self.fails.append(msg)

    def warn(self, msg):
        self.warns.append(msg)

    def note(self, msg):
        self.notes.append(msg)

    def render(self):
        lines = [f"── {self.name} ──"]
        for n in self.notes:
            lines.append(f"   {n}")
        for w in self.warns:
            lines.append(f"{WARN} {w}")
        for f in self.fails:
            lines.append(f"{FAIL} {f}")
        if not self.fails and not self.warns:
            lines.append(f"{OK} 合格")
        elif not self.fails:
            lines.append(f"{OK} 合格（WARN {len(self.warns)}件・要目視）")
        else:
            lines.append(f"{FAIL} 不合格（FAIL {len(self.fails)}件 / WARN {len(self.warns)}件）")
        return "\n".join(lines)

    def exit_code(self):
        return 1 if self.fails else 0


# ---- 文字数（全角=1.0 / 半角=0.5） ----
def zenkaku_len(s):
    total = 0.0
    for ch in s:
        if ch in ("\n", "\r"):
            continue
        w = unicodedata.east_asian_width(ch)
        total += 1.0 if w in ("F", "W", "A") else 0.5
    return total


def load_thresholds(profile, path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    profs = data.get("profiles", {})
    if profile not in profs:
        sys.stderr.write(f"profile '{profile}' が thresholds.json に無い。候補: {list(profs)}\n")
        sys.exit(2)
    return profs[profile]


def load_items(p):
    """校閲json / clips.json / segsjson から items[{start,end,text}] を取り出す"""
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    if isinstance(data, list):
        # [[a,b,"text"], ...] or [{start,end,text}, ...]
        out = []
        for x in data:
            if isinstance(x, (list, tuple)) and len(x) >= 3:
                out.append({"start": float(x[0]), "end": float(x[1]), "text": x[2]})
            elif isinstance(x, dict):
                out.append(x)
        return out
    raise ValueError("items が読めない形式")


def run_ff(args):
    """ffmpeg/ffprobe を実行し (returncode, stdout, stderr) を返す"""
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


# =========================================================
# caption — テロップlint
# =========================================================
def _find_font():
    """NotoSansJP-ExtraBold.ttf を探す（パッケージ同梱 → 環境変数 → ホーム → システム）"""
    env = os.environ.get("FULLTELOP_FONT")
    if env and Path(env).exists():
        return env
    pkg_root = HERE.parent.parent.parent
    candidates = [
        str(pkg_root / "assets/fonts/NotoSansJP-ExtraBold.ttf"),
        str(Path.home() / "Library/Fonts/NotoSansJP-ExtraBold.ttf"),
        "/Library/Fonts/NotoSansJP-ExtraBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "C:/Windows/Fonts/NotoSansJP-ExtraBold.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def check_caption(items, th, font_px_override=None):
    from PIL import ImageFont

    c = th["caption"]
    rep = Report("caption テロップlint")
    font_px = int(font_px_override or c["font_px"])
    font_path = c.get("font_path", "@find_font")
    if font_path == "@find_font" or not Path(font_path).exists():
        font_path = _find_font()
    if not font_path:
        rep.fail("NotoSansJP-ExtraBold.ttf が見つかりません。"
                 "assets/fonts/ にあるか確認してください。")
        return rep
    try:
        font = ImageFont.truetype(font_path, font_px)
    except Exception as e:
        rep.fail(f"フォント読込失敗 {font_path}: {e}")
        return rep
    rep.note(f"profile幅基準 font_px={font_px} max_px={c['max_px']}(快適≤{c['comfort_px']}) "
             f"max_chars={c['max_chars']} cps_max={c['cps_max']}")

    # 辞書（誤形パターン）。VOCAB が見つからない環境では辞書チェックをスキップ
    vocab_patterns = []
    if VOCAB is not None and VOCAB.exists():
        try:
            v = json.loads(VOCAB.read_text(encoding="utf-8"))
            for corr in v.get("corrections", []):
                vocab_patterns.append((corr["pattern"], corr.get("replacement", "")))
        except Exception:
            pass

    ng_head = set(c.get("ng_head", []))
    texts = [(it.get("text") or "").strip() for it in items]
    for i, it in enumerate(items):
        text = texts[i]
        if not text:
            continue
        start, end = float(it.get("start", 0)), float(it.get("end", 0))
        dur = max(0.001, end - start)
        lines = text.split("\n")
        total_chars = sum(zenkaku_len(ln) for ln in lines)
        tag = f"#{i:02d}[{start:6.2f}-{end:6.2f}] 「{text.replace(chr(10), '／')}」"
        # 畳み掛け（同textの連続表示）= 意図的演出。cps検査から除外
        tatami = (i > 0 and texts[i - 1] == text) or (i < len(texts) - 1 and texts[i + 1] == text)

        # 表示が短すぎ
        if dur < c.get("min_dur_s", 0.35):
            rep.warn(f"{tag} 表示{dur:.2f}s（短すぎ・< {c['min_dur_s']}s）")

        # 行ごと幅・行頭NG・字数
        for li, ln in enumerate(lines):
            px = font.getlength(ln)
            ch = zenkaku_len(ln)
            if px > c["max_px"]:
                rep.fail(f"{tag} 行{li+1} 幅{px:.0f}px > {c['max_px']}（横長・短縮/2行化）")
            elif px > c["comfort_px"]:
                rep.warn(f"{tag} 行{li+1} 幅{px:.0f}px > 快適{c['comfort_px']}")
            if ch > c["max_chars"]:
                rep.fail(f"{tag} 行{li+1} {ch:.0f}字 > {c['max_chars']}字")
            elif ch > c["comfort_chars"]:
                rep.warn(f"{tag} 行{li+1} {ch:.0f}字 > 快適{c['comfort_chars']}字")
            head = ln.lstrip()[:1]
            if head in ng_head:
                rep.fail(f"{tag} 行{li+1} 行頭NG「{head}」")

        # cps（全文字数÷表示秒）。畳み掛けは除外。高すぎ(cps_hard)のみFAIL、cps_max超はWARN
        if not tatami:
            cps = total_chars / dur
            if cps > c.get("cps_hard", 12.0):
                rep.fail(f"{tag} cps={cps:.1f} > {c['cps_hard']}（物理的に読めない・尺を伸ばす/大幅削る）")
            elif cps > c["cps_max"]:
                rep.warn(f"{tag} cps={cps:.1f} > {c['cps_max']}（読速オーバー・分割か字削り検討）")

        # 句読点
        if c.get("forbid_punctuation") and re.search(r"[、。]", text):
            rep.warn(f"{tag} 句読点あり（縦リールは句読点なし）")

        # 辞書未補正（誤形が残っている）
        for pat, repl in vocab_patterns:
            try:
                if re.search(pat, text):
                    rep.warn(f"{tag} 未補正の疑い: /{pat}/ → 「{repl}」（要確認）")
            except re.error:
                continue
    return rep


# =========================================================
# audio — 音質事故
# =========================================================
def _max_volume_dbfs(path):
    rc, out, err = run_ff([FFMPEG, "-hide_banner", "-i", path, "-af", "volumedetect", "-f", "null", "-"])
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", err)
    return float(m.group(1)) if m else None


def _long_silences(path, noise_db, min_s):
    rc, out, err = run_ff([FFMPEG, "-hide_banner", "-i", path, "-af",
                           f"silencedetect=noise={noise_db}dB:d={min_s}", "-f", "null", "-"])
    sl = []
    for m in re.finditer(r"silence_start:\s*([\d.]+)", err):
        sl.append(float(m.group(1)))
    durs = re.findall(r"silence_duration:\s*([\d.]+)", err)
    return list(zip(sl, [float(d) for d in durs] + [None] * (len(sl) - len(durs))))


def _integrated_lufs(path):
    rc, out, err = run_ff([FFMPEG, "-hide_banner", "-i", path, "-af", "ebur128", "-f", "null", "-"])
    # 最後のサマリ "I:   -14.0 LUFS"
    vals = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", err)
    return float(vals[-1]) if vals else None


def check_audio(path, th, mode=None):
    a = th["audio"]
    rep = Report("audio 音質事故")
    mode = mode or a.get("mode_default", "muka")
    rep.note(f"mode={mode}（muka=無加工/seion=整音） peak上限={a['true_peak_max_dbfs']}dBFS "
             f"無音上限={a['max_silence_s']}s")

    mv = _max_volume_dbfs(path)
    if mv is None:
        rep.fail("音声が読めない（音声トラック無し？）")
        return rep
    rep.note(f"max_volume={mv:.1f}dBFS")
    if mv > a["true_peak_max_dbfs"]:
        rep.fail(f"ピーク {mv:.1f}dBFS > {a['true_peak_max_dbfs']}（クリップ/音割れリスク）")

    sils = _long_silences(path, a.get("silence_noise_db", -30), a["max_silence_s"])
    for st, du in sils:
        rep.fail(f"無音 {st:.2f}s〜（{du if du else '?'}s）> {a['max_silence_s']}s（間延び）")

    if mode == "seion":
        lufs = _integrated_lufs(path)
        if lufs is None:
            rep.warn("LUFS計測不可")
        else:
            tgt, tol = a["seion_lufs_target"], a["seion_lufs_tol"]
            rep.note(f"integrated={lufs:.1f}LUFS（目標{tgt}±{tol}）")
            if abs(lufs - tgt) > tol:
                rep.fail(f"LUFS {lufs:.1f} が {tgt}±{tol} 外（整音やり直し）")
    else:
        rep.note("無加工経路: LUFS整合は検査しない（声トラック非加工が前提）")
    return rep


# =========================================================
# render — 書き出し事故
# =========================================================
def _probe(path):
    rc, out, err = run_ff([FFPROBE, "-v", "error", "-show_entries",
                           "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,bit_rate:format=duration",
                           "-of", "json", path])
    if rc != 0:
        return None
    return json.loads(out)


def check_render(path, th):
    r = th["render"]
    rep = Report("render 書き出し事故")
    info = _probe(path)
    if not info:
        rep.fail(f"ffprobe失敗（壊れ/未生成）: {path}")
        return rep
    vs = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    as_ = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info.get("format", {}).get("duration", 0))
    rep.note(f"尺={dur:.1f}s")

    if not vs:
        rep.fail("映像トラック無し")
        return rep
    w, h = int(vs["width"]), int(vs["height"])
    rep.note(f"解像度={w}x{h}")
    if w != r["w"] or h != r["h"]:
        rep.fail(f"解像度 {w}x{h} ≠ 規定 {r['w']}x{r['h']}")
    num, den = vs["r_frame_rate"].split("/")
    fps = float(num) / float(den) if float(den) else 0
    rep.note(f"fps={fps:.2f}")
    if abs(fps - r["fps"]) > r.get("fps_tol", 0.5):
        rep.fail(f"fps {fps:.2f} ≠ 規定 {r['fps']}")
    if dur > r["max_duration_s"]:
        rep.fail(f"尺 {dur:.1f}s > 上限 {r['max_duration_s']}s")

    if r.get("require_audio"):
        if not as_:
            rep.fail("音声トラック無し")
        else:
            sr = int(as_.get("sample_rate", 0))
            br = int(as_.get("bit_rate", 0)) if as_.get("bit_rate") else 0
            rep.note(f"音声={as_.get('codec_name')} {sr}Hz {br}bps")
            if sr != r["sample_rate"]:
                rep.warn(f"サンプルレート {sr} ≠ {r['sample_rate']}")
            if br and br < r["aac_bitrate_min"]:
                rep.warn(f"音声ビットレート {br} < {r['aac_bitrate_min']}")
    return rep


# =========================================================
# sync — テロップ↔発話ズレ
#   主経路: word-anchor（出力動画を再文字起こし→出力時刻のword列に語頭照合）
#   フォールバック: VAD onset（words得られない時のみ）
#   ※どちらも「独立データ」。retime_telop.pyのNW整列は再利用しない（自己循環回避）
# =========================================================
NONSPOKEN_RE = re.compile(r"残り\d|円$|\d+日|\d+%")  # カウントダウン/末尾カードは整列対象外


def _output_words(video):
    """出力動画を再文字起こしして出力時刻のword列[(start,end,word)]を返す（キャッシュ）。
    独立データ＝ビルドのソース→出力マッピングを信用しない検算。mlx_whisper無ければNone。"""
    if not Path(MLX).exists():
        return None
    # stem内の"."はmlx_whisperが出力名で最初の"."までしか取らないため "_" に置換
    stem = Path(video).stem.replace(".", "_")
    cache = Path("/tmp") / f"qc_owords_{stem}.json"
    try:
        if cache.exists() and cache.stat().st_mtime >= Path(video).stat().st_mtime:
            data = json.loads(cache.read_text(encoding="utf-8"))
            return [(w["s"], w["e"], w["w"]) for w in data]
    except Exception:
        pass
    wav = Path("/tmp") / f"qc_owav_{stem}.wav"
    run_ff([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", video,
            "-ac", "1", "-ar", "16000", str(wav)])
    outdir = Path("/tmp") / f"qc_otr_{stem}"
    r = subprocess.run([MLX, "--model", MLX_MODEL, "--language", "ja",
                        "--word-timestamps", "True", "--output-format", "json",
                        "--output-dir", str(outdir), str(wav)],
                       capture_output=True, text=True)
    # mlx_whisperは出力ファイル名を「.wav」直前でなく**最初の"."まで**で切る癖がある
    # → wav名の最初の "." までを取って .json を付ける
    base = wav.name.split(".", 1)[0]
    jf = outdir / (base + ".json")
    if not jf.exists():
        return None
    try:
        d = json.loads(jf.read_text(encoding="utf-8"))
    except Exception:
        return None
    words = []
    for seg in d.get("segments", []):
        for w in seg.get("words", []):
            ww = (w.get("word") or w.get("text") or "").strip()
            if ww:
                words.append((float(w["start"]), float(w["end"]), ww))
    if not words:
        return None
    cache.write_text(json.dumps([{"s": a, "e": b, "w": c} for a, b, c in words],
                                ensure_ascii=False), encoding="utf-8")
    return words


def _word_anchor_seq(items, words):
    """テロップ全文と出力再認識wordを difflib で大域整列（順序保持・繰り返し語/言い換え耐性）。
    各テロップの先頭一致文字が対応するwordのstartに照合し、表示開始との差(ms)を返す。
    ※整列対象は『出力動画の再認識』という独立データ＝ビルドのソース時刻には依存しない（自己循環なし）。
    返り: [(item_index, st, head, diff_ms or None)]（発話テロップのみ）。"""
    import difflib
    # B: 再認識word の連結文字列 と 各文字→word開始時刻
    B = ""
    bt = []
    for ws, we, ww in words:
        for ch in ww:
            B += ch
            bt.append(ws)
    # A: テロップ本文（改行/空白除去）の連結 と 各発話テロップのA内開始位置
    A = ""
    spoken = []
    for i, it in enumerate(items):
        text = (it.get("text") or "").strip()
        if not text or NONSPOKEN_RE.search(text):
            continue
        st = float(it.get("start", 0))
        head = text.split(chr(10))[0]
        core = text.replace("\n", "").replace(" ", "").replace("　", "")
        spoken.append((i, st, head, len(A), len(A) + len(core)))
        A += core
    if not A or not B:
        return [(i, st, head, None) for (i, st, head, a0, a1) in spoken]
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    a2b = {}
    for a0, b0, size in sm.get_matching_blocks():
        for off in range(size):
            a2b[a0 + off] = b0 + off
    out = []
    for (i, st, head, a_start, a_end) in spoken:
        bpos = None
        for a in range(a_start, a_end):
            if a in a2b:
                bpos = a2b[a]
                break
        if bpos is None:
            out.append((i, st, head, None))
            continue
        out.append((i, st, head, (st - bt[bpos]) * 1000.0))
    return out


def _check_sync_wordanchor(items, th, words):
    s = th["sync"]
    rep = Report("sync テロップ↔発話ズレ（word-anchor・出力再認識・順次整列）")
    rep.note(f"許容窓 {s['min_ms']}〜{s['max_ms']}ms ※出力動画を再文字起こしし語頭に順次照合（独立データ・繰り返し語耐性）")
    diffs = []
    total = 0
    unmatched = 0
    for i, st, head, diff in _word_anchor_seq(items, words):
        total += 1
        if diff is None:
            rep.note(f"#{i:02d} {st:6.2f}s 「{head}」整列不能→要目視")
            unmatched += 1
            continue
        diffs.append(diff)
        # 個別テロップのズレは「要目視」WARN止まり（言い換え/繰り返し語/再認識ノイズで誤検出が出るため
        # ハードFAILにしない）。理想窓は-80〜280だが、再認識ノイズ床(~300ms)込みのwarn帯を出た候補のみ人に回す。
        if diff < s.get("warn_early_ms", -350) or diff > s.get("warn_late_ms", 480):
            arrow = "早め" if diff < 0 else "遅め"
            rep.warn(f"#{i:02d} {st:6.2f}s ズレ {diff:+.0f}ms（{arrow}・要目視）「{head}」")
    cov = len(diffs) / max(1, total)
    rep.note(f"整列{len(diffs)}/{total}件（カバレッジ{cov*100:.0f}%・整列不能{unmatched}）")
    if diffs:
        med = sorted(abs(d) for d in diffs)[len(diffs) // 2]
        rep.note(f"|中央値|={med:.0f}ms（再認識ノイズ床~300ms込み）")
        # ハードFAILは「全体が系統的にズレてる」＝中央値が大きい時だけ（オフセット間違い等）
        if med > s.get("median_fail_ms", 600):
            rep.fail(f"|中央値|{med:.0f}ms > {s.get('median_fail_ms',600)}ms＝**全テロップが系統的にズレてる**（要再同期）")
        elif med > s.get("median_warn_ms", 400):
            rep.warn(f"|中央値|{med:.0f}ms > {s.get('median_warn_ms',400)}ms（全体的にズレ気味・要目視）")
    if total > 3 and cov < 0.5:
        rep.warn(f"整列カバレッジ{cov*100:.0f}%が低い→未整列分は要目視（緑でも目視省略しない）")
    rep.note("※個別ズレは目視候補（自動FAILにしない）。最後は焼き上がりを目で確認")
    return rep


def _speech_onsets(path, noise_db=-30, min_sil=0.18):
    """silencedetect の silence_end = 発話再開時刻（VADフォールバック）。"""
    rc, out, err = run_ff([FFMPEG, "-hide_banner", "-i", path, "-af",
                           f"silencedetect=noise={noise_db}dB:d={min_sil}", "-f", "null", "-"])
    onsets = [0.0]
    for m in re.finditer(r"silence_end:\s*([\d.]+)", err):
        onsets.append(float(m.group(1)))
    return sorted(onsets)


def _check_sync_vad(items, path, th):
    s = th["sync"]
    rep = Report("sync テロップ↔発話ズレ（VAD onset・フォールバック）")
    rep.note(f"許容窓 {s['min_ms']}〜{s['max_ms']}ms ※mlx_whisper無し→VAD onset計測（ソフト発話で誤差大・参考値）")
    onsets = _speech_onsets(path, th["audio"].get("silence_noise_db", -30))
    if len(onsets) < 2:
        rep.warn("発話onsetがほぼ検出されない→VAD計測は弱い。要目視")
    diffs = []
    for i, it in enumerate(items):
        text = (it.get("text") or "").strip()
        if not text or NONSPOKEN_RE.search(text):
            continue
        st = float(it.get("start", 0))
        near = min(onsets, key=lambda o: abs(o - st)) if onsets else None
        if near is None or abs(near - st) > 0.5:
            rep.note(f"#{i:02d} {st:6.2f}s 近傍onset無し（測定対象外）")
            continue
        diff_ms = (st - near) * 1000.0
        diffs.append(diff_ms)
        if diff_ms < s["min_ms"] or diff_ms > s["max_ms"]:
            arrow = "早すぎ" if diff_ms < 0 else "遅すぎ"
            rep.fail(f"#{i:02d} {st:6.2f}s ズレ {diff_ms:+.0f}ms（{arrow}）「{text.split(chr(10))[0]}」")
    if diffs:
        med = sorted(abs(d) for d in diffs)[len(diffs) // 2]
        rep.note(f"計測{len(diffs)}件 |中央値|={med:.0f}ms")
    return rep


def check_sync(items, path, th, words_override=None):
    """主経路=word-anchor（出力再認識）。words得られない時のみVADフォールバック。"""
    words = words_override or _output_words(path)
    if words:
        return _check_sync_wordanchor(items, th, words)
    return _check_sync_vad(items, path, th)


# =========================================================
# 前提チェック
# =========================================================
def check_spec(path):
    rep = Report("spec 経路宣言")
    required = ["route", "layout_type", "audio_mode", "delivery", "threshold_profile"]
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        rep.fail(f"spec.json読めない: {e}")
        return rep
    missing = [k for k in required if not data.get(k)]
    if missing:
        rep.fail(f"未記入: {missing}（経路が確定してない＝着手不可）")
    else:
        rep.note("route=%s layout=%s audio=%s delivery=%s profile=%s" % tuple(data[k] for k in required))
    return rep


def check_words(path, items=None):
    rep = Report("words 文字起こし前提")
    p = Path(path)
    if not p.exists():
        rep.fail(f"words.json不在: {path}（文字起こし未生成＝GATE_BLOCKED）")
        rep._blocked = True
        return rep
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        words = [w for seg in data.get("segments", []) for w in seg.get("words", [])]
        if not words:
            rep.fail("words配列が空（word単位で起こせていない）")
            rep._blocked = True
        else:
            t0 = words[0].get("start", 0)
            t1 = words[-1].get("end", 0)
            rep.note(f"word数={len(words)} 範囲={t0:.1f}〜{t1:.1f}s")
    except Exception as e:
        rep.fail(f"words.json壊れ: {e}")
        rep._blocked = True
    return rep


# =========================================================
# main
# =========================================================
def main():
    ap = argparse.ArgumentParser(description="qc_gate — ショート編集の品質改札（MVP）")
    ap.add_argument("cmd", choices=["caption", "audio", "render", "sync", "spec", "words", "all"])
    ap.add_argument("input", nargs="?", help="校閲json または 動画パス")
    ap.add_argument("input2", nargs="?", help="sync時の動画パス")
    ap.add_argument("--profile", default="vertical_reel")
    ap.add_argument("--thresholds", default=str(DEFAULT_THRESHOLDS))
    ap.add_argument("--mode", default=None, help="audio: muka|seion（既定はprofile）")
    ap.add_argument("--font-px", type=int, default=None, help="caption: フォントpx上書き")
    ap.add_argument("--words", default=None, help="sync: 出力時刻のword JSON（無ければ出力動画を再認識）")
    args = ap.parse_args()

    if args.cmd in ("caption", "audio", "render", "sync", "all"):
        th = load_thresholds(args.profile, args.thresholds)

    reps = []
    blocked = False
    if args.cmd == "caption":
        reps.append(check_caption(load_items(args.input), th, args.font_px))
    elif args.cmd == "audio":
        reps.append(check_audio(args.input, th, args.mode))
    elif args.cmd == "render":
        reps.append(check_render(args.input, th))
    elif args.cmd == "sync":
        wov = None
        if args.words:
            wd = json.loads(Path(args.words).read_text(encoding="utf-8"))
            segs_w = wd.get("segments", wd) if isinstance(wd, dict) else wd
            wov = [(float(w["start"]), float(w["end"]), (w.get("word") or w.get("text") or "").strip())
                   for s_ in segs_w for w in (s_.get("words", []) if isinstance(s_, dict) else [])]
            wov = [x for x in wov if x[2]] or None
        reps.append(check_sync(load_items(args.input), args.input2, th, wov))
    elif args.cmd == "spec":
        reps.append(check_spec(args.input))
    elif args.cmd == "words":
        reps.append(check_words(args.input))
    elif args.cmd == "all":
        # spec.json を起点に出力物をまとめて検査する想定（MVPでは個別呼び出し推奨）
        sys.stderr.write("all はMVP未実装。個別に caption/audio/render/sync を呼んでください\n")
        sys.exit(2)

    print("\n\n".join(r.render() for r in reps))
    code = 0
    for r in reps:
        if getattr(r, "_blocked", False):
            code = 2
        elif r.exit_code() == 1 and code != 2:
            code = 1
    print()
    label = {0: f"{OK} PASS", 1: f"{FAIL} FAIL（納品不可）", 2: "⛔ BLOCKED（前提不足）"}[code]
    print(f"=== qc_gate {args.cmd}: {label} ===")
    sys.exit(code)


if __name__ == "__main__":
    main()
