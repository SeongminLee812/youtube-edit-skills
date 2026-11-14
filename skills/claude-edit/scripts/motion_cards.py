"""모션 카드 목록(JSON) 하나로 채널 모션 카드를 렌더합니다(claude-edit S3 모션).

예시 영상 make_v4.py·make_v5.py처럼 영상마다 손으로 짜던 렌더 스크립트를 일반화했다. 영상마다 바뀌는 것은 카드 목록뿐이다.
엔진은 smartdaddy scripts/render_motion.py + motion/cards_channel.html(밝은) 또는 motion/cards.html(어두운 유리, profile.md motion_style). 색·글꼴은 profile.md.

카드마다: 검사 → (알파 카드) 그 시각 촬영 프레임을 _bg/에 뽑기 → 렌더 → 정지 프레임 → 알파 MOV 모든 프레임 안전영역 검사.
  - 알파 카드(place=glass·side·split): <id>_alpha.mov(ProRes 4444) · _black.mp4 · _preview.mp4/jpg(배경 합성) · _alpha.png · _safe.json
  - 전체 화면 카드(place=full): <id>.mp4(끝 0.5초 멈춤)
  - 안전영역 검사에서 떨어지면 그 카드 폴더를 _rejected/<id>_<시각>/으로 옮기고 끝에 실패로 알린다(다음 실행 때 다시 렌더).
끝에(렌더한 카드가 없어도) 출력 폴더에 _render_log.json(누적) · 파일_목록.json · 연락표.jpg · augment_items.json ·
판단_기록.md(없을 때만 뼈대)를 쓴다. augment_items.json 은 capcut_augment.py --spec 형식이다:
replaces 가 있는 카드 → replace_media(같은 자리 교체), 없고 src 가 있으면 → items(원본 시각에 새로 얹기).

렌더 전 검사(하나라도 걸리면 아무것도 렌더하지 않음):
  - 화면에 나갈 값의 금지 낱말: 메타 라벨(설명용·예시·참고용…), 출처 표기(출처·DOI·라이선스·스톡 회사…), 이전 채널명(CHANNEL NAME·채널).
    내용상 꼭 필요하면 카드에 "allow": ["예시"]처럼 적는다(기록에 남음).
  - 필수 값(toc items·hook title 등), 없는 kind, glass 는 toc·hook만, 시각(at·…at·stills)이 길이 안인지, id 중복, 모르는 칸(오타).
  - 길이 기본값: toc 3초 · hook 5초(사용자 확정). 나머지 종류는 dur 필수.

카드 목록 형식(templates/motion_cards.example.json 참고). 상대 경로는 영상 폴더 기준, '_'로 시작하는 칸은 설명(읽지 않음):
  {"video": "예시 영상",                  영상 폴더 또는 주제 ID(없으면 JSON 위치에서 <영상 폴더> · videos/<영상>을 찾음)
   "footage": "촬영본.MOV",         배경 프레임을 뽑을 촬영본(기본: <편집 폴더>/edit_state.json inputs.footage)
   "bg_crop": "0.034,0.017,1,0.983",  그 프레임 크롭 x0,y0,x1,y1 비율(기본: edit_state inputs.crop = 편집 화면). "rotate": 90|180|270
   "fps": 30, "subtitle_top": 886, "face_safe": "520,0,1400,620", "track": "v006 모션", "request": "사용자 지시 …",
   "chapters": ["장 제목1", "장 제목2", "장 제목3"],     toc 카드에 items가 없으면 이것을 쓴다(장 제목은 한 번만 적는다)
   "defaults": {"toc": {"at": 0.8}},                     종류별 공통 값(카드 값이 이긴다)
   "cards": [{"id": "v6_02_목차_01", "q": {"kind": "toc", "now": 1}, "src": 107.24, "cue": "1막 …"},
             {"id": "v6_01_도입질문", "q": {"kind": "hook", "title": "…", "items": ["3개월?", "6개월?"], "at": [1.3, 2.5]}, "src": 13.04},
             {"id": "v6_T1_제목", "q": "kind=title&title=두 번째 이야기&place=full", "dur": 3, "src": 41.11}]}
  q   : 템플릿 값. 객체면 목록을 '|'로 잇고 & 를 %26 으로 바꿔 쿼리로 만든다. 문자열이면 쿼리 그대로 쓴다.
        place 가 없으면 toc·hook → glass, title → full, 나머지 → side. 어두운 스타일(motion_style: dark, 원작 cards.html)은 모두 full.
        place 기본 덧붙임: glass·side·split → noscale=1(끝 0.45초 퇴장, 첫·끝 알파 0) · full → exit=0&noscale=1&bgin=0
  카드 칸: id · q · dur · src(원본 초: 덧입히기 자리·배경 시각) · bg(원본 초 또는 그림 경로. 기본 src+0.4×dur 을 0.5초 단위로)
          stills(정지 프레임 초, 없으면 자동: 등장 끝·요소 등장 직후·중간·퇴장 직전) · cue·line(대사) · replaces(바꿀 기존 파일)
          track · name(출력 파일 이름) · allow · face_safe · subtitle_top · why(판단_기록에 옮길 한 줄) · note

사용 예(프로젝트 루트에서):
  python <스킬 폴더>/claude-edit/scripts/motion_cards.py $W/모션카드_v6/cards.json        출력 = JSON 이 있는 폴더
  ($W = 편집 폴더: 영상 폴더 안 편집/ · tools/topic_paths.py)
  ... cards.json --only v6_02_목차_01 v6_05_목차_02 --force   다시 렌더(기존 카드 폴더는 _이전/으로 옮김)
  ... cards.json --dry-run                                     검사 + 실행할 명령만 출력(파일을 쓰지 않음)
  ... cards.json --out <스크래치 폴더>                         시험 렌더(영상 폴더에 쓰지 않음)
무거운 렌더 동안 프로젝트 루트 .edit_busy 를 지킨다(다른 작업의 표시가 있으면 --wait 초까지 기다림).
"""
import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(os.environ.get('PROJECT_ROOT') or os.getcwd()).resolve()     # 프로젝트 루트(PROJECT_ROOT 또는 작업 폴더)
SK = Path(__file__).resolve().parents[2] / 'smartdaddy-video-edit'
sys.path[:0] = [str(SK / 'scripts'), str(ROOT / 'tools')]
import _common as C  # noqa: E402
import topic_paths as TP  # noqa: E402   영상 폴더 안 단계 폴더
from _busy import FLAG, busy  # noqa: E402

W, H = 1920, 1080
PY = str(ROOT / '.venv' / 'bin' / 'python') if (ROOT / '.venv' / 'bin' / 'python').exists() else sys.executable
DUR = {'toc': 3.0, 'hook': 5.0}            # 사용자 확정(preferences.md 모션): 챕터 목차 3초 · 도입 질문 5초
PLACE = {'toc': 'glass', 'hook': 'glass', 'title': 'full'}
EXTRA = {'glass': {'noscale': '1'}, 'side': {'noscale': '1'}, 'split': {'noscale': '1'},     # 크기 변화 없이 이동·흐림만
         'full': {'exit': '0', 'noscale': '1', 'bgin': '0'}}                                 # 끝 0.5초 멈춤, 첫 프레임부터 바탕
NEED = {'toc': ['items'], 'hook': ['title'], 'steps': ['items'], 'number': [('to', 'value')], 'score': ['names', 'scores'],
        'title': ['title']}
FORMAT = {'glass': '반투명 알파 ProRes 4444 MOV(+검정 MP4 · 확인용 합성 MP4 · 투명 PNG)',
          'side': '얼굴 옆 알파 ProRes 4444 MOV(+검정 MP4 · 확인용 합성 MP4 · 투명 PNG)',
          'split': '오른쪽 패널 알파 ProRes 4444 MOV(+검정 MP4 · 확인용 합성 MP4 · 투명 PNG)', 'full': '전체 화면 H.264 MP4'}
NOT_TEXT = {'kind', 'place', 'side', 'y', 'img', 'avatar', 'bgimg'}     # 화면 글자가 아닌 값: 금지 낱말 검사에서 뺀다
# 화면에 나가면 안 되는 낱말(preferences.md 모션·출처, AGENTS.md). 한글은 띄어쓰기를 무시하고, 영문은 낱말 단위·대소문자 무시로 찾는다
FORBID = {
    '메타 라벨': ['설명용', '예시', '참고용', '참고 이미지', '이해를 돕기', '연출 이미지', '자료화면', 'AI 생성', 'AI로 만든'],
    '출처 표기': ['출처', 'DOI', 'doi.org', '라이선스', 'License', 'Licence', 'CC BY', 'CC0', '©', 'Source', 'Sources', 'Credit',
               'Credits', 'Courtesy', 'Pexels', 'Pixabay', 'Mixkit', 'Unsplash', 'Shutterstock', 'Getty'],
    '이전 채널명': [x.strip() for x in C.load_profile().get('old_channel_names', '').split(',') if x.strip()],
}
TOP_KEYS = {'video', 'footage', 'bg_crop', 'rotate', 'fps', 'subtitle_top', 'face_safe', 'track', 'request', 'chapters',
            'defaults', 'cards', 'template', 'assets', 'alpha_tol', 'note'}
CARD_KEYS = {'id', 'q', 'dur', 'src', 'bg', 'stills', 'cue', 'line', 'replaces', 'track', 'name', 'allow', 'face_safe',
             'subtitle_top', 'why', 'note', 'src_in'}


# ── 값 다루기 ─────────────────────────────────────────
def fmt_num(v):
    v = float(v)
    return str(int(v)) if v.is_integer() else repr(v)


def to_text(v):
    """객체 값 하나 → 쿼리 글자. 목록은 '|'로 잇고, & 는 %26(템플릿이 되돌림)."""
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, (int, float)):
        return fmt_num(v)
    if isinstance(v, list):
        return '|'.join(to_text(x) for x in v)
    if isinstance(v, dict):
        raise ValueError('값 안에 객체는 쓸 수 없습니다(쿼리 문자열로 적기)')
    return str(v).replace('&', '%26')


def parse_query(s):
    """'a=1&b=x|y' → [(a, 1), (b, x|y)] (순서 유지, 풀지 않음)."""
    pairs = []
    for part in str(s).split('&'):
        if part.strip():
            k, _, v = part.partition('=')
            pairs.append((k.strip(), v))
    return pairs


def times(v):
    """'1.3|2.5' · [1.3, 2.5] · 0.8 → [1.3, 2.5] · [0.8] (숫자가 아니면 건너뜀)."""
    out = []
    for x in (v if isinstance(v, list) else str(v).split('|')):
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            pass
    return out


def forbidden(text):
    low = ' '.join(str(text).split()).lower()
    flat = re.sub(r'\s+', '', low)
    hits = []
    for why, words in FORBID.items():
        for w in words:
            wl = w.lower()
            if re.fullmatch(r'[a-z0-9 .]+', wl):           # 영문: 낱말 단위, 사이 띄어쓰기는 있든 없든
                pat = r'(?<![a-z])' + r'\s*'.join(map(re.escape, wl.replace(' ', ''))) + r'(?![a-z])'
                if re.search(pat, low):
                    hits.append((why, w))
            elif re.sub(r'\s+', '', wl) in flat:
                hits.append((why, w))
    return hits


def template_kinds(html):
    m = re.search(r'const KINDS = (\{.*?\});\n', html.read_text('utf-8'))
    return re.findall(r'(?:\{|,)\s*(\w+):', m.group(1)) if m else []


def rel(p, *bases):
    p = Path(os.path.abspath(p))                 # 링크(.venv/bin/python 등)는 풀지 않는다
    for b in bases:
        if b:
            try:
                return p.relative_to(os.path.abspath(b)).as_posix()
            except ValueError:
                pass
    return str(p)


# ── 카드 목록 읽기·검사 ────────────────────────────────
class Spec:
    def __init__(self, path, a):
        self.path = path
        self.raw = C.read_json(path)
        self.errors, self.warns = [], []
        r = self.raw
        self.V = self.find_video(r.get('video'))
        self.out = Path(a.out).expanduser().resolve() if a.out else path.parent
        state = {}
        es = TP.part(self.V, 'edit') / 'edit_state.json' if self.V else None
        if es and es.exists():
            state = C.read_json(es).get('inputs', {})
        self.footage = self.find(r['footage']) if r.get('footage') else (self.find(state['footage']) if state.get('footage') else None)
        crop = r['bg_crop'] if 'bg_crop' in r else state.get('crop')
        self.crop = [float(x) for x in str(crop).split(',')] if crop else [0.0, 0.0, 1.0, 1.0]
        self.rotate = r['rotate'] if 'rotate' in r else state.get('rotate')
        self.fps = int(r.get('fps', 30))
        self.sub_top = int(r.get('subtitle_top', 886))           # 아래 18%(자막 띠)
        self.face = str(r.get('face_safe', '520,0,1400,620'))
        self.tol = int(r.get('alpha_tol', 0))                   # 얼굴·자막 띠·첫·끝 프레임에 허용할 최대 알파
        self.track = r.get('track', '모션 카드')
        self.html = SK / r.get('template', C.motion_template())
        self.assets = self.find(r['assets']) if r.get('assets') else (self.out / '_assets' if (self.out / '_assets').is_dir() else None)
        if self.fps != 30:
            self.warns.append(f'fps {self.fps}: 채널 카드는 30fps가 기본입니다(preferences.md 모션)')
        if not self.html.exists():
            C.die(f'템플릿이 없습니다: {self.html}')
        self.kinds = template_kinds(self.html)
        for k in r:
            if k not in TOP_KEYS and not k.startswith('_'):
                self.errors.append(f'맨 위 칸 "{k}"을(를) 모릅니다(오타?). 쓸 수 있는 칸: {", ".join(sorted(TOP_KEYS))}')
        self.cards = [self.card(c, i) for i, c in enumerate(r.get('cards') or [])]
        if not self.cards:
            self.errors.append('cards 가 비어 있습니다')
        ids = [c['id'] for c in self.cards]
        for x in sorted({x for x in ids if ids.count(x) > 1}):
            self.errors.append(f'id "{x}"가 겹칩니다')

    def find_video(self, v):
        if v:
            try:
                p = TP.resolve(str(v), ROOT)
            except ValueError as e:
                C.die(str(e))
            if not p.is_dir():
                C.die(f'영상 폴더가 없습니다: {p}')
            return p.resolve()
        for p in self.path.resolve().parents:
            if p.parent.name == TP.LEGACY_HOME or TP.is_topic(p):
                return p
        return None

    def find(self, x):
        """상대 경로: 영상 폴더 → 프로젝트 루트 → JSON 폴더 순으로 찾는다. 없으면 영상 폴더 기준 경로."""
        p = Path(str(x)).expanduser()
        if p.is_absolute():
            return p
        for b in (self.V, ROOT, self.path.parent):
            if b and (b / p).exists():
                return (b / p).resolve()
        return (self.V or self.path.parent) / p

    def card(self, c, i):
        err = lambda m: self.errors.append(f"{c.get('id', f'{i + 1}번째 카드')}: {m}")
        cid = str(c.get('id', '')).strip()
        if not cid or re.search(r'[/\\]', cid) or cid.startswith(('.', '_')):
            err('id 가 없거나 파일 이름으로 쓸 수 없습니다')
            cid = cid or f'card{i + 1}'
        for k in c:
            if k not in CARD_KEYS and not k.startswith('_'):
                err(f'칸 "{k}"을(를) 모릅니다(오타?). 쓸 수 있는 칸: {", ".join(sorted(CARD_KEYS))}')
        q = c.get('q')
        try:
            pairs = parse_query(q) if isinstance(q, str) else [(k, to_text(v)) for k, v in (q or {}).items() if v is not None]
        except ValueError as e:
            err(str(e))
            pairs = []
        if not pairs:
            err('q(템플릿 값)가 없습니다')
        d = dict(pairs)
        kind = d.get('kind', '')
        if kind not in self.kinds:
            err(f'kind="{kind}" 는 템플릿에 없습니다. {" · ".join(self.kinds)} 중 하나')
        # 순서: kind → (toc) 장 제목 → 종류별 공통 값 → 카드 값 → place 와 그 기본 덧붙임
        head = [('kind', kind)] if kind else []
        if kind == 'toc' and 'items' not in d and self.raw.get('chapters'):
            head.append(('items', to_text(self.raw['chapters'])))
        dflt = [(k, to_text(v)) for k, v in (self.raw.get('defaults') or {}).get(kind, {}).items() if k not in d]
        pairs = head + dflt + [(k, v) for k, v in pairs if k != 'kind']
        d = dict(pairs)
        place = d.get('place') or ('full' if self.html.name == 'cards.html' else PLACE.get(kind, 'side'))   # 어두운 스타일(원작)은 전체 화면만
        if 'place' not in d:
            pairs.append(('place', place))
        pairs += [(k, v) for k, v in EXTRA.get(place, {}).items() if k not in d]
        d = dict(pairs)
        if place == 'glass' and kind not in ('toc', 'hook'):
            err(f'place=glass 는 toc·hook 만 됩니다(kind={kind})')
        for need in NEED.get(kind, []):
            alts = need if isinstance(need, tuple) else (need,)
            if not any(str(d.get(k, '')).strip() for k in alts):
                err(f'{kind} 에는 {" 또는 ".join(alts)} 값이 필요합니다' + (' (맨 위 chapters 로 줄 수도 있음)' if need == 'items' and kind == 'toc' else ''))
        if kind == 'toc' and d.get('items'):
            n = len([x for x in d['items'].split('|') if x.strip()])
            now = times(d.get('now', 1))
            if place == 'glass' and n > 4:
                err(f'반투명 목차는 4장까지입니다(지금 {n}장)')
            if now and not 1 <= now[0] <= n:
                err(f'now={fmt_num(now[0])} 가 장 수({n}) 밖입니다')
        # 금지 낱말: 화면에 나갈 값만 본다(그림 경로 _assets/… 는 뺀다)
        allow = {str(x) for x in (c.get('allow') or [])}
        for k, v in pairs:
            if k in NOT_TEXT:
                continue
            text = re.sub(r'_assets/[^|~]*', '', v.replace('%26', '&'))
            for why, w in forbidden(text):
                if w in allow:
                    self.warns.append(f'{cid}: "{w}"({why})를 allow 로 허용함 — {k}={v[:40]}')
                else:
                    err(f'화면 글자에 금지 낱말 "{w}"({why}): {k}={v[:60]}  (내용상 꼭 필요하면 "allow": ["{w}"])')
        # 길이·시각
        dur = c.get('dur', DUR.get(kind))
        try:
            dur = float(dur)
            assert dur > 0
        except (TypeError, ValueError, AssertionError):
            err('dur(길이 초)가 필요합니다(기본값은 toc 3 · hook 5뿐)')
            dur = 4.0
        if kind in DUR and 'dur' in c and dur != DUR[kind]:
            self.warns.append(f'{cid}: {kind} 길이 {fmt_num(dur)}초(사용자 확정 기본 {fmt_num(DUR[kind])}초)')
        ex = times(d.get('exit', ''))
        exit_s = ex[0] if ex else 0.45                       # 템플릿 기본 0.45초 퇴장(full 은 위에서 exit=0)
        events = sorted(t for k, v in pairs if k.endswith('at') or k == 'brickend' for t in times(v))
        if kind == 'toc' and 'at' not in d:
            events.append(0.8)                               # 템플릿 기본: 0.8초에 지금 장 표시
        late = [t for t in events if t > dur]
        if late:
            err(f'등장 시각 {", ".join(map(fmt_num, late))}초가 길이 {fmt_num(dur)}초를 넘습니다')
        stills = c.get('stills')
        if stills is not None:
            stills = times(stills) if isinstance(stills, list) and len(times(stills)) == len(stills) else []
            if not stills:
                err('stills 는 초(숫자) 목록입니다. 예: [0.8, 1.6, 4.75]')
            bad = [t for t in stills if not 0 <= t < dur]
            if bad:
                err(f'stills {", ".join(map(fmt_num, bad))}초가 0~{fmt_num(dur)}초 밖입니다')
        else:
            stills = auto_stills(dur, exit_s, events)
        fmt = 'full' if place == 'full' else 'alpha'
        src = c.get('src')
        if src is not None and not isinstance(src, (int, float)):
            err('src 는 원본 초(숫자)입니다')
            src = None
        bg = c.get('bg')
        bg_t = bg_file = None
        if fmt == 'alpha':
            if isinstance(bg, (int, float)):
                bg_t = float(bg)
            elif isinstance(bg, str) and bg:
                bg_file = self.find(bg)
                if not bg_file.exists() and (self.out / '_bg' / bg).exists():
                    bg_file = self.out / '_bg' / bg
                if not bg_file.exists():
                    err(f'배경 그림이 없습니다: {bg}')
            elif src is not None:
                bg_t = round((src + 0.4 * dur) * 2) / 2        # 카드가 들어간 뒤 조금 지난 순간(예시 영상 v5 _bg 와 같은 규칙)
            else:
                self.warns.append(f'{cid}: src·bg 가 없어 배경 합성 미리보기(_preview)를 만들지 않습니다')
            if bg_t is not None:
                if not self.footage or not self.footage.exists():
                    err(f'배경 프레임을 뽑을 촬영본이 없습니다(footage: {self.footage})')
                bg_file = self.out / '_bg' / f'bg_{cid}_src{bg_t:.1f}.jpg'
        if kind == 'hook' and d.get('items') and d.get('at') and len(times(d['at'])) != len(d['items'].split('|')):
            self.warns.append(f'{cid}: hook 보기 수와 at 수가 다릅니다(모자란 at 은 1.3 + 1.2초 간격)')
        return dict(id=cid, kind=kind, place=place, fmt=fmt, dur=dur, exit=exit_s, query='&'.join(f'{k}={v}' for k, v in pairs),
                    stills=stills, src=src, src_in=c.get('src_in'), bg_t=bg_t, bg_file=bg_file, cue=c.get('cue') or c.get('line', ''),
                    replaces=c.get('replaces'), track=c.get('track') or self.track, name=c.get('name') or cid,
                    face=str(c.get('face_safe') or self.face), sub_top=int(c.get('subtitle_top') or self.sub_top),
                    allow=sorted(allow), why=c.get('why', ''), note=c.get('note', ''))


def auto_stills(dur, exit_s, events):
    """정지 프레임 시각: 등장 끝 · 요소가 들어온 직후 · 중간 · 퇴장 직전 · 퇴장 중간(알파)/멈춘 장면(전체 화면). 6장까지."""
    end = dur - exit_s if exit_s > 0 else dur - 0.5          # 내용이 움직이는 끝
    ts = [min(0.6, end * 0.3)] + [t + 0.45 for t in events if 0 < t + 0.45 < end] + [end * 0.5, end - 0.05]
    ts.append(dur - exit_s / 2 if exit_s > 0 else dur - 0.25)
    ts = sorted({round(min(max(t, 0.0), dur - 0.01), 2) for t in ts})
    while len(ts) > 6:                                       # 가장 붙어 있는 안쪽 시각부터 뺀다(처음·끝은 남김)
        k = min(range(1, len(ts) - 1), key=lambda i: ts[i + 1] - ts[i - 1])
        ts.pop(k)
    return ts


# ── 렌더 ──────────────────────────────────────────────
def bg_cmd(S, t, dst):
    vf = []
    # rotate: 90|180|270 은 방향 바꾸기(transpose). edit_state의 -0.5 같은 작은 값은 기울기 보정(도)이라
    # transpose 대상이 아니고, 그 각도만큼 돌려 준다(2026-11-10 예시 영상: int(-0.5)로 멈추던 것 고침).
    rdeg = float(S.rotate or 0)
    rot = {90: 'transpose=1', 180: 'transpose=1,transpose=1', 270: 'transpose=2'}.get(int(rdeg) if rdeg == int(rdeg) else None)
    if rot:
        vf.append(rot)
    elif abs(rdeg) > 1e-6:
        vf.append(f'rotate={rdeg}*PI/180:ow=iw:oh=ih:c=black')
    x0, y0, x1, y1 = S.crop
    if (x0, y0, x1, y1) != (0.0, 0.0, 1.0, 1.0):
        vf.append(f'crop=iw*{x1 - x0:.5f}:ih*{y1 - y0:.5f}:iw*{x0:.5f}:ih*{y0:.5f}')
    if vf:
        vf.append(f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}')
    return (['ffmpeg', '-v', 'error', '-nostdin', '-y', '-ss', f'{t:.3f}'.rstrip('0').rstrip('.'), '-i', str(S.footage), '-frames:v', '1']
            + (['-vf', ','.join(vf)] if vf else []) + ['-q:v', '2', str(dst)])


def render_cmds(S, c):
    """→ (본 렌더 인자, 정지 프레임 인자, 본 파일). render_motion.py 는 스킬 폴더에서 돈다."""
    d = S.out / c['id']
    common = ['--dur', fmt_num(c['dur']), '--query', C.theme_query(c['query'])] + (['--asset-dir', str(S.assets)] if S.assets else [])
    tpl = rel(S.html, SK)
    frames = ['--frames', ','.join(fmt_num(t) for t in c['stills'])]
    if c['fmt'] == 'full':
        main = d / f"{c['name']}.mp4"
        return ([tpl, str(main), '--fps', str(S.fps)] + common, [tpl, str(d / 'stills')] + frames + common, main)
    bg = ['--background-image', str(c['bg_file'])] if c['bg_file'] else []
    main = d / f"{c['name']}_alpha.mov"
    first = [tpl, str(d / c['name']), '--alpha', '--fps', str(S.fps), '--check-safe', '--subtitle-top', str(c['sub_top']),
             '--face-safe', c['face']] + bg + common
    return first, [tpl, str(d / 'stills'), '--alpha'] + frames + bg + common, main


def run_render(args, label):
    t0 = time.time()
    r = subprocess.run([PY, 'scripts/render_motion.py'] + args, cwd=SK, capture_output=True, text=True)
    out = r.stdout + r.stderr
    if r.returncode or 'HTML 오류' in out:
        raise RuntimeError(f'{label} 렌더 실패\n' + out[-1500:])
    return out, time.time() - t0


def alpha_scan(mov, face, sub_top, covers_subs):
    """알파 MOV 의 모든 프레임에서 얼굴 안전영역·자막 띠 최대 알파와 첫·끝 프레임 최대 알파를 잰다(render_motion 은 0.25초마다)."""
    import numpy as np
    x0, y0, x1, y1 = (int(v) for v in face.split(','))
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(mov), '-vf', 'alphaextract', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                         stdout=subprocess.PIPE)
    n = fz = sz = 0
    first = last = None
    while True:
        buf = p.stdout.read(W * H)
        if len(buf) < W * H:
            break
        al = np.frombuffer(buf, np.uint8).reshape(H, W)
        fz = max(fz, int(al[y0:y1, x0:x1].max()))
        if not covers_subs:
            sz = max(sz, int(al[sub_top:, :].max()))
        last = int(al.max())
        first = last if first is None else first
        n += 1
    p.wait()
    return dict(frames=n, face_max_alpha=fz, subtitle_max_alpha=None if covers_subs else sz, first_alpha=first, last_alpha=last)


def probe(p):
    try:
        info = C.probe(str(p))
    except Exception:
        return {}
    v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), {})
    num, _, den = str(v.get('r_frame_rate', '0/1')).partition('/')
    return dict(width=v.get('width'), height=v.get('height'), fps=round(int(num) / max(1, int(den or 1)), 3),
                frames=int(v['nb_frames']) if str(v.get('nb_frames', '')).isdigit() else None,
                seconds=round(float(info.get('format', {}).get('duration', 0)), 3), codec=v.get('codec_name'))


def wait_free(limit):
    """다른 무거운 작업의 .edit_busy 가 있으면 기다린다. 만든 프로세스가 이미 끝났으면 남은 표시를 지운다(pipeline.md)."""
    t0, said = time.time(), 0.0
    while FLAG.exists():
        try:
            info = FLAG.read_text('utf-8').strip()
        except OSError:
            info = ''
        m = re.search(r'pid (\d+)', info)
        if m:
            try:
                os.kill(int(m.group(1)), 0)
            except ProcessLookupError:
                print(f'[안내] {FLAG.name}를 만든 작업(pid {m.group(1)})이 이미 끝나 남은 표시를 지웁니다: {info}', flush=True)
                FLAG.unlink(missing_ok=True)
                break
            except PermissionError:
                pass
        if time.time() - t0 > limit:
            C.die(f'{FLAG.name} 가 {limit:.0f}초 넘게 남아 있습니다({info or "내용 없음"}). 그 작업이 끝난 뒤 다시 실행하거나 --wait 를 늘리세요.')
        if time.time() - said > 60:
            print(f'[대기] 다른 무거운 작업이 끝나기를 기다립니다: {info or FLAG}', flush=True)
            said = time.time()
        time.sleep(5)


def render_card(S, c):
    """한 장 렌더 → 기록 한 줄. 안전영역에서 떨어지면 폴더를 _rejected/ 로 옮긴다."""
    first, still, main = render_cmds(S, c)
    d = S.out / c['id']
    d.mkdir(parents=True, exist_ok=True)
    out, sec = run_render(first, c['id'])
    run_render(still, c['id'] + ' 정지 프레임')
    row = dict(id=c['id'], kind=c['kind'], place=c['place'], format=c['fmt'], dur=c['dur'], fps=S.fps, src=c['src'], cue=c['cue'],
               replaces=c['replaces'], q=c['query'], stills=c['stills'], render_sec=round(sec))
    if c['bg_file']:
        row['bg'] = rel(c['bg_file'], S.V, ROOT)
    if c['allow']:
        row['allow'] = c['allow']
    pr = probe(main)
    row['probe'] = pr
    ok = pr.get('width') == W and pr.get('height') == H and pr.get('frames') in (None, round(c['dur'] * S.fps))
    if not ok:
        row['note'] = f"크기·프레임 수가 다릅니다: {pr}"
    if c['fmt'] == 'alpha':
        row['safe'] = [ln.strip() for ln in out.splitlines() if '안전영역' in ln or '프레임 최대' in ln]
        sc = alpha_scan(main, c['face'], c['sub_top'], c['place'] == 'split')
        x0, y0, x1, y1 = c['face'].split(',')
        sub = '' if sc['subtitle_max_alpha'] is None else f", 자막 띠(y {c['sub_top']}+) 최대 알파 {sc['subtitle_max_alpha']}"
        row['safe'].insert(0, f"프레임마다 검사(모든 프레임 {sc['frames']}장): 얼굴({x0}–{x1}×{y0}–{y1}) 최대 알파 {sc['face_max_alpha']}{sub}, "
                              f"첫 프레임 알파 {sc['first_alpha']}, 끝 프레임 알파 {sc['last_alpha']}")
        row['scan'] = sc
        bad = sc['face_max_alpha'] > S.tol or (sc['subtitle_max_alpha'] or 0) > S.tol or (sc['first_alpha'] or 0) > S.tol \
            or (c['exit'] > 0 and (sc['last_alpha'] or 0) > S.tol)
        if bad:
            ok = False
            dst = S.out / '_rejected' / f"{c['id']}_{time.strftime('%Y%m%d-%H%M%S')}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(d), str(dst))
            main = dst / main.name
            row['note'] = (row.get('note', '') + ' ' if row.get('note') else '') + f'안전영역 검사 실패(허용 알파 {S.tol}) → {rel(dst, S.V, ROOT)}'
    row.update(file=rel(main, S.V, ROOT), ok=ok, rendered_at=time.strftime('%Y-%m-%d %H:%M'))
    return row


# ── 산출 ──────────────────────────────────────────────
def main_file(S, c):
    d = S.out / c['id']
    return d / (f"{c['name']}.mp4" if c['fmt'] == 'full' else f"{c['name']}_alpha.mov")


def still_files(S, c):
    """[(초, 파일)] — 알파 카드는 배경 합성 jpg 가 있으면 그것, 없으면 투명 PNG."""
    out = []
    for p in sorted((S.out / c['id'] / 'stills').glob('*.png')):
        m = re.search(r'_(\d+\.\d+)$', p.stem)
        if m:
            j = p.with_name(p.stem + '_preview.jpg')
            out.append((float(m.group(1)), j if j.exists() else p))
    return out


def file_rows(S, log):
    last = {}
    for r in log:
        last[r['id']] = r
    rows = []
    for c in S.cards:
        f = main_file(S, c)
        if not f.exists():
            continue
        L = last.get(c['id'], {})
        stem = f.with_name(c['name'])
        files = {'main': rel(f, S.V, ROOT)}
        if c['fmt'] == 'alpha':
            for k, suf in (('black', '_black.mp4'), ('preview', '_preview.mp4'), ('poster', '_alpha.png')):
                p = stem.with_name(stem.name + suf)
                if p.exists():
                    files[k] = rel(p, S.V, ROOT)
        pr = probe(f)
        safe = L.get('safe')
        if safe is None and c['fmt'] == 'alpha':
            sj = stem.with_name(stem.name + '_safe.json')
            if sj.exists():
                j = C.read_json(sj)
                safe = [f"안전영역 검사(_safe.json, {j.get('samples')}장): 얼굴 최대 알파 {j.get('face_max_alpha')}, 자막 띠 최대 알파 {j.get('subtitle_max_alpha')}"]
        row = dict(id=c['id'], replaces=c['replaces'], format=FORMAT[c['place']], files=files, seconds=c['dur'],
                   frames=pr.get('frames'), fps=pr.get('fps'), ok=L.get('ok'), src=c['src'], cue=c['cue'], q=c['query'],
                   safe=safe or [], stills=[rel(p, S.V, ROOT) for _, p in still_files(S, c)])
        if c['bg_file'] and c['bg_file'].exists():
            row['preview_bg'] = rel(c['bg_file'], S.V, ROOT) + (f" (그 시각 원본 {S.footage.name} 정지 프레임)" if c['bg_t'] is not None else '')
        if c['note'] or L.get('note'):
            row['note'] = ' · '.join(x for x in (c['note'], L.get('note', '')) if x)
        rows.append(row)
    return rows


def contact_sheet(S, path):
    """카드마다 한 줄: 머리띠(id · 길이 · 형식) + 정지 프레임 칸(시각 표시). 예시 영상 v5 연락표와 같은 모양."""
    from PIL import Image, ImageDraw
    font = C.korean_font
    rows = [(c, still_files(S, c)) for c in S.cards if main_file(S, c).exists()]
    rows = [(c, st) for c, st in rows if st]
    if not rows:
        return None
    cols = max(len(st) for _, st in rows)
    cw, hh = W // cols, 34
    ch = round(cw * 9 / 16)
    sheet = Image.new('RGB', (W, len(rows) * (hh + ch)), (29, 36, 52))
    d = ImageDraw.Draw(sheet)
    fh, ft = font(22, True), font(24, True)
    iv, ink = (255, 255, 255), (29, 36, 52)
    for i, (c, st) in enumerate(rows):
        y = i * (hh + ch)
        how = FORMAT[c['place']].split('(')[0] if c['fmt'] == 'full' else ('알파 MOV(실제 프레임 합성)' if c['bg_file'] else '알파 MOV(투명 PNG, 회색 바탕)')
        d.text((10, y + 4), f"{c['id']}  ·  {fmt_num(c['dur'])}초  ·  {how}", font=fh, fill=iv)
        for k, (t, f) in enumerate(st):
            with Image.open(f) as im:
                im = im.convert('RGBA')
                base = Image.new('RGBA', im.size, (90, 94, 102, 255))
                base.alpha_composite(im)
                cell = base.convert('RGB').resize((cw, ch), Image.LANCZOS)
            sheet.paste(cell, (k * cw, y + hh))
            d.text((k * cw + 8, y + hh + ch - 34), f'{t:.2f}s', font=ft, fill=iv, stroke_width=2, stroke_fill=ink)
    sheet.save(path, quality=88)
    return sheet.size


def augment_spec(S, rows):
    """capcut_augment.py --spec 에 바로 쓰는 목록. 파일은 프로젝트 루트 기준(어느 폴더에서 돌려도 찾음)."""
    rep, items, left = [], [], []
    for r in rows:
        if not r.get('ok'):
            left.append(f"{r['id']}(검사 통과 기록 없음)")
            continue
        c = next(x for x in S.cards if x['id'] == r['id'])
        f = rel(main_file(S, c), ROOT)
        if c['replaces']:
            rep.append(dict(match=Path(c['replaces']).stem, file=f))
        elif c['src'] is not None:
            it = dict(id=c['id'], file=f, src=c['src'], dur=c['dur'], kind=c['fmt'], track=c['track'], line=c['cue'])
            if c['src_in'] is not None:
                it['src_in'] = c['src_in']
            items.append(it)
        else:
            left.append(f"{c['id']}(src·replaces 없음)")
    spec = {'note': f"motion_cards.py 가 {rel(S.path, ROOT)} 에서 만듦({time.strftime('%Y-%m-%d %H:%M')}). "
                    "capcut_augment.py --spec 으로 쓰거나 replace_media·items 를 그 버전 덧입히기 목록에 옮긴다",
            'replace_media': rep, 'items': items}
    if left:
        spec['not_included'] = left
    return spec


def decision_skeleton(S, path, rows, log):
    """판단_기록.md 뼈대(없을 때만). 판단은 사람이 채우고, 카드 표·다시 만든 것·확인 범위는 기록에서 옮긴다."""
    L = [f"# {S.out.name} · 판단 기록 ({time.strftime('%Y-%m-%d')})", '',
         f"요청: {S.raw.get('request') or '(사용자 지시를 그대로 옮겨 적는다)'}", '',
         f"템플릿: `{rel(S.html, ROOT)}`. 생성: `motion_cards.py {rel(S.path, ROOT)}`. 형식: 1920×1080, {S.fps}fps, 화면 속 출처·메타 라벨 없음.", '',
         '## 카드', '', '| id | 종류 · 배치 | 길이 | 대사 | 바꾸는 파일 |', '|---|---|---|---|---|']
    L += [f"| {c['id']} | {c['kind']} · {c['place']} | {fmt_num(c['dur'])}초 | {c['cue']} | {c['replaces'] or '—'} |" for c in S.cards]
    L += ['', '## 판단', '']
    L += [f"- **{c['id']}**: {c['why']}" for c in S.cards if c['why']] or ['- (왜 이 배치·길이·문구인가를 적는다)']
    bad = [r for r in log if r.get('ok') is False]
    L += ['', '## 다시 만든 것', '']
    L += [f"- {r['id']} ({r['rendered_at']}): {r.get('note', '')}" + (f" — {r['safe'][0]}" if r.get('safe') else '') for r in bad] or ['- 없음']
    al = [r for r in rows if r['format'] != FORMAT['full']]
    chk = []
    if al:
        chk.append(f"알파 MOV {len(al)}개의 모든 프레임에서 얼굴·자막 띠 최대 알파와 첫·끝 프레임 알파(파일_목록.json safe)")
    chk.append(f"길이·{S.fps}fps·프레임 수·1920×1080(ffprobe)")
    if any(r.get('preview_bg') for r in rows):
        chk.append('카드가 들어갈 그 시각의 실제 촬영 프레임(_bg/)에 합성한 정지 장면(연락표.jpg)')
    L += ['', '## 확인 범위', '', '- 확인: ' + '. '.join(chk) + '.',
          '- 안 함: 움직이는 촬영본 위 겹침(정지 프레임 합성만), 편집본 안에서 대사와의 실제 맞춤, CapCut에서의 실제 표시.', '']
    path.write_text('\n'.join(L), 'utf-8')


# ── 실행 ──────────────────────────────────────────────
def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='모션 카드 목록(JSON) → 채널 모션 카드 렌더')
    ap.add_argument('spec', help='카드 목록 JSON(예: <편집 폴더>/모션카드_v6/cards.json)')
    ap.add_argument('--out', help='출력 폴더(기본: JSON 이 있는 폴더). 시험 렌더는 스크래치 폴더로')
    ap.add_argument('--only', nargs='+', metavar='ID', help='이 카드들만 렌더')
    ap.add_argument('--force', action='store_true', help='이미 있는 카드도 다시 렌더(기존 폴더는 _이전/<id>_<시각>/으로 옮김)')
    ap.add_argument('--dry-run', action='store_true', help='검사하고 실행할 명령만 출력(파일을 쓰지 않음)')
    ap.add_argument('--wait', type=float, default=1800, help='다른 작업의 .edit_busy 를 기다릴 최대 초(기본 1800)')
    a = ap.parse_args()
    C.need_ffmpeg()
    spec_path = Path(a.spec).expanduser().resolve()
    if not spec_path.exists():
        C.die(f'카드 목록이 없습니다: {spec_path}')
    S = Spec(spec_path, a)
    if a.only:
        miss = [x for x in a.only if x not in {c['id'] for c in S.cards}]
        if miss:
            S.errors.append(f"--only 에 없는 id: {', '.join(miss)}")
    for w in S.warns:
        print('[주의]', w, flush=True)
    if S.errors:
        print(f'[검사 실패] {len(S.errors)}건 — 아무것도 렌더하지 않았습니다', file=sys.stderr)
        for e in S.errors:
            print('  -', e, file=sys.stderr)
        sys.exit(2)
    print(f"카드 {len(S.cards)}장 검사 통과 · 출력 {S.out}" + (f" · 영상 {rel(S.V, ROOT)}" if S.V else ''))

    pick = [c for c in S.cards if not a.only or c['id'] in a.only]
    todo = [c for c in pick if a.force or not main_file(S, c).exists()]
    for c in pick:
        if c not in todo:
            print(f"  있음(건너뜀) {rel(main_file(S, c), S.V, ROOT)}")
    bgs = {c['bg_file']: c['bg_t'] for c in todo if c['bg_t'] is not None and (a.dry_run or not c['bg_file'].exists())}
    if a.dry_run:
        for f, t in bgs.items():
            print('$', shlex.join(bg_cmd(S, t, f)))
        for c in todo:
            first, still, _ = render_cmds(S, c)
            print(f"# {c['id']}  ({c['kind']} · {c['place']} · {fmt_num(c['dur'])}초 · 정지 {', '.join(map(fmt_num, c['stills']))})")
            for args in (first, still):
                print(f'$ (cd {rel(SK, ROOT)} &&', shlex.join([PY, 'scripts/render_motion.py'] + args) + ')')
        print(f'dry-run: 렌더 {len(todo)}장 · 배경 프레임 {len(bgs)}장 (파일을 쓰지 않음)')
        return

    S.out.mkdir(parents=True, exist_ok=True)
    for f, t in bgs.items():
        f.parent.mkdir(parents=True, exist_ok=True)
        C.run(bg_cmd(S, t, f))
        print(f'  배경 프레임 {rel(f, S.V, ROOT)} (원본 {t:g}초)')
    new, failed = [], []
    t0 = time.time()
    if todo:
        wait_free(a.wait)
        with busy(f'motion_cards {len(todo)}장'):
            for c in todo:
                d = S.out / c['id']
                if d.exists():                                   # --force: 지우지 않고 옮겨 둔다
                    old = S.out / '_이전' / f"{c['id']}_{time.strftime('%Y%m%d-%H%M%S')}"
                    old.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(d), str(old))
                    print(f"  기존 폴더 → {rel(old, S.V, ROOT)}")
                try:
                    row = render_card(S, c)
                except RuntimeError as e:
                    failed.append(c['id'])
                    print(f'[실패] {e}', file=sys.stderr)
                    continue
                new.append(row)
                if not row['ok']:
                    failed.append(c['id'])
                print(f"  {'만듦' if row['ok'] else '[불합격]'} {c['id']} {fmt_num(c['dur'])}초 {row['render_sec']}s", *row.get('safe', [])[:1],
                      row.get('note', ''), flush=True)

    lp = S.out / '_render_log.json'
    log = (C.read_json(lp) if lp.exists() else []) + new
    if new:
        C.write_json(lp, log)
    rows = file_rows(S, log)
    sheet = contact_sheet(S, S.out / '연락표.jpg')
    C.write_json(S.out / '파일_목록.json', {
        'created': time.strftime('%Y-%m-%d %H:%M'), 'base': rel(S.V, ROOT) + '/' if S.V else None, 'spec': rel(spec_path, S.V, ROOT),
        'request': S.raw.get('request'),
        'rule': f"{S.fps}fps · 1920×1080 · 화면 속 출처·메타 라벨 없음. 알파 카드는 얼굴({S.face})·자막 띠(y {S.sub_top}+) 알파 {S.tol}{' 이하' if S.tol else ''}, "
                f"첫 프레임 알파 0, 끝 0.45초 퇴장이면 끝 프레임 알파 0. 전체 화면 카드는 끝 0.5초 멈춤",
        'contact_sheet': rel(S.out / '연락표.jpg', S.V, ROOT) if sheet else None, 'decision_log': rel(S.out / '판단_기록.md', S.V, ROOT),
        'render_log': rel(lp, S.V, ROOT), 'augment_items': rel(S.out / 'augment_items.json', S.V, ROOT),
        'render_script': f".skill-build/claude-edit/scripts/motion_cards.py {rel(spec_path, ROOT)}", 'cards': rows})
    aug = augment_spec(S, rows)
    C.write_json(S.out / 'augment_items.json', aug)
    dp = S.out / '판단_기록.md'
    made_dp = not dp.exists()
    if made_dp:
        decision_skeleton(S, dp, rows, log)

    print('\n| 카드 | 형식 | 길이 | 상태 | 안전영역 |\n|---|---|---|---|---|')
    done = {r['id']: r for r in new}
    for c in pick:
        r = done.get(c['id'])
        state = ('만듦' if r['ok'] else '불합격') if r else ('실패' if c['id'] in failed else '있음(건너뜀)')
        safe = (r.get('safe') or ['—'])[0] if r else '—'
        print(f"| {c['id']} | {c['kind']} · {c['place']} | {fmt_num(c['dur'])}초 | {state} | {safe} |")
    print(f"\n만듦 {sum(r['ok'] for r in new)} · 실패 {len(failed)} · 건너뜀 {len(pick) - len(todo)} · {time.time() - t0:.0f}초 걸림")
    print(f"연락표 {S.out / '연락표.jpg'}" + (f' ({sheet[0]}×{sheet[1]})' if sheet else ' (정지 프레임 없음)'))
    print(f"파일_목록.json · _render_log.json · augment_items.json(교체 {len(aug['replace_media'])} · 새 자리 {len(aug['items'])})"
          + (' · 판단_기록.md 뼈대(판단 칸을 채우세요)' if made_dp else ' · 판단_기록.md 는 이미 있어 그대로 둠'))
    if failed:
        sys.stdout.flush()
        print(f"[주의] 실패·불합격: {', '.join(failed)} — 불합격 판은 _rejected/ 에 있습니다", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
