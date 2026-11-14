"""업로드 묶음 초안(S5): 사용자가 마무리한 CapCut 프로젝트에서 챕터 후보·설명란·고정댓글 초안을 만듭니다.

claude-edit 스킬 references/upload_pack.md 를 따른다. 사용자 CapCut 프로젝트는 읽기만 한다.
  - 챕터: 후보 경계를 모은다 — 목차 카드 시각, 범퍼 직후 첫 자막, 단계·기간·전환·질문·경험·연구·반론·비유·마무리 말로
    시작하는 문장(자막을 문장 끝 '다·요·?' 기준으로 이어 붙여 판단). 범퍼 앞(도입부)은 한 챕터로 둔다.
    유튜브 규칙(첫 줄 00:00, 오름차순, 각 10초 이상, 최종 길이 안)으로 고른다. 10초 안의 두 후보는 점수가 높은 쪽을 남기고,
    연구 소개가 60초 안에 이어지거나 앞 챕터와 같은 말(예: '주 2회')로 다시 시작하면 앞 챕터에 합친다. 이름은 경계의 첫 자막 문장을 '{이름: …}' 초안으로 붙인다(에이전트가 고친다).
    --chapters 로 사람이 고른 목록(MD·txt의 'mm:ss 이름' 줄, 기존 설명란 파일도 됨)을 주면 검사만 한다.
  - 설명란: templates/description.txt 순서. 해시태그는 profile.md '### 설명란 해시태그' 표의 --type 행(선택).
    근거·출처는 --sources 자료목록의 '설명란' 절 붙여넣기 블록에서 뽑고, 최종 프로젝트에 남은 미디어와 이어지는 줄만 남긴다
    (논문은 첫 저자 성, 인용 영상은 채널명, 그림은 이름표 낱말이 미디어 파일 이름에 있으면 남음). 빠진 줄은 검사 보고에 적는다.
    AI 사진(원본 경로에 생성이미지·v00N_이미지·_파생)과 스톡(Pexels·Mixkit·Pixabay)이 남아 있으면 고지 줄을 넣는다.
    원본 경로는 영상 폴더 파일·<캡컷_가져오기>/편집자료_목록.json·assets/stock/library.json 에서 CapCut 복제본 이름으로 찾는다.
  - 고정댓글(3줄): 관련 영상 실제 제목을 yt-dlp 로 한 번 확인하고(--key-title 이 있으면 네트워크를 쓰지 않음),
    영상 속 '고정 댓글' 문장과 CTA 카드를 나란히 보여 줘 말과 링크 내용을 비교하게 한다.
출력: <업로드 폴더>/업로드_초안/ 유튜브_설명란_초안.txt · 고정댓글_초안.txt · 챕터_검사.md(챕터·출처·고지·고정댓글 검사)
  업로드 폴더: 영상 폴더 안 업로드/(tools/topic_paths.py).
  내보낸 최종 영상도 업로드 폴더에서 찾는다. 기존 유튜브_설명란.txt·고정댓글.txt 는 고치지 않는다. 초안 파일이 이미 있고 내용이 다르면 '<이름>_이전_<시각>' 으로 옮겨 두고 새로 쓴다.
  채울 곳은 '{…}' 자리표시로 남긴다(grep '{' 로 찾는다). 내보낸 영상이 있으면 youtube-chapter-timestamps 로 실제 발화 기준을 맞춰 보라고 안내한다.

사용 예(작업 폴더에서):
  python <스킬 폴더>/claude-edit/scripts/upload_pack.py 내영상_초벌_v006 --video 내영상 [--type <해시태그 행>] [--key-url <관련 영상 URL>]
  … --chapters 내영상/업로드/챕터.txt     ← 사람이 고른 챕터 검사만
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
ROOT = Path(os.environ.get('PROJECT_ROOT') or os.getcwd()).resolve()     # 프로젝트 루트(PROJECT_ROOT 또는 작업 폴더)
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / 'smartdaddy-video-edit' / 'scripts'), str(ROOT / 'tools')]
import _common as C  # noqa: E402
import topic_paths as TP  # noqa: E402   영상 폴더 안 단계 폴더

MIN_GAP = 10.0      # 유튜브 챕터 최소 길이(초)
NEAR = 2            # --compare 에서 같은 경계로 보는 차이(초)
STUDY_CHAIN = 60.0  # 연구 소개가 이 초 안에 이어지면 한 챕터
HASH = re.compile(r'_[0-9a-f]{8}$')      # CapCut 복제본 이름 끝 '_<해시8>'
MEDIA_EXT = ('.mp4', '.mov', '.m4v', '.png', '.jpg', '.jpeg', '.webp', '.wav', '.m4a', '.mp3')
VIDEO_EXT = ('.mp4', '.mov', '.m4v')
AI_MARK = re.compile(r'생성이미지|v\d{3}_이미지|_파생', re.I)
STOCK_MARK = re.compile(r'pexels|mixkit|pixabay|스톡', re.I)
PROVIDER = re.compile(r'pexels|mixkit|pixabay', re.I)

# 문장 첫머리 말 → 챕터 후보. (종류, 점수, 정규식, 찾는 앞 글자 수: 0이면 맨 앞에서만)
NUM = r'(?:\d+(?:\s*[,~\-]\s*\d+)?|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)'
CUES = [
    ('단계', 3, re.compile(r'^(?:첫|두|세|네|다섯|마지막)\s*번째|^(?:첫째|둘째|셋째|넷째)|^\d+\s*(?:단계|번째)'), 0),
    ('기간', 2, re.compile(rf'^(?!\d{{4}}년){NUM}\s*(?:개월|달|주차|주째|년차|년|일차)|^주\s*\d+\s*(?:회|번)'), 0),
    ('전환', 4, re.compile(r'그렇다면|결론부터|결론은|결론적으로|다음으로|이번에는|본론'), 14),
    ('마무리', 4, re.compile(r'오늘 말씀드린|정리하면|정리해 ?보면|정리를 하면|마지막으로'), 14),
    ('질문', 3, re.compile(r'^(?:왜|어떻게|얼마나|언제|무엇|뭐가|정말|진짜)\s'), 0),      # 문장이 '?'로 끝날 때만
    ('경험', 3, re.compile(r'제가 예전에|저는 예전에|제 경험|제가 처음|저도 처음|저는 처음'), 14),
    ('연구', 3, re.compile(r'^\d{4}년|연구팀|연구를 보면|메타 ?분석'), 20),
    ('반론', 2, re.compile(r'^(?:그래도|물론|반대로)\s'), 0),
    ('비유', 2, re.compile(r'비유'), 14),
]
FILLER = re.compile(r'^(?:(?:그리고|그래서|그럼|그러면|이때|이제|자|네|일단|또|먼저|근데|아)[\s,.]+)+')
SENT_END = re.compile(r'(?:[.?!…]|[다요죠까네])["\'”’)\s/]*$')
STOP = {'그림', '사진', '영상', '자료', '화면', '이미지', '카드', '해부', '원본', '변경'}


def nfc(s):
    return unicodedata.normalize('NFC', s or '')


def stem_of(path):
    """CapCut 복제본 '<원래 이름>_<해시8>.mp4' → 원래 이름."""
    return HASH.sub('', nfc(Path(path).stem))


def clock(t):
    """초 → 유튜브 챕터 시각(초 단위 내림)."""
    t = int(math.floor(t + 1e-6))
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'


def parse_clock(s):
    sec = 0
    for p in s.split(':'):
        sec = sec * 60 + int(p)
    return sec


def short(s, n=40):
    s = re.sub(r'\s+', ' ', s).strip()
    return s if len(s) <= n else s[:n - 1] + '…'


def rel(p):
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


# ── 프로젝트 읽기 ─────────────────────────────────────
def read_project(arg, cc_arg):
    pdir = C.resolve_project(arg, cc_arg)
    dfile = C.draft_file(pdir)
    D = C.read_draft(dfile)
    mats = C.material_index(D)

    def text_of(m):
        c = m.get('content') or ''
        try:
            c = json.loads(c).get('text', '')
        except Exception:
            pass
        return nfc(re.sub(r'\s+', ' ', c)).strip()

    vtracks = [t for t in D['tracks'] if t['type'] == 'video']
    main = vtracks[0] if vtracks else None
    media = []
    for t in D['tracks']:
        if t['type'] not in ('video', 'audio'):
            continue
        for s in t['segments']:
            p = nfc(mats.get(s['material_id'], (None, {}))[1].get('path', ''))
            if not p or 'draftpath_placeholder' in p:      # CapCut 복합 클립 내부 소리
                continue
            st = s['target_timerange']['start'] / C.US
            media.append(dict(stem=stem_of(p), path=p, start=st, end=st + s['target_timerange']['duration'] / C.US,
                              track=t.get('name') or t['type'], main=t is main))
    texts = []
    for t in D['tracks']:
        if t['type'] != 'text':
            continue
        segs = []
        for s in t['segments']:
            m = mats.get(s['material_id'], (None, {}))[1]
            st = s['target_timerange']['start'] / C.US
            segs.append(dict(start=st, end=st + s['target_timerange']['duration'] / C.US, text=text_of(m)))
        texts.append(sorted(segs, key=lambda x: x['start']))
    subs = max(texts, key=len) if texts else []          # 조각이 가장 많은 글자 트랙이 자막
    main_src = Counter(m['path'] for m in media if m['main']).most_common(1)
    return dict(dir=pdir, file=dfile, name=nfc(pdir.name), duration=D['duration'] / C.US, mtime=dfile.stat().st_mtime,
                media=media, subs=[s for s in subs if s['text']], all_texts={s['text'] for tx in texts for s in tx},
                main_src=main_src[0][0] if main_src else '')


def sentences(subs, gap=1.0):
    """자막 조각을 문장으로 잇는다. 문장 끝(다·요·?·.)이거나 1초 넘게 비면 끊는다."""
    out, cur = [], None
    for s in subs:
        if cur and s['start'] - cur['end'] > gap:
            out.append(cur)
            cur = None
        if cur is None:
            cur = dict(start=s['start'], end=s['end'], text=s['text'])
        else:
            cur['end'] = s['end']
            cur['text'] += ' ' + s['text']
        if SENT_END.search(s['text']):
            out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    return out


def cue_of(text):
    """문장 첫머리 말의 종류. 가장 점수가 높은 것 하나."""
    best = None
    bare = FILLER.sub('', text)
    for kind, score, rx, span in CUES:
        for s in (bare, text):
            hit = rx.search(s[:span]) if span else rx.search(s)
            if hit and (span or hit.start() == 0):
                if kind == '질문' and not text.rstrip(' /').endswith('?'):
                    continue
                if not best or score > best[1]:
                    best = (kind, score, hit.group(0).strip())
                break
    return best


def sentence_at(sents, t, before=0.6):
    return next((s for s in sents if s['start'] >= t - before), None)


def sentence_near(sents, t):
    """사람이 고른 시각의 문장: 그 시각을 덮는 문장이 3초 안에 시작했으면 그것, 아니면 다음 문장."""
    cover = next((s for s in sents if s['start'] <= t + 0.5 < s['end']), None)
    return cover if cover and t - cover['start'] <= 3 else sentence_at(sents, t, 1.0)


def collect(P, sents):
    """챕터 후보 경계(전부). 범퍼 앞(도입부)의 문장 후보는 넣지 않는다."""
    cands = [dict(t=0.0, kind='시작', score=9, why='영상 시작')]
    for m in P['media']:
        if not m['main'] and '목차' in m['stem']:
            cands.append(dict(t=m['start'], kind='목차 카드', score=5, why=m['stem']))
    bumper = next((m for m in P['media'] if m['main'] and re.search(r'범퍼|bumper', m['stem'], re.I)), None)
    intro_end = 0.0
    if bumper:
        intro_end = bumper['end'] - 0.5
        s = next((x for x in P['subs'] if x['start'] >= intro_end), None)
        if s:
            cands.append(dict(t=s['start'], kind='범퍼 직후', score=5, why=f"범퍼 {C.mmss(bumper['start'])}–{C.mmss(bumper['end'])}"))
    for s in sents:
        if s['start'] < intro_end or s['start'] < 1.0:
            continue
        c = cue_of(s['text'])
        if c:
            cands.append(dict(t=s['start'], kind=c[0], score=c[1], why=f"'{c[2]}'"))
    for c in cands:
        s = sentence_at(sents, c['t'])
        c['line'] = s['text'] if s else ''
    return sorted(cands, key=lambda c: (c['t'], -c['score'])), bumper


def pick(cands, duration):
    """10초 규칙으로 고르기. 10초 안이면 점수 높은 쪽(같으면 앞쪽)을 남긴다."""
    kept = []
    for c in cands:
        c.pop('drop', None)
        if not kept:
            kept.append(c)
            continue
        last = kept[-1]
        if c['kind'] == '연구' and last['kind'] == '연구' and c['t'] - last['t'] < STUDY_CHAIN:
            c['drop'] = f"{clock(last['t'])} 연구 소개와 한 챕터"
        elif c['kind'] == last['kind'] and c['why'] == last['why']:
            c['drop'] = f"{clock(last['t'])}와 같은 말({c['why']}) → 같은 이야기"
        elif c['t'] - last['t'] >= MIN_GAP:
            kept.append(c)
        elif (last['kind'] != '시작' and c['score'] > last['score']
              and (len(kept) < 2 or c['t'] - kept[-2]['t'] >= MIN_GAP)):
            last['drop'] = f"{clock(c['t'])} {c['kind']}에 자리를 내줌({c['t'] - last['t']:.1f}초 차)"
            kept[-1] = c
        else:
            c['drop'] = f"{clock(last['t'])}와 {c['t'] - last['t']:.1f}초 → 합침"
    while len(kept) > 1 and duration - kept[-1]['t'] < MIN_GAP:
        kept.pop()['drop'] = '끝까지 10초 미만'
    return kept


def check(chs, duration):
    """유튜브 챕터 규칙 검사. chs: [{'sec', 'name'}] (초는 내림한 정수)."""
    probs = []
    if len(chs) < 3:
        probs.append(f'챕터가 {len(chs)}개 — 3개 이상이어야 유튜브가 챕터로 인식한다')
    if not chs or chs[0]['sec'] != 0:
        probs.append('첫 줄이 00:00이 아니다')
    for a, b in zip(chs, chs[1:]):
        if b['sec'] <= a['sec']:
            probs.append(f"{clock(b['sec'])}: 앞 줄({clock(a['sec'])})보다 늦지 않다(오름차순 아님)")
        elif b['sec'] - a['sec'] < MIN_GAP:
            probs.append(f"{clock(a['sec'])}→{clock(b['sec'])}: {b['sec'] - a['sec']}초 — 10초 미만이라 앞이나 뒤와 합친다")
    for c in chs:
        if c['sec'] >= duration:
            probs.append(f"{clock(c['sec'])}: 최종 길이({clock(duration)}) 밖")
        if not c.get('name'):
            probs.append(f"{clock(c['sec'])}: 이름이 비었다")
    if chs and 0 < duration - chs[-1]['sec'] < MIN_GAP:
        probs.append(f"마지막 {clock(chs[-1]['sec'])}: 끝까지 {duration - chs[-1]['sec']:.1f}초 — 10초 미만")
    return probs


def read_chapters(path):
    """'mm:ss 이름' 줄(목록·표·설명란 모두)을 읽는다."""
    out = []
    for line in nfc(Path(path).read_text('utf-8-sig')).splitlines():
        if line.lstrip().startswith('|'):
            cells = [c.strip().strip('`') for c in line.strip().strip('|').split('|')]
            i = next((k for k, c in enumerate(cells) if re.fullmatch(r'(?:\d{1,2}:)?\d{1,2}:\d{2}', c)), None)
            if i is not None:
                out.append(dict(sec=parse_clock(cells[i]), name=next((c for c in cells[i + 1:] if c), '')))
            continue
        m = re.match(r'^\s*(?:[-*·]\s*)?((?:\d{1,2}:)?\d{1,2}:\d{2})\s+(.+?)\s*$', line)
        if m:
            out.append(dict(sec=parse_clock(m.group(1)), name=m.group(2)))
    return out


# ── 해시태그 ─────────────────────────────────────────
def hashtags(vtype, part):
    md = ROOT / (C.load_profile(ROOT).get('hashtag_table') or 'profile.md')   # '### 설명란 해시태그' 표
    txt = nfc(md.read_text('utf-8'))
    if '### 설명란 해시태그' not in txt:
        C.die(f'{rel(md)} 에 "### 설명란 해시태그" 절이 없습니다.')
    sec = re.split(r'\n## ', txt.split('### 설명란 해시태그', 1)[1], 1)[0]
    rows, banned = {}, []
    for line in sec.splitlines():
        if line.startswith('|') and '#' in line:
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            rows[cells[0]] = re.findall(r'#[^\s`]+', cells[1])
        if '쓰지 않는 해시태그' in line:
            banned = re.findall(r'`(#[^`\s]+)`', line)
    key = re.sub(r'[\s·]', '', vtype)
    row = next((r for r in rows if re.sub(r'[\s·]', '', r).startswith(key) or key.startswith(re.sub(r'[\s·]', '', r))), None)
    if not row:
        C.die(f'--type "{vtype}" 이(가) 해시태그 표에 없습니다. 고를 수 있는 값: {" | ".join(rows)}')
    tags, notes = [], []
    for tg in rows[row]:
        if '(부위)' in tg:
            if part:
                tg = tg.replace('(부위)', re.sub(r'\s', '', part))
            else:
                tg = tg.replace('(부위)', '{부위}')
                notes.append('(부위) 자리: --part 로 값을 주거나 {부위}를 고친다')
        tags.append(tg)
    bad = [t for t in tags if t in banned]
    if bad:
        notes.append(f'쓰지 않는 해시태그가 들어감: {" ".join(bad)}')
    if len(tags) > 5:
        notes.append(f'해시태그 {len(tags)}개 — 최대 5개')
    return row, tags, notes


# ── 근거·출처 ────────────────────────────────────────
def parse_sources(md):
    """자료목록 MD → (표 행[{files, src}], 붙여넣기 항목[{group, head, more}])."""
    lines = nfc(Path(md).read_text('utf-8-sig')).splitlines()
    rows, i = [], 0
    while i < len(lines):
        if (lines[i].startswith('|') and '파일' in lines[i] and i + 1 < len(lines)
                and re.match(r'^\|[\s:|-]+\|?\s*$', lines[i + 1])):
            head = [c.strip() for c in lines[i].strip().strip('|').split('|')]
            fi = next(k for k, c in enumerate(head) if '파일' in c)
            si = next((k for k, c in enumerate(head) if '출처' in c), len(head) - 1)
            i += 2
            while i < len(lines) and lines[i].startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if len(cells) > fi:
                    rows.append(dict(files=re.findall(r'`([^`]+)`', cells[fi]) or [cells[fi]],
                                     src=cells[si] if si < len(cells) else ''))
                i += 1
            continue
        i += 1
    text = '\n'.join(lines)
    entries, group = [], ''
    for m in re.finditer(r'^#+ [^\n]*설명란[^\n]*\n(.*?)(?=^#+ |\Z)', text, re.M | re.S):
        for block in re.findall(r'```[^\n]*\n(.*?)```', m.group(1), re.S):
            for line in block.splitlines():
                if not line.strip():
                    continue
                g = re.match(r'^\s*\[(.+?)\]\s*$', line)
                if g:
                    group = g.group(1)
                elif re.match(r'^ ?[·•\-*]\s+', line):
                    entries.append(dict(group=group, head=re.sub(r'^\s*[·•\-*]\s+', '', line).strip(), more=[]))
                elif entries:
                    entries[-1]['more'].append(line.strip())
    return rows, entries


def group_kind(g):
    if '인용' in g:
        return 'cite'
    if '연구' in g or '논문' in g or '참고' in g:
        return 'paper'
    return 'figure'


def entry_keys(e, kind):
    """항목을 미디어 파일 이름과 잇는 낱말: 논문은 첫 저자 성, 인용 영상은 채널명, 그 밖은 이름표 낱말."""
    h = e['head']
    if kind == 'paper':
        m = re.match(r"([A-Za-zÀ-ÿ'\-]{2,})", h)
        return [m.group(1)] if m else []
    label = h.split('「')[0] if kind == 'cite' else h.split(':')[0]
    return [w for w in re.findall(r'[가-힣]{2,}|[A-Za-z]{4,}', label) if w not in STOP]


def fmt_paper(n, h):
    """'Damas F, … (2016). 제목. 학술지, 594(18), 5209–5222. DOI' → '[n] F. Damas et al., 학술지 594, 5209 (2016).'"""
    doi = re.search(r'https?://(?:dx\.)?doi\.org/\S+', h)
    doi = doi.group(0).rstrip('.') if doi else ''
    body = h.replace(doi, '').strip()
    m = re.match(r'^(?P<auth>.+?)\s*\((?P<year>\d{4})\)\.\s*(?P<rest>.+)$', body)
    if not m:
        return f'[{n}] {body} {{한 줄 요약}}', doi
    names = [a.strip() for a in m['auth'].split(',') if a.strip()]
    first = names[0].split()
    if len(first) >= 2 and re.fullmatch(r'[A-Z]{1,3}', first[-1]):
        fa = ' '.join(f'{c}.' for c in first[-1]) + ' ' + ' '.join(first[:-1])
    else:
        fa = names[0]
    etal = ' et al.' if len(names) > 1 else ''
    j = re.search(r'\.\s+(?P<jn>[^.]+?),\s*(?P<vol>\d+)(?:\([^)]*\))?,\s*(?P<p1>[A-Za-z]?\d+)', m['rest'])
    title = m['rest'][:j.start()].strip() if j else m['rest']
    cite = f"{fa}{etal}, {j['jn']} {j['vol']}, {j['p1']} ({m['year']})" if j else f"{fa}{etal} ({m['year']})"
    return f'[{n}] {cite}. {{한 줄 요약 — 원제: {short(title, 70)}}}', doi


def provenance(V, P):
    """최종 프로젝트 미디어마다 원본 경로·이용 조건을 찾아 AI 사진·스톡을 가린다."""
    idx = {}
    for p in V.rglob('*'):
        if p.suffix.lower() in MEDIA_EXT and p.is_file():
            idx.setdefault(nfc(p.stem), []).append(nfc(rel(p)))
    bundle = {}
    bj = TP.part(V, 'capcut') / '편집자료_목록.json'
    if bj.exists():
        for it in C.read_json(bj).get('items', []):
            info = dict(source=nfc(it.get('source', '')), license=nfc(it.get('license', '')))
            for k in ('source', 'bundle_file'):
                if it.get(k):
                    bundle[stem_of(it[k])] = info
    lib = {}
    lj = ROOT / (C.load_profile(ROOT).get('stock_library') or 'stock/library.json')   # (선택) 스톡 목록
    if lj.exists():
        for a in C.read_json(lj):
            lib[a['id']] = nfc(a.get('license_name', '') + ' ' + a.get('creator', ''))
    out = {}
    for m in P['media']:
        st = m['stem']
        if st in out:
            out[st]['at'].append(m['start'])
            continue
        b = bundle.get(st) or next((v for k, v in bundle.items() if st.startswith(k) or k.startswith(st)), None)
        paths = idx.get(st, []) + ([b['source']] if b else []) + [m['path']]
        lic = [b['license']] if b else []
        lic += [lib[t] for t in re.split(r'[_\s]+', st) if t in lib]
        if any('stock/' in p for p in paths) and not lic:
            lic.append('스톡')
        if m['main'] and m['path'] == P['main_src']:
            kind = '촬영본'
        elif re.search(r'범퍼|bumper', st, re.I):
            kind = '범퍼'
        elif any(AI_MARK.search(p) for p in paths):
            kind = 'AI 사진'
        elif any(STOCK_MARK.search(x) for x in lic):
            kind = '스톡' if not b or '자체' not in b['license'] else '자체 제작 + 스톡'
        elif b or len(paths) > 1:
            kind = '기록 있음'
        else:
            kind = '출처 기록 없음'
        prov = list(dict.fromkeys(x.group(0).capitalize() for s in lic for x in PROVIDER.finditer(s)))
        out[st] = dict(kind=kind, at=[m['start']], track=m['track'], paths=paths[:-1], license=lic, providers=prov)
    return out


# ── 고정댓글 ─────────────────────────────────────────
def key_title(url):
    py = ROOT / '.venv' / 'bin' / 'python'
    try:
        r = subprocess.run([str(py if py.exists() else sys.executable), '-m', 'yt_dlp', '--skip-download', '--no-warnings',
                            '--no-playlist', '--print', 'title', url], capture_output=True, text=True, timeout=90)
        out = [x for x in r.stdout.splitlines() if x.strip()]
        if r.returncode == 0 and out:
            return nfc(out[-1].strip()), ''
        return None, (r.stderr or '').strip()[-300:]
    except Exception as e:
        return None, str(e)[:300]


def write_out(path, text, keep=True):
    """초안을 쓴다. 내용이 다른 파일이 있으면 '<이름>_이전_<시각>'으로 옮겨 둔다(keep=False 인 검사 보고는 그냥 새로 쓴다)."""
    if path.exists():
        if path.read_text('utf-8') == text:
            return '그대로'
        if not keep:
            path.write_text(text, 'utf-8')
            return '새로 씀'
        bak = path.with_name(f"{path.stem}_이전_{time.strftime('%m%d_%H%M%S', time.localtime(path.stat().st_mtime))}{path.suffix}")
        os.replace(path, bak)
        path.write_text(text, 'utf-8')
        return f'새로 씀(이전 것: {bak.name})'
    path.write_text(text, 'utf-8')
    return '새로 씀'


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='최종 CapCut 프로젝트 → 챕터 후보·설명란·고정댓글 초안(S5)')
    ap.add_argument('project', help='사용자가 마무리한 최종 CapCut 프로젝트(이름·폴더·draft_info.json, 읽기만 함)')
    ap.add_argument('--video', required=True, help='영상 폴더(작업 폴더 안 <영상 이름>/)')
    ap.add_argument('--type', help='해시태그 표의 행 이름(profile.md "### 설명란 해시태그"). 없으면 해시태그를 넣지 않는다')
    ap.add_argument('--part', help='해시태그 표의 (부위) 자리에 넣을 말')
    ap.add_argument('--key-url', help='관련 영상 URL')
    ap.add_argument('--key-title', help='관련 영상 실제 제목(주면 yt-dlp 로 확인하지 않음)')
    ap.add_argument('--sources', help="자료목록 MD('설명란' 절의 붙여넣기 블록과 '파일·출처' 표)")
    ap.add_argument('--chapters', help="사람이 고른 챕터 목록(MD·txt의 'mm:ss 이름' 줄) — 주면 자동 후보 대신 검사만")
    ap.add_argument('--compare', help='자동 후보를 이 파일의 챕터와 비교(규칙 점검용)')
    ap.add_argument('--export', help='내보낸 최종 영상(없으면 업로드 폴더에서 찾음)')
    ap.add_argument('--capcut-dir')
    a = ap.parse_args()

    try:
        V = (TP.topic_folder(a.video, ROOT) if TP.TOPIC_ID.match(a.video) else Path(a.video).expanduser()).resolve()
    except ValueError as e:
        C.die(str(e))
    if not V.is_dir():
        C.die(f'영상 폴더가 없습니다: {a.video}')
    P = read_project(a.project, a.capcut_dir)
    dur = P['duration']
    sents = sentences(P['subs'])
    if not P['subs']:
        C.die('프로젝트에 자막(글자 트랙)이 없어 챕터·CTA를 찾을 수 없습니다.')
    rep = [f"# 업로드 초안 검사 — {P['name']}", '',
           f"- 프로젝트: `{P['name']}` (최종 길이 {C.mmss(dur)}, draft 저장 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(P['mtime']))}) — 읽기만 함",
           f"- 만든 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}", '- 채울 곳은 `{…}` 자리표시다. 최종본은 에이전트가 고쳐 `유튜브_설명란.txt`·`고정댓글.txt`로 옮긴다.', '']
    say = []      # 콘솔 요약

    # 1) 챕터
    cands, bumper = collect(P, sents)
    kept = pick(cands, dur)
    rep += ['## 1. 챕터', '']
    if a.chapters:
        chs = read_chapters(a.chapters)
        probs = check(chs, dur)
        rep += [f"사람이 고른 목록 `{rel(a.chapters)}` {len(chs)}개를 검사했다(자동 후보는 참고로만 아래에 둔다).", '',
                '| 시각 | 이름 | 그 시각의 자막 문장 | 자동 후보 |', '|---|---|---|---|']
        for c in chs:
            s = sentence_near(sents, c['sec'])
            near = next((k for k in cands if abs(math.floor(k['t']) - c['sec']) <= NEAR), None)
            rep.append(f"| {clock(c['sec'])} | {c['name']} | {short(s['text'], 45) if s else '—'} | "
                       f"{near['kind'] if near else '—'} |")
        chapter_lines = [f"{clock(c['sec'])} {c['name']}" for c in chs]
        say.append(f"챕터 {len(chs)}개 검사: " + ('통과' if not probs else f'문제 {len(probs)}건'))
    else:
        chs = [dict(sec=int(math.floor(c['t'])), name=short(c['line'] or c['why'])) for c in kept]
        probs = check(chs, dur)
        rep += [f"자동 후보 {len(cands)}개 중 10초 규칙으로 {len(kept)}개를 골랐다. 이름은 경계의 첫 자막 문장(초안)이다 — "
                "검색할 말을 앞에 두고, 8분 안팎이면 큰 구간 5개 정도로 줄인다.", '',
                '| 시각 | 근거 | 이름 초안(첫 문장) |', '|---|---|---|']
        for c in kept:
            rep.append(f"| {clock(c['t'])} | {c['kind']} {c['why']} | {short(c['line'], 50)} |")
        chapter_lines = [f"{clock(c['sec'])} {{검색 키워드: 구체적인 답 — 경계 말: {c['name']}}}" for c in chs]
        say.append(f'챕터 후보 {len(cands)}개 → {len(kept)}개 고름')
    rep += ['', '**규칙 검사(00:00 시작·오름차순·각 10초 이상·길이 안·3개 이상):** ' + ('통과' if not probs else '문제 있음')]
    rep += [f'- {p}' for p in probs]
    rep += ['', '<details><summary>자동 후보 전부</summary>', '', '| 시각 | 근거 | 점수 | 고름 | 첫 문장 |', '|---|---|---|---|---|']
    for c in cands:
        rep.append(f"| {C.mmss(c['t'])} | {c['kind']} {c['why']} | {c['score']} | {c.get('drop') or 'O'} | {short(c['line'], 40)} |")
    rep += ['', '</details>', '']
    if a.compare:
        exp = read_chapters(a.compare)
        kept_t = [math.floor(c['t']) for c in kept]
        raw_t = [math.floor(c['t']) for c in cands]
        hit_raw = [e for e in exp if any(abs(t - e['sec']) <= NEAR for t in raw_t)]
        hit_kept = [e for e in exp if any(abs(t - e['sec']) <= NEAR for t in kept_t)]
        extra = [t for t in kept_t if not any(abs(t - e['sec']) <= NEAR for e in exp)]
        miss = [e for e in exp if e not in hit_raw]
        rep += [f"### 비교: `{rel(a.compare)}` 챕터 {len(exp)}개 (±{NEAR}초)", '',
                f"- 후보 전부가 포함: **{len(hit_raw)}/{len(exp)}**", f"- 고른 목록과 일치: **{len(hit_kept)}/{len(exp)}**, 고른 목록에만 있음 {len(extra)}개"
                + (f" ({', '.join(clock(t) for t in extra)})" if extra else '')]
        rep += [f"- 후보에 없음: {clock(e['sec'])} {e['name']} — 그 시각 문장: “{short(sentence_near(sents, e['sec'])['text'], 40)}”"
                for e in miss if sentence_near(sents, e['sec'])]
        rep.append('')
        say.append(f"비교: 후보 {len(hit_raw)}/{len(exp)} 포함, 고른 목록 {len(hit_kept)}/{len(exp)} 일치, 여분 {len(extra)}")

    exports = [Path(a.export).expanduser()] if a.export else sorted(
        [p for p in TP.part(V, 'upload').glob('*') if p.suffix.lower() in VIDEO_EXT and p.is_file()
         and (p.stat().st_mtime > P['mtime'] or re.search(r'업로드|최종|내보내|export|_음량', nfc(p.name), re.I))],
        key=lambda p: p.stat().st_mtime, reverse=True)
    if exports:
        tip = (f"내보낸 영상 `{rel(exports[0])}`이(가) 있다 → `youtube-chapter-timestamps` 스킬로 실제 발화 시작 기준 챕터를 뽑아 "
               "이 목록과 맞춘다(AGENTS.md 기준). 자막 시각은 말보다 조금 이르게 뜰 수 있다.")
        rep += ['> ' + tip, '']
        say.append('안내: ' + tip)

    # 2) 해시태그
    row, tags, tag_notes = hashtags(a.type, a.part) if a.type else ('(없음)', [], ['해시태그: --type 을 주지 않아 넣지 않음(profile.md 해시태그 표)'])
    rep += ['## 2. 해시태그', '', f"`{a.type}` → 표의 '{row}' 행: {' '.join(tags)}"] + [f'- {n}' for n in tag_notes] + ['']

    # 3) 근거·출처
    prov = provenance(V, P)
    final_stems = set(prov)
    papers, cites, figures, warns, dropped = [], [], [], [], []
    summary_note = page_note = False
    rows, entries = parse_sources(a.sources) if a.sources else ([], [])
    table_stems = {stem_of(f) for r in rows for f in r['files']}
    for e in entries:
        kind = group_kind(e['group'])
        keys = entry_keys(e, kind)
        present = [k for k in keys if any(k.lower() in s.lower() for s in final_stems)]
        known = [k for k in keys if any(k.lower() in s.lower() for s in table_stems | final_stems)]
        if not present and known:
            dropped.append(f"[{e['group']}] {short(e['head'], 60)} — 최종 프로젝트에 '{'·'.join(known)}' 미디어가 없어 뺐다")
            continue
        if not present:
            warns.append(f"[{e['group']}] {short(e['head'], 60)} — 미디어와 이어지지 않아 남겼다(직접 확인)")
        if kind == 'paper':
            papers.append(e)
            more = ' '.join(e['more'])
            summary_note |= '자체 요약' in more
            page_note |= bool(re.search(r'페이지', more) and re.search(r'빨간|표시', more) and '없음' not in more)
        elif kind == 'cite':
            cites.append(e)
        else:
            figures.append(e)
    for r in rows:      # 이용 조건이 있는 자료가 마무리에서 빠졌는지
        if re.search(r'CC BY|제3자|허락|Pexels|Mixkit|Pixabay', r['src'], re.I):
            for f in r['files']:
                st = stem_of(f)
                if not any(s.startswith(st) or st.startswith(s) for s in final_stems) and f not in P['all_texts']:
                    dropped.append(f"표: `{f}` ({short(r['src'], 50)}) — 최종 프로젝트에 없음")
    if not a.sources:
        warns.append('--sources 가 없어 논문·인용·그림 줄을 만들지 않았다')
    elif not entries:
        warns.append("자료목록에 '설명란' 절의 붙여넣기 블록(``` … ```)이 없어 출처 줄을 만들지 못했다")
    ai = {k: v for k, v in prov.items() if v['kind'] == 'AI 사진'}
    stock = {k: v for k, v in prov.items() if '스톡' in v['kind']}
    providers = list(dict.fromkeys(p for v in stock.values() for p in v['providers']))
    src_lines = []
    for n, e in enumerate(papers, 1):
        line, doi = fmt_paper(n, e['head'])
        src_lines += [line] + ([doi] if doi else []) + ['']
    if summary_note:
        src_lines += ['영상 속 연구 화면은 위 논문 내용을 정리한 자체 요약이며, 논문 페이지를 그대로 옮긴 것이 아닙니다.', '']
    elif page_note:
        src_lines += ['{원문 페이지를 보여 줬으면: 페이지·빨간 박스 표시 사실}', '']
    if cites:
        src_lines.append('[인용 영상]')
        for e in cites:
            url = re.search(r'https?://\S+', e['head'])
            src_lines += [e['head'].replace(url.group(0), '').strip() if url else e['head']] + ([url.group(0)] if url else [])
        src_lines.append('')
    notice = []
    for e in figures:
        notice += ['· ' + e['head']] + ['  ' + x for x in e['more']]
    if ai:
        notice.append('· 일부 장면 사진은 AI로 만든 재현 이미지이며 실제 인물이 아닙니다.')
    if stock:
        notice.append(f"· 일부 장면은 {'·'.join(providers) if providers else '{제공자}'} 무료 스톡 영상을 사용했습니다.")
    if notice:
        src_lines += ['[그림·영상 자료]'] + notice
    while src_lines and not src_lines[-1]:
        src_lines.pop()
    rep += ['## 3. 근거와 출처', '', f"- 자료목록: `{rel(a.sources)}`" if a.sources else '- 자료목록 없음',
            f"- 남긴 줄: 논문 {len(papers)} · 인용 영상 {len(cites)} · 그림 {len(figures)}"]
    rep += ['- **뺀 자료(최종본에서 빠짐):**'] + [f'  - {d}' for d in dropped] if dropped else ['- 뺀 자료: 없음']
    rep += [f'- 확인: {w}' for w in warns] + ['- 근거가 약한 대사의 숫자(예: 확인 안 된 %)는 설명란에 되풀이하지 않는다(upload_pack.md 3절).', '']
    for d in dropped:
        say.append('출처에서 뺌: ' + d)

    # 4) 고지 판단과 최종 미디어
    intro_ai = [(k, v) for k, v in ai.items() if bumper and min(v['at']) < bumper['start']]
    rep += ['## 4. AI·스톡 고지와 최종 미디어', '',
            f"- AI 사진 {len(ai)}개 → 고지 줄 {'넣음' if ai else '없음'}" + (f" ({', '.join(sorted(ai))})" if ai else ''),
            f"- 스톡 {len(stock)}개 → 고지 줄 {'넣음' if stock else '없음'}"
            + (f" ({', '.join(k + ': ' + ('·'.join(v['providers']) or '; '.join(v['license'])) for k, v in stock.items())})" if stock else '')]
    unknown = [k for k, v in prov.items() if v['kind'] == '출처 기록 없음']
    if unknown:
        rep.append(f"- 출처 기록 없는 미디어 {len(unknown)}개: {', '.join(unknown)} — 사용자 사진·직접 넣은 자료면 그대로, 아니면 출처를 확인해 설명란에 적는다")
    if ai:
        rep.append("- 업로드 설정의 '변경되거나 합성된 콘텐츠' 표시를 확인한다(upload_pack.md 6절).")
    if intro_ai:
        rep.append('- **도입부(범퍼 앞) AI 사진:** ' + ', '.join(f"{k} {C.mmss(min(v['at']))}" for k, v in intro_ai)
                   + " — preferences '도입부 AI 느낌 사진 금지'와 다르다. 사용자가 남긴 것이면 그대로 둔다.")
    rep += ['', '| 미디어(복제본 해시 뺌) | 판정 | 첫 시각 | 트랙 | 근거 |', '|---|---|---|---|---|']
    for k, v in sorted(prov.items(), key=lambda kv: min(kv[1]['at'])):
        ev = '; '.join(v['license']) or (v['paths'][0] if v['paths'] else '—')
        rep.append(f"| {k} | {v['kind']} | {C.mmss(min(v['at']))} | {v['track']} | {short(ev, 60)} |")
    rep.append('')

    # 5) 고정댓글
    title, err = (a.key_title, '') if a.key_title else (key_title(a.key_url) if a.key_url else (None, ''))
    cta = [s for s in sents if '고정댓글' in C.norm_text(s['text'])]
    cards = sorted({k for k in final_stems if re.search(r'고정\s*댓글|CTA', k, re.I)})
    rep += ['## 5. 고정댓글 확인', '',
            f"- 관련 영상: {a.key_url or '{관련 영상 URL — 없으면 이 줄을 지운다}'}",
            f"- 링크 영상 실제 제목: {'「' + title + '」' if title else '(확인 못 함' + (': ' + err if err else '') + ')'}"
            + (' — --key-title 로 받은 값' if a.key_title else (' — yt-dlp 로 확인' if title else ''))]
    rep += [f"- 영상 속 말({C.mmss(s['start'])}): “{s['text']}”" for s in cta] or ['- 영상 속 말: 자막에 "고정 댓글"이 없다']
    rep += [f'- CTA 카드: `{c}` — 카드 문구도 링크 내용과 맞는지 본다' for c in cards]
    rep += ['- 말과 링크 내용이 다르면 고정댓글은 **링크 내용대로** 쓰고, 같은 말을 하는 카드는 고칠지 사용자에게 묻는다(upload_pack.md 4절).', '']
    if a.key_url and not title:
        say.append(f'관련 영상 제목 확인 실패: {err}')

    # 초안 글
    kt = f' — 링크 영상 「{title}」' if title else ''
    desc = ['{첫 줄 — 핵심 키워드를 앞에, 무엇을 정리한 영상인지}', '{둘째 줄 — 영상의 답을 숫자로, 키워드를 문장 안에}', '',
            '{누가 왜 보는지와 근거(연구·진행자가 확인한 수치) — 키워드는 upload_pack.md 0절의 표에서}', '',
            '이 영상에서 답하는 질문', '· {사람들이 검색할 말을 넣은 질문 — 본문이 답하는 것만, 4~7줄}', '']
    if a.key_url:
        desc += [f'▶ {{관련 영상가 실제로 주는 것{kt}}}', a.key_url, '']
    desc += ['⏱ 타임스탬프'] + chapter_lines
    if src_lines:
        desc += ['', '📚 근거와 출처'] + src_lines
    desc += ['', ' '.join(tags)]  # 해시태그는 맨 끝(첫 줄은 핵심 요약, upload_pack.md 1절)
    desc_txt = '\n'.join(desc) + '\n'
    pin = [f"📌 {{영상에서 약속한 것}}, {{링크 영상이 실제로 주는 것}}부터 이렇게 챙겨 보세요 👉 {a.key_url or '{관련 영상 URL}'}",
           f'{{그 영상이 실제로 주는 것 한 줄{kt}}}',
           '{시청자 경험을 묻는 참여 질문 한 줄} 🙂', '',
           '──── 아래는 확인용 메모(붙여넣지 않음) ────',
           f"링크 영상 실제 제목: {'「' + title + '」' if title else '(확인 못 함)'}"]
    pin += [f"영상 속 말({C.mmss(s['start'])}): “{s['text']}”" for s in cta] or ['영상 속 말: 자막에 "고정 댓글"이 없음']
    pin += [f'CTA 카드: {c}' for c in cards] + ['말과 링크 내용이 다르면 링크 내용대로 쓴다. 같은 말을 하는 카드는 고칠지 사용자에게 묻는다.']
    pin_txt = '\n'.join(pin) + '\n'
    holes = len(re.findall(r'\{[^{}]+\}', desc_txt)) + len(re.findall(r'\{[^{}]+\}', '\n'.join(pin[:3])))
    rep += ['## 6. 남은 일', '', f'- 자리표시 {holes}곳: 설명(키워드 요약·질문)·관련 영상 줄·챕터 이름(키워드 앞)·논문 한 줄 요약·고정댓글 2줄', '- 제목 후보는 사용자가 정한다', '']

    out = TP.part(V, 'upload') / '업로드_초안'
    out.mkdir(exist_ok=True)
    res = [(n, write_out(out / n, t, keep)) for n, t, keep in (('유튜브_설명란_초안.txt', desc_txt, True), ('고정댓글_초안.txt', pin_txt, True),
                                                              ('챕터_검사.md', '\n'.join(rep) + '\n', False))]
    print(f"프로젝트 {P['name']} · 길이 {C.mmss(dur)} · 자막 {len(P['subs'])}조각 → 문장 {len(sents)}개")
    print(f"해시태그: {' '.join(tags)}" + ''.join(f'\n  [주의] {n}' for n in tag_notes))
    for s in say:
        print(s)
    for p in probs:
        print('  [챕터 문제] ' + p)
    print(f"고지: AI 사진 {len(ai)} · 스톡 {len(stock)}{' (' + '·'.join(providers) + ')' if providers else ''} · 관련 영상 제목: {title or '미확인'}")
    for n, r in res:
        print(f'  {rel(out / n)}: {r}')
    print(f'자리표시 {holes}곳이 남았습니다(grep "{{" 로 찾기).')


if __name__ == '__main__':
    main()
