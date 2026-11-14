"""강조 자막 후보 뽑기 — 자막 문장마다 글·소리 특징을 재서 점수순 CSV 로 낸다(후보만, 최종 선택은 사람·에이전트).

CapCut 프로젝트(읽기만)의 자막과, 그 편집본 소리(메인 트랙 원본 클립을 preview.mix_audio 로 섞음, 또는 --audio wav)를 쓴다.

## 강조 6유형(한 문장 하나)
  훅       대상 지목 + 약속·명령        "처음 시작하는 분들은 그냥 이것만 보세요"     효과음 ding(차임)
  원인지목 정답·원인을 예고하는 말       "제가 실패했던 이유가 딱 이거였어요"             효과음 ding(20초 안 반복이면 pop)
  공감     시청자 고민·경험 고백·고통     "먹는 재미가 그냥 아예 사라졌었어요"             효과음 pop(짧은 뾱) 또는 없음
  정정     오해 바로잡기(부정 단언)      "그런데 그거 우리 문제가 아니에요"               효과음 없음(사용자: 삐는 별로)
  결과     수치·변화, 기대감             "체지방은 2% 정도만 늘었습니다"                  효과음 rise
  핵심     주장·행동 지시(수치 포함)      "평소보다 하루 300에서 500칼로리"                효과음 ding
  어디에도 들지 않으면 '-'(강조하지 않음).

## 특징과 가중치(단순하게, 과적합 주의)
  글(정답지 4문장이 공통으로 가진 표지에서 출발한 손규칙. 문장당 표지 1~3개가 보통이라 1~2점 단위)
    지시·예고어(이거·이것만·딱·바로 이)          +2.0   원인·정답 예고는 '무엇'을 숨겨 다음 말을 듣게 한다
    부정 단언(아니에요·필요 없·안 맞·하지 마)     +2.0   오해 정정의 표지
    대상 지목(분들·여러분·~라면)                  +1.5   훅의 표지(누구 이야기인지)
    극단 부사(아예·절대·진짜·무조건·도저히·그냥)  +1.5   감정 강도
    숫자+단위(kg·%·칼로리·끼·g)                   +1.5   결과·핵심 수치
    1인칭 경험 고백(제가·저는·저도 + 과거형)       +1.0   공감·원인지목
    수치 변화(숫자+단위 + 늘었·줄었·증량·빠졌)      +1.0   결과(기대감)의 표지
    고통·상실(배부르·더부룩·힘든·사라졌·실패)       +1.0   공감의 표지
    챕터 제목(첫 번째·두 번째 …로 시작)             −3.0   챕터 전환 카드가 이미 강조한다
    명령·권유 어미(하세요·보세요·마세요)           +1.0
    질문형(?·까요)                                 +0.5   도입 질문은 카드가 대신하는 일이 많아 낮게
    13자 이하 +0.5 / 25자 초과는 쉼표·연결어미로 나눈 구절 가운데 가장 높은 것을 '강조 구절'로 내고 −0.5
  소리(웨이브폼, 분석 구간 안에서 z값)
    평균 음량 z                       +0.4 × z (−2~2로 자름)   힘줘 말한 문장
    앞 쉼 ≥ 0.25초 / 뒤 쉼 ≥ 0.25초   각 +0.3                    말을 끊고 던진 문장(컷 뒤 쉼은 0.15초로 줄어 있어 약함)
    말 빠르기 z < −0.5                +0.3                       또박또박 천천히
    음높이(F0) 범위 z > 0.5           +0.3                       억양이 큰 문장(자기상관, 75~300Hz)
  글 점수가 1 미만이면 소리만으로는 후보가 되지 않는다(소리는 동점 가르기용).

사용:
  python <스킬 폴더>/smartdaddy-video-edit/scripts/emphasis_candidates.py <CapCut 프로젝트 이름|폴더> --out 후보.csv \
      [--start 0 --end 92] [--audio 편집본.wav] [--truth "문구1|문구2"]
  --truth: 정답지(사용자가 고른 문장 일부)를 주면 각 순위를 출력한다(가중치 점검용).
"""
import argparse
import copy
import csv
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np
import soundfile as sf

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

SR = 16000
HOP = 0.02

TEXT_FEATS = [   # (이름, 정규식, 점수)
    ('지시·예고', r'이거|이것만|이것|딱|바로 이|요것', 2.0),
    ('부정 단언', r'아니에요|아닙니다|아니라|필요(가)? 없|안 맞|하지 마|먹지 마|마세요', 2.0),
    ('대상 지목', r'분들|여러분|분이라면|(?<![가-힣])라면|이라면|하시는 분', 1.5),
    ('극단 부사', r'아예|절대|진짜|무조건|도저히|그냥|전혀|제일|완전', 1.5),
    ('숫자+단위', r'\d[\d,.]*\s*(kg|%|칼로리|kcal|끼|g|그램|키로|배|개|년|세트)', 1.5),
    ('명령·권유', r'(하세요|보세요|드세요|마세요|해 ?보세요|챙기세요)[!.?]?$', 1.0),
    ('질문형', r'(\?|까요)$', 0.5),
]
CONFESS = (r'(제가|저는|저도|저 ?역시)', r'(었|았|였|했)')
PAIN = r'배부르|더부룩|힘들|힘든|사라졌|못 먹|안 먹히|배만 나|붓고|실패'
CHANGE = r'늘었|줄었|증량|감량|빠졌|쪘|찌웠'
STICKERS = [  # (낱말, 이모지) — 말하는 사물이 분명할 때만
    ('치킨', '🍗'), ('계란', '🥚'), ('달걀', '🥚'), ('우유', '🥛'), ('바나나', '🍌'), ('밥', '🍚'), ('끼', '🍚'),
    ('칼로리', '🔥'), ('몸무게', '⚖️'), ('체중', '⚖️'), ('논문', '📊'), ('데이터', '📊'), ('팁', '💡'),
    ('체지방', '📉'), ('셰이크', '🥤'), ('고기', '🥩'),
]
SFX = {'훅': 'ding', '원인지목': 'ding', '핵심': 'ding', '공감': 'pop', '결과': 'rise', '정정': '없음', '-': '없음'}


def text_features(t):
    hit, score = [], 0.0
    s = t.strip()
    for name, rx, w in TEXT_FEATS:
        if re.search(rx, s):
            hit.append(name)
            score += w
    if re.search(CONFESS[0], s) and re.search(CONFESS[1], s):
        hit.append('1인칭 고백')
        score += 1.0
    if '숫자+단위' in hit and re.search(CHANGE, s):
        hit.append('수치 변화')
        score += 1.0
    if re.search(PAIN, s):
        hit.append('고통·상실')
        score += 1.0
    if re.match(r'(첫|두|세|네|다섯) ?번째', s):
        hit.append('챕터 제목')
        score -= 3.0
    n = len(s)
    if n <= 13:
        hit.append('13자 이하')
        score += 0.5
    return score, hit


def kind_of(t, hit):
    s = t.strip()
    if '대상 지목' in hit and ('명령·권유' in hit or '지시·예고' in hit):
        return '훅'
    if re.search(r'이유|원인|때문|비밀|정답', s) and '지시·예고' in hit:
        return '원인지목'
    if '부정 단언' in hit and not ('명령·권유' in hit and '숫자+단위' in hit):
        return '정정'
    if '숫자+단위' in hit and re.search(r'(늘|줄|증량|감량|빠졌|쪘|찌웠|됐|었습니다|했고)', s) and re.search(CONFESS[1], s):
        return '결과'
    if '1인칭 고백' in hit or re.search(PAIN, s) or re.search(r'잖아요$', s):
        return '공감'
    if '숫자+단위' in hit or '명령·권유' in hit or '지시·예고' in hit:
        return '핵심'
    return '-'


def clauses(t):
    parts = re.split(r'(?<=[,，])\s*|(?<=고)\s+|(?<=는데)\s+|(?<=서)\s+|(?<=면)\s+', t.strip())
    return [p.strip() for p in parts if len(C.norm_text(p)) >= 4]


def sticker_word(t):
    for w, e in STICKERS:
        if w in t:
            return f'{w} {e}'
    return ''


# ── 소리 ─────────────────────────────────────────────
def project_audio(D, start, end, dest):
    """메인 트랙 원본 클립(목소리)만 섞은 편집본 소리."""
    import preview as P
    M = {k: v[1] for k, v in C.material_index(D).items()}
    main = next(t for t in D['tracks'] if t['type'] == 'video')
    src = Counter(M.get(s['material_id'], {}).get('path') for s in main['segments']).most_common(1)[0][0]
    only = copy.deepcopy(D)
    only['tracks'] = [dict(main, segments=[s for s in main['segments'] if M.get(s['material_id'], {}).get('path') == src])]
    P.mix_audio(only, M, start, end, Path(dest))


def frames_db(x):
    h = int(SR * HOP)
    n = len(x) // h
    f = x[:n * h].reshape(n, h)
    return 20 * np.log10(np.sqrt((f ** 2).mean(1)) + 1e-9)


def f0_track(x, voiced):
    h = int(SR * HOP)
    w = int(SR * 0.04)
    out = np.full(len(voiced), np.nan)
    lo, hi = int(SR / 300), int(SR / 75)
    for i in np.nonzero(voiced)[0]:
        seg = x[i * h:i * h + w]
        if len(seg) < w:
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, 'full')[w - 1:]
        if ac[0] <= 0:
            continue
        ac = ac / ac[0]
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.5:
            out[i] = SR / k
    return out


def z(v):
    v = np.asarray(v, float)
    m = np.nanmean(v)
    s = np.nanstd(v)
    return (v - m) / (s if s > 1e-9 else 1)


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='강조 자막 후보(글·소리 특징 점수순 CSV)')
    ap.add_argument('project')
    ap.add_argument('--out', required=True)
    ap.add_argument('--start', type=float, default=0.0)
    ap.add_argument('--end', type=float)
    ap.add_argument('--audio', help='편집본 소리 wav(없으면 프로젝트 메인 트랙에서 섞음)')
    ap.add_argument('--capcut-dir')
    ap.add_argument('--truth', help='정답지 문구들을 | 로 구분')
    a = ap.parse_args()
    folder = C.resolve_project(a.project, a.capcut_dir)
    D = C.read_draft(C.draft_file(folder))
    total = D['duration'] / C.US
    end = min(a.end or total, total)
    M = C.material_index(D)
    main_t = next(t for t in D['tracks'] if t['type'] == 'video')
    paths = Counter(M[s['material_id']][1].get('path') for s in main_t['segments'])
    src = paths.most_common(1)[0][0]
    blocked = [(s['target_timerange']['start'] / C.US, (s['target_timerange']['start'] + s['target_timerange']['duration']) / C.US)
               for s in main_t['segments'] if M[s['material_id']][1].get('path') != src]
    texts = [t for t in D['tracks'] if t['type'] == 'text']
    sub = max(texts, key=lambda t: sum(1 for s in t['segments'] if M[s['material_id']][1].get('type') == 'subtitle'))
    cues = []
    for s in sorted(sub['segments'], key=lambda s: s['target_timerange']['start']):
        a0 = s['target_timerange']['start'] / C.US
        a1 = a0 + s['target_timerange']['duration'] / C.US
        if a0 >= a.start and a1 <= end + 0.5:
            cues.append((a0, a1, json.loads(M[s['material_id']][1]['content']).get('text', '').replace('\n', ' ')))

    # 소리
    with tempfile.TemporaryDirectory() as td:
        if a.audio:
            x, sr = sf.read(a.audio, dtype='float32', always_2d=True)
            off = 0.0
        else:
            wp = Path(td) / 'voice.wav'
            project_audio(D, a.start, end, wp)
            x, sr = sf.read(wp, dtype='float32', always_2d=True)
            off = a.start
    x = x.mean(1)
    if sr != SR:
        idx = np.arange(0, len(x), sr / SR).astype(int)
        x = x[idx[idx < len(x)]]
    db = frames_db(x)
    thr = max(np.percentile(db, 10) + 10, np.percentile(db, 90) - 30)
    voiced = db > thr
    f0 = f0_track(x, voiced)
    fi = lambda t: int(round((t - off) / HOP))

    feats = []
    for a0, a1, t in cues:
        i0, i1 = max(0, fi(a0 - 0.3)), min(len(db), fi(a1 + 0.3))
        v = np.nonzero(voiced[i0:i1])[0]
        if len(v):
            on, offi = i0 + v[0], i0 + v[-1]
            k = on - 1
            while k >= 0 and not voiced[k] and on - k < 100:
                k -= 1
            pb = (on - k - 1) * HOP
            k = offi + 1
            while k < len(voiced) and not voiced[k] and k - offi < 100:
                k += 1
            pa = (k - offi - 1) * HOP
            seg = db[on:offi + 1][voiced[on:offi + 1]]
            loud = float(np.mean(seg)) if len(seg) else np.nan
            dur = max(0.2, (offi - on + 1) * HOP)
            syl = len(re.findall(r'[가-힣]', t)) + len(re.findall(r'\d', t))
            rate = syl / dur
            ff = f0[on:offi + 1]
            ff = ff[~np.isnan(ff)]
            f0r = float(12 * np.log2(np.percentile(ff, 90) / np.percentile(ff, 10))) if len(ff) > 5 else np.nan
        else:
            pb = pa = rate = f0r = loud = np.nan
        feats.append(dict(loud=loud, pb=pb, pa=pa, rate=rate, f0r=f0r))
    lz, rz, fz = z([f['loud'] for f in feats]), z([f['rate'] for f in feats]), z([f['f0r'] for f in feats])

    rows = []
    for k, ((a0, a1, t), f) in enumerate(zip(cues, feats)):
        if any(b0 < a1 and a0 < b1 for b0, b1 in blocked):
            continue
        phrase = ''
        tscore, hit = text_features(t)
        if len(t.strip()) > 25:
            best = max(((text_features(c)[0], c) for c in clauses(t)), default=(0.0, ''))
            if best[1] and len(best[1]) <= 25:
                phrase = best[1]
                tscore, hit = text_features(phrase)
                tscore -= 0.5
                hit = hit + ['구절']
            else:
                tscore, hit = -9, hit + ['25자 초과']
        aud = 0.0
        if not np.isnan(lz[k]):
            aud += 0.4 * float(np.clip(lz[k], -2, 2))
        aud += 0.3 * (f['pb'] >= 0.25 if not np.isnan(f['pb']) else 0) + 0.3 * (f['pa'] >= 0.25 if not np.isnan(f['pa']) else 0)
        aud += 0.3 * (rz[k] < -0.5 if not np.isnan(rz[k]) else 0) + 0.3 * (fz[k] > 0.5 if not np.isnan(fz[k]) else 0)
        kind = kind_of(phrase or t, hit) if tscore >= 1 else '-'
        score = tscore + aud if tscore >= 1 else min(tscore, 0) + aud * 0.3
        rows.append(dict(시각=f'{int(a0 // 60)}:{a0 % 60:05.2f}', 초=round(a0, 2), 문장=t, 강조구절=phrase, 유형=kind,
                         점수=round(score, 2), 글점수=round(tscore, 2), 소리점수=round(aud, 2), 글특징='·'.join(hit),
                         음량z=None if np.isnan(lz[k]) else round(float(lz[k]), 2),
                         앞쉼=None if np.isnan(f['pb']) else round(f['pb'], 2), 뒤쉼=None if np.isnan(f['pa']) else round(f['pa'], 2),
                         빠르기=None if np.isnan(f['rate']) else round(f['rate'], 1),
                         F0범위반음=None if np.isnan(f['f0r']) else round(f['f0r'], 1),
                         권장효과음=SFX[kind], 권장스티커=sticker_word(phrase or t)))
    rows.sort(key=lambda r: -r['점수'])
    for i, r in enumerate(rows):
        r['순위'] = i + 1
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ['순위', '시각', '초', '문장', '강조구절', '유형', '점수', '글점수', '소리점수', '글특징', '음량z', '앞쉼', '뒤쉼', '빠르기',
            'F0범위반음', '권장효과음', '권장스티커']
    with out.open('w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in cols})
    print(f'자막 {len(cues)}문장 → 후보 CSV {out} (범퍼·CTA 위 자막 제외)')
    for r in rows[:12]:
        print(f"  {r['순위']:2d}. {r['시각']} [{r['유형']}] {r['점수']:5.2f} {r['강조구절'] or r['문장']}  ({r['글특징']})")
    if a.truth:
        print('정답지 순위:')
        for q in a.truth.split('|'):
            hitr = [r for r in rows if C.norm_text(q) in C.norm_text(r['문장'])]
            print(f"  '{q}': " + (f"{hitr[0]['순위']}위 / {len(rows)} [{hitr[0]['유형']}] 점수 {hitr[0]['점수']}" if hitr else '못 찾음'))


if __name__ == '__main__':
    main()
