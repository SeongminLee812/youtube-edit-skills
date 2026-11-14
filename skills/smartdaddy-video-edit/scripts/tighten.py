"""컷 계획(plan.json)의 남긴 클립 안팎 쉼을 촘촘하게 줄입니다(원본·plan.json은 읽기만 함, 받아쓰기 없음).

cut_plan.py 는 1.5초 넘는 쉼만 0.6초로 줄인다(스마트대디 기본). 원고를 보며 원테이크로 찍은 토킹헤드는 문장 사이·안의
짧은 쉼이 쌓여 늘어진다. 이 도구는 소리 크기(10ms 프레임)만으로 쉼을 찾아 클립을 나눈다.
  - 말소리: 바닥 잡음 + --speech-db(기본 18dB)보다 큰 프레임
  - 쉼: 말소리가 --gap(기본 0.25초) 넘게 없는 구간. 앞말 끝 뒤 --keep-out(0.08초), 뒷말 앞 --keep-in(0.07초)만 남긴다
  - 말 끝 꼬리음: 쉼은 소리가 바닥 + --tail-db(기본 8dB) 아래로 0.03초 내려간 뒤부터 센다("~요", "~니다"가 잘리지 않게)
  - 클립 낱말(words)을 가로질러 자르지 않는다. 쉼까지 늘어 붙은 낱말(받아쓰기가 첫 낱말을 쉼 앞부터 찍은 것)은 무시한다
  - --cut 시작-끝 / --cut-file 재테이크판독.json 으로 지울 구간을 함께 뺄 수 있다(confidence low 는 뺀다)
결과: plan.json 과 같은 형식의 새 컷 계획. 클립이 쉼마다 나뉘고, removed 에 '긴 쉼 줄임'(사람 지정은 '사람 지정 컷')을 더한다.

사용 예:
  python tighten.py 편집/02_cut/plan_v2.json 편집/02_cut/audio16k.wav --out 편집/02_cut/plan_tight.json
  python tighten.py ... --cut-file 편집/03_review/retake_review2.json --gap 0.25
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

FR = 0.01           # 프레임(초)


def frames_db(x, sr):
    hop = int(sr * FR)
    n = len(x) // hop
    rms = np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms)


def stretched(w):
    """쉼까지 늘어 붙은 낱말(받아쓰기 시각이 밀림): 글자당 0.2초 + 0.35초보다 길다."""
    return (w[1] - w[0]) > 0.2 * max(1, len(C.norm_text(w[2]))) + 0.35


def anchor(w):
    return w[1] - 0.15 if stretched(w) else (w[0] + w[1]) / 2


def subtract(spans, cuts):
    out = []
    for a, b in spans:
        cur = [(a, b)]
        for c0, c1 in cuts:
            nxt = []
            for x0, x1 in cur:
                if c1 <= x0 or c0 >= x1:
                    nxt.append((x0, x1))
                    continue
                if c0 > x0:
                    nxt.append((x0, c0))
                if c1 < x1:
                    nxt.append((c1, x1))
            cur = nxt
        out += cur
    return [(a, b) for a, b in out if b - a > 0.04]


def pauses(db, i0, i1, sp, tl, gap, keep_out, keep_in, words):
    """[i0, i1) 프레임 안에서 줄일 쉼 구간(초) 목록. 클립 앞뒤 가장자리 쉼도 포함."""
    v = db[i0:i1] > sp
    if not v.any():
        return []
    n = len(v)
    quiet = db[i0:i1] < tl
    runs, k = [], 0
    while k < n:
        j = k
        while j < n and v[j] == v[k]:
            j += 1
        if not v[k]:
            runs.append((k, j))
        k = j
    cuts = []
    for p0, p1 in runs:
        edge_lead, edge_tail = p0 == 0, p1 == n
        if (p1 - p0) * FR < (gap if not (edge_lead or edge_tail) else keep_in + 0.05):
            continue
        # 꼬리음은 말 끝 뒤 최대 0.25초, 뒷말 들숨·첫소리는 최대 0.15초까지만 지킨다(릴스 규칙: 문장 끝 +0.28초 이내).
        # 그 너머의 숨소리처럼 바닥보다 크지만 말이 아닌 소리는 쉼으로 본다.
        t_end = p0                              # 앞말 꼬리음이 끝나는 곳
        if not edge_lead:
            lim = min(p1, p0 + 25)
            while t_end < lim and not quiet[t_end:t_end + 3].all():
                t_end += 1
        t_on = p1                               # 뒷말이 올라오기 시작하는 곳
        if not edge_tail:
            lim = max(t_end, p1 - 15)
            while t_on > lim and not quiet[t_on - 3:t_on].all():
                t_on -= 1
        c0 = (i0 + t_end) * FR + (0 if edge_lead else keep_out)
        c1 = (i0 + t_on) * FR - (0 if edge_tail else keep_in)
        for w in words:                          # 낱말을 가로질러 자르지 않는다
            if stretched(w):
                continue
            w0, w1 = w[0] + 0.03, w[1] - 0.03
            if w1 <= c0 or w0 >= c1:
                continue
            if w0 <= c0:
                c0 = w[1] + 0.02
            else:
                c1 = w[0] - 0.02
        if c1 - c0 >= 0.05:
            cuts.append((round(c0, 3), round(c1, 3)))
    return cuts


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='남긴 클립의 쉼을 촘촘하게 줄인 새 컷 계획')
    ap.add_argument('plan')
    ap.add_argument('wav', help='16kHz 모노(컷 계획 폴더의 audio16k.wav)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--gap', type=float, default=0.25, help='이보다 긴 쉼을 줄인다(초)')
    ap.add_argument('--keep-out', type=float, default=0.08, help='앞말 끝 뒤에 남길 쉼(초)')
    ap.add_argument('--keep-in', type=float, default=0.07, help='뒷말 앞에 남길 쉼(초)')
    ap.add_argument('--speech-db', type=float, default=18.0, help='말소리 기준: 바닥 잡음 + 이 값(dB)')
    ap.add_argument('--tail-db', type=float, default=8.0, help='꼬리음 끝 기준: 바닥 잡음 + 이 값(dB)')
    ap.add_argument('--cut', action='append', default=[], help='함께 지울 원본 구간 "시작-끝"(초)')
    ap.add_argument('--cut-file', help='재테이크 판독 JSON(cut 또는 cut_adjusted, confidence low 제외)')
    ap.add_argument('--words', help='전체 받아쓰기 낱말(words.json 또는 words_script.json). 주면 낱말 없는 조각 판정에 함께 쓴다')
    ap.add_argument('--max-wordless', type=float, default=2.0,
                    help='클립·전체 받아쓰기 어디에도 낱말이 없는 조각은 이 길이(초) 미만이면 말 아닌 소리로 보고 뺀다')
    ap.add_argument('--keep', action='append', default=[],
                    help='자르지 않을 원본 구간 "시작-끝"(초). 쉼 줄이기·말 없는 조각 빼기·사람 지정 컷보다 앞선다')
    ap.add_argument('--chapter-pause', action='append', default=[],
                    help='챕터 첫 문장의 원본 시작 초(여러 번). 그 앞 쉼을 --chapter-len 초까지 남긴다(챕터 전환 앞 쉼을 남길 때)')
    ap.add_argument('--chapter-len', type=float, default=1.5, help='챕터 첫 문장 앞에 남길 쉼(초)')
    a = ap.parse_args()

    P = C.read_json(a.plan)
    x, sr = sf.read(a.wav)
    if x.ndim > 1:
        x = x.mean(1)
    db = frames_db(x, sr)
    floor = float(np.percentile(db, 10))
    sp, tl = floor + a.speech_db, floor + a.tail_db

    manual = []
    for c in a.cut:
        s0, s1 = (float(v) for v in c.split('-'))
        manual.append((s0, s1, c))
    if a.cut_file:
        for r in C.read_json(a.cut_file):
            if r.get('confidence') == 'low':
                continue
            c = r.get('cut_adjusted') or r['cut']
            manual.append((float(c[0]), float(c[1]), r.get('removed_text', '')[:30]))
    keeps = [tuple(float(v) for v in k.split('-')) for k in a.keep]
    chap = sorted(float(v) for v in a.chapter_pause)
    for t in chap:          # 챕터 첫 문장 앞 쉼: 문장 시작 0.05초 뒤까지를 지키는 구간으로 더한다(쉼 줄이기가 건드리지 않음)
        keeps.append((max(0.0, t - a.chapter_len), t + 0.05))
    keeps = sorted(keeps)
    for t in chap:          # 컷 계획이 그 쉼을 이미 지웠으면, 조용한 곳에 한해 클립 시작을 앞으로 늘려 쉼을 되살린다
        seg = next((sg for sg in P['segments'] if sg['src_in'] <= t + 0.3 and sg['src_out'] > t), None)
        if seg is None:
            print(f'[챕터 쉼] 원본 {t:.2f}초가 남긴 클립 안에 없습니다. 시각을 확인하세요.')
            continue
        i = P['segments'].index(seg)
        lo = max(t - a.chapter_len, P['segments'][i - 1]['src_out'] if i else 0.0)
        new_in = seg['src_in']
        while new_in - FR >= lo and db[int(round((new_in - FR) / FR))] < sp:     # 말소리가 나오면 거기서 멈춘다
            new_in -= FR
        if new_in < seg['src_in'] - 1e-6:
            seg['src_in'] = round(new_in, 3)
        have = t - seg['src_in']
        if have < a.chapter_len - 0.05:
            print(f'[챕터 쉼] 원본 {t:.2f}초 앞 쉼을 {have:.2f}초까지만 남겼습니다(목표 {a.chapter_len:g}초). '
                  f'그 앞에 말소리나 앞 클립이 있습니다. 촬영 때 챕터 사이에 2초쯤 쉬면 됩니다.')
        else:
            print(f'[챕터 쉼] 원본 {t:.2f}초 앞에 쉼 {have:.2f}초를 남겼습니다.')
    manual = sorted((x0, x1, why) for m0, m1, why in manual for x0, x1 in subtract([(m0, m1)], keeps))

    fw = [w for w in C.read_json(a.words) if C.norm_text(w[2])] if a.words else None
    segs, removed, review = [], list(P.get('removed', [])), []
    before = sum(s['src_out'] - s['src_in'] for s in P['segments'])
    for s in P['segments']:
        words = [w for w in (s.get('words') or []) if C.norm_text(w[2])]
        if fw is not None:      # 숨·무음 위에 지어낸 "감사합니다." 낱말은 뺀다(전체 받아쓰기에도 있는 진짜 끝인사는 남긴다)
            words = [w for w in words if not (C.is_hallucination(w[2]) and not any(
                C.norm_text(f[2]) == C.norm_text(w[2]) and f[0] - 1.0 < w[1] and w[0] < f[1] + 1.0 for f in fw))]
        spans = subtract([(s['src_in'], s['src_out'])], [(m[0], m[1]) for m in manual])
        for m0, m1, why in manual:
            if m0 < s['src_out'] and m1 > s['src_in']:
                removed.append(dict(src_in=round(max(m0, s['src_in']), 3), src_out=round(min(m1, s['src_out']), 3),
                                    reason=f'사람 지정 컷({why})', text=''))
        for b0, b1 in spans:
            ws = [w for w in words if b0 <= anchor(w) < b1]
            cuts = pauses(db, int(round(b0 / FR)), int(round(b1 / FR)), sp, tl, a.gap, a.keep_out, a.keep_in, ws)
            cuts = [(round(x0, 3), round(x1, 3)) for x0, x1 in subtract(cuts, keeps)]
            for c0, c1 in cuts:
                removed.append(dict(src_in=c0, src_out=c1, reason='긴 쉼 줄임', text=''))
            for p0, p1 in subtract([(b0, b1)], cuts):
                pw = [w for w in ws if p0 <= anchor(w) < p1]
                loud = float(db[int(p0 / FR):int(p1 / FR)].max()) if p1 - p0 >= FR else -120.0
                kept = any(min(p1, k1) - max(p0, k0) > 0.05 for k0, k1 in keeps)
                if not pw and not kept and p1 - p0 < 0.25 and loud < sp + 3:
                    removed.append(dict(src_in=round(p0, 3), src_out=round(p1, 3), reason='말 없는 짧은 소리', text=''))
                    continue
                # 숨·입소리·웃음, 지운 재테이크 끝에 남은 "습니다" 같은 조각: 클립 받아쓰기에도 전체 받아쓰기에도 낱말이 없다.
                # (클립 받아쓰기가 실패해 비어 있는 긴 말 구간은 전체 받아쓰기 낱말이 있어 남는다)
                speechy = float((db[int(p0 / FR):int(p1 / FR)] > sp).sum()) * FR
                if not pw and not kept and fw is not None and speechy >= 0.25 and \
                        not any(p0 <= anchor(w) < p1 for w in fw if not stretched(w)):
                    # 말소리 크기가 0.25초 넘게 이어지는데 낱말이 없다: 받아쓰기 시각이 1초쯤 밀린 진짜 말일 수 있다
                    # (2026-10-31 끝인사 "감사합니다"가 이렇게 빠졌다). 남기고 사람이 판단하게 한다
                    review.append(dict(src_in=round(p0, 3), src_out=round(p1, 3), words=[], speech=round(speechy, 2)))
                elif not pw and not kept and fw is not None and (p1 - p0 < a.max_wordless or loud < sp) and \
                        not any(p0 <= anchor(w) < p1 for w in fw if not stretched(w)):
                    removed.append(dict(src_in=round(p0, 3), src_out=round(p1, 3), reason='말 없는 소리(낱말 없음)', text=''))
                    # 쉼까지 늘어 붙은 낱말과 겹치면 진짜 말일 수 있다(2026-10-31 '매일' 누락). 사람이 판단하도록 남긴다
                    sw = [w[2].strip() for w in fw if stretched(w) and min(p1, w[1]) - max(p0, w[0]) >= 0.12]
                    if sw:
                        review.append(dict(src_in=round(p0, 3), src_out=round(p1, 3), words=sw))
                    continue
                segs.append(dict(src_in=round(p0, 3), src_out=round(p1, 3),
                                 text=''.join(w[2] for w in pw).strip(), words=pw))
    removed.sort(key=lambda r: r['src_in'])
    after = sum(s['src_out'] - s['src_in'] for s in segs)
    for r in review:                    # 다음 클립이 같은 말로 시작하면 말 더듬기(앞 조각을 지운 것이 맞음)
        nxt = next((s for s in segs if s['src_in'] >= r['src_out'] - 0.01), None)
        head = C.norm_text(nxt['text'])[:8] if nxt else ''
        r['next_text'] = nxt['text'][:30] if nxt else ''
        r['repeat'] = any(C.norm_text(w)[:2] and head.startswith(C.norm_text(w)[:2]) for w in r['words'])
    Q = dict(P)
    Q.update(segments=segs, removed=removed, edited_duration=round(after, 3),
             tighten=dict(source=str(Path(a.plan).name), gap=a.gap, keep_out=a.keep_out, keep_in=a.keep_in,
                          floor_db=round(floor, 1), speech_db=round(sp, 1), tail_db=round(tl, 1),
                          manual_cuts=len(manual), keep=[list(k) for k in keeps], review=review))
    C.write_json(Path(a.out), Q)
    print(f'바닥 잡음 {floor:.0f}dB · 말소리 {sp:.0f}dB · 꼬리음 끝 {tl:.0f}dB')
    print(f'{C.mmss(before)} → {C.mmss(after)} · 클립 {len(P["segments"])} → {len(segs)}개 · 사람 지정 컷 {len(manual)}곳')
    for r in review:
        if 'speech' in r:
            print(f'  [확인 필요] 원본 {r["src_in"]:.2f}-{r["src_out"]:.2f} 말소리 크기 {r["speech"]:.2f}초인데 받아쓰기 낱말이 없어 남김'
                  ' → 숨·웃음·재테이크 조각이면 --cut 시작-끝')
            continue
        mark = '되풀이(지워도 됨)' if r['repeat'] else '확인 필요'
        print(f'  [{mark}] 원본 {r["src_in"]:.2f}-{r["src_out"]:.2f} 뺀 조각에 늘어 붙은 낱말 {r["words"]} · 다음 클립 "{r["next_text"]}"'
              + ('' if r['repeat'] else ' → 진짜 말이면 --keep 시작-끝'))
    print(f'  {a.out}')


if __name__ == '__main__':
    main()
