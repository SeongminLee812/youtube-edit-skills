"""남긴 클립의 처음·끝이 말소리 한가운데서 잘렸는지 소리 크기로 검사하고, 소리 골까지 늘린 경계를 제안합니다(claude-edit S1-4).
원본 음성과 입력 컷 계획은 읽기만 합니다.

컷 계획(plan.json·plan_tight.json)의 남긴 클립 경계마다 10ms 프레임 소리 크기(dB)를 잰다.
  - 바닥 잡음 = 전체 프레임의 10번째 백분위, 말소리 = 바닥 + --speech-db(18dB), 조용함 = 바닥 + --quiet-db(8dB)
  - 소리 골: 경계 뒤(앞)로 가며 처음 나오는 조용한 프레임, 또는 말소리 아래로 내려간 골의 가장 낮은 곳이 조용함 + --valley-db(6dB) 이하인 곳
  - [끝 잘림] 경계 앞 3프레임·뒤 3프레임 가운데값이 모두 말소리이고, 경계 뒤 소리 골까지 말소리가 --min-speech(0.15초) 이상
      → 새 끝 = 경계 뒤 첫 소리 골. 다음 클립 시작 0.02초 앞을 넘지 않는다. 골이 --max-ext(0.8초) 안에 없으면 [끝 잘림·골 없음](제안 없음)
  - [꼬리 짧음] 같은 조건인데 경계 뒤 말소리가 0.15초 미만(말 끝 꼬리음이 조금 잘림). 제안만 하고 --tail 이면 적용
  - [처음 잘림] 클립 시작이 말소리 한가운데. 앞 소리 골(늘려 살리기)과 뒤 소리 골(남은 조각 빼기)을 함께 적는다.
      --starts extend 면 앞 골로 늘리고, --starts trim 이면 뒤 골로 미룬다. 기본은 제안만 한다
      (시험한 plan_v2의 처음 잘림 8곳은 모두 지운 테이크의 끝 조각이 남은 것이어서 컷을 뒤로 미뤄 고쳤다 → 들어 보고 고른다)
  - [이음매 쉼] 사람 지정 컷(removed reason '사람 지정 …') 뒤 이음매의 쉼이 --seam-gap(0.25초)을 넘으면 뒤 클립 시작을 뒷말 첫소리
      --keep-in(0.07초) 앞까지 미룬다. 첫소리는 조용함보다 큰 프레임, 또는 2kHz 위 에너지가 바닥 + --hf-db(15dB)를 2프레임 넘는 곳
      (ㅎ·ㅅ 같은 마찰음은 전체 크기가 작아 이것으로 찾는다). 그래도 넘으면 앞 클립 끝을 꼬리음 끝 + --keep-out(0.08초)로 당긴다
결과(--out 폴더): edge_check.md(사람이 읽는 표), edge_check.json
--apply: [끝 잘림]·[이음매 쉼](+ --tail, --starts extend|trim)을 반영한 새 컷 계획을 쓴다. 기본 이름은 같은 폴더의 <이름>_vN.json(비어 있는 다음 번호),
  --out-plan 으로 정할 수 있다. 입력 컷 계획은 덮어쓰지 않는다. 지운 구간(removed)은 늘린 클립과 겹치지 않게 줄이고,
  manual_fix·edge_check 기록을 더한다. 쓴 뒤 새 컷 계획을 다시 검사해 남은 문제 수를 알린다.
  plan_tight.json에 바로 적용하면 다시 tighten 할 필요가 없다(늘린 구간은 다음 소리 골까지라 새 쉼이 생기지 않는다).

사용 예(프로젝트 루트에서):
  python edge_check.py <편집>/02_cut/plan_tight.json <편집>/02_cut/audio16k.wav --out <편집>/02_cut/edge_check
  python edge_check.py … --apply                                   # → plan_tight_v2.json
  python edge_check.py … --apply --out-plan <편집>/02_cut/plan_edge.json --force
  (<편집>·<화면자료>: 영상 폴더 안 편집·편집/화면자료 — tools/topic_paths.py)
"""
import argparse
import re
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
ROOT = Path(os.environ.get('PROJECT_ROOT') or os.getcwd()).resolve()     # 프로젝트 루트(PROJECT_ROOT 또는 작업 폴더)
ENGINE = Path(__file__).resolve().parents[2] / 'smartdaddy-video-edit' / 'scripts'
sys.path.insert(0, str(ENGINE))
import _common as C  # noqa: E402

FR = 0.01           # 프레임(초)
CONTIG = 0.02       # 두 클립 사이가 이보다 가까우면 이어진 것(컷 없음)
GAP_NEXT = 0.02     # 늘린 경계와 이웃 클립 사이에 남길 틈(초)


# ── 소리 크기 ─────────────────────────────────────────
def frames_db(x, sr):
    hop = int(sr * FR)
    n = len(x) // hop
    rms = np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms)


def frames_hf(x, sr, cutoff=2000.0):
    """프레임마다 cutoff Hz 위 에너지(dB). 프레임 가운데에 맞춘 20ms 해닝 창."""
    hop = int(sr * FR)
    win = 2 * hop
    n = len(x) // hop
    w = np.hanning(win)
    band = np.fft.rfftfreq(win, 1 / sr) >= cutoff
    pad = np.concatenate([np.zeros(hop // 2), x, np.zeros(win)])
    out = np.empty(n)
    for c0 in range(0, n, 8192):
        c1 = min(n, c0 + 8192)
        idx = np.arange(c0, c1)[:, None] * hop + np.arange(win)[None, :]
        S = np.abs(np.fft.rfft(pad[idx] * w, axis=1)) ** 2
        out[c0:c1] = 10 * np.log10(S[:, band].sum(1) / win + 1e-12)
    return out


class Audio:
    def __init__(self, wav, a):
        x, sr = sf.read(str(wav))
        if x.ndim > 1:
            x = x.mean(1)
        self.db = frames_db(x, sr)
        self.hf = frames_hf(x, sr)
        self.n = len(self.db)
        self.floor = float(np.percentile(self.db, 10))
        self.sp = self.floor + a.speech_db
        self.ql = self.floor + a.quiet_db
        self.vl = self.ql + a.valley_db
        self.hf_thr = float(np.percentile(self.hf, 10)) + a.hf_db

    def i(self, t):
        return max(0, min(self.n, int(round(t / FR))))

    def rel(self, v):
        return round(float(v) - self.floor, 1)

    def mid(self, i):
        """경계(프레임 i 앞)가 말소리 한가운데인가 → (판정, 앞 가운데값, 뒤 가운데값)"""
        if i < 3 or i + 3 > self.n:
            return False, 0.0, 0.0
        pre, post = float(np.median(self.db[i - 3:i])), float(np.median(self.db[i:i + 3]))
        return pre >= self.sp and post >= self.sp, pre, post

    def valley_fwd(self, i, lim):
        """i부터 뒤로 가며 첫 소리 골의 프레임(없으면 None)."""
        db, k = self.db, i
        while k < lim:
            if db[k] <= self.ql:
                return k
            if db[k] < self.sp:
                best, j = k, k
                while j < lim and db[j] < self.sp:
                    if db[j] < db[best]:
                        best = j
                    if db[j] <= self.ql:
                        return j
                    j += 1
                if db[best] <= self.vl:
                    return best
                k = j
                continue
            k += 1
        return None

    def valley_bwd(self, i, lim):
        """i-1부터 앞으로 가며 첫 소리 골. 돌려주는 값은 새 시작 프레임(골 다음 프레임 또는 골 가장 낮은 곳)."""
        db, k = self.db, i - 1
        while k >= lim:
            if db[k] <= self.ql:
                return k + 1
            if db[k] < self.sp:
                best, j = k, k
                while j >= lim and db[j] < self.sp:
                    if db[j] < db[best]:
                        best = j
                    if db[j] <= self.ql:
                        return j + 1
                    j -= 1
                if db[best] <= self.vl:
                    return best
                k = j
                continue
            k -= 1
        return None

    def speech(self, i0, i1):
        return float((self.db[i0:i1] > self.sp).sum()) * FR

    def onset(self, i0, i1):
        """[i0, i1)에서 뒷말 첫소리 프레임: 조용함보다 크거나, 2kHz 위 에너지가 2프레임 이어 기준을 넘는 곳."""
        for k in range(i0, i1):
            if self.db[k] > self.ql or (self.hf[k] > self.hf_thr and k + 1 < self.n and self.hf[k + 1] > self.hf_thr):
                return k
        return None

    def tail_end(self, i0, i1):
        """[i0, i1)에서 마지막으로 조용함보다 큰 프레임 다음(꼬리음 끝)."""
        for k in range(i1 - 1, i0 - 1, -1):
            if self.db[k] > self.ql:
                return k + 1
        return i0


# ── 컷 계획 ───────────────────────────────────────────
def load_plan(p):
    P = C.read_json(p)
    if isinstance(P, list):
        P = dict(segments=P)
    segs = [dict(s) for s in P['segments'] if float(s['src_out']) - float(s['src_in']) > 0.04]
    segs.sort(key=lambda s: s['src_in'])
    return P, segs


def human_seam(removed, b, a):
    return [r for r in removed if str(r.get('reason', '')).startswith('사람 지정')
            and r['src_in'] >= b - 0.011 and r['src_out'] <= a + 0.011]


def snippet(s, head):
    t = (s.get('text') or '').strip()
    return (t[:18] + '…' if len(t) > 18 else t) if head else ('…' + t[-18:] if len(t) > 18 else t)


def detect(A, segs, removed, a):
    """경계 문제 목록. 각 항목: kind, k(클립 번호), side, src, new, alt, edit, …"""
    edit_at, t = [], 0.0
    for s in segs:
        edit_at.append(t)
        t += s['src_out'] - s['src_in']
    me = int(round(a.max_ext / FR))
    rows = []
    for k, s in enumerate(segs):
        nxt = segs[k + 1] if k + 1 < len(segs) else None
        prv = segs[k - 1] if k else None
        # ── 끝 ──
        b = s['src_out']
        if not (nxt and nxt['src_in'] - b < CONTIG):
            i = A.i(b)
            hit, pre, post = A.mid(i)
            if hit:
                lim = min(i + me, A.i(nxt['src_in'] - GAP_NEXT) if nxt else A.n)
                v = A.valley_fwd(i, lim)
                spa = A.speech(i, v if v is not None else lim)
                if v is None:
                    kind = '끝 잘림·골 없음'
                elif spa >= a.min_speech:
                    kind = '끝 잘림'
                else:
                    kind = '꼬리 짧음'
                rows.append(dict(kind=kind, k=k, side='end', src=round(b, 3),
                                 new=round(v * FR, 3) if v is not None and v * FR > b + 0.005 else None,
                                 edit=round(edit_at[k] + b - s['src_in'], 2), pre=A.rel(pre), post=A.rel(post),
                                 speech_after=round(spa, 2), text=snippet(s, False),
                                 next_text=snippet(nxt, True) if nxt else ''))
        # ── 처음 ──
        a0 = s['src_in']
        if not (prv and a0 - prv['src_out'] < CONTIG):
            i = A.i(a0)
            hit, pre, post = A.mid(i)
            if hit:
                lo = max(i - me, A.i(prv['src_out'] + GAP_NEXT) if prv else 0)
                v_ext = A.valley_bwd(i, lo)
                v_trim = A.valley_fwd(i, min(i + me, A.i(s['src_out']) - 5))
                rows.append(dict(kind='처음 잘림', k=k, side='start', src=round(a0, 3),
                                 new=round(v_ext * FR, 3) if v_ext is not None and v_ext * FR < a0 - 0.005 else None,
                                 alt=round(v_trim * FR, 3) if v_trim is not None and v_trim * FR > a0 + 0.005 else None,
                                 edit=round(edit_at[k], 2), pre=A.rel(pre), post=A.rel(post),
                                 text=snippet(s, True), prev_text=snippet(prv, False) if prv else ''))
        # ── 사람 지정 컷 뒤 이음매 쉼 ──
        if nxt and nxt['src_in'] - s['src_out'] >= CONTIG and (a.all_seams or human_seam(removed, s['src_out'], nxt['src_in'])):
            ib, ia = A.i(s['src_out']), A.i(nxt['src_in'])
            te = A.tail_end(A.i(s['src_in']), ib)
            on = A.onset(ia, A.i(nxt['src_out']))
            if on is None:
                continue
            trail, lead = (ib - te) * FR, (on - ia) * FR
            if trail + lead <= a.seam_gap + 1e-6:
                continue
            new_a = max(nxt['src_in'], round(on * FR - a.keep_in, 3))
            lead2 = on * FR - new_a
            new_b = None
            if trail + lead2 > a.seam_gap + 1e-6:
                cand = round(te * FR + a.keep_out, 3)
                if cand < s['src_out'] - 0.005 and cand > s['src_in'] + 0.05:
                    new_b = cand
            rows.append(dict(kind='이음매 쉼', k=k, side='seam', src=round(nxt['src_in'], 3),
                             new=new_a if new_a > nxt['src_in'] + 0.005 else None, prev_end=round(s['src_out'], 3),
                             new_prev_end=new_b, pause=round(trail + lead, 2),
                             pause_after=round((trail if new_b is None else new_b - te * FR) + lead2, 2),
                             edit=round(edit_at[k + 1], 2), text=snippet(s, False), next_text=snippet(nxt, True),
                             cuts=[r.get('reason', '') for r in human_seam(removed, s['src_out'], nxt['src_in'])][:2]))
    return rows


def applies(r, a):
    if r['kind'] == '끝 잘림':
        return r['new'] is not None
    if r['kind'] == '꼬리 짧음':
        return a.tail and r['new'] is not None
    if r['kind'] == '처음 잘림':
        return start_target(r, a) is not None
    if r['kind'] == '이음매 쉼':
        return r['new'] is not None or r.get('new_prev_end') is not None
    return False


def start_target(r, a):
    return {'extend': r['new'], 'trim': r.get('alt')}.get(a.starts)


def apply_rows(segs, rows, a):
    S = [dict(s) for s in segs]
    log = []
    for r in rows:
        if not applies(r, a):
            continue
        s = S[r['k']]
        if r['side'] == 'end':
            log.append(f'{s["src_out"]:.2f}→{r["new"]:.2f}')
            s['src_out'] = r['new']
        elif r['side'] == 'start':
            log.append(f'처음 {s["src_in"]:.2f}→{start_target(r, a):.2f}')
            s['src_in'] = start_target(r, a)
        else:
            n = S[r['k'] + 1]
            if r['new'] is not None:
                log.append(f'이음매 {n["src_in"]:.2f}→{r["new"]:.2f}')
                n['src_in'] = r['new']
            if r.get('new_prev_end') is not None:
                log.append(f'이음매 앞 끝 {s["src_out"]:.2f}→{r["new_prev_end"]:.2f}')
                s['src_out'] = r['new_prev_end']
    for k in range(len(S) - 1):         # 겹침 방지(앞 끝을 늘리고 뒤 처음도 늘린 경우)
        if S[k]['src_out'] > S[k + 1]['src_in'] - 0.005:
            S[k]['src_out'] = round(S[k + 1]['src_in'] - 0.005, 3)
    return [s for s in S if s['src_out'] - s['src_in'] > 0.04], log


def trim_removed(removed, segs):
    out = []
    for r in removed:
        pieces = [(r['src_in'], r['src_out'])]
        for s in segs:
            nxt = []
            for x0, x1 in pieces:
                if s['src_out'] <= x0 or s['src_in'] >= x1:
                    nxt.append((x0, x1))
                    continue
                if s['src_in'] > x0:
                    nxt.append((x0, s['src_in']))
                if s['src_out'] < x1:
                    nxt.append((s['src_out'], x1))
            pieces = nxt
        for x0, x1 in pieces:
            if x1 - x0 > 0.01:
                q = dict(r)
                q.update(src_in=round(x0, 3), src_out=round(x1, 3))
                out.append(q)
    return out


def next_name(plan_path):
    stem = re.sub(r'_v\d+$', '', plan_path.stem)
    n = 2
    while (plan_path.parent / f'{stem}_v{n}.json').exists():
        n += 1
    return plan_path.parent / f'{stem}_v{n}.json'


def counts(rows, a):
    c = {}
    for r in rows:
        c[r['kind']] = c.get(r['kind'], 0) + 1
    return c


def fmt_row(r, a):
    if r['side'] == 'end':
        what = f'끝 {r["src"]:.2f}'
        prop = f'끝 → {r["new"]:.2f} (+{r["new"] - r["src"]:.2f}초)' if r['new'] is not None else '골 없음 — 들어 보고 판단'
        snd = f'{r["pre"]:.0f}/{r["post"]:.0f} · 경계 뒤 말소리 {r["speech_after"]:.2f}초'
        txt = f'"{r["text"]}" ‖ "{r["next_text"]}"'
    elif r['side'] == 'start':
        what = f'처음 {r["src"]:.2f}'
        ext = f'살리기 {r["new"]:.2f}' if r['new'] is not None else '살리기 골 없음'
        trim = f'조각 빼기 {r["alt"]:.2f}' if r.get('alt') is not None else '조각 빼기 골 없음'
        prop = f'{ext} / {trim}'
        snd = f'{r["pre"]:.0f}/{r["post"]:.0f}'
        txt = f'"{r["prev_text"]}" ‖ "{r["text"]}"'
    else:
        what = f'이음매 {r["prev_end"]:.2f}‖{r["src"]:.2f}'
        parts = []
        if r['new'] is not None:
            parts.append(f'뒤 처음 → {r["new"]:.2f}')
        if r.get('new_prev_end') is not None:
            parts.append(f'앞 끝 → {r["new_prev_end"]:.2f}')
        prop = ' · '.join(parts) + f' (쉼 {r["pause"]:.2f} → {r["pause_after"]:.2f}초)'
        snd = f'쉼 {r["pause"]:.2f}초'
        txt = f'"{r["text"]}" ‖ "{r["next_text"]}"'
    return what, prop, snd, txt


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='남긴 클립 경계의 말 잘림 검사·소리 골까지 늘리기')
    ap.add_argument('plan', help='컷 계획(plan.json · plan_tight.json 등)')
    ap.add_argument('wav', help='16kHz 모노(컷 계획 폴더의 audio16k.wav)')
    ap.add_argument('--out', required=True, help='보고서 폴더(edge_check.md · edge_check.json)')
    ap.add_argument('--apply', action='store_true', help='[끝 잘림]·[이음매 쉼]을 반영한 새 컷 계획을 쓴다')
    ap.add_argument('--out-plan', help='새 컷 계획 경로(기본: 같은 폴더 <이름>_vN.json)')
    ap.add_argument('--force', action='store_true', help='--out-plan 파일이 이미 있으면 덮어쓴다(입력 컷 계획은 절대 덮지 않음)')
    ap.add_argument('--tail', action='store_true', help='[꼬리 짧음]도 소리 골까지 늘린다')
    ap.add_argument('--starts', choices=['extend', 'trim'],
                    help='[처음 잘림] 적용: extend = 앞 소리 골까지 늘려 살리기, trim = 뒤 소리 골까지 미뤄 남은 조각 빼기(기본: 제안만)')
    ap.add_argument('--all-seams', action='store_true', help='사람 지정 컷뿐 아니라 모든 이음매의 쉼을 검사')
    ap.add_argument('--speech-db', type=float, default=18.0, help='말소리 기준: 바닥 잡음 + 이 값(dB)')
    ap.add_argument('--quiet-db', type=float, default=8.0, help='조용함 기준: 바닥 잡음 + 이 값(dB)')
    ap.add_argument('--valley-db', type=float, default=6.0, help='소리 골로 인정할 골 바닥: 조용함 + 이 값(dB)')
    ap.add_argument('--hf-db', type=float, default=15.0, help='마찰음 첫소리 기준: 2kHz 위 에너지 바닥 + 이 값(dB)')
    ap.add_argument('--min-speech', type=float, default=0.15, help='경계 뒤 말소리가 이만큼(초) 이어지면 [끝 잘림], 아니면 [꼬리 짧음]')
    ap.add_argument('--max-ext', type=float, default=0.8, help='소리 골을 찾는 최대 거리(초)')
    ap.add_argument('--seam-gap', type=float, default=0.25, help='이음매 쉼이 이보다 길면 줄인다(초)')
    ap.add_argument('--keep-in', type=float, default=0.07, help='뒷말 첫소리 앞에 남길 쉼(초)')
    ap.add_argument('--keep-out', type=float, default=0.08, help='앞말 꼬리음 뒤에 남길 쉼(초)')
    a = ap.parse_args()

    plan_path, wav = Path(a.plan).resolve(), Path(a.wav).resolve()
    for p in (plan_path, wav):
        if not p.exists():
            C.die(f'파일이 없습니다: {p}')
    P, segs = load_plan(plan_path)
    if not segs:
        C.die('컷 계획에 남긴 클립이 없습니다.')
    removed = list(P.get('removed', []))
    A = Audio(wav, a)
    rows = detect(A, segs, removed, a)
    for r in rows:
        r['apply'] = applies(r, a)
    c = counts(rows, a)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    head = dict(plan=plan_path.as_posix(), wav=wav.as_posix(), floor_db=round(A.floor, 1), speech_db=round(A.sp, 1),
                quiet_db=round(A.ql, 1), clips=len(segs), counts=c,
                params=dict(min_speech=a.min_speech, max_ext=a.max_ext, seam_gap=a.seam_gap, keep_in=a.keep_in,
                            keep_out=a.keep_out, tail=a.tail, starts=a.starts, all_seams=a.all_seams))
    plan_out, log, after = None, [], None
    if a.apply:
        plan_out = Path(a.out_plan).resolve() if a.out_plan else next_name(plan_path)
        if plan_out == plan_path:
            C.die('입력 컷 계획을 덮어쓸 수 없습니다. --out-plan 에 다른 이름을 주세요.')
        if plan_out.exists() and not a.force:
            C.die(f'이미 있는 파일입니다(덮어쓰려면 --force): {plan_out}')
        S2, log = apply_rows(segs, rows, a)
        Q = dict(P)
        mf = list(Q.get('manual_fix', []))
        if log:
            mf.append(f'{time.strftime("%Y-%m-%d")} edge_check 경계 고침 {len(log)}곳: ' + ', '.join(log))
        Q.update(segments=S2, removed=sorted(trim_removed(removed, S2), key=lambda r: r['src_in']),
                 edited_duration=round(sum(s['src_out'] - s['src_in'] for s in S2), 3), manual_fix=mf,
                 edge_check=dict(source=plan_path.name, changes=log, report=(out / 'edge_check.json').as_posix(), **head['params']))
        C.write_json(plan_out, Q)
        after = detect(A, S2, Q['removed'], a)
        head.update(plan_out=plan_out.as_posix(), changes=log, after_counts=counts(after, a),
                    after=[r for r in after if r['kind'] in ('끝 잘림', '끝 잘림·골 없음', '이음매 쉼')])
    C.write_json(out / 'edge_check.json', dict(head, rows=rows))

    before_d = sum(s['src_out'] - s['src_in'] for s in segs)
    L = [f'# 경계 검사 · {plan_path.name}', '',
         f'- 바닥 잡음 {A.floor:.0f}dB · 말소리 {A.sp:.0f}dB(바닥+{a.speech_db:.0f}) · 조용함 {A.ql:.0f}dB(바닥+{a.quiet_db:.0f}) · '
         f'클립 {len(segs)}개 · 편집 길이 {C.mmss(before_d)}',
         '- ' + (' · '.join(f'{k} {v}곳' for k, v in c.items()) or '문제 없음'),
         '- 소리 칸: 경계 앞/뒤 3프레임 가운데값(바닥 위 dB). 편집 초는 이 컷 계획 기준(범퍼 없음).',
         '- 적용 규칙: [끝 잘림]·[이음매 쉼]은 --apply 로 반영, [꼬리 짧음]은 --tail, [처음 잘림]은 --starts extend(살리기)|trim(조각 빼기). '
         '[처음 잘림]은 지운 테이크의 끝 조각이 남은 경우가 많으니 들어 보고 고른다.', '']
    if a.apply:
        L += [f'- 새 컷 계획: `{plan_out}` · 고친 경계 {len(log)}곳 · 적용 뒤 남은 것: '
              + (' · '.join(f'{k} {v}곳' for k, v in head['after_counts'].items()) or '없음'), '']
    L += ['| # | 종류 | 편집 초 | 원본 경계 | 소리 | 제안 | 적용 | 앞 ‖ 뒤 글 |', '|---|---|---|---|---|---|---|---|']
    for n, r in enumerate(rows, 1):
        what, prop, snd, txt = fmt_row(r, a)
        L.append(f'| {n} | {r["kind"]} | {C.mmss(r["edit"])} | {what} | {snd} | {prop} | {"○" if r["apply"] else "—"} | {txt} |')
    if not rows:
        L.append('| — | 문제 없음 | | | | | | |')
    (out / 'edge_check.md').write_text('\n'.join(L) + '\n', 'utf-8')

    print(f'바닥 잡음 {A.floor:.0f}dB · 말소리 {A.sp:.0f}dB · 조용함 {A.ql:.0f}dB · 클립 {len(segs)}개')
    print('검사: ' + (' · '.join(f'{k} {v}곳' for k, v in c.items()) or '문제 없음'))
    for r in rows:
        what, prop, snd, txt = fmt_row(r, a)
        print(f'  [{r["kind"]}] 편집 {C.mmss(r["edit"])} · {what} · {prop}{" (적용)" if r["apply"] else ""} · {txt}')
    if a.apply:
        print(f'새 컷 계획: {plan_out} · 고친 경계 {len(log)}곳 · {C.mmss(before_d)} → {C.mmss(Q["edited_duration"])}')
        print('  적용 뒤 다시 검사: ' + (' · '.join(f'{k} {v}곳' for k, v in head['after_counts'].items()) or '문제 없음'))
    print(f'  {out / "edge_check.md"}')


if __name__ == '__main__':
    main()
