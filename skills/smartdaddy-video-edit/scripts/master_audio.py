"""CapCut에서 내보낸 최종 영상의 목소리 크기를 영상 전체 기준으로 고르게 맞춥니다(영상 화면은 다시 압축하지 않음).

CapCut '음량 정규화'는 클립마다 따로 계산해서, 클립이 바뀔 때 목소리가 커졌다 작아졌다 한다.
이 도구는 클립 정규화를 끄고 내보낸 영상 하나를 받아서
  1) 말 덩어리(쉼으로 나뉜 구간)마다 크기를 재고, 전체 가운데 값에 맞춰 덩어리 단위로 소리를 올리고 내린다
     (덩어리 안의 강약은 그대로, 바꾸는 폭은 --max-db 까지, 바꾸는 정도는 --strength)
  2) 영상 전체를 유튜브 기준 크기(-14 LUFS, 최대 -1.5 dBTP)로 맞춘다(loudnorm 두 번 측정, 선형 모드)
결과: 화면은 그대로 복사한 새 MP4(+ --wav 이면 CapCut 오디오 교체용 WAV), 고르기 전·후 수치 보고.

사용 예:
  python master_audio.py 최종.mp4 --out 최종_음량.mp4
  python master_audio.py 최종.mp4 --out 최종_음량.mp4 --wav --target -14
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

FR = 0.01           # 분석 프레임(초)
SR = 48000


def frames_db(mono):
    hop = int(SR * FR)
    n = len(mono) // hop
    return 10 * np.log10(np.mean(mono[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)


def phrases(db, sp, min_gap=0.12):
    """말소리 프레임 덩어리 [(시작 프레임, 끝 프레임)] — min_gap 초보다 짧은 쉼은 이어 본다."""
    v = db > sp
    idx = np.flatnonzero(v)
    if not len(idx):
        return []
    out, s, prev = [], idx[0], idx[0]
    for i in idx[1:]:
        if (i - prev) * FR > min_gap:
            out.append((s, prev + 1))
            s = i
        prev = i
    out.append((s, prev + 1))
    return [(a, b) for a, b in out if (b - a) * FR >= 0.15]


def levels(db, sp, ph, ctx=0.4):
    """덩어리마다 말소리 프레임의 평균 크기(dB). 짧은 덩어리는 앞뒤 ctx 초 말소리까지 같이 잰다."""
    e, v, c = 10 ** (db / 10), db > sp, int(ctx / FR)
    out = []
    for a, b in ph:
        lo, hi = max(0, a - c), min(len(db), b + c)
        m = v[lo:hi]
        out.append(10 * np.log10(e[lo:hi][m].mean() + 1e-12))
    return np.array(out)


def spread(db, sp):
    """보고용: 말 덩어리 크기의 퍼짐(표준편차·10~90% 폭)과 이웃 덩어리 사이 크기 차이."""
    ph = [(a, b) for a, b in phrases(db, sp) if (b - a) * FR >= 0.6]
    lv = levels(db, sp, ph, ctx=0.0)
    j = np.abs(np.diff(lv))
    return dict(phrases=len(ph), sd=round(float(lv.std()), 2), p10_90=round(float(np.percentile(lv, 90) - np.percentile(lv, 10)), 2),
                jump_med=round(float(np.median(j)), 2), jump_p90=round(float(np.percentile(j, 90)), 2), jump_max=round(float(j.max()), 2))


def level_gain(db, sp, strength, max_db, window=1.0, ramp=0.04, hold_silence=0.5):
    """프레임마다 곱할 이득(dB). 덩어리 안은 한 값, 쉼에서 이웃 값으로 이어 주고 긴 쉼은 올리지 않는다.
    덩어리 크기는 앞뒤 window 초 말소리와 함께 잰다: 문장 끝이 작아지는 말투는 두고, 문장·클립끼리의 차이만 메운다."""
    ph = phrases(db, sp)
    lv = levels(db, sp, ph, ctx=window)
    target = float(np.median(lv))
    g = np.clip((target - lv) * strength, -max_db, max_db)
    n = len(db)
    gain = np.zeros(n)
    centers = np.array([(a + b) / 2 for a, b in ph])
    gain[:] = np.interp(np.arange(n), centers, g)           # 쉼은 이웃 덩어리 이득을 잇는다
    r = int(ramp / FR)
    for (a, b), gi in zip(ph, g):                             # 덩어리 안은 한 값(강약 보존), 가장자리 ramp 만 이어 붙임
        gain[a:b] = gi
    for (a0, b0), (a1, b1), g0, g1 in zip(ph, ph[1:], g, g[1:]):
        gap = a1 - b0
        if gap * FR > hold_silence:                           # 긴 쉼: 잡음을 키우지 않게 0 이하로만
            gain[b0 + r:a1 - r] = np.minimum(gain[b0 + r:a1 - r], 0)
    k = np.ones(max(1, r)) / max(1, r)                        # 계단을 부드럽게
    return np.convolve(gain, k, mode='same'), target, ph


def measure(path, target, tp, lra):
    p = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-af',
                        f'loudnorm=I={target}:TP={tp}:LRA={lra}:print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True)
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', p.stderr, re.S)
    if not m:
        C.die('loudnorm 측정 실패:\n' + p.stderr[-1500:])
    return json.loads(m.group(0))


def main():
    C.setup_console()
    C.need_ffmpeg()
    ap = argparse.ArgumentParser(description='최종 영상 목소리 크기를 전체 기준으로 고르게 맞춤')
    ap.add_argument('video', help='CapCut에서 내보낸 최종 영상(클립별 음량 정규화는 끄고 내보냄)')
    ap.add_argument('--out', required=True, help='새 MP4 경로(화면은 복사)')
    ap.add_argument('--wav', action='store_true', help='CapCut 오디오 교체용 48kHz WAV도 같이 저장')
    ap.add_argument('--target', type=float, default=-14.0, help='전체 크기(LUFS). 유튜브 기준 -14')
    ap.add_argument('--tp', type=float, default=-1.5, help='최대 순간 크기(dBTP)')
    ap.add_argument('--lra', type=float, default=11.0)
    ap.add_argument('--strength', type=float, default=0.8, help='덩어리 크기 차이를 얼마나 메울지(0~1)')
    ap.add_argument('--max-db', type=float, default=6.0, help='덩어리마다 올리고 내리는 최대 폭(dB)')
    ap.add_argument('--window', type=float, default=1.0, help='덩어리 크기를 잴 때 함께 보는 앞뒤 말소리(초)')
    ap.add_argument('--speech-db', type=float, default=18.0, help='말소리 기준: 바닥 잡음 + 이 값(dB)')
    a = ap.parse_args()

    src, out = Path(a.video).resolve(), Path(a.out).resolve()
    if out == src:
        C.die('--out 은 원본과 다른 경로여야 합니다(원본을 덮어쓰지 않음).')
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / 'raw.wav'
        C.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-vn', '-ac', '2', '-ar', str(SR), '-c:a', 'pcm_f32le', raw])
        x, _ = sf.read(raw, dtype='float32', always_2d=True)
        db = frames_db(x.mean(1))
        floor = float(np.percentile(db, 10))
        sp = floor + a.speech_db
        before = spread(db, sp)

        gdb, target, ph = level_gain(db, sp, a.strength, a.max_db, a.window)
        t_fr = (np.arange(len(gdb)) + 0.5) * FR
        g = 10 ** (np.interp(np.arange(len(x)) / SR, t_fr, gdb) / 20)
        lev = Path(td) / 'leveled.wav'
        sf.write(lev, (x * g[:, None]).astype('float32'), SR, subtype='FLOAT')
        mid = spread(frames_db((x * g[:, None]).mean(1)), sp + float(np.median(gdb)))

        m = measure(lev, a.target, a.tp, a.lra)
        ln = (f"loudnorm=I={a.target}:TP={a.tp}:LRA={a.lra}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
        fin = Path(td) / 'final.wav'
        C.run(['ffmpeg', '-y', '-v', 'error', '-i', lev, '-af', ln, '-ar', str(SR), '-c:a', 'pcm_s24le', fin])
        after_m = measure(fin, a.target, a.tp, a.lra)

        out.parent.mkdir(parents=True, exist_ok=True)
        C.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-i', fin, '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
               '-c:a', 'aac', '-b:a', '256k', '-ar', str(SR), '-movflags', '+faststart', '-shortest', out])
        if a.wav:
            w = out.with_suffix('.wav')
            C.run(['ffmpeg', '-y', '-v', 'error', '-i', fin, '-c:a', 'pcm_s24le', w])

    src_m = measure(src, a.target, a.tp, a.lra)
    gm = np.array([gdb[(p0 + p1) // 2] for p0, p1 in ph])
    print(f'말 덩어리 {len(ph)}개 · 덩어리 이득 {gm.min():+.1f} ~ {gm.max():+.1f}dB (중간 {np.median(gm):+.1f}) · 세기 {a.strength}')
    print(f"말 덩어리 크기 퍼짐  전: 표준편차 {before['sd']}dB · 10~90% 폭 {before['p10_90']}dB · 이웃 차이 중간 {before['jump_med']} / 90% {before['jump_p90']} / 최대 {before['jump_max']}dB")
    print(f"                    후: 표준편차 {mid['sd']}dB · 10~90% 폭 {mid['p10_90']}dB · 이웃 차이 중간 {mid['jump_med']} / 90% {mid['jump_p90']} / 최대 {mid['jump_max']}dB")
    print(f"전체 크기  전: {src_m['input_i']} LUFS · 최대 {src_m['input_tp']} dBTP · 범위 {src_m['input_lra']} LU")
    print(f"          후: {after_m['input_i']} LUFS · 최대 {after_m['input_tp']} dBTP · 범위 {after_m['input_lra']} LU (목표 {a.target} LUFS / {a.tp} dBTP)")
    print(f'  {out}' + (f'\n  {out.with_suffix(".wav")}' if a.wav else ''))


if __name__ == '__main__':
    main()
