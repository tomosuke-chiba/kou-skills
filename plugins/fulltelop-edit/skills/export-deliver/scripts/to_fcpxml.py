#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""to_fcpxml.py — koetsu.json + 元動画 から FCPXML (v1.10) を出力

Final Cut Pro でテロップ込みのプロジェクトを開けるようにする。
テロップは Title 要素・白＋黒ドロップシャドウ・縦中央 y=3.75（インチ的単位）。
"""
import argparse, json, re, subprocess, sys, urllib.parse
from pathlib import Path

FFPROBE = "ffprobe"


def probe_duration(video):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", video],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def rt(sec):
    """秒→FCPXMLタイムコード（3000分母）"""
    return f"{int(round(sec * 3000))}/3000s"


def file_url(path):
    p = str(Path(path).resolve())
    return "file://" + urllib.parse.quote(p)


def make_title(local_id, offset_s, dur_s, text):
    """1テロップ分の <title> 要素"""
    ts_id = f"ts{local_id}"
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_name = safe.replace("\n", " ")
    return (
        f'    <title ref="r3" lane="1" offset="{rt(offset_s)}" '
        f'name="{safe_name}" start="0s" duration="{rt(dur_s)}">\n'
        f'      <param name="配置" key="9999/10199/10201/2/354/1002961760/401" value="1 (水平方向に中央揃え)"/>\n'
        f'      <param name="サイズ" key="9999/10199/10201/5/10203/3" value="31"/>\n'
        f'      <text><text-style ref="{ts_id}">{safe}</text-style></text>\n'
        f'      <text-style-def id="{ts_id}">\n'
        f'        <text-style font="Noto Sans JP" fontSize="31" fontFace="ExtraBold" '
        f'fontColor="1 1 1 1" bold="1" shadowColor="0 0 0 1" shadowOffset="5 315" '
        f'shadowBlurRadius="10.08" alignment="center" lineSpacing="-7"/>\n'
        f'      </text-style-def>\n'
        f'      <adjust-transform position="0 3.75"/>\n'
        f'    </title>\n'
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("koetsu")
    ap.add_argument("--video", required=True, help="元動画パス（メディア参照に使う）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=2160)
    ap.add_argument("--height", type=int, default=3840)
    args = ap.parse_args()

    d = json.loads(Path(args.koetsu).read_text(encoding="utf-8"))
    src_dur = probe_duration(args.video)
    src_url = file_url(args.video)
    stem = Path(args.video).stem

    # spine の <asset-clip> は単一・テロップは lane=1 の <title>
    titles = ""
    for ti, it in enumerate(d["items"]):
        a, b = float(it["start"]), float(it["end"])
        titles += make_title(ti, a, b - a, it["text"])

    fcpxml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.10">
  <resources>
    <format id="r1" frameDuration="100/3000s" width="{args.width}" height="{args.height}" colorSpace="1-1-1 (Rec. 709)"/>
    <asset id="r2" name="{stem}" start="0s" duration="{rt(src_dur)}" hasVideo="1" format="r1" hasAudio="1" videoSources="1" audioSources="1" audioChannels="2" audioRate="48000">
      <media-rep kind="original-media" src="{src_url}"/>
    </asset>
    <effect id="r3" name="カスタム" uid=".../Titles.localized/Build In:Out.localized/Custom.localized/Custom.moti"/>
  </resources>
  <library>
    <event name="{stem}">
      <project name="{stem}_テロップ付き">
        <sequence format="r1" duration="{rt(src_dur)}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">
          <spine>
            <asset-clip ref="r2" offset="0s" name="{stem}" start="0s" duration="{rt(src_dur)}" tcFormat="NDF" audioRole="dialogue">
{titles}            </asset-clip>
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
'''
    # Python 3.9 互換のため open で書く
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(fcpxml)
    print(f"FCPXML written: {args.out}  ({len(d['items'])} titles, {src_dur:.1f}s)")


if __name__ == "__main__":
    main()
