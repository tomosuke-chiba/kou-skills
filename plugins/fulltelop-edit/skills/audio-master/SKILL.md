---
name: audio-master
description: 整音。loudnorm 2パス測定→線形ゲイン→軽コンプ→真ピーク -1dBFS リミッターで確実に -14LUFS（SNS標準）に当てる。素材の音量がバラついても再現性高く一定。境界12msフェードでクリック除去。無加工モード（声をそのまま渡す iPhone収録のレベリング済み）も対応。整音／LUFS／音量調整／ノイズ除去で発火。
---

# audio-master — 2パス整音 -14LUFS

## やること

### 整音モード（seion）— 既定

1. **loudnorm の1パス目で測定** → integrated LUFS / TP / LRA / threshold
2. **線形ゲイン**で目標 -14LUFS まで持ち上げ（loudnorm の動的補正は使わない＝素材依存で外れる）
3. **軽コンプ**（threshold -18dB / ratio 2.5 / makeup 1）で body を底上げ
4. **真ピークリミッター**（alimiter level=false limit=0.84＝-1.5dBFS）で確実にクリップ回避

```bash
# 1パス目（測定のみ）
ffmpeg -hide_banner -i input.mp4 \
  -af "loudnorm=I=-14:TP=-1.0:print_format=json" \
  -f null - 2>&1 | grep -A20 input_i

# 結果 input_i=-25.8 → gain = -14.0 - (-25.8) = +11.8dB

# 2パス目（適用）
ffmpeg -y -i input.mp4 \
  -af "acompressor=threshold=-18dB:ratio=2.5:attack=10:release=200:makeup=1,volume=+12.4dB,alimiter=level=false:limit=0.84" \
  -c:v copy -c:a aac -b:a 256k output.mp4
```

`+12.4dB` は理論ゲイン +11.8 にリミッター減衰補正 +0.6 を足した値（経験則）。

### 無加工モード（muka）

iPhone 等で収録時にレベリング済みの素材は **声トラックを触らない**（制作実例での確定運用）。境界12msフェードのみ：

```
afade=t=in:st=0:d=0.012,afade=t=out:st={D-0.012}:d=0.012
```

## 「素材の音量がバラついても確実に -14LUFS」

単一パス loudnorm は素材によって ±2dB ズレるので、必ず2パス（測定→適用）。

| 素材タイプ | 結果 |
|---|---|
| iPhone 内蔵マイク（音量低め） | gain +9〜+14dB |
| 別撮りピンマイク（適正音量） | gain +3〜+6dB |
| ノイズ多めの環境音込み | acompressor + afftdn nr=6 |

## ノイズ除去（任意）

afftdn を loudnorm の前段に入れる：

```
[acat]afftdn=nr=6:nf=-25,acompressor=...,volume=...,alimiter=...
```

`nr=6` は控えめ（著者の声を不自然にしない）。`nr=15` 以上は声が痩せるので避ける。

## 別撮り音声と映像の同期（横講座）

カメラMOV＋別撮りm4a の場合、本スキル起動前に `transcribe-words` 系で相互相関を取って同期オフセット（例 +43.451s）を出し、`spec.json` の `audio_sync_offset_s` に書く。本スキルはそのオフセットを apply：

```
ffmpeg -i camera.MOV -ss <offset> -i mic.m4a -map 0:v -map 1:a ...
```

## クリップ事故防止

- リミッターの level=false（自動正規化を切る）が肝。default の level=true だとリミット後に 0dB へ自動正規化される＝フルクリップ
- limit=0.84（≒ -1.5dBFS）で AAC re-encoding の overshoot に余裕

## qc-gate audio との関係

整音後、`qc-gate audio` で：
- max_volume ≤ -1.0dBFS（ピーク事故）
- integrated_lufs ∈ [-15, -13]（目標 -14 ± 1）
- 長すぎる無音 < 2.0秒

を必ず通す。
