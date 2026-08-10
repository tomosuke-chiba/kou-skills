#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preview_server.py — koetsu.json をブラウザでチャンク表示・編集する軽量サーバ。

使い方:
  python3 preview_server.py --koetsu koetsu.json [--video output.mp4] [--port 5050]

ブラウザで http://localhost:<port> を開く。
- 各テロップを編集（テキスト/start/end）
- 「✂️ 分割」「⇡ 統合」
- 「💾 保存」で koetsu.json に書き戻し
- 「📤 SRT 出力」「📤 FCPXML 出力」

依存: 標準ライブラリのみ（http.server, json, urllib.parse）。
"""
import argparse, json, os, subprocess, sys, threading, webbrowser
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


HTML = r"""<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8">
<title>telop-preview</title>
<style>
  body { font-family: -apple-system, "Helvetica Neue", "Noto Sans JP", sans-serif;
         margin: 0; background: #1a1a1a; color: #f0f0f0; }
  header { padding: 12px 16px; background: #111; border-bottom: 1px solid #333;
           display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  header h1 { font-size: 16px; margin: 0; }
  button { background: #2563eb; color: white; border: 0; padding: 8px 14px;
           border-radius: 6px; cursor: pointer; font-size: 14px; }
  button:hover { background: #1d4ed8; }
  button.secondary { background: #4b5563; }
  button.secondary:hover { background: #374151; }
  button.danger { background: #b91c1c; }
  #status { margin-left: auto; font-size: 13px; color: #9ca3af; }
  #status.ok { color: #34d399; }
  #status.err { color: #f87171; }
  main { padding: 16px; max-width: 1200px; margin: 0 auto; }
  video { width: 100%; max-height: 400px; background: black; margin-bottom: 16px; }
  .item { background: #262626; padding: 12px; border-radius: 8px; margin-bottom: 8px;
          border: 1px solid #333; display: grid; grid-template-columns: 80px 80px 1fr auto;
          gap: 10px; align-items: center; }
  .item.active { border-color: #2563eb; background: #1e293b; }
  .item input.time { background: #1f1f1f; color: #fde68a; border: 1px solid #444;
                     padding: 6px 8px; border-radius: 4px; width: 70px;
                     font-family: ui-monospace, monospace; font-size: 13px; }
  .item textarea { background: #1f1f1f; color: #f0f0f0; border: 1px solid #444;
                   padding: 8px; border-radius: 4px; resize: vertical;
                   min-height: 38px; font-family: inherit; font-size: 14px;
                   line-height: 1.4; }
  .item .actions { display: flex; gap: 4px; }
  .item .actions button { padding: 4px 8px; font-size: 12px; }
  .idx { color: #6b7280; font-family: ui-monospace, monospace; font-size: 12px;
         text-align: center; }
  .dur { color: #fbbf24; font-family: ui-monospace, monospace; font-size: 11px;
         text-align: center; }
  .cps { font-family: ui-monospace, monospace; font-size: 11px; text-align: center;
         margin-top: 4px; }
  .cps.ok { color: #34d399; }
  .cps.warn { color: #fbbf24; }
  .cps.bad { color: #f87171; font-weight: bold; }
  #snap-info { font-size: 12px; color: #6b7280; margin-left: 8px; }
  #snap-info.ok { color: #34d399; }
  button.primary { background: #16a34a; }
  button.primary:hover { background: #15803d; }
  button:disabled { background: #374151; color: #6b7280; cursor: not-allowed; }
  #learn-banner { background: #1e293b; border: 1px solid #2563eb; padding: 10px 16px;
                  margin: 0 16px 12px; border-radius: 6px; font-size: 13px;
                  color: #93c5fd; display: none; }
  footer { padding: 16px; text-align: center; color: #6b7280; font-size: 12px; }
</style>
</head>
<body>
<header>
  <h1>📝 telop-preview</h1>
  <button class="primary" id="btn-snap" onclick="snapAll()" title="🎯 全テロップのタイミングを音声に再スナップ（要 words.json + 動画）">🎯 音に合わせる</button>
  <button onclick="save()">💾 保存</button>
  <button class="secondary" onclick="exportFile('srt')">📤 SRT 出力</button>
  <button class="secondary" onclick="exportFile('fcpxml')">📤 FCPXML 出力</button>
  <span id="snap-info"></span>
  <span id="status"></span>
</header>
<div id="learn-banner"></div>
<main>
  <video id="video" controls></video>
  <div id="list"></div>
</main>
<footer>Ctrl+C でサーバを停止</footer>

<script>
let data = null;
const cursorPos = {};
let videoPath = "";
let hasWords = false;
let hasProposed = false;
const VIDEO = document.getElementById("video");
const LIST = document.getElementById("list");
const STATUS = document.getElementById("status");
const SNAP_INFO = document.getElementById("snap-info");
const SNAP_BTN = document.getElementById("btn-snap");
const LEARN_BANNER = document.getElementById("learn-banner");

async function load() {
  const r = await fetch("/api/data");
  const j = await r.json();
  data = j.koetsu;
  videoPath = j.video || "";
  hasWords = !!j.has_words;
  hasProposed = !!j.has_proposed;
  if (videoPath) VIDEO.src = "/video";
  if (!hasWords) {
    SNAP_BTN.disabled = true;
    SNAP_INFO.textContent = "🎯/word吸着分割は words.json 指定で有効化";
  } else {
    SNAP_INFO.textContent = "🎯 word吸着分割 有効";
    SNAP_INFO.className = "ok";
  }
  render();
}

// cps（文字数 ÷ 秒）の計算と色分け
function cpsOf(it) {
  const dur = Math.max(0.01, it.end - it.start);
  // 全角=1.0, 半角=0.5 で雑に
  let n = 0;
  for (const ch of it.text.replace(/\n/g, "")) {
    n += ch.charCodeAt(0) < 0x80 ? 0.5 : 1.0;
  }
  return n / dur;
}
function cpsClass(c) {
  if (c <= 6) return "ok";
  if (c <= 7) return "warn";
  if (c <= 12) return "warn";
  return "bad";
}

function render() {
  LIST.innerHTML = "";
  data.items.forEach((it, i) => {
    const div = document.createElement("div");
    div.className = "item";
    const cps = cpsOf(it);
    const cpsLabel = cps.toFixed(1) + " cps";
    div.innerHTML = `
      <div>
        <input class="time" type="number" step="0.01" value="${it.start.toFixed(2)}"
               onchange="data.items[${i}].start = parseFloat(this.value); updateDur(${i})"
               title="start">
        <div class="dur">${(it.end-it.start).toFixed(2)}s</div>
        <div class="cps ${cpsClass(cps)}">${cpsLabel}</div>
      </div>
      <div>
        <input class="time" type="number" step="0.01" value="${it.end.toFixed(2)}"
               onchange="data.items[${i}].end = parseFloat(this.value); updateDur(${i})"
               title="end">
        <div class="idx">#${i.toString().padStart(2,'0')}</div>
      </div>
      <textarea onchange="data.items[${i}].text = this.value"
                onfocus="seek(${it.start})"
                onkeyup="cursorPos[${i}]=this.selectionStart"
                onclick="cursorPos[${i}]=this.selectionStart"
                onselect="cursorPos[${i}]=this.selectionStart">${escapeHTML(it.text)}</textarea>
      <div class="actions">
        <button onclick="seek(${it.start})" class="secondary" title="動画を頭出し">▶</button>
        <button onclick="splitItem(${i})" class="secondary" title="分割（word吸着・words.json必要）">✂️</button>
        <button onclick="mergeItem(${i})" class="secondary" title="次と統合">⇡</button>
        <button onclick="deleteItem(${i})" class="danger" title="削除">🗑</button>
      </div>
    `;
    LIST.appendChild(div);
  });
}
function escapeHTML(s) {
  return s.replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"})[c]);
}
function updateDur(i) {
  render();  // 雑だが簡潔。data.items[i] の再描画で十分
}
function seek(t) {
  if (VIDEO.src) { VIDEO.currentTime = t; VIDEO.play(); }
}
async function splitItem(i) {
  const it = data.items[i];
  const txt = it.text;
  // カーソル位置があればそこでテキストを切る（文字位置が正）。無ければ中央。
  const cur = cursorPos[i];
  const hasCursor = Number.isInteger(cur) && cur > 0 && cur < txt.length;
  const targetRatio = hasCursor ? (cur / txt.length) : 0.5;
  // 時刻はサーバに「targetRatio 付近の語頭 or 無音」を尋ねて吸着（無ければ按分）
  let t = it.start + (it.end - it.start) * targetRatio;
  if (hasWords) {
    try {
      const r = await fetch("/api/split", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({start: it.start, end: it.end, ratio: targetRatio}),
      });
      const j = await r.json();
      if (j.ok && j.t) t = j.t;
    } catch(e) { /* fallback to按分 */ }
  }
  if (t <= it.start || t >= it.end) t = it.start + (it.end - it.start) * targetRatio;
  // テキストはカーソル位置優先。カーソルが無いときだけ時刻比で按分
  let cut;
  if (hasCursor) {
    cut = cur;
  } else {
    const ratio = (t - it.start) / Math.max(0.01, it.end - it.start);
    cut = Math.max(1, Math.min(txt.length - 1, Math.round(txt.length * ratio)));
  }
  data.items.splice(i, 1,
    {start: it.start, end: t, text: txt.slice(0, cut).trim()},
    {start: t, end: it.end, text: txt.slice(cut).trim()}
  );
  delete cursorPos[i];
  render();
  setStatus(hasCursor ? `✂️ カーソル位置で分割 (t=${t.toFixed(2)}s)` : (hasWords ? `✂️ word吸着で分割 (t=${t.toFixed(2)}s)` : `✂️ 中央で分割`), "ok");
}
function mergeItem(i) {
  if (i + 1 >= data.items.length) return;
  const a = data.items[i], b = data.items[i+1];
  data.items.splice(i, 2,
    {start: a.start, end: b.end, text: a.text + " " + b.text}
  );
  render();
}
function deleteItem(i) {
  if (!confirm("削除します。よろしいですか？")) return;
  data.items.splice(i, 1);
  render();
}
async function snapAll() {
  if (!hasWords) {
    setStatus("❌ words.json 未指定。--words を付けて起動してください", "err");
    return;
  }
  setStatus("🎯 音に合わせています…（数秒〜数十秒）");
  SNAP_BTN.disabled = true;
  try {
    const r = await fetch("/api/snap", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(data),
    });
    const j = await r.json();
    if (j.ok) {
      data = j.koetsu;
      render();
      setStatus(`✅ 🎯 音に合わせました（${data.items.length} 行）。確認して 💾 保存してください`, "ok");
    } else {
      setStatus(`❌ snap 失敗: ${j.error}`, "err");
    }
  } catch(e) {
    setStatus(`❌ snap エラー: ${e.message}`, "err");
  } finally {
    SNAP_BTN.disabled = false;
  }
}
async function save() {
  setStatus("保存中…");
  const r = await fetch("/api/save", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data)
  });
  const j = await r.json().catch(() => ({ok: false}));
  if (j.ok) {
    setStatus("✅ 保存しました", "ok");
    // 差分学習候補があれば通知
    if (j.learn_candidates > 0) {
      LEARN_BANNER.style.display = "block";
      LEARN_BANNER.innerHTML = `💡 直した差分から <strong>${j.learn_candidates}件</strong> の辞書学習候補が出ました → <code>${j.learn_path}</code><br>` +
        `<small>vocabulary.json に追記して次回から自動補正できます</small>`;
    }
  } else {
    setStatus(`❌ 保存失敗: ${j.error || ""}`, "err");
  }
}
async function exportFile(fmt) {
  setStatus(`${fmt.toUpperCase()} 書き出し中…`);
  const r = await fetch(`/api/export?format=${fmt}`, {method: "POST"});
  const j = await r.json();
  if (j.ok) setStatus(`✅ ${fmt.toUpperCase()} -> ${j.path}`, "ok");
  else setStatus(`❌ ${j.error}`, "err");
}
function setStatus(msg, cls) {
  STATUS.textContent = msg;
  STATUS.className = cls || "";
}
load();
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    koetsu_path = None  # set externally
    video_path = None
    words_path = None        # words.json（word timestamp・snap/split で使う）
    proposed_path = None     # proposed_telops.json（差分学習の raw 起点）
    skills_root = None

    def log_message(self, fmt, *args):
        pass  # 静かに

    def _send(self, status, body, ctype="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        body_bytes = body.encode("utf-8") if isinstance(body, str) else body
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _send_json(self, obj, status=200):
        self._send(status, json.dumps(obj, ensure_ascii=False),
                   ctype="application/json; charset=utf-8")

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/" or u.path == "/index.html":
            self._send(200, HTML)
        elif u.path == "/api/data":
            koetsu = json.loads(Path(self.koetsu_path).read_text(encoding="utf-8"))
            self._send_json({
                "koetsu": koetsu,
                "video": str(self.video_path) if self.video_path else "",
                "has_words": bool(self.words_path and Path(self.words_path).exists()),
                "has_proposed": bool(self.proposed_path and Path(self.proposed_path).exists()),
            })
        elif u.path == "/video" and self.video_path:
            self._send_video()
        else:
            self._send(404, "Not Found", ctype="text/plain")

    def _send_video(self):
        vp = Path(self.video_path)
        if not vp.exists():
            self._send(404, "video missing", ctype="text/plain")
            return
        size = vp.stat().st_size
        ext = vp.suffix.lower()
        mime = {".mp4": "video/mp4", ".mov": "video/quicktime",
                ".webm": "video/webm"}.get(ext, "application/octet-stream")
        # Range 対応（シーク高速化・部分転送）
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng and rng.startswith("bytes="):
            try:
                a, _, b = rng[6:].partition("-")
                if a:
                    start = int(a)
                    if b:
                        end = min(int(b), size - 1)
                elif b:  # bytes=-N（末尾N bytes）
                    start = max(0, size - int(b))
            except ValueError:
                start, end = 0, size - 1
        if start > end or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return
        length = end - start + 1
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(vp, "rb") as f:
            f.seek(start)
            remain = length
            while remain > 0:
                chunk = f.read(min(1 << 16, remain))
                if not chunk:
                    break
                remain -= len(chunk)
                self.wfile.write(chunk)

    def do_POST(self):
        u = urlparse(self.path)
        ln = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(ln) if ln > 0 else b""
        if u.path == "/api/save":
            try:
                koetsu = json.loads(body.decode("utf-8"))
                koetsu["items"] = sorted(koetsu["items"], key=lambda x: x["start"])
                Path(self.koetsu_path).write_text(
                    json.dumps(koetsu, ensure_ascii=False, indent=2),
                    encoding="utf-8")
                # 保存と同時に差分学習（proposed_telops があれば）
                cands_count = 0
                cands_path = None
                if self.proposed_path and Path(self.proposed_path).exists():
                    cands_path, cands_count = self._run_diff_learner()
                self._send_json({
                    "ok": True,
                    "learn_candidates": cands_count,
                    "learn_path": str(cands_path) if cands_path else None,
                })
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)
        elif u.path == "/api/snap":
            # 🎯 音に合わせる：retime_telop.py を呼ぶ（words.json + 動画が必要）
            try:
                koetsu = json.loads(body.decode("utf-8"))
                Path(self.koetsu_path).write_text(
                    json.dumps(koetsu, ensure_ascii=False, indent=2),
                    encoding="utf-8")
                result = self._run_snap()
                if result["ok"]:
                    # 書き戻し済み koetsu を読み直して返す
                    new_koetsu = json.loads(Path(self.koetsu_path).read_text(encoding="utf-8"))
                    self._send_json({"ok": True, "koetsu": new_koetsu, "log": result["log"]})
                else:
                    self._send_json({"ok": False, "error": result["error"]}, status=500)
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)
        elif u.path == "/api/split":
            # ✂️ word吸着分割：分割候補時刻を返す（クライアントが2つの item に割る）
            try:
                d = json.loads(body.decode("utf-8"))
                start = float(d.get("start", 0))
                end = float(d.get("end", 0))
                ratio = float(d.get("ratio", 0.5))
                t = self._best_split_time(start, end, ratio)
                self._send_json({"ok": True, "t": t})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)
        elif u.path == "/api/export":
            qs = parse_qs(u.query)
            fmt = qs.get("format", ["srt"])[0]
            try:
                outp = self._export(fmt)
                self._send_json({"ok": True, "path": str(outp)})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)
        else:
            self._send(404, "Not Found", ctype="text/plain")

    # ---------- helpers: snap / split / diff_learner ----------
    def _run_snap(self):
        """retime_telop.py を呼んで koetsu.json を音にスナップ"""
        if not self.video_path:
            return {"ok": False, "error": "動画パス未指定（--video）。snap には動画が要ります"}
        if not self.words_path or not Path(self.words_path).exists():
            return {"ok": False, "error": "words.json 未指定 or 不在。--words で指定してください"}
        retime = self.skills_root / "skills" / "smart-caption" / "scripts" / "retime_telop.py"
        if not retime.exists():
            return {"ok": False, "error": f"retime_telop.py が見つかりません: {retime}"}
        r = subprocess.run(
            [sys.executable, str(retime), self.koetsu_path, self.video_path,
             "--words", self.words_path],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return {"ok": False, "error": (r.stderr or r.stdout or "snap 失敗").strip()}
        return {"ok": True, "log": r.stdout.strip()}

    def _best_split_time(self, start, end, ratio=0.5):
        """word JSON を読んで、[start,end] 内の ratio 位置に近い「語頭」or「無音>0.18s」に吸着"""
        if not self.words_path or not Path(self.words_path).exists():
            # 無ければ単純な中央分割
            return start + (end - start) * ratio
        try:
            wdata = json.loads(Path(self.words_path).read_text(encoding="utf-8"))
        except Exception:
            return start + (end - start) * ratio
        words = [w for seg in wdata.get("segments", []) for w in seg.get("words", [])]
        target = start + (end - start) * ratio
        # 1) [start,end] 内の無音>0.18s を優先
        best_silence = None
        best_silence_score = 1e9
        for i in range(len(words) - 1):
            ws = float(words[i].get("end", 0))
            ns = float(words[i + 1].get("start", 0))
            gap = ns - ws
            mid = (ws + ns) / 2
            if start <= mid <= end and gap >= 0.18:
                score = abs(mid - target)
                if score < best_silence_score:
                    best_silence_score = score
                    best_silence = mid
        if best_silence is not None:
            return round(best_silence, 3)
        # 2) 語頭に吸着
        best_head = None
        best_head_score = 1e9
        for w in words:
            ws = float(w.get("start", 0))
            if start <= ws <= end:
                score = abs(ws - target)
                if score < best_head_score:
                    best_head_score = score
                    best_head = ws
        if best_head is not None:
            return round(best_head, 3)
        # 3) フォールバック
        return round(target, 3)

    def _run_diff_learner(self):
        """proposed_telops.json と koetsu.json の差分から学習候補を出す"""
        dl = self.skills_root / "skills" / "smart-caption" / "scripts" / "diff_learner.py"
        if not dl.exists():
            return None, 0
        stem = Path(self.koetsu_path).stem
        out = Path(self.koetsu_path).parent / f"{stem}_learn_candidates.json"
        r = subprocess.run(
            [sys.executable, str(dl),
             "--proposed", self.proposed_path,
             "--reviewed", self.koetsu_path,
             "--out", str(out),
             "--stem", stem],
            capture_output=True, text=True,
        )
        if r.returncode != 0 or not out.exists():
            return None, 0
        try:
            d = json.loads(out.read_text(encoding="utf-8"))
            return out, len(d.get("candidates", []))
        except Exception:
            return None, 0

    def _export(self, fmt):
        kp = Path(self.koetsu_path)
        out_dir = kp.parent
        stem = kp.stem.replace("koetsu", "preview_export") or "preview_export"
        export_root = self.skills_root / "skills" / "export-deliver" / "scripts"
        if fmt == "srt":
            out = out_dir / f"{stem}.srt"
            import subprocess
            subprocess.run([sys.executable, str(export_root / "to_srt.py"),
                            str(kp), "--out", str(out)], check=True)
        elif fmt == "fcpxml":
            out = out_dir / f"{stem}.fcpxml"
            if not self.video_path:
                raise RuntimeError("--video が指定されていないため FCPXML 出力できません")
            import subprocess
            subprocess.run([sys.executable, str(export_root / "to_fcpxml.py"),
                            str(kp), "--video", str(self.video_path),
                            "--out", str(out)], check=True)
        else:
            raise ValueError(f"unknown format: {fmt}")
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--koetsu", required=True, help="編集対象の koetsu.json")
    ap.add_argument("--video", default=None, help="任意：プレビュー用動画")
    ap.add_argument("--words", default=None,
                    help="任意：words.json（指定すると🎯音吸着・✂️word吸着分割が有効になる）")
    ap.add_argument("--proposed", default=None,
                    help="任意：proposed_telops.json（指定すると保存時に差分学習候補が出る）")
    ap.add_argument("--port", type=int, default=5050)
    ap.add_argument("--no-browser", action="store_true", help="ブラウザ自動起動しない")
    args = ap.parse_args()

    kp = Path(args.koetsu).resolve()
    if not kp.exists():
        sys.stderr.write(f"koetsu not found: {kp}\n")
        sys.exit(2)
    Handler.koetsu_path = str(kp)
    Handler.video_path = str(Path(args.video).resolve()) if args.video else None
    # words.json は --words 優先、なければ koetsu と同じ work_dir を探索
    if args.words:
        Handler.words_path = str(Path(args.words).resolve())
    else:
        cand = kp.parent / "words.json"
        Handler.words_path = str(cand) if cand.exists() else None
    # proposed_telops.json も同様
    if args.proposed:
        Handler.proposed_path = str(Path(args.proposed).resolve())
    else:
        cand = kp.parent / "proposed_telops.json"
        Handler.proposed_path = str(cand) if cand.exists() else None
    # skills/ root の解決
    here = Path(__file__).resolve().parent
    Handler.skills_root = here.parent.parent.parent  # telop-preview/scripts/ → telop-preview/ → skills/ → root

    addr = ("127.0.0.1", args.port)
    server = ThreadingHTTPServer(addr, Handler)
    server.daemon_threads = True
    url = f"http://localhost:{args.port}/"
    print(f"telop-preview サーバ起動: {url}")
    print(f"  koetsu:   {kp}")
    if Handler.video_path:
        print(f"  video:    {Handler.video_path}")
    if Handler.words_path:
        print(f"  words:    {Handler.words_path}  [🎯 音吸着・✂️ word吸着分割 有効]")
    else:
        print(f"  words:    未指定（🎯 と word吸着分割は無効になります）")
    if Handler.proposed_path:
        print(f"  proposed: {Handler.proposed_path}  [💡 保存時に差分学習候補を抽出]")
    print(f"Ctrl+C で停止")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止しました")


if __name__ == "__main__":
    main()
