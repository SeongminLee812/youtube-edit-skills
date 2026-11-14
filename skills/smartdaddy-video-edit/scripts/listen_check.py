"""컷 계획대로 이어 붙인 편집본 음성을 whisper.cpp(Apple GPU)로 다시 받아써서 듣는 대신 검사합니다(원본은 읽기만 함).

조립·CapCut 없이 컷 계획만으로 확인한다. 9~10분 편집본이 M1 Pro에서 1분 안팎이다.
  - 받아쓰기가 비는 구간: 말이 아닌 소리(숨·입소리·웃음)나 지운 재테이크 끝 조각이 남은 곳
  - 바로 이어지는 같은 말: 남은 재테이크·말 더듬기 후보(앞 줄의 끝 3글자 이상이 다음 줄 첫머리와 같음)
결과(--out 폴더): <이름>.wav(편집본 음성), <이름>_map.json(편집 초 ↔ 원본 초), <이름>.txt(줄마다 편집 초·원본 초·글), 보고 출력

사용 예:
  python listen_check.py 편집/02_cut/plan_tight.json 편집/02_cut/audio16k.wav --out 편집/04_check --name tight
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

MODEL = Path.home() / '.codex' / 'models' / 'whisper' / 'ggml-small.bin'


def sec(ts):
    h, m, s = ts.split(':')
    s, ms = s.split(',')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='편집본 음성 다시 받아쓰기 검사(whisper.cpp)')
    ap.add_argument('plan')
    ap.add_argument('wav', help='16kHz 모노(컷 계획 폴더의 audio16k.wav)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--name', default='listen')
    ap.add_argument('--model', default=str(MODEL), help='whisper.cpp ggml 모델')
    ap.add_argument('--prompt', default='', help='고유명사 힌트')
    ap.add_argument('--gap', type=float, default=1.0, help='받아쓰기가 이보다 길게 비면 보고(초)')
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    x, sr = sf.read(a.wav)
    if x.ndim > 1:
        x = x.mean(1)
    segs = C.read_json(a.plan)['segments']
    parts, mp, t = [], [], 0.0
    for s in segs:
        seg = x[int(s['src_in'] * sr):int(s['src_out'] * sr)].copy()
        f = min(len(seg) // 2, int(0.004 * sr))              # 이음매 딸깍 방지 4ms 페이드
        if f > 0:
            seg[:f] *= np.linspace(0, 1, f)
            seg[-f:] *= np.linspace(1, 0, f)
        parts.append(seg)
        mp.append([round(t, 3), s['src_in'], s['src_out']])
        t += len(seg) / sr
    wav = out / f'{a.name}.wav'
    sf.write(wav, np.concatenate(parts), sr)
    C.write_json(out / f'{a.name}_map.json', mp, compact=True)
    cmd = ['whisper-cli', '-m', a.model, '-l', 'ko', '-f', str(wav), '-oj', '-of', str(out / f'{a.name}_ws'), '-t', '6']
    if a.prompt:
        cmd += ['--prompt', a.prompt]
    subprocess.run(cmd, check=True, capture_output=True)
    tr = json.loads((out / f'{a.name}_ws.json').read_text('utf-8'))['transcription']

    def src(e):
        for e0, s0, s1 in reversed(mp):
            if e >= e0:
                return round(s0 + (e - e0), 2)
        return 0.0
    rows = [(sec(r['timestamps']['from']), sec(r['timestamps']['to']), r['text'].strip()) for r in tr]
    (out / f'{a.name}.txt').write_text('\n'.join(f'{e0:6.1f}-{e1:6.1f} [src {src(e0):7.2f}] {txt}' for e0, e1, txt in rows),
                                       'utf-8')
    print(f'편집본 {C.mmss(t)} · 받아쓰기 {len(rows)}줄 → {out / (a.name + ".txt")}')
    prev_end, prev = 0.0, ''
    for e0, e1, txt in rows:
        if e0 - prev_end > a.gap:
            print(f'  [빈 구간] 편집 {prev_end:.1f}-{e0:.1f}({e0 - prev_end:.1f}초) · 원본 {src(prev_end):.2f}~{src(e0):.2f}')
        p, q = C.norm_text(prev), C.norm_text(txt)
        for k in range(min(len(p), len(q), 12), 2, -1):
            if p[-k:] == q[:k]:
                print(f'  [이어진 같은 말] 편집 {e0:.1f} · 원본 {src(e0):.2f} · "{prev[-20:]}" → "{txt[:20]}"')
                break
        prev_end, prev = e1, txt
    if t - prev_end > a.gap:
        print(f'  [빈 구간] 편집 {prev_end:.1f}-{t:.1f}(끝)')


if __name__ == '__main__':
    main()
