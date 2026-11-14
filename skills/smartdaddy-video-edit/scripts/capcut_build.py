"""컷 계획(plan.json)으로 CapCut 프로젝트(초벌)를 조립합니다.

- 메인 트랙: 남긴 구간을 순서대로 이어 붙인다. 문장 하나 = 클립 하나.
  각 클립은 원본 파일 '전체'를 참조하므로 CapCut에서 클립 가장자리를 끌어 지운 부분을 되살리거나 더 줄일 수 있다.
- --voice 로 마이크 파일을 따로 주면 보이스 트랙도 같은 방식(문장 클립 + 원본 전체 참조)으로 깔고 영상 소리는 끈다.
- --subtitles: 단어 시각(words.json)으로 의미 단위 자막을 만든다. CapCut 네이티브 텍스트 클립 + 같은 내용의 SRT 파일.
  (꾸밈말·관형어 뒤에서 끊지 않음, 문장 끝·쉼표·연결어미·주어/목적어 조사 뒤에서 끊음, 한 줄 30자 남짓, 시작 = 목소리 + 0.15초)
- --script 대본.md: 자막 글자를 대본 표기로 맞춘다(받아쓰기와 대본을 글자 단위로 맞춰 봄). "채찌피티"→"챗GPT",
  "삼십 시간"→"30시간"처럼 받아쓰기 오류와 숫자 표기가 대본대로 나온다. 대본에 없는 즉흥 멘트는 받아쓰기 그대로 둔다.
  *[화면 신호]*, [대괄호], # 제목 줄은 읽지 않는 것으로 보고 뺀다.
- --overlays 덧입히기.json: 효과음·줌·모션 카드·강조 글자·배경음을 각각 따로 클립으로 얹는다(아래 '덧입히기 형식').
- --bumper 범퍼.mp4 --bumper-src 원본초: 채널 범퍼(소리 포함)를 메인 트랙에 끼우고 그 뒤 클립·자막·덧입히기를 범퍼 길이만큼 민다.
  원본초 이후에 시작하는 첫 클립 앞에 들어간다(도입부 마지막 문장 끝이나 본문 첫 문장 시작을 준다).
  편집본 시각으로 받은 값(덧입히기 "at"·"end"·"near", --edit-words, --listen)은 범퍼 없는 편집본 시각으로 보고 범퍼 뒤면 민다.
  범퍼에 걸친 B롤·모션·강조 글자는 범퍼 앞에서 자르고, 걸친 자막은 범퍼 시작에서 끝낸다.
- 템플릿: 사용자가 실제로 쓰던 CapCut 프로젝트 하나. 그 프로젝트의 클립·재료 형식(자막 글꼴·크기·위치 포함)을 복제하고
  내용은 비운다. 템플릿 프로젝트는 읽기만 하고 절대 고치지 않는다.
  템플릿에 있어야 하는 것: 영상 클립 1개 이상, 로컬 파일 오디오 클립 1개(보이스/음성 파일·효과음을 쓸 때), 텍스트 클립 1개(자막·강조 글자를 쓸 때).

결과:
  <스테이징 폴더>/<새 이름>/     CapCut 프로젝트 폴더(아직 CapCut에 등록 안 됨)
  <스테이징 폴더>/<새 이름>.srt   자막 파일(--subtitles)
  <스테이징 폴더>/<새 이름>_timeline.json   편집 시각 ↔ 원본 시각 대응표, 덧입힌 것 목록(피드백 반영용)

사용 예:
  python capcut_build.py --template "내 평소 프로젝트" --plan 편집/02_cut/plan.json --media 녹화.mp4 --name "초벌_v001" --subtitles
  python capcut_build.py --template "내 평소 프로젝트" --plan plan.json --media 화면.mp4 --voice 마이크.wav --name "초벌_v002"
  python capcut_build.py ... --subtitles --script 대본.md --overlays 편집/overlays.json --name "초벌_v003"
  python capcut_build.py ... --bumper 범퍼_3초_효과음.mp4 --bumper-src 31.2 --name "초벌_v004"   # 도입부 뒤 채널 범퍼
  python capcut_build.py ... --name "초벌_v001" --install      # CapCut을 끈 뒤에, 사용자 허락을 받고 등록

덧입히기 형식(overlays.json — 목록 하나, 또는 {"items": [...]}). 시각은 셋 중 하나로 정한다:
  "at": 편집본 초 · "src": 원본 초(잘린 곳이면 다음 클립 시작으로) · "word": "실제로 말한 낱말"(받아쓰기에서 찾음,
  "near": 편집본 초 근처에서, "nth": 몇 번째) — 장면 박자는 대본이 아니라 실제로 말한 낱말에 맞춘다.
  길이는 "dur"(초) 또는 "end"/"end_src"/"end_word". "offset": 시작을 이만큼 옮김(초).
  {"type": "sfx",    "word": "결과는", "file": "sfx/snap.wav", "db": -20, "from": 0.0, "dur": 1.2}
  {"type": "zoom",   "at": 12.0, "dur": 3.0, "scale": 1.4, "x": 0.25, "y": 0.8, "ramp": 0.3, "out": "smooth"}
       x, y = 확대할 곳(화면 왼쪽 위 0,0 ~ 오른쪽 아래 1,1). 원본 위 '줌' 트랙에 얹으므로 지우면 원래 화면.
       "out": "cut"이면 줌이 풀리지 않은 채 끝나며 원래 화면으로 바로 돌아온다.
  {"type": "motion", "at": 30.5, "file": "편집/motion/time.mp4", "fade": 0.2}      길이 생략 = 파일 길이
  {"type": "text",   "word": "마동석", "dur": 1.5, "text": "마동석?!", "x": 0.5, "y": 0.5, "size": 1.6}
       템플릿 텍스트 스타일(사용자 글꼴·테두리)로 화면 가운데에 강조 글자. size = 템플릿 글자 크기 배수.
  {"type": "bgm",    "at": 0, "end": 45.0, "file": "music.mp3", "db": -40}         모자라면 반복해서 채운다
  {"type": "broll",  "word": "드리퍼", "near_src": 63.2, "file": "캡컷_가져오기/05_B롤/B롤_LOWER01_….mp4", "asset_id": "LOWER01",
                     "in": 2.0, "dur": 4.0, "scale": 1.0, "x": 0.5, "y": 0.5, "crop": [0.1, 0, 0.9, 1], "fade": 0, "sound": false}
       스톡·본인 촬영본을 메인 위 'B롤' 트랙(줌 위, 모션 아래)에 얹는다. 지우면 원래 화면. in = 영상 파일 안 시작 초,
       dur = 길이(다음 B롤 시작 전까지로 자름). 원음은 기본 끔(sound: true 면 "db" 기본 −20). scale = 화면 채움 대비 배율,
       x·y = 확대 중심(0~1, 화면 밖 검은 띠가 생기지 않게 제한), crop = 원본 [x0, y0, x1, y1] 비율(CapCut 재료 크롭).
       "near_src": 원본 초 근처의 같은 낱말을 찾는다(컷 뒤 편집 시각으로 바꿔 near 로 씀). asset_id·note 는 _timeline.json 에 남는다.
  어떤 항목이든 "note": "왜 넣었는지"를 적어 두면 _timeline.json 에 같이 남는다.

설치(--install) 규칙: CapCut이 켜져 있으면 거부, 같은 이름 프로젝트가 있으면 거부(새 이름으로 만들 것),
root_meta_info.json(프로젝트 목록)을 백업하고 기존 항목은 그대로 둔 채 맨 앞에 새 항목만 추가, 복사 후 검증.

피해 가는 함정:
- 오디오 재료는 로컬 파일 형식(extract_music). 라이브러리 소리(effect_id 있음)를 복제하면 CapCut이 열 때 소리를 바꿔 버린다.
- 템플릿 클립의 키프레임·애니메이션은 지운다(영상 클립 키프레임 time_offset은 원본 시각 기준 = source start 포함).
- 트랙 안 클립은 시작 시각 순으로 정렬해 저장한다.
"""
import argparse
import copy
import difflib
import hashlib
import json
import math
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

MARKER = '_staging_by_capcut_build.txt'
LEAD = 0.15        # 자막 시작 = Whisper 단어 시작 + 0.15초(목소리 시작에 맞춤)
TAIL = 0.20        # 자막 끝 = 마지막 단어 끝 + 0.2초
MAXC, HARD = 30, 36
ONE_LINE = 34      # 한 문장이 이 글자 수 이하면 나누지 않는다


def uid():
    return str(uuid.uuid4()).upper()


def kf(prop, pts):
    """키프레임 묶음. pts = [(time_offset us, 값)]. 영상 클립의 time_offset은 원본 시각 기준(source start 포함)."""
    return dict(id=uid(), material_id='', property_type=prop, keyframe_list=[
        dict(id=uid(), curveType='Line', time_offset=int(t), left_control=dict(x=0.0, y=0.0), right_control=dict(x=0.0, y=0.0),
             values=[round(v, 5)], string_value='', graphID='') for t, v in pts])


# ── 자막: 의미 단위 나누기 ─────────────────────────────
FILLER = {'어', '음', '아', '흠', '호', '흐', '으', '엄', '어어', '음음', '으음'}
NEVER = {'잘', '좀', '더', '되게', '진짜', '너무', '다', '꽤', '조금', '가장', '아주', '정말', '막', '그냥', '이렇게', '저렇게', '그렇게',
         '이런', '그런', '저런', '이', '그', '저', '한', '두', '세', '네', '제', '내', '약간', '특히', '바로', '먼저', '자', '와', '아', '오', '야',
         '또', '역시', '이제', '일단', '여기', '거의', '훨씬', '확실히', '어떤', '무슨', '모든', '각', '몇', '첫', '다른', '같은', '새', '옛',
         '필요'}   # 2026-11-02 '필요 없다'의 '필요'가 문장 끝(…요)으로 잡힘
# 관형어(뒤 명사를 꾸미는 말): 이 뒤에서는 끊지 않는다("철권 같은 / 3D 게임" 금지)
ATTR_END = ('하는', '되는', '있는', '없는', '않는', '같은', '다른', '어떤', '이런', '그런', '저런', '던', '좋은', '많은', '작은', '높은',
            '낮은', '싶은', '받은', '만든', '만드는', '나오는', '보는', '주는', '가는', '오는', '쓰는', '먹는', '아는', '모르는', '하신', '되신')
# 앞말에 붙어야 뜻이 되는 말(의존명사·세는 말·보조용언): 이 말 앞에서는 끊지 않는다("첫 / 번째", "할 / 수 있다", "세 / 가지" 금지, 2026-11-14 사용자)
BOUND = {'번째', '번', '가지', '개', '명', '분', '시간', '세트', '회', '킬로', '그램', '끼', '주', '달', '개월', '년', '수', '것', '거', '게', '걸', '건',
         '때', '줄', '적', '데', '뿐', '만큼', '정도', '때문에', '때문', '동안', '이상', '이하', '같아요', '같습니다', '같은데', '있습니다', '있어요',
         '없습니다', '없어요', '않습니다', '않아요', '싶어요', '싶습니다', '됩니다', '돼요', '합니다', '해요', '보세요', '주세요',
         '하지', '않고', '않게', '않는', '않아도', '말고', '못하고'}


def bound_start(t):
    b = bare(t)
    return b in BOUND or bool(re.match(r'(수|것|거|때|줄|적|데|뿐)(가|는|도|를|을|이|에|만|로|까지|밖에)$', b))


NOT_END = ('보다', '까지', '부터', '처럼', '만큼', '니까', '는데', '아까', '지금', '먼저', '마다', '에다')   # 2026-11-02 '사람마다'·'앱에다'가 문장 끝(…다)으로 잡힘


def bare(t):
    return re.sub(r'[.,?!…~]+$', '', t)


def is_end(t):
    if re.search(r'[.?!]$', t):
        return True
    b = bare(t)
    if len(b) < 2 or b in NEVER or b.endswith(NOT_END):
        return False
    return bool(re.search(r'(요|다|죠|까|네)$', b))


def score(t):
    """이 말 뒤에서 끊기 좋은 정도(0=끊지 않음)."""
    b = bare(t)
    if b in NEVER or len(b) < 2 or b.endswith(ATTR_END):
        return 0
    if t.endswith(','):
        return 3
    if b.endswith(('는데', '지만', '니까', '어서', '아서', '해서', '하고', '이고', '면서', '거든요', '는데요')):
        return 3
    if re.search(r'(고|며|면|서)$', b):
        return 2.5
    if b.endswith(('에서', '으로', '한테', '에게', '이랑', '보다')):
        return 1.6
    if re.search(r'(은|는|이|가|을|를|로|에|과|와|랑|도)$', b):
        return 1.5
    return 0


def clen(ws):
    return len(' '.join(x[2] for x in ws))


def split_long(st):
    if clen(st) <= MAXC:
        return [st]
    best = None
    for k in range(1, len(st)):
        l, r = clen(st[:k]), clen(st[k:])
        if l < 6 or r < 6:
            continue
        sc = score(st[k - 1][2])
        if sc <= 0 or bound_start(st[k][2]):
            continue
        val = sc * 10 - abs(l - r) * 0.35 - (8 if max(l, r) > HARD else 0)
        if best is None or val > best[0]:
            best = (val, k)
    if best is None:
        if clen(st) <= HARD:
            return [st]
        ks = [k for k in range(1, len(st)) if bare(st[k - 1][2]) not in NEVER and not bare(st[k - 1][2]).endswith(ATTR_END)
              and not bound_start(st[k][2])
              and clen(st[:k]) >= 6 and clen(st[k:]) >= 6]
        if not ks:
            return [st]
        k = min(ks, key=lambda k: abs(clen(st[:k]) - clen(st[k:])))
    else:
        k = best[1]
    return split_long(st[:k]) + split_long(st[k:])


def load_replace(paths):
    """자막 표기 고치기 파일들 → (바꿀 것 {틀린 말: 고칠 말}, 물어볼 것 [(틀린 말, 고칠 말, 이유)]).
    파일은 {"틀린 말": "고칠 말"} 또는 채널 공용 사전 {"entries": [{"from", "to", "mode": "auto|ask", "why"}]}.
    같은 말이 여러 파일에 있으면 앞 파일이 이긴다(영상 고침 사전 → 채널 공용 사전 순서로 준다)."""
    rep, ask = {}, []
    for p in paths or []:
        d = C.read_json(p)
        items = ([(e['from'], e['to'], e.get('mode', 'auto'), e.get('why', '')) for e in d['entries']]
                 if isinstance(d.get('entries'), list) else [(k, v, 'auto', '') for k, v in d.items()])
        for w, r, mode, why in items:
            if w in rep or any(w == x[0] for x in ask):
                continue
            if mode == 'ask':
                ask.append((w, r, why))
            else:
                rep[w] = r
    return rep, ask


def make_cues(W, replace=None, vetted=False, hits=None):
    """W: [(시작, 끝, 단어)] 타임라인 시각 → [(시작, 끝, 자막)]
    vetted: 받아쓰기 단계에서 환각 문구를 이미 걸러 원고와 대조해 되살린 낱말(--edit-words)이면 자막에서 다시 거르지 않는다
    ("오늘 이 영상이 도움이 되셨다면 구독과 좋아요 부탁드리고요"는 진짜 끝인사다).
    hits: 주면 {틀린 말: 바꾼 횟수}를 채운다."""
    W = [[a, b, w.strip()] for a, b, w in W if w.strip() and w.strip().rstrip('.,?!') not in FILLER]
    sents, cur = [], []
    for w in W:
        if cur and (is_end(cur[-1][2]) or w[0] - cur[-1][1] > 2.0):
            sents.append(cur)
            cur = []
        cur.append(w)
    if cur:
        sents.append(cur)
    cues = [c for st in sents for c in ([st] if clen(st) <= ONE_LINE else split_long(st))]   # 한 문장이면 30자를 조금 넘어도 한 줄
    merged = []
    for c in cues:            # 아주 짧은 조각(5자 이하)은 앞과 합침
        if merged and clen(c) <= 5 and c[0][0] - merged[-1][-1][1] < 0.5 and clen(merged[-1]) + clen(c) + 1 <= HARD:
            merged[-1] = merged[-1] + c
        else:
            merged.append(c)
    out = []
    for c in merged:
        txt = ' '.join(x[2] for x in c).strip()
        txt = re.sub(r'\s+([,.?!%])', r'\1', txt).rstrip('.,')
        for a, b in (replace or {}).items():
            if hits is not None and a in txt:
                hits[a] = hits.get(a, 0) + txt.count(a)
            txt = txt.replace(a, b)
        if not txt or (not vetted and C.is_hallucination(txt, exact_too=False)):
            continue
        out.append([c[0][0] + LEAD, c[-1][1] + TAIL, txt])
    for i in range(len(out)):
        if i + 1 < len(out):
            nxt = out[i + 1][0]
            if nxt - out[i][1] < 0.35:
                out[i][1] = nxt - 0.03
            out[i][1] = min(out[i][1], nxt - 0.03)
        if out[i][1] - out[i][0] < 0.8:
            out[i][1] = out[i][0] + 0.8 if i + 1 >= len(out) else max(out[i][1], min(out[i][0] + 0.8, out[i + 1][0] - 0.03))
    return [c for c in out if c[1] - c[0] > 0.1]


# ── 대본 표기로 맞추기 ─────────────────────────────────
def clean_script(raw):
    """대본에서 읽지 않는 것(# 제목, *[화면 신호]*, [대괄호], 목록 기호, 굵게 표시)을 뺀다."""
    out = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith(('#', '>', '|', '```', '---')):
            continue
        s = re.sub(r'\*?\[[^\]]*\]\*?', ' ', s)
        s = re.sub(r'^[-*+]\s+|^\d+[.)]\s+', '', s)
        s = s.replace('**', '').replace('__', '')
        if s.strip():
            out.append(s.strip())
    return ' '.join(out)


def _key(ch):
    return ch.isalnum()


def apply_script(TW, script_text):
    """받아쓰기 단어(TW)의 글자를 대본 표기로 바꾼다. 대본에 없는 말(즉흥 멘트)은 받아쓰기 그대로 둔다.
    돌려주는 것: (바뀐 단어 목록, 대본과 일치한 글자 비율)"""
    S = clean_script(script_text)
    merged = []                            # 글자 없는 조각("%", ",")은 앞 단어에 붙인다
    for w in TW:
        if merged and not any(_key(ch) for ch in w[2]):
            p = merged[-1]
            merged[-1] = (p[0], max(p[1], w[1]), p[2].rstrip() + w[2].strip())
        else:
            merged.append(tuple(w))
    TW = merged
    s_norm, s_pos = [], []
    for i, ch in enumerate(S):
        if _key(ch):
            s_norm.append(ch.lower())
            s_pos.append(i)
    a_norm, a_word = [], []
    for k, w in enumerate(TW):
        for ch in w[2]:
            if _key(ch):
                a_norm.append(ch.lower())
                a_word.append(k)
    if not s_norm or not a_norm:
        return TW, 0.0
    A, B = ''.join(a_norm), ''.join(s_norm)
    blocks = difflib.SequenceMatcher(None, A, B, autojunk=False).get_matching_blocks()
    amap = [None] * (len(A) + 1)          # 받아쓰기 글자 위치 → 대본 글자 위치(경계)
    keep_asr = [False] * len(A)           # 대본에 없는 즉흥 멘트 구간
    matched = 0
    pa = pb = 0
    for bl in blocks:
        ga, gb = bl.a - pa, bl.b - pb     # 맞지 않은 구간(받아쓰기 ga글자 ↔ 대본 gb글자)
        if ga:
            bad = (gb == 0 and ga > 6) or (gb and ga > 6 and not (0.4 <= gb / ga <= 2.5))
            for i in range(ga):
                amap[pa + i] = pb + (round(i * gb / ga) if gb else 0)
                keep_asr[pa + i] = bad
        for i in range(bl.size):
            amap[bl.a + i] = bl.b + i
        matched += bl.size
        pa, pb = bl.a + bl.size, bl.b + bl.size
    amap[len(A)] = len(B)
    first = {}                             # 단어마다 첫 글자 위치
    for i, k in enumerate(a_word):
        first.setdefault(k, i)
    starts = sorted(first.items())
    out = []
    last_o1 = None                         # 앞 단어가 대본에서 끝난 자리
    for n, (k, i0) in enumerate(starts):
        i1 = starts[n + 1][1] if n + 1 < len(starts) else len(A)
        w = TW[k]
        if any(keep_asr[i0:i1]):
            out.append((w[0], w[1], w[2]))
            last_o1 = None
            continue
        b0, b1 = amap[i0], amap[i1]
        if b1 <= b0:
            continue                       # 대본에 없는 군말("어", "음")은 빠진다
        o0 = s_pos[b0]
        o1 = s_pos[b1] if b1 < len(s_pos) else len(S)
        seg = S[o0:o1]
        if not seg.strip():
            continue
        if out and last_o1 == o0 and o0 > 0 and not S[o0 - 1].isspace():
            p = out[-1]                    # 대본에서 한 낱말 안이면("구현했고") 띄어 쓰지 않고 앞 단어에 붙인다
            out[-1] = (p[0], w[1], p[2] + seg.rstrip())
        else:
            out.append((w[0], w[1], seg.strip()))
        last_o1 = o1
    return out, matched / max(1, len(A))


def find_word(TW, query, near=None, nth=1):
    """편집본 단어 목록에서 query(띄어쓰기·기호 무시)를 찾아 시작 시각을 돌려준다."""
    q = ''.join(ch.lower() for ch in query if _key(ch))
    if not q:
        return None
    chars, owner = [], []
    for k, w in enumerate(TW):
        for ch in w[2]:
            if _key(ch):
                chars.append(ch.lower())
                owner.append(k)
    s = ''.join(chars)
    hits, i = [], s.find(q)
    while i >= 0:
        hits.append(TW[owner[i]][0])
        i = s.find(q, i + 1)
    if not hits:
        return None
    if near is not None:
        hits = sorted(hits, key=lambda t: abs(t - near))
        return hits[0]
    return hits[nth - 1] if 0 < nth <= len(hits) else None


def srt_time(t):
    t = max(0.0, t)
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


# ── 템플릿 ─────────────────────────────────────────────
class Template:
    def __init__(self, folder):
        self.folder = Path(folder)
        f = C.draft_file(self.folder)
        if not f:
            C.die(f'템플릿 폴더에 draft_content.json·draft_info.json이 없습니다: {self.folder}')
        self.draft_name = f.name        # Windows draft_content.json · Mac(CapCut 9.x) draft_info.json
        self.D = C.read_draft(f)
        self.M = C.material_index(self.D)
        segs = [(t, s) for t in self.D['tracks'] for s in t['segments']]

        def kind(s):
            return self.M.get(s['material_id'], (None, {}))[1].get('type')

        def pack(s):
            if s is None:
                return None
            refs = {r: copy.deepcopy(self.M[r]) for r in s.get('extra_material_refs', []) if r in self.M}
            return copy.deepcopy(s), copy.deepcopy(self.M[s['material_id']][1]), refs

        v = [s for t, s in segs if t['type'] == 'video' and kind(s) == 'video']
        self.vid = pack(next((s for s in v if not s.get('common_keyframes')), v[0] if v else None))
        a = [s for t, s in segs if t['type'] == 'audio' and kind(s) == 'extract_music']
        self.aud_converted = False
        if not a:      # 로컬 파일 오디오가 없으면 라이브러리 소리를 로컬 형식으로 바꿔 쓴다(경고)
            a = [s for t, s in segs if t['type'] == 'audio']
            self.aud_converted = bool(a)
        self.aud = pack(a[0] if a else None)
        texts = [t for t in self.D['tracks'] if t['type'] == 'text' and t['segments']]
        self.text_track = copy.deepcopy(max(texts, key=lambda t: len(t['segments']))) if texts else None
        self.txt = pack(self.text_track['segments'][0]) if texts else None


class Builder:
    def __init__(self, tpl):
        self.tpl = tpl
        D = copy.deepcopy(tpl.D)
        for k, v in D['materials'].items():
            if isinstance(v, list):
                D['materials'][k] = []
        D['tracks'] = []
        self.D = D
        self.M = D['materials']
        self.mats = {}       # (경로, 종류, 크롭) → 재료
        self.tracks = {}
        self.sub_group = f'import_{int(time.time() * 1000)}'
        self.frame = None    # 메인 원본 화면 맞춤 (경로, 크롭, 회전도) — --crop/--rotate. 메인·줌 조각에 똑같이 건다

    def track(self, name, typ, proto=None):
        if name not in self.tracks:
            t = dict(id=uid(), type=typ, segments=[], flag=0, attribute=0, name=name, is_default_name=False)
            if proto:
                t.update(flag=proto.get('flag', 0), attribute=proto.get('attribute', 0))
            self.tracks[name] = t
            self.D['tracks'].append(t)
        return self.tracks[name]

    def free_track(self, base, typ, start_us, dur_us, proto=None):
        """base, base 2, base 3 … 중 이 구간이 비어 있는 트랙 이름(한 트랙 안 클립은 겹치면 안 된다)."""
        n = 1
        while True:
            name = base if n == 1 else f'{base} {n}'
            t = self.tracks.get(name)
            if t is None or all(s['target_timerange']['start'] + s['target_timerange']['duration'] <= start_us
                                or start_us + dur_us <= s['target_timerange']['start'] for s in t['segments']):
                self.track(name, typ, proto)
                return name
            n += 1

    def clone_refs(self, refs, kind, dur_us=0):
        out = []
        for r, (k, m) in refs.items():
            if k == 'audio_fades':
                continue
            v = copy.deepcopy(m)
            v['id'] = uid()
            if k == 'speeds':
                v.update(speed=1.0, curve_speed=None)
            if k == 'material_animations':
                if kind != 'text':
                    v['animations'] = []
                else:
                    for an in v.get('animations', []):
                        if an.get('type') == 'out':
                            an['start'] = max(0, dur_us - an.get('duration', 0))
            self.M.setdefault(k, []).append(v)
            out.append(v['id'])
        return out

    def material(self, path, typ, crop=None):
        """crop = (x0, y0, x1, y1) 원본 비율. CapCut은 크롭을 재료에 저장하므로 크롭마다 재료를 따로 만든다."""
        path = C.capcut_media(path)         # Mac: ~/Movies 밖 파일은 CapCut이 못 읽어 ~/Movies 아래 복제본을 쓴다
        crop = tuple(round(float(v), 5) for v in crop) if crop else None
        key = (path.as_posix(), typ, crop)
        if key in self.mats:
            return self.mats[key]
        info = C.media_info(path)
        if typ == 'audio':
            if not self.tpl.aud:
                C.die('템플릿 프로젝트에 오디오 클립이 없습니다. 로컬 음성 파일(효과음·녹음 등)을 하나라도 올려 둔 프로젝트를 템플릿으로 고르세요.')
            m = copy.deepcopy(self.tpl.aud[1])
            m.update(id=uid(), path=path.as_posix(), name=path.name, duration=C.us(info['duration']), type='extract_music',
                     unique_id=uuid.uuid4().hex, local_material_id='', category_name='local', wave_points=[])
            for k in ('effect_id', 'category_id', 'music_id', 'request_id', 'resource_id', 'third_resource_id', 'source_from',
                      'music_source', 'pgc_id', 'pgc_name', 'query', 'search_id'):
                if k in m:
                    m[k] = ''
            self.M.setdefault('audios', []).append(m)
        else:
            if not self.tpl.vid:
                C.die('템플릿 프로젝트에 영상 클립이 없습니다. 영상 파일을 하나라도 올려 둔 프로젝트를 템플릿으로 고르세요.')
            m = copy.deepcopy(self.tpl.vid[1])
            m.update(id=uid(), unique_id=uuid.uuid4().hex, path=path.as_posix(), material_name=path.name, type='video',
                     width=info['width'], height=info['height'], duration=C.us(info['duration']), has_audio=info['has_audio'],
                     local_material_id='', local_id='', media_path='', reverse_path='', intensifies_path='',
                     reverse_intensifies_path='', intensifies_audio_path='', cartoon_path='', freeze=None, smart_motion=None)
            x0, y0, x1, y1 = crop or (0.0, 0.0, 1.0, 1.0)
            m['crop'] = dict(upper_left_x=x0, upper_left_y=y0, upper_right_x=x1, upper_right_y=y0,
                             lower_left_x=x0, lower_left_y=y1, lower_right_x=x1, lower_right_y=y1)
            if 'crop_ratio' in m:          # CapCut 9.x 사용자 프로젝트의 크롭 저장 형식(2026-10-30 확인)
                m['crop_ratio'] = 'free'
                m['crop_scale'] = 1.0
            if isinstance(m.get('video_algorithm'), dict):
                m['video_algorithm']['algorithms'] = []
                m['video_algorithm']['path'] = ''
            if isinstance(m.get('matting'), dict):
                m['matting'].update(flag=0, path='', strokes=[], interactiveTime=[])
            self.M.setdefault('videos', []).append(m)
        self.mats[key] = (m, info)
        return self.mats[key]

    def put_video(self, track, path, start_us, dur_us, src_us, scale, volume, crop=None):
        fr = self.frame if self.frame and Path(path).resolve() == self.frame[0] else None
        if fr and crop is None:
            crop = fr[1]
        m, info = self.material(path, 'video', crop)
        if fr and crop and 'crop_ratio' in m:      # 사용자 프로젝트처럼 16:9 잘라내기면 비율 이름도 16:9
            w, h = (crop[2] - crop[0]) * info.get('width', 0), (crop[3] - crop[1]) * info.get('height', 0)
            if h and abs(w / h - 16 / 9) < 0.01:
                m['crop_ratio'] = '16:9'
        s = copy.deepcopy(self.tpl.vid[0])
        s.update(id=uid(), material_id=m['id'], extra_material_refs=self.clone_refs(self.tpl.vid[2], 'video'),
                 common_keyframes=[], keyframe_refs=[], volume=volume, last_nonzero_volume=1.0, speed=1.0, visible=True,
                 group_id='', raw_segment_id='', desc=Path(path).name, reverse=False, is_loop=False,
                 target_timerange=dict(start=start_us, duration=dur_us),
                 source_timerange=dict(start=src_us, duration=dur_us),
                 render_timerange=dict(start=0, duration=0))
        s['clip'] = dict(scale=dict(x=scale, y=scale), rotation=fr[2] if fr else 0.0, transform=dict(x=0.0, y=0.0),
                         flip=dict(vertical=False, horizontal=False), alpha=1.0)
        s['uniform_scale'] = dict(on=True, value=scale)
        self.track(track, 'video')['segments'].append(s)
        return s

    def put_audio(self, track, path, start_us, dur_us, src_us, volume=1.0):
        m, info = self.material(path, 'audio')
        s = copy.deepcopy(self.tpl.aud[0])
        s.update(id=uid(), material_id=m['id'], extra_material_refs=self.clone_refs(self.tpl.aud[2], 'audio'),
                 common_keyframes=[], keyframe_refs=[], volume=volume, last_nonzero_volume=1.0, speed=1.0, visible=True,
                 group_id='', raw_segment_id='', desc=Path(path).name, reverse=False, is_loop=False,
                 target_timerange=dict(start=start_us, duration=dur_us),
                 source_timerange=dict(start=src_us, duration=dur_us),
                 render_timerange=dict(start=0, duration=0))
        self.track(track, 'audio')['segments'].append(s)
        return s

    def put_text(self, track, text, start_us, dur_us, emphasis=None):
        """emphasis=(x, y, 크기 배수)면 자막이 아닌 강조 글자(type text)로, 그 위치에 넣는다."""
        seg_t, mat_t, refs = self.tpl.txt
        m = copy.deepcopy(mat_t)
        m['id'] = uid()
        c = json.loads(m['content'])
        n = len(text.encode('utf-16-le')) // 2          # CapCut 범위는 UTF-16 글자 수
        st = copy.deepcopy((c.get('styles') or [{}])[0])
        st['range'] = [0, n]
        if emphasis and isinstance(st.get('size'), (int, float)):
            st['size'] = round(st['size'] * emphasis[2], 2)
        c['text'] = text
        c['styles'] = [st]
        m['content'] = json.dumps(c, ensure_ascii=False)
        for k in ('words', 'current_words'):
            if isinstance(m.get(k), dict):
                m[k] = {kk: [] for kk in m[k]}
        for k in ('base_content', 'recognize_text', 'recognize_task_id'):
            if k in m:
                m[k] = ''
        for k in ('text_to_audio_ids', 'relevance_segment'):
            if k in m:
                m[k] = []
        if emphasis:
            m['type'] = 'text'
        m['group_id'] = self.sub_group if m.get('type') == 'subtitle' else ''
        self.M.setdefault('texts', []).append(m)
        s = copy.deepcopy(seg_t)
        s.update(id=uid(), material_id=m['id'], extra_material_refs=self.clone_refs(refs, 'text', dur_us),
                 common_keyframes=[], keyframe_refs=[], visible=True, group_id='', raw_segment_id='', desc=text[:20],
                 target_timerange=dict(start=start_us, duration=dur_us), render_timerange=dict(start=0, duration=0))
        if emphasis:
            s.setdefault('clip', {})['transform'] = dict(x=round((emphasis[0] - 0.5) * 2, 4), y=round((0.5 - emphasis[1]) * 2, 4))
        self.track(track, 'text', None if emphasis else self.tpl.text_track)['segments'].append(s)
        return s


def canvas_for(info, cur):
    """원본 방향에 맞는 캔버스. 템플릿과 방향이 같으면 템플릿 캔버스를 그대로 쓴다."""
    w, h = info['width'], info['height']
    if not w or not h:
        return cur
    kind = 'land' if w >= h * 1.2 else 'port' if h >= w * 1.2 else 'sq'
    cw, ch = cur.get('width', 1920), cur.get('height', 1080)
    ckind = 'land' if cw >= ch * 1.2 else 'port' if ch >= cw * 1.2 else 'sq'
    if kind == ckind:
        return cur
    new = dict(cur)
    new.update({'land': dict(width=1920, height=1080, ratio='16:9'), 'port': dict(width=1080, height=1920, ratio='9:16'),
                'sq': dict(width=1080, height=1080, ratio='1:1')}[kind])
    return new


def cover_scale(info, cv):
    """CapCut 기본(화면 안에 맞춤) 대비 배율: 검은 띠 없이 화면을 채운다."""
    w, h = info['width'], info['height']
    if not w or not h:
        return 1.0
    f = min(cv['width'] / w, cv['height'] / h)
    return round(max(cv['width'] / (w * f), cv['height'] / (h * f)), 4)


def trim_edges(ws, want):
    """클립 낱말(ws) 중 클립을 따로 받아쓴 글(want)과 두 글자 이상 이어 맞는 곳이 없는 앞·뒤 낱말을 떼어 낸다.
    돌려주는 것: (앞에서 뗀 것, 남길 것, 뒤에서 뗀 것). want 가 없거나 하나도 안 맞으면 그대로 둔다."""
    if not want or not ws:
        return [], ws, []
    chars, owner = [], []
    for k, w in enumerate(ws):
        for ch in C.norm_text(w[2]):
            chars.append(ch)
            owner.append(k)
    hit = set()
    for bl in difflib.SequenceMatcher(None, ''.join(chars), want, autojunk=False).get_matching_blocks():
        if bl.size >= 2:
            hit.update(owner[bl.a:bl.a + bl.size])
    if not hit:
        return [], ws, []
    lo, hi = min(hit), max(hit)
    return ws[:lo], ws[lo:hi + 1], ws[hi + 1:]


def load_words(p):
    j = C.read_json(p)
    out = []
    for w in j:
        if isinstance(w, dict):
            out.append((float(w['start']), float(w['end']), str(w.get('word', ''))))
        else:
            out.append((float(w[0]), float(w[1]), str(w[2])))
    return out


def write_staging(b, tpl, stage, name, dest, media_paths, cover_src):
    D = b.D
    if stage.exists():
        if not (stage / MARKER).exists():
            C.die(f'스테이징 폴더가 이미 있는데 이 스크립트가 만든 것이 아닙니다. 지우지 않습니다: {stage}')
        shutil.rmtree(stage)
    ign = shutil.ignore_patterns('*.bak', '.locked', 'Resources', 'adjust_mask', 'smart_crop', 'subdraft', 'draft_cover.jpg',
                                 MARKER)
    shutil.copytree(tpl.folder, stage, ignore=ign)
    for sub in ('adjust_mask', 'matting', 'qr_upload', 'smart_crop', 'subdraft', 'Resources/audioAlg', 'Resources/videoAlg',
                'Resources/combination'):
        (stage / sub).mkdir(parents=True, exist_ok=True)
    tl = stage / 'Timelines'
    tl.mkdir(exist_ok=True)
    pj_path = tl / 'project.json'
    pj = C.read_json(pj_path) if pj_path.exists() else {}
    old_main = pj.get('main_timeline_id') or tpl.D['id']
    new = D['id']
    tl_name = next((x.get('name') for x in pj.get('timelines', []) if x.get('id') == old_main), None) or 'Timeline 01'
    for x in list(tl.iterdir()):          # 메인 타임라인 하나만 남긴다
        if x.is_dir() and x.name != old_main:
            shutil.rmtree(x)
    if (tl / old_main).exists():
        (tl / old_main).rename(tl / new)
    (tl / new).mkdir(exist_ok=True)
    js = json.dumps(D, ensure_ascii=False, separators=(',', ':'))
    for p in [stage / tpl.draft_name, stage / 'template-2.tmp', tl / new / tpl.draft_name]:
        p.write_text(js, 'utf-8')
    for p in [tl / new / 'template-2.tmp', tl / new / 'template.tmp', stage / 'template.tmp']:
        if p.exists():
            p.write_text(js, 'utf-8')
    now = int(time.time())
    pj.update(id=new, main_timeline_id=new, create_time=now * C.US, update_time=now * C.US,
              timelines=[dict(create_time=now * C.US, id=new, is_marked_delete=False, name=tl_name, update_time=now * C.US)])
    C.write_json(pj_path, pj, compact=True)
    C.write_json(stage / 'timeline_layout.json', {'dockItems': [{'dockIndex': 0, 'ratio': 1, 'timelineIds': [new],
                                                                 'timelineNames': [tl_name]}], 'layoutOrientation': 1}, compact=True)
    # 재료 목록(meta)
    mp = stage / 'draft_meta_info.json'
    meta = C.read_json(mp) if mp.exists() else {}
    items = []
    proto = None
    for g in meta.get('draft_materials', []):
        if g.get('type') == 0 and g.get('value'):
            proto = g['value'][0]
    listed = set()
    for (path, typ, _crop), (m, info) in b.mats.items():
        if (path, typ) in listed:          # 크롭만 다른 재료는 미디어 목록에 한 번만
            continue
        listed.add((path, typ))
        it = copy.deepcopy(proto) if proto else dict(ai_group_type='', enter_from=0, item_source=1, material_color_tag='', md5='',
                                                     sub_time_range={'duration': -1, 'start': -1}, type=0)
        dur = m.get('duration', 0)
        it.update(id=m['id'], file_Path=path, extra_info=Path(path).name, metetype='music' if typ == 'audio' else 'video',
                  width=info.get('width', 0), height=info.get('height', 0), duration=dur, create_time=now, import_time=now,
                  import_time_ms=now * C.US, roughcut_time_range={'duration': dur, 'start': 0})
        items.append(it)
    for g in meta.get('draft_materials', []):
        g['value'] = items if g.get('type') == 0 else []
    size = 0
    for p in media_paths:
        try:
            size += Path(p).stat().st_size
        except OSError:
            pass
    meta.update(draft_id=new, draft_name=name, draft_fold_path=dest.as_posix(), draft_root_path=dest.parent.as_posix(),
                draft_cover='draft_cover.jpg', tm_draft_create=now * C.US, tm_draft_modified=now * C.US,
                tm_duration=D['duration'], draft_timeline_materials_size_=size, draft_is_invisible=False)
    C.write_json(mp, meta, compact=True)
    vp = stage / 'draft_virtual_store.json'
    if vp.exists():
        vs = C.read_json(vp)
        for g in vs.get('draft_virtual_store', []):
            if g.get('type') == 1:
                g['value'] = [{'child_id': it['id'], 'parent_id': ''} for it in items]
            elif g.get('type') != 0:
                g['value'] = []
        C.write_json(vp, vs, compact=True)
    (stage / 'draft_settings').write_text(f'[General]\ncloud_last_modify_platform={C.capcut_platform()}\ndraft_create_time={now}\n'
                                          f'draft_last_edit_time={now}\nreal_edit_seconds=0\nreal_edit_keys=0\n', 'utf-8')
    if cover_src:
        try:
            C.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{cover_src[1]:.3f}', '-i', cover_src[0], '-frames:v', '1',
                   '-vf', 'scale=720:-2', stage / 'draft_cover.jpg'])
        except Exception as e:
            print('[주의] 표지 이미지 만들기 실패(무시해도 됨):', str(e)[:120])
    (stage / MARKER).write_text('capcut_build.py 가 만든 스테이징 폴더입니다. CapCut 설치 때 이 파일은 복사되지 않습니다.\n', 'utf-8')


def install(stage, cc, name, backup_root):
    """스테이징 → CapCut 프로젝트 폴더 등록. 실패하면 아무것도 덮어쓰지 않는다."""
    if C.capcut_running():
        print('[거부] CapCut이 켜져 있습니다. CapCut을 완전히 끈 뒤 다시 --install 해 주세요(스테이징은 그대로 있음).')
        return 2
    dest = cc / name
    catalog = cc / 'root_meta_info.json'
    if not catalog.exists():
        print(f'[거부] 프로젝트 목록 파일이 없습니다: {catalog}. CapCut에서 프로젝트를 하나 만든 뒤 다시 해 주세요.')
        return 3
    raw = catalog.read_bytes()
    before = hashlib.sha256(raw).hexdigest()
    try:
        cat = json.loads(raw.decode('utf-8-sig'))
    except Exception:
        print('[거부] root_meta_info.json 을 읽을 수 없습니다(이 CapCut 버전은 지원하지 않음).')
        return 3
    store = cat.get('all_draft_store')
    if not isinstance(store, list) or not store:
        print('[거부] root_meta_info.json 형식이 예상과 다릅니다.')
        return 3
    if dest.exists() or any(x.get('draft_name') == name for x in store):
        print(f'[거부] 같은 이름의 프로젝트가 이미 있습니다: {name}. 덮어쓰지 않습니다. 새 이름(예: _v002)으로 다시 만드세요.')
        return 3
    meta = C.read_json(stage / 'draft_meta_info.json')
    dn = C.draft_file(stage).name
    backup = Path(backup_root) / time.strftime('%Y%m%d_%H%M%S')
    backup.mkdir(parents=True, exist_ok=True)
    (backup / 'root_meta_info.json').write_bytes(raw)
    entry = copy.deepcopy(store[0])
    entry.update(draft_id=meta['draft_id'], draft_name=name, draft_fold_path=dest.as_posix(), draft_root_path=cc.as_posix(),
                 draft_cover=dest.as_posix() + '/draft_cover.jpg', draft_json_file=dest.as_posix() + '/' + dn,
                 tm_draft_create=meta.get('tm_draft_create', C.now_us()), tm_draft_modified=C.now_us(),
                 tm_duration=meta.get('tm_duration', 0), draft_timeline_materials_size=meta.get('draft_timeline_materials_size_', 0),
                 draft_is_invisible=False, draft_cloud_last_action_download=False)
    old = copy.deepcopy(store)
    cat['all_draft_store'] = [entry] + old
    shutil.copytree(stage, dest, ignore=shutil.ignore_patterns(MARKER))
    if C.capcut_running() or C.sha256(catalog) != before:
        print(f'[중단] 복사하는 동안 CapCut이 켜졌거나 목록이 바뀌었습니다. 목록 등록은 하지 않았습니다(폴더만 복사됨): {dest}')
        return 4
    tmp = cc / 'root_meta_info.install.tmp'
    tmp.write_text(json.dumps(cat, ensure_ascii=False, separators=(',', ':')), 'utf-8')
    os.replace(tmp, catalog)
    after = json.loads(catalog.read_text('utf-8-sig'))
    ok = (after['all_draft_store'][0]['draft_id'] == meta['draft_id'] and after['all_draft_store'][1:] == old
          and C.sha256(dest / dn) == C.sha256(stage / dn))
    print(('설치 완료: ' if ok else '[확인 실패] ') + str(dest))
    print(f'  목록 백업: {backup / "root_meta_info.json"}')
    return 0 if ok else 5


def place_overlays(b, items, timeline, total, media, main_scale, cv, TW_fix, TW_raw, base_dir, shift=lambda x: x, bumper=None):
    """덧입히기 목록을 트랙에 얹는다. 돌려주는 것: 실제로 놓인 자리 목록(_timeline.json 에 남김).
    shift: 범퍼 없는 편집본 시각("at"·"end"·"near") → 범퍼를 끼운 시각. bumper: 화면을 덮으면 안 되는 범퍼 자리."""
    def room(st):
        """범퍼 앞에서 시작한 화면 덧입히기가 범퍼를 덮지 않도록 남은 길이."""
        return bumper['start'] - st if bumper and st < bumper['start'] else math.inf
    def resolve(p):
        p = Path(p)
        if p.is_absolute():
            return p
        for root in (Path.cwd(), base_dir):
            if (root / p).exists():
                return (root / p).resolve()
        return (Path.cwd() / p).resolve()

    def src_to_edit(x):
        for r in timeline:
            if r['src_in'] <= x < r['src_out']:
                return r['start'] + (x - r['src_in'])
        nxt = [r for r in timeline if r['src_in'] >= x]
        return nxt[0]['start'] if nxt else total

    def anchor(o, k_at, k_src, k_word):
        if o.get(k_at) is not None:
            return shift(float(o[k_at]))
        if o.get(k_src) is not None:
            return src_to_edit(float(o[k_src]))
        if o.get(k_word):
            near = shift(float(o['near'])) if o.get('near') is not None else None
            if near is None and o.get('near_src') is not None and k_word == 'word':
                near = src_to_edit(float(o['near_src']))     # 원본 시각 힌트 → 편집본 시각(같은 말이 여러 번일 때)
            for W in (TW_fix, TW_raw):
                t = find_word(W, o[k_word], near, int(o.get('nth', 1)))
                if t is not None:
                    return t
            return 'missing'
        return None

    prio = {'zoom': 0, 'broll': 0.5, 'motion': 1, 'text': 2, 'sfx': 3, 'bgm': 4}   # 트랙 쌓는 순서(뒤가 위)
    order = sorted(range(len(items)), key=lambda i: (prio.get(items[i].get('type'), 9), i))
    broll_starts = []            # B롤끼리 겹치지 않게 다음 B롤 시작에서 자른다
    for o in items:
        if o.get('type') == 'broll':
            t = anchor(o, 'at', 'src', 'word')
            if isinstance(t, float):
                broll_starts.append(max(0.0, t + float(o.get('offset', 0.0))))
    placed, miss = [], []
    for i in order:
        o = items[i]
        typ = o.get('type')
        st = anchor(o, 'at', 'src', 'word')
        if st == 'missing' or st is None:
            miss.append(f'{i + 1}번 {typ}: ' + (f'낱말 "{o.get("word")}"을 편집본에서 못 찾음' if st == 'missing' else '시작 시각(at/src/word) 없음'))
            continue
        st = max(0.0, st + float(o.get('offset', 0.0)))
        en = anchor(o, 'end', 'end_src', 'end_word')
        if en == 'missing':
            en = None
        dur = float(o['dur']) if o.get('dur') is not None else (en - st if en is not None else None)
        rec = dict(n=i + 1, type=typ, start=round(st, 3), note=o.get('note', ''))
        if st >= total:
            miss.append(f'{i + 1}번 {typ}: 시작 {st:.2f}초가 편집본 길이({total:.2f}초) 밖')
            continue

        if typ == 'sfx':
            f = resolve(o['file'])
            if not f.exists():
                miss.append(f'{i + 1}번 sfx: 파일 없음 {f}')
                continue
            fi = C.media_info(f)
            src0 = float(o.get('from', 0.0))
            du = min(dur or (fi['duration'] - src0), fi['duration'] - src0, total - st)
            if du <= 0.02:
                miss.append(f'{i + 1}번 sfx: 길이 0')
                continue
            db = float(o.get('db', -20))
            name = b.free_track('효과음', 'audio', C.us(st), C.us(du))
            b.put_audio(name, f, C.us(st), C.us(du), C.us(src0), round(10 ** (db / 20), 4))
            rec.update(track=name, dur=round(du, 3), file=f.as_posix(), db=db)

        elif typ == 'bgm':
            f = resolve(o['file'])
            if not f.exists():
                miss.append(f'{i + 1}번 bgm: 파일 없음 {f}')
                continue
            fi = C.media_info(f)
            end = min(total, st + dur) if dur else total
            db = float(o.get('db', -40))
            name = b.free_track('BGM', 'audio', C.us(st), C.us(end - st))
            t, k = st, 0
            while end - t > 0.05:
                du = min(fi['duration'], end - t)
                b.put_audio(name, f, C.us(t), C.us(du), 0, round(10 ** (db / 20), 4))
                t += du
                k += 1
            rec.update(track=name, dur=round(end - st, 3), file=f.as_posix(), db=db, clips=k)

        elif typ == 'broll':
            f = resolve(o['file'])
            if not f.exists():
                miss.append(f'{i + 1}번 broll: 파일 없음 {f}')
                continue
            fi = C.media_info(f)
            if fi['kind'] != 'video':
                miss.append(f'{i + 1}번 broll: 영상 파일이 아님 {f.name}')
                continue
            src0 = max(0.0, float(o.get('in', 0.0)))
            want = dur if dur is not None else (float(o['out']) - src0 if o.get('out') is not None else 4.0)
            nxt = min((x for x in broll_starts if x > st + 1e-3), default=total)
            du = min(want, fi['duration'] - src0, total - st, nxt - st, room(st))
            if du < 0.3:
                miss.append(f'{i + 1}번 broll: 길이 {du:.2f}초(파일 길이·다음 B롤·편집본 끝에 막힘)')
                continue
            crop = o.get('crop')
            cw, ch = fi['width'], fi['height']
            if crop:
                x0, y0, x1, y1 = [float(v) for v in crop]
                if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                    miss.append(f'{i + 1}번 broll: crop은 [x0, y0, x1, y1], 0~1 사이')
                    continue
                cw, ch = cw * (x1 - x0), ch * (y1 - y0)
            z = max(1.0, float(o.get('scale', 1.0)))
            fit = min(cv['width'] / cw, cv['height'] / ch)
            sc = round(max(cv['width'] / (cw * fit), cv['height'] / (ch * fit)) * z, 4)   # 화면 채움 × 배율
            rw, rh = cw * fit * sc / cv['width'], ch * fit * sc / cv['height']           # 화면 대비 크기(1 = 꽉 참)
            px, py = (float(o.get('x', 0.5)) - 0.5) * 2, (0.5 - float(o.get('y', 0.5))) * 2
            tx = max(-(rw - 1), min(rw - 1, -px * rw))      # 중심을 가운데 쪽으로, 화면 밖 검은 띠는 생기지 않게
            ty = max(-(rh - 1), min(rh - 1, -py * rh))
            sound = bool(o.get('sound'))
            name = b.free_track('B롤', 'video', C.us(st), C.us(du))
            s = b.put_video(name, f, C.us(st), C.us(du), C.us(src0), sc,
                            round(10 ** (float(o.get('db', -20)) / 20), 4) if sound else 0.0, crop=crop)
            s['clip']['transform'] = dict(x=round(tx, 4) + 0.0, y=round(ty, 4) + 0.0)
            fade = min(float(o.get('fade', 0.0)), du / 3)
            if fade > 0:                          # 영상 클립 키프레임 시각은 원본 기준(source start 포함)
                off, d = C.us(src0), C.us(du)
                s['common_keyframes'] = [kf('KFTypeAlpha', [(off, 0.0), (off + C.us(fade), 1.0), (off + d - C.us(fade), 1.0), (off + d, 0.0)])]
            rec.update(track=name, dur=round(du, 3), file=f.as_posix(), asset_id=o.get('asset_id', ''), src_in=round(src0, 3),
                       src_out=round(src0 + du, 3), scale=round(z, 3), x=float(o.get('x', 0.5)), y=float(o.get('y', 0.5)),
                       crop=crop, muted=not sound, fade=round(fade, 3), shortened=round(want - du, 3) if want - du > 0.05 else 0)

        elif typ == 'motion':
            f = resolve(o['file'])
            if not f.exists():
                miss.append(f'{i + 1}번 motion: 파일 없음 {f}')
                continue
            fi = C.media_info(f)
            du = min(dur or fi['duration'], fi['duration'], total - st, room(st))
            if room(st) < 0.3:
                miss.append(f'{i + 1}번 motion: 범퍼 {room(st):.2f}초 앞에서 시작해 넣지 않음')
                continue
            name = b.free_track('모션', 'video', C.us(st), C.us(du))
            sc = cover_scale(fi, cv) * float(o.get('scale', 1.0))
            s = b.put_video(name, f, C.us(st), C.us(du), 0, sc, 1.0 if o.get('sound') else 0.0)
            fade = min(float(o.get('fade', 0.2)), du / 3)
            if fade > 0:
                d = C.us(du)
                s['common_keyframes'] = [kf('KFTypeAlpha', [(0, 0.0), (C.us(fade), 1.0), (d - C.us(fade), 1.0), (d, 0.0)])]
            rec.update(track=name, dur=round(du, 3), file=f.as_posix())

        elif typ == 'text':
            du = min(dur or 1.5, total - st, room(st))
            if room(st) < 0.2:
                miss.append(f'{i + 1}번 text: 범퍼 {room(st):.2f}초 앞에서 시작해 넣지 않음')
                continue
            name = b.free_track('강조 글자', 'text', C.us(st), C.us(du))
            b.put_text(name, str(o['text']), C.us(st), C.us(du),
                       emphasis=(float(o.get('x', 0.5)), float(o.get('y', 0.5)), float(o.get('size', 1.6))))
            rec.update(track=name, dur=round(du, 3), text=o['text'])

        elif typ == 'zoom':
            du = min(dur or 2.5, total - st)
            en = st + du
            z = float(o.get('scale', 1.3))
            ramp = max(0.0, min(float(o.get('ramp', 0.3)), du / (2 if o.get('out', 'smooth') == 'smooth' else 1)))
            px, py = (float(o.get('x', 0.5)) - 0.5) * 2, (0.5 - float(o.get('y', 0.5))) * 2

            def clamp(v):
                return max(-(z - 1), min(z - 1, v))
            tx, ty = clamp(-z * px), clamp(-z * py)     # 가리킨 곳을 가운데 쪽으로, 화면 밖 검은 띠는 생기지 않게
            pts = [(st, 1.0, 0.0, 0.0), (st + ramp, z, tx, ty)]
            pts += [(en - ramp, z, tx, ty), (en, 1.0, 0.0, 0.0)] if o.get('out', 'smooth') == 'smooth' else [(en, z, tx, ty)]

            def at(t):
                for (t0, *v0), (t1, *v1) in zip(pts, pts[1:]):
                    if t0 <= t <= t1:
                        f = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
                        return [a_ + (b_ - a_) * f for a_, b_ in zip(v0, v1)]
                return pts[-1][1:] if t > pts[-1][0] else pts[0][1:]
            pieces = []
            for r in timeline:            # 줌 구간이 문장 클립 여러 개에 걸치면 클립마다 조각으로 얹는다
                p0, p1 = max(st, r['start']), min(en, r['start'] + r['dur'])
                if p1 - p0 < 0.04:
                    continue
                src0 = r['src_in'] + (p0 - r['start'])
                times = [p0] + [t for t, *_ in pts if p0 < t < p1] + [p1]
                name = b.free_track('줌', 'video', C.us(p0), C.us(p1) - C.us(p0))
                s = b.put_video(name, media, C.us(p0), C.us(p1) - C.us(p0), C.us(src0), main_scale * at(p0)[0], 0.0)
                off = C.us(src0)
                vals = [(off + C.us(t - p0), at(t)) for t in times]
                s['common_keyframes'] = [kf('KFTypeScaleX', [(t, main_scale * v[0]) for t, v in vals]),
                                         kf('KFTypeScaleY', [(t, main_scale * v[0]) for t, v in vals]),
                                         kf('KFTypePositionX', [(t, v[1]) for t, v in vals]),
                                         kf('KFTypePositionY', [(t, v[2]) for t, v in vals])]
                pieces.append(name)
            rec.update(track=pieces[0] if pieces else '', dur=round(du, 3), scale=z, pieces=len(pieces))
        else:
            miss.append(f'{i + 1}번: 모르는 종류 "{typ}" (sfx, zoom, broll, motion, text, bgm 중 하나)')
            continue
        placed.append(rec)

    placed.sort(key=lambda r: r['start'])
    cnt = {}
    for r in placed:
        cnt[r['type']] = cnt.get(r['type'], 0) + 1
    print(f'덧입히기 {len(placed)}개: ' + ', '.join(f'{k} {v}' for k, v in cnt.items()))
    for m in miss:
        print('  [못 넣음]', m)
    # 규칙 점검: 효과음은 본편 1분에 보통 1~2개, 많아도 5개(rules.md 6장)
    sfx = [r['start'] for r in placed if r['type'] == 'sfx']
    if sfx and total >= 30:
        rate = len(sfx) / (total / 60)
        busiest = max(sum(1 for y in sfx if x <= y < x + 60) for x in sfx)
        if busiest > 5 or (total >= 120 and rate > 3):
            print(f'  [규칙 점검] 효과음이 1분에 평균 {rate:.1f}개, 가장 많은 1분에 {busiest}개입니다. '
                  f'기준(본편 1분에 1~2개, 많아도 5개)보다 많습니다. 줄일지 사용자에게 물어보세요.')
    zooms = [r['start'] for r in placed if r['type'] == 'zoom']
    if len(zooms) >= 2 and min(b_ - a_ for a_, b_ in zip(zooms, zooms[1:])) < 4:
        print('  [규칙 점검] 4초 안에 줌이 두 번 있습니다. 줌은 잦지 않게(rules.md 8장).')
    br = [r for r in placed if r['type'] == 'broll']
    if br and total > 0:
        share = sum(r['dur'] for r in br) / total
        if share > 0.35:
            print(f'  [규칙 점검] B롤이 편집본의 {share:.0%}를 덮습니다. 토킹헤드는 얼굴·시범·본인 영상이 주인공이고 스톡은 보조입니다'
                  f'(references/channel-profile.md 4). 줄일지 사용자에게 물어보세요.')
        ids = [r['asset_id'] for r in br if r.get('asset_id')]
        dup = sorted({x for x in ids if ids.count(x) > 1})
        if dup:
            print(f'  [규칙 점검] 같은 B롤을 여러 번 씁니다: {", ".join(dup)}')
    return placed


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='컷 계획 → CapCut 프로젝트 조립')
    ap.add_argument('--template', required=True, help='형식을 복제할 기존 CapCut 프로젝트 이름(또는 프로젝트 폴더 경로)')
    ap.add_argument('--plan', required=True, help='cut_plan.py 가 만든 plan.json')
    ap.add_argument('--media', required=True, help='원본 영상(또는 음성) 파일')
    ap.add_argument('--name', required=True, help='새 프로젝트 이름(기존 이름과 겹치면 안 됨)')
    ap.add_argument('--voice', help='따로 녹음한 마이크 파일(원본과 같은 시각). 주면 영상 소리는 끈다')
    ap.add_argument('--voice-offset', type=float, default=0.0, help='마이크 시각 = 원본 시각 + 이 값(초)')
    ap.add_argument('--media-db', type=float, default=None, help='영상 클립 소리 크기(dB). --voice 를 주면 기본은 끔')
    ap.add_argument('--crop', help='메인 원본 잘라내기 "x0,y0,x1,y1"(원본 비율 0~1). 인물을 가운데로. frame_check.py 가 값을 알려 줌')
    ap.add_argument('--rotate', type=float, default=0.0,
                    help='메인 원본 회전(도, + = 시계 방향). 수평 맞추기. 모서리 빈틈이 안 보이게 배율을 자동으로 키움')
    ap.add_argument('--words', help='words.json(transcribe.py 결과). 없으면 plan.json 옆 또는 plan 안 단어를 쓴다')
    ap.add_argument('--subtitles', action='store_true', help='의미 단위 자막(텍스트 클립 + SRT)을 넣는다')
    ap.add_argument('--replace', action='append', default=[],
                    help='자막 표기 고치기 JSON 파일 {"틀린 말": "고칠 말", ...} 또는 채널 공용 사전(entries). 여러 번 주면 앞 파일이 이긴다')
    ap.add_argument('--listen', help='같은 컷 계획의 listen_check.py 결과(<이름>.txt). [자막 점검]이 뺀 낱말이 편집본 다시 받아쓰기에 '
                                     '옆 낱말과 붙어 있으면 되살린다(클립 받아쓰기가 놓친 진짜 말)')
    ap.add_argument('--edit-words', help='편집본 소리를 다시 받아쓴 낱말 JSON(편집본 시각: listen_check 의 wav → transcribe.py → '
                                         'script_check.py 의 words_script.json). 주면 자막을 이것으로 만든다(권장)')
    ap.add_argument('--script', help='대본 파일(.md/.txt). 자막 글자를 대본 표기로 맞춘다')
    ap.add_argument('--overlays', help='효과음·줌·모션 카드·강조 글자·배경음 목록 JSON(형식은 맨 위 설명)')
    ap.add_argument('--capcut-dir', help='CapCut 프로젝트 폴더(자동으로 못 찾을 때)')
    ap.add_argument('--staging', help='스테이징 폴더(기본: plan.json 옆 capcut_staging)')
    ap.add_argument('--bumper', help='채널 범퍼 영상(소리 포함 가능). --bumper-src 자리에 메인 트랙으로 끼우고 뒤 내용을 민다')
    ap.add_argument('--bumper-src', type=float, help='범퍼를 끼울 원본 초. 이 시각 이후에 시작하는 첫 클립 앞에 들어간다')
    ap.add_argument('--bumper-db', type=float, default=-8.0, help='범퍼 소리 크기(dB, 기본 -8)')
    ap.add_argument('--install', action='store_true', help='CapCut 프로젝트 목록에 등록(CapCut을 끈 상태에서만)')
    a = ap.parse_args()

    C.need_ffmpeg()
    if re.search(r'[\\/:*?"<>|]', a.name) or not a.name.strip():
        C.die('프로젝트 이름에 \\ / : * ? " < > | 는 쓸 수 없습니다.')
    plan_path = Path(a.plan).resolve()
    plan = C.read_json(plan_path)
    segs = plan['segments'] if isinstance(plan, dict) else plan
    segs = [s for s in segs if float(s['src_out']) - float(s['src_in']) > 0.04]
    if not segs:
        C.die('plan.json 에 남길 구간이 없습니다.')
    media = Path(a.media).resolve()
    if not media.exists():
        C.die(f'원본이 없습니다: {media}')
    info = C.media_info(media)
    if info['kind'] == 'photo':
        C.die('--media 는 영상 또는 음성 파일이어야 합니다.')
    if info['has_video'] and max(info['width'], info['height']) > 2200:
        print(f'[주의] 원본이 {info["width"]}x{info["height"]}로 큽니다. 화면 녹화처럼 키프레임 간격이 길면 CapCut 미리보기가 끊길 수 있습니다.\n'
              f'  편집용 사본 예: ffmpeg -i 원본.mp4 -vf scale=1920:-2 -c:v libx264 -crf 18 -g 15 -c:a copy 원본_edit.mp4')
    voice = Path(a.voice).resolve() if a.voice else None
    if voice and not voice.exists():
        C.die(f'--voice 파일이 없습니다: {voice}')
    bump_path = binfo = None
    if a.bumper or a.bumper_src is not None:
        if not (a.bumper and a.bumper_src is not None):
            C.die('범퍼는 --bumper(파일)와 --bumper-src(끼울 원본 초)를 함께 주세요.')
        bump_path = Path(a.bumper).resolve()
        if not bump_path.exists():
            C.die(f'--bumper 파일이 없습니다: {bump_path}')
        binfo = C.media_info(bump_path)
        if not binfo['has_video'] or not info['has_video']:
            C.die('범퍼와 원본 모두 영상이어야 합니다.')

    cc = C.find_capcut_dir(a.capcut_dir, required=a.install or not Path(a.template).exists())
    tpl_dir = C.resolve_project(a.template, a.capcut_dir)
    tpl = Template(tpl_dir)
    if info['has_video'] and not tpl.vid:
        C.die('템플릿 프로젝트에 영상 클립이 없습니다. 영상이 들어 있는 프로젝트를 템플릿으로 고르세요.')
    need_audio = bool(voice) or not info['has_video']
    if need_audio and not tpl.aud:
        C.die('템플릿 프로젝트에 오디오 클립(로컬 음성 파일)이 없습니다. 효과음·음성 파일을 올려 둔 프로젝트를 고르세요.')
    if need_audio and tpl.aud_converted:
        print('[주의] 템플릿에 로컬 파일 오디오가 없어 라이브러리 소리 형식을 로컬 형식으로 바꿔 씁니다(effect_id 비움).')
    if a.subtitles and not tpl.txt:
        C.die('템플릿 프로젝트에 텍스트(자막) 클립이 없습니다. 자막이 들어 있는 프로젝트를 템플릿으로 고르세요.')
    overlays = []
    if a.overlays:
        ov = C.read_json(a.overlays)
        overlays = ov.get('items', []) if isinstance(ov, dict) else ov
        types = {o.get('type') for o in overlays}
        if types & {'sfx', 'bgm'} and not tpl.aud:
            C.die('효과음·배경음을 넣으려면 템플릿 프로젝트에 로컬 음성 파일 클립이 하나 있어야 합니다.')
        if 'text' in types and not tpl.txt:
            C.die('강조 글자를 넣으려면 템플릿 프로젝트에 텍스트 클립이 하나 있어야 합니다.')
        if types & {'zoom', 'broll'} and not info['has_video']:
            C.die('줌·B롤은 영상 원본에만 쓸 수 있습니다.')
    print(f'템플릿: {tpl_dir.name} (읽기만 함)')

    b = Builder(tpl)
    D = b.D
    cv = canvas_for(info, D.get('canvas_config', {})) if info['has_video'] else D.get('canvas_config', {})
    D['canvas_config'] = cv
    scale = cover_scale(info, cv) if info['has_video'] else 1.0
    if info['has_video'] and (a.crop or a.rotate):
        crop = tuple(float(v) for v in a.crop.split(',')) if a.crop else None
        if crop and not (len(crop) == 4 and 0 <= crop[0] < crop[2] <= 1 and 0 <= crop[1] < crop[3] <= 1):
            C.die(f'--crop 은 "x0,y0,x1,y1"(0~1, x0<x1, y0<y1)로 주세요: {a.crop}')
        b.frame = (Path(media).resolve(), crop, round(a.rotate, 3))
        th = math.radians(abs(a.rotate))   # 회전한 화면이 캔버스를 덮도록 키울 배율
        scale *= math.cos(th) + max(cv['width'], cv['height']) / min(cv['width'], cv['height']) * math.sin(th)
        print(f'화면 맞춤: 잘라내기 {crop or "없음"} · 회전 {a.rotate:+.2f}° · 배율 {scale:.3f}')
    vol = 1.0 if not voice else 0.0
    if a.media_db is not None:
        vol = round(10 ** (a.media_db / 20), 4)
    vinfo = C.media_info(voice) if voice else None

    # ── 메인 트랙: 문장 클립 ───────────────────────────────
    t = 0.0
    timeline = []
    bumper = None          # 범퍼는 원본 시각이 없어 timeline(원본 ↔ 편집 대응표)에 넣지 않고 따로 남긴다
    for i, s in enumerate(segs):
        src_in = max(0.0, float(s['src_in']))
        src_out = min(float(s['src_out']), info['duration'] or float(s['src_out']))
        if src_out - src_in < 0.04:
            continue
        if bump_path and bumper is None and src_in >= a.bumper_src - 0.05:
            b0, b1 = C.us(t), C.us(t + binfo['duration'])
            b.put_video('메인', bump_path, b0, b1 - b0, 0, cover_scale(binfo, cv),
                        round(10 ** (a.bumper_db / 20), 4) if binfo['has_audio'] else 0.0)
            bumper = dict(start=round(b0 / C.US, 3), dur=round((b1 - b0) / C.US, 3), file=bump_path.as_posix(),
                          before_clip=len(timeline) + 1, src=round(src_in, 3), db=a.bumper_db)
            t = b1 / C.US
        st_us = C.us(t)
        en_us = C.us(t + (src_out - src_in))
        dur_us = en_us - st_us
        if info['has_video']:
            b.put_video('메인', media, st_us, dur_us, C.us(src_in), scale, vol)
            if voice:
                v_in = src_in + a.voice_offset
                if 0 <= v_in and v_in + (src_out - src_in) <= vinfo['duration'] + 0.05:
                    b.put_audio('보이스', voice, st_us, dur_us, C.us(v_in), 1.0)
                else:
                    print(f'[주의] {i + 1}번 클립은 마이크 파일 범위를 벗어나 보이스를 넣지 못했습니다.')
        else:
            b.put_audio('보이스', media, st_us, dur_us, C.us(src_in), 1.0)
        timeline.append(dict(n=len(timeline) + 1, start=round(st_us / C.US, 3), dur=round(dur_us / C.US, 3),
                             src_in=round(src_in, 3), src_out=round(src_out, 3), text=s.get('text', '')))
        t = en_us / C.US
    total = t
    if bump_path and bumper is None:
        C.die(f'--bumper-src {a.bumper_src}초 이후에 시작하는 클립이 없습니다(마지막 클립 원본 {timeline[-1]["src_out"]}초).')

    def shift(x):
        """범퍼 없는 편집본 시각 → 범퍼를 끼운 편집본 시각."""
        return x + bumper['dur'] if bumper and x >= bumper['start'] - 1e-6 else x
    if bumper:
        print(f'범퍼: 편집본 {C.mmss(bumper["start"])}에 {bumper["dur"]:.2f}초({bump_path.name}, {bumper["db"]:+.0f}dB) · '
              f'{bumper["before_clip"]}번 클립(원본 {bumper["src"]:.2f}초) 앞 · 뒤 내용 +{bumper["dur"]:.2f}초')

    # ── 편집본 단어(자막·덧입히기 박자용) ─────────────────────
    wpath = Path(a.words).resolve() if a.words else None
    if wpath is None:
        for cand in (plan_path.parent / 'words.json', plan_path.parent.parent / '01_asr' / 'words.json'):
            if cand.exists():
                wpath = cand
                break
    allw = load_words(wpath) if wpath else []
    TW = []
    swapped = 0
    picked = []                            # 클립마다 (낱말들, 클립을 따로 받아쓴 글)
    for s, row in zip(segs, timeline):
        a0, a1, t0 = row['src_in'], row['src_out'], row['start']
        ws = [w for w in allw if a0 <= (w[0] + w[1]) / 2 < a1]
        pw = [tuple(w) for w in (s.get('words') or [])]
        want = C.norm_text(s.get('text', ''))
        if pw:
            got = C.norm_text(''.join(w[2] for w in ws))
            if not ws or (want and difflib.SequenceMatcher(None, got, want).ratio() < 0.85):
                ws = [w for w in pw if a0 - 0.1 <= (w[0] + w[1]) / 2 < a1 + 0.1]   # 전체 받아쓰기가 이 구간을 놓치면 조각 받아쓰기로
                swapped += 1
        picked.append((list(ws), want))
    # 전체 받아쓰기는 쉼 앞뒤에서 낱말 시각이 밀려, 옆 문장(지운 테이크 포함)의 첫 낱말이 클립 끝에 딸려 오곤 한다
    # ("많잖아요 | 그런데" — "그런데"는 지운 재테이크의 첫 낱말). 클립 가장자리 낱말이 그 클립을 따로 받아쓴 글에 없으면
    # 앞뒤 클립으로 넘겨 보고, 거기에도 없으면 자막에서 뺀다.
    # 쉼만 줄인 틈(지운 말 없음)에 떨어진 낱말도 시각이 밀린 것이라 다음 클립 앞에 붙여 대조한다
    # ("출석 | 일수가 | 중요한…"에서 "일수가"가 줄인 쉼 안에 찍혀 빠졌다). 재테이크를 지운 틈의 낱말은 붙이지 않는다.
    removed = plan.get('removed', []) if isinstance(plan, dict) else []

    def pause_only(x0, x1):
        rs = [r for r in removed if r['src_in'] < x1 - 0.02 and r['src_out'] > x0 + 0.02]
        return all(r.get('reason', '') in ('긴 쉼 줄임', '끝 무음') for r in rs)
    gap_words, prev_end = [], None
    for row in timeline:
        a0 = row['src_in']
        gap_words.append([w for w in allw if prev_end <= (w[0] + w[1]) / 2 < a0]
                         if prev_end is not None and pause_only(prev_end, a0) else [])
        prev_end = row['src_out']
    dropped, carry = [], []
    for i, (ws, want) in enumerate(picked):
        lead, keep, tail = trim_edges(carry + gap_words[i] + ws, want)
        for w in lead:
            # 앞 클립 끝에 이미 같은 낱말이 있으면 넘기지 않는다("하루 한 번 | 한 번," → "한 번 한 번" 겹침, 2026-10-31)
            if i and picked[i - 1][1].endswith(C.norm_text(w[2])) and C.norm_text(w[2]) and \
                    not any(C.norm_text(x[2]) == C.norm_text(w[2]) for x in picked[i - 1][0][-2:]):
                picked[i - 1][0].append(w)
            else:
                dropped.append(w)
        picked[i] = (keep, want)
        carry = tail
    dropped += carry
    # 클립 받아쓰기가 놓친 진짜 말("그렇다면 | 옷 | 입었을 때"의 "옷")도 위에서 빠진다. 편집본을 다시 받아쓴 글에
    # 옆 낱말과 붙어 나오면 되살린다. 지운 테이크에서 딸려 온 낱말은 편집본 소리에 없어 붙어 나오지 않는다.
    if a.listen and dropped:
        rows = []
        for line in Path(a.listen).read_text('utf-8').splitlines():
            m = re.match(r'\s*([\d.]+)-\s*([\d.]+) \[src\s+[\d.]+\] (.*)', line)
            if m:
                rows.append((shift(float(m.group(1))), shift(float(m.group(2))), C.norm_text(m.group(3))))
        back = []
        for w in dropped:
            mid = (w[0] + w[1]) / 2
            nw = C.norm_text(w[2])
            # 낱말이 걸친 클립: 가운데가 든 클립 → 가장 많이 겹친 클립 → 0.6초 안의 가장 가까운 클립(컷 경계에 반쯤 걸린 낱말)
            k = next((k for k, row in enumerate(timeline) if row['src_in'] <= mid < row['src_out']), None)
            if k is None:
                ov = [(min(w[1], row['src_out']) - max(w[0], row['src_in']), k) for k, row in enumerate(timeline)]
                best = max(ov) if ov else (0, None)
                if best[0] > 0:
                    k = best[1]
                else:
                    gap, k = min(((max(row['src_in'] - mid, mid - row['src_out']), k) for k, row in enumerate(timeline)),
                                 default=(9.0, None))
                    k = k if gap <= 0.6 else None
            if k is None or not nw:
                continue
            row = timeline[k]
            t = row['start'] + min(row['src_out'], max(row['src_in'], mid)) - row['src_in']
            near = ''.join(r[2] for r in rows if r[1] >= t - 2.0 and r[0] <= t + 2.0)
            ws, want = picked[k]
            prev = [C.norm_text(x[2]) for x in ws if x[0] < w[0]]
            nxt = [C.norm_text(x[2]) for x in ws if x[0] > w[0]]
            heard = (prev and re.search(re.escape(prev[-1]) + '.?' + re.escape(nw), near)) or \
                    (nxt and re.search(re.escape(nw) + '.?' + re.escape(nxt[0]), near)) or \
                    (not prev and not nxt and len(nw) >= 2 and nw in near)
            # 클립을 따로 받아쓴 글이 이 낱말로 시작하거나 끝나는데 남은 낱말에는 없다(가운데가 경계 밖에 찍힌 경우)
            edge = len(nw) >= 2 and ((not prev and want.startswith(nw) and not (nxt and nxt[0].startswith(nw[:2])))
                                     or (not nxt and want.endswith(nw) and not (prev and prev[-1].endswith(nw[-2:]))))
            # 이미 자막에 있는 낱말(조각 받아쓰기 단어로 만든 클립은 같은 말이 다른 시각으로 들어 있다)이면 되살리지 않는다
            def et(j, x):                 # 편집본 시각(조각 받아쓰기 낱말은 원본 시각이 어긋나 있어 편집본에서 비교)
                r = timeline[j]
                return r['start'] + min(r['src_out'] - r['src_in'], max(0.0, x[0] - r['src_in']))
            tw = et(k, w)
            dup = any(C.norm_text(x[2]) and (C.norm_text(x[2]) in nw or nw in C.norm_text(x[2])) and abs(et(j, x) - tw) < 2.0
                      for j in range(len(picked)) for x in picked[j][0])
            if (heard or edge) and not dup:
                picked[k] = (sorted(ws + [w], key=lambda x: x[0]), want)
                back.append(w)
        if back:
            dropped = [w for w in dropped if w not in back]
            print(f'[자막 점검] 편집본 다시 받아쓰기({Path(a.listen).name})에 옆 낱말과 붙어 있어 되살린 낱말 {len(back)}개: '
                  + ', '.join(f'"{w[2].strip()}"(원본 {w[0]:.2f}초)' for w in sorted(back, key=lambda x: x[0])))
    for (ws, _), row in zip(picked, timeline):
        a0, a1, t0 = row['src_in'], row['src_out'], row['start']
        for w0, w1, w in ws:
            TW.append((t0 + min(a1 - a0, max(0.0, w0 - a0)), t0 + min(a1 - a0, max(0.05, w1 - a0)), w))
    TW.sort(key=lambda x: x[0])
    if dropped and not a.edit_words:
        print(f'[자막 점검] 클립을 따로 받아쓴 글과 맞지 않는 가장자리 낱말 {len(dropped)}개를 자막에서 뺐습니다'
              '(시각이 밀려 옆 문장에서 딸려 왔거나 이미 있는 낱말과 겹침): '
              + ', '.join(f'"{w[2].strip()}"(원본 {w[0]:.2f}초)' for w in sorted(dropped)))
    if a.edit_words:
        # 편집본 소리를 다시 받아쓴 낱말(편집본 시각)을 그대로 쓴다. 컷 경계마다 원본 받아쓰기 시각이 밀려
        # 첫 낱말이 빠지거나 겹치던 문제가 없다(2026-10-31). 원고 표기는 script_check.py 로 미리 맞춘다
        ew = load_words(Path(a.edit_words).resolve())
        if bumper:
            # 범퍼 없는 편집본을 받아쓴 시각이라 범퍼 뒤 낱말을 민다. 쉼 뒤 첫 낱말은 받아쓰기가 앞당겨 찍곤 해서
            # (본문 첫 낱말이 실제 시작보다 0.3초 일찍 찍힌 예) 경계를 넘어 끝나는 낱말도 범퍼 뒤로 보낸다
            g0, g1 = bumper['start'], bumper['start'] + bumper['dur']
            ew = [(max(w0 + bumper['dur'], g1), w1 + bumper['dur'], w) if w1 > g0 + 0.05 else (w0, w1, w) for w0, w1, w in ew]
        TW = sorted((max(0.0, w0), min(total, max(w0 + 0.05, w1)), w) for w0, w1, w in ew if C.norm_text(w) and w0 < total)
        print(f'자막 낱말: 편집본 다시 받아쓰기 {Path(a.edit_words).name} · {len(TW)}개(편집본 시각, 원본 받아쓰기 대조 안 함)')
    TW_fix = TW
    if a.script:
        sp = Path(a.script).resolve()
        if not sp.exists():
            C.die(f'--script 파일이 없습니다: {sp}')
        TW_fix, ratio = apply_script(TW, sp.read_text('utf-8-sig'))
        print(f'대본 맞추기: 받아쓰기 글자의 {ratio:.0%}가 대본과 일치. 대본에 없는 말은 받아쓰기 그대로 둠.')
        if ratio < 0.5:
            print('  [주의] 일치율이 낮습니다. 이 녹화와 다른 대본이거나 즉흥 멘트가 많습니다. 자막을 꼭 훑어보세요.')

    # ── 자막 ────────────────────────────────────────────
    cues = []
    if a.subtitles:
        print(f'자막 단어: {wpath if wpath else "plan.json 안 단어(조각 받아쓰기)"}')
        rep, ask = load_replace(a.replace)
        hits = {}
        cues = make_cues(TW_fix, rep, vetted=bool(a.edit_words), hits=hits)
        if hits:
            print('  자막 표기 고침: ' + ' · '.join(f'{w}→{rep[w]} {n}곳' for w, n in hits.items()))
        for w, r, why in ask:              # 진짜 낱말일 수 있어 바꾸지 않고 보여 준다
            for c in cues:
                if w in c[2]:
                    print(f'  [확인 필요] {C.mmss(c[0])} "{c[2]}" — "{w}"→"{r}"? ({why}) 맞으면 영상 고침 사전에 넣고 다시 조립')
        cues = [c for c in cues if c[0] < total]
        for c in cues:
            c[1] = min(c[1], total)
        if bumper:                         # 범퍼 화면에 자막이 남지 않게 한다
            g0, g1 = bumper['start'], bumper['start'] + bumper['dur']
            crossed = []
            for c in cues:
                if c[0] < g0 < c[1]:
                    if c[1] > g0 + 0.5:
                        crossed.append(c[2])
                    c[1] = g0
                elif g0 <= c[0] < g1:
                    crossed.append(c[2])
                    c[0], c[1] = g1, max(c[1], g1 + 0.3)
            if crossed:
                print(f'  [범퍼 점검] 범퍼에 걸친 자막 {len(crossed)}개를 범퍼 밖으로 옮겼습니다. 범퍼 자리가 문장 중간인지 확인: '
                      + ' / '.join(crossed))
        for c0, c1, txt in cues:
            b.put_text('자막', txt, C.us(c0), C.us(c1) - C.us(c0))
        if swapped:
            print(f'  {swapped}개 클립은 전체 받아쓰기와 내용이 달라 조각 받아쓰기 단어로 자막을 만들었습니다.')

    # ── 덧입히기: 줌 → B롤 → 모션 카드 → 강조 글자 → 효과음 → 배경음 (트랙 쌓는 순서) ──
    placed = place_overlays(b, overlays, timeline, total, media, scale, cv, TW_fix, TW,
                            Path(a.overlays).resolve().parent, shift, bumper) if overlays else []

    # ── 정리 ────────────────────────────────────────────
    for x in D['tracks']:
        x['segments'].sort(key=lambda s: s['target_timerange']['start'])
    order = {'video': 0, 'text': 1, 'audio': 2}
    D['tracks'].sort(key=lambda x: order.get(x['type'], 9))
    for i, x in enumerate(D['tracks']):
        for s in x['segments']:
            s['track_render_index'] = i
            s['render_index'] = i if x['type'] in ('video', 'text') else 0
    cc_root = cc if cc else Path(tpl_dir).parent
    dest = cc_root / a.name
    now = int(time.time())
    D.update(id=uid(), name=a.name, duration=C.us(total), path=dest.as_posix(), create_time=now, update_time=now,
             static_cover_image_path='', keyframe_graph_list=[], time_marks=None, relationships=[], group_container=None,
             cover=None, retouch_cover=None)
    D['keyframes'] = {k: [] for k in D.get('keyframes', {})} if isinstance(D.get('keyframes'), dict) else D.get('keyframes')
    fai = D.get('function_assistant_info')
    if isinstance(fai, dict):
        for k, v in fai.items():
            if isinstance(v, list):
                fai[k] = []

    stage_root = Path(a.staging).resolve() if a.staging else plan_path.parent / 'capcut_staging'
    stage = stage_root / a.name
    stage_root.mkdir(parents=True, exist_ok=True)
    media_paths = [media] + ([voice] if voice else []) + ([bump_path] if bumper else []) + \
        sorted({p['file'] for p in placed if p.get('file')})
    write_staging(b, tpl, stage, a.name, dest, media_paths, (media, segs[0]['src_in'] + 0.5) if info['has_video'] else None)
    if cues:
        (stage_root / f'{a.name}.srt').write_text('\n'.join(f'{k + 1}\n{srt_time(c0)} --> {srt_time(c1)}\n{txt}\n'
                                                            for k, (c0, c1, txt) in enumerate(cues)), 'utf-8-sig')
    C.write_json(stage_root / f'{a.name}_timeline.json', dict(name=a.name, media=media.as_posix(), total=round(total, 3),
                                                              clips=timeline, subtitles=[[round(x, 3), round(y, 3), z] for x, y, z in cues],
                                                              overlays=placed, bumper=bumper))
    ntr = {x['name']: len(x['segments']) for x in D['tracks']}
    print(f'조립 완료: {a.name} · 길이 {C.mmss(total)} · 트랙 {ntr} · 캔버스 {cv.get("width")}x{cv.get("height")} · 화면 배율 {scale}')
    print(f'  스테이징: {stage}')
    if cues:
        print(f'  자막 {len(cues)}개 · 최대 {max(len(c[2]) for c in cues)}자 · SRT: {stage_root / (a.name + ".srt")}')
    if a.install:
        if cc is None:
            C.die('CapCut 프로젝트 폴더를 찾지 못해 설치할 수 없습니다(--capcut-dir).')
        sys.exit(install(stage, cc, a.name, stage_root / 'backups'))
    else:
        print('  CapCut 등록은 아직 안 했습니다. CapCut을 끈 뒤 같은 명령에 --install 을 붙이면 등록합니다.')


if __name__ == '__main__':
    main()
