"""받아쓰기를 촬영 원고와 맞춰 봅니다(파일은 읽기만 함). 원고 표기로 고치는 건 발음이 거의 같은 받아쓰기 오류뿐입니다.

원고를 보고 원테이크로 찍되 말을 조금씩 바꿔 하는 촬영본을 위한 교차검증이다.
  - 재테이크 후보: 이어지는 두 문장 클립이 원고의 같은 자리를 말함 → 앞 클립을 --cut 후보로 제안
  - 잡음 후보: 짧은 "음, 음, 음" 같은 받아쓰기 환각
  - 말하지 않은 원고 문장: 촬영 구간 안인데 받아쓰기에 없는 원고 문장(빠뜨렸거나 받아쓰기가 놓침)
  - 원고에 없는 말·말을 바꿔 한 곳: 자막은 실제로 한 말 그대로 둔다
  - 표기 맞춤: 원고와 발음이 거의 같은 낱말만 원고 표기로 바꾸고(예: "2분알" → "2분할"),
    원고 문장 끝 부호(. ? ! ,)를 붙여 자막이 문장 끝에서 끊기게 한다.

capcut_build.py --script 는 원고와 글자 수가 비슷하면 다르게 말한 곳도 원고 문구로 바꾸고("계획도 짜보고" →
"계획도 세우고"), 원고가 촬영 구간보다 길면 남은 원고를 마지막 낱말에 붙인다. 원고를 고쳐 말하는 촬영본에서는
--script 대신 이 도구가 만든 words_script.json 을 --words 로 넘긴다.

원고: 촬영원고 .md는 '**읽을 대사**' 묶음만, youtube-script-production .json은 "lines"만, 그 밖(.txt)은 모든 줄을 읽는다.
문장 클립: --plan(컷 계획의 남긴 문장)이 있으면 그것, 없으면 받아쓰기 segments.json 을 쓴다.
재테이크를 찾으려면 사람이 --cut 을 넣기 전의 컷 계획을 준다.

결과(--out 폴더):
  script_check.md     사람이 읽는 보고서
  script_check.json   같은 내용(다른 도구용)
  words_script.json   표기를 맞춘 단어 시각(capcut_build.py --words 로 쓴다)
  cut_suggest.txt     재테이크·잡음 후보의 --cut 인자(붙이기 전에 사람이 확인)

사용 예:
  python script_check.py --script 촬영원고_v5.md --words 편집/01_asr/words.json --plan 편집/02_cut/plan.json --out 편집/03_script
  python script_check.py --script 한국어_원고.txt --words 편집/01_asr/words.json --out 편집/03_script   # 컷 계획 전
"""
import argparse
import bisect
import difflib
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

QUOTES = '“”‘’"\''
NOISE = re.compile(r'^(?:[음어아으흠네]+[\s,.…~!?]*)+$')
CUE = re.compile(r'\((?:강조|연출|화면|촬영|편집|자막|효과|모션|B롤|컷)[^)]*\)')     # 읽지 않는 연출 지시
FIX_MIN = 0.75          # 원고 표기로 바꿀 때 필요한 자모 유사도
FIX_MAX_CH = 6          # 바꿀 수 있는 한 구간의 최대 글자 수(더 길면 말을 바꾼 것으로 본다)


# ── 원고 읽기 ──────────────────────────────────────────
def read_lines(path):
    raw = path.read_text('utf-8-sig')
    lines = []
    if path.suffix.lower() == '.json':
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == 'lines' and isinstance(v, list):
                        lines.extend(x for x in v if isinstance(x, str))
                    else:
                        walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(json.loads(raw))
    elif '**읽을 대사**' in raw:
        on = got = False
        for line in raw.splitlines():
            s = line.strip()
            if s == '**읽을 대사**':
                on, got = True, False
            elif on and not s:
                on = not got
            elif on:
                lines.append(s)
                got = True
    else:       # '[1막 · 주장] … (0:30–1:05)' 같은 구간 머리말·링크 줄은 읽지 않는다
        lines = [x.strip() for x in raw.splitlines() if x.strip() and not x.strip().startswith(('#', '>', '['))]
    return [x.strip() for x in lines if x.strip()]


def script_text(lines):
    """대사를 한 줄로 잇고 연출 지시 '(강조 - 화면 확대)'를 뺀다. 돌려주는 것: (대사, [(지시가 있던 글자 위치, 지시)])"""
    text = re.sub(r'\s+', ' ', ' '.join(lines))
    out, cues, last, n = [], [], 0, 0
    for m in CUE.finditer(text):
        out.append(text[last:m.start()])
        n += m.start() - last
        cues.append((n, m.group(0)[1:-1].strip()))
        last = m.end()
    out.append(text[last:])
    return ''.join(out), cues


def split_sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.?!])\s+|(?<=[.?!][”’"\'])\s+', text) if s.strip()]


def norm(s):
    return ''.join(ch.lower() for ch in s if ch.isalnum())


def jamo(s):
    out = []
    for ch in s:
        o = ord(ch) - 0xAC00
        if 0 <= o < 11172:
            out += [chr(0x1100 + o // 588), chr(0x1161 + o % 588 // 28)] + ([chr(0x11A7 + o % 28)] if o % 28 else [])
        else:
            out.append(ch)
    return ''.join(out)


def sounds_alike(a, b):
    return difflib.SequenceMatcher(None, jamo(a), jamo(b), autojunk=False).ratio()


# ── 표기 맞춤(단어) ───────────────────────────────────
def fix_words(W, S_text, cues=()):
    """원고 전체와 받아쓰기 전체를 글자 단위로 맞춰, 발음이 거의 같은 낱말만 원고 표기로 바꾼다.
    연출 지시는 바로 뒤 대사를 실제로 말한 시각(원본 초)을 찾아 돌려준다."""
    A, a_word = [], []
    for k, w in enumerate(W):
        for ch in w[2]:
            if ch.isalnum():
                A.append(ch.lower())
                a_word.append(k)
    B, b_pos = [], []
    for i, ch in enumerate(S_text):
        if ch.isalnum():
            B.append(ch.lower())
            b_pos.append(i)
    A, B = ''.join(A), ''.join(B)
    amap, b2a = [None] * len(A), {}
    for op in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
        for i in range(op[1], op[2]):
            amap[i] = op
            if op[0] == 'equal':
                b2a[op[3] + i - op[1]] = i
    cue_at = []
    for p, cue in cues:
        j = bisect.bisect_left(b_pos, p)
        hit = next((b2a[x] for x in range(j, min(j + 30, len(B))) if x in b2a), None)   # 뒤 대사 30글자 안에서 처음 맞는 글자
        said = S_text[p:p + 24].strip()
        if hit is None:
            cue_at.append(dict(cue=cue, script=said, at=None, word=None))
        else:
            k = a_word[hit]
            cue_at.append(dict(cue=cue, script=said, at=W[k][0], word=W[k][2].strip()))

    def bidx(i, first):
        tag, i1, _, j1, j2 = amap[i]
        if tag == 'equal':
            return j1 + (i - i1)
        return j1 if first else j2 - 1

    span = {}
    for i, k in enumerate(a_word):
        s, _ = span.get(k, (i, i))
        span[k] = (s, i + 1)
    out, fixed = [], []
    for k, w in enumerate(W):
        t = w[2]
        if k not in span:
            out.append([w[0], w[1], t])
            continue
        s, e = span[k]
        ops = {amap[i] for i in range(s, e)}
        bad = [op for op in ops if op[0] != 'equal']
        # 받아쓰기 오류는 글자 수가 같고 소리만 비슷하다("분알"→"분할"). 글자 수가 다르면 말을 바꾼 것("준비해보지만").
        if bad and all(op[0] == 'replace' and op[1] >= s and op[2] <= e and op[2] - op[1] <= FIX_MAX_CH
                       and op[2] - op[1] == op[4] - op[3] and sounds_alike(A[op[1]:op[2]], B[op[3]:op[4]]) >= 0.5
                       for op in bad):
            lo, hi = bidx(s, True), bidx(e - 1, False)
            if lo <= hi:
                cand = ''.join(ch for ch in S_text[b_pos[lo]:b_pos[hi] + 1] if ch not in QUOTES).strip()
                if cand and sounds_alike(norm(t), norm(cand)) >= FIX_MIN:
                    lead = t[:len(t) - len(t.lstrip())]
                    tail = ''.join(ch for ch in t.rstrip()[len(t.rstrip().rstrip('.?!,…')):])
                    fixed.append(dict(start=w[0], end=w[1], asr=t.strip(), script=cand))
                    t = lead + cand + tail
                    bad = []
        if not bad and amap[e - 1][0] == 'equal':      # 원고 문장 끝 부호를 붙인다
            j = b_pos[bidx(e - 1, False)] + 1
            while j < len(S_text) and S_text[j] in QUOTES:
                j += 1
            if j < len(S_text) and S_text[j] in '.?!,' and not t.rstrip().endswith(('.', '?', '!', ',', '…')):
                t = t.rstrip() + S_text[j]
        out.append([w[0], w[1], t])
    return out, fixed, cue_at


# ── 문장 클립 ↔ 원고 문장 ─────────────────────────────
def locate(u, sents_n, window=None, near=None):
    """문장 클립 글자 u가 원고 몇 번째 문장의 어디를 말했는지: (문장, 시작, 끝, 클립을 덮은 비율, 맞은 원고 글자 위치들)
    비슷하게 맞는 문장이 여럿이면(덮은 비율 0.05 안) 바로 앞 클립이 말한 문장(near)에 가까운 것을 고른다.
    원고는 대체로 앞에서부터 읽으므로 "증명해 줄 겁니다"가 먼 곳의 같은 말에 붙지 않게 한다."""
    cands = []
    for si in window or range(len(sents_n)):
        s = sents_n[si]
        sm = difflib.SequenceMatcher(None, u, s, autojunk=False)
        if sm.real_quick_ratio() < 0.2:
            continue
        blocks = [b for b in sm.get_matching_blocks() if b.size >= 2]
        m = sum(b.size for b in blocks)
        if m:
            cands.append((m / len(u), si, blocks))
    if not cands:
        return None
    top = max(c[0] for c in cands)
    cov, si, blocks = min((c for c in cands if c[0] >= top - 0.05),
                          key=lambda c: (abs(c[1] - near) if near is not None else 0, -c[0]))
    return (si, blocks[0].b, blocks[-1].b + blocks[-1].size, cov,
            frozenset(i for b in blocks for i in range(b.b, b.b + b.size)))


def restart_at(words, later_text):
    """뒤 테이크 첫머리(두 낱말)가 앞 클립 중간에서 다시 시작되면 그 낱말의 시작 시각. 처음부터 같거나 못 찾으면 None."""
    head = norm(' '.join(later_text.split()[:2]))[:6]
    if len(head) < 2:
        return None
    for m in range(1, len(words)):
        if norm(''.join(w[2] for w in words[m:])).startswith(head):
            return words[m][0]
    return None


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='받아쓰기 ↔ 촬영 원고 교차검증')
    ap.add_argument('--script', required=True, help='촬영 원고(.md/.json/.txt)')
    ap.add_argument('--words', required=True, help='받아쓰기 words.json')
    ap.add_argument('--plan', help='컷 계획 plan.json(사람이 --cut 넣기 전 것을 주면 재테이크를 찾는다)')
    ap.add_argument('--segments', help='plan 이 없을 때 쓸 받아쓰기 segments.json(기본: words.json 옆)')
    ap.add_argument('--out', required=True, help='결과 폴더')
    a = ap.parse_args()

    sp, wp = Path(a.script), Path(a.words)
    for p in (sp, wp):
        if not p.exists():
            C.die(f'파일이 없습니다: {p}')
    S_text, cues = script_text(read_lines(sp))
    sents = split_sentences(S_text)
    if not sents:
        C.die(f'원고에서 읽을 대사를 찾지 못했습니다: {sp}')
    sents_n = [norm(s) for s in sents]
    W = C.read_json(wp)
    if a.plan:
        units = [dict(start=s['src_in'], end=s['src_out'], text=s['text'], words=s.get('words', []))
                 for s in C.read_json(a.plan)['segments']]
        src = '컷 계획의 남긴 문장'
    else:
        segp = Path(a.segments) if a.segments else wp.with_name('segments.json')
        units = [dict(start=s['start'], end=s['end'], text=s['text'],
                      words=[w for w in W if s['start'] - 0.05 <= w[0] < s['end']]) for s in C.read_json(segp)]
        src = '받아쓰기 문장(컷 계획 전 · 시각은 컷 계획에서 다시 확인)'
    prev = None
    for u in units:
        u['loc'] = locate(norm(u['text']), sents_n, near=prev) if norm(u['text']) else None
        if u['loc'] and u['loc'][3] >= 0.5:
            prev = u['loc'][0]
    # 덜 맞는 클립은 확실히 맞는 앞뒤 클립 사이의 원고에서만 다시 찾는다(흔한 말이 먼 문장에 붙지 않게)
    sure = [i for i, u in enumerate(units) if u['loc'] and u['loc'][3] >= 0.6]
    for i, u in enumerate(units):
        if u['loc'] and u['loc'][3] < 0.6 and sure:
            lo = max([units[x]['loc'][0] for x in sure if x < i] or [0])
            hi = min([units[x]['loc'][0] for x in sure if x > i] or [len(sents_n) - 1])
            u['loc'] = locate(norm(u['text']), sents_n, range(max(0, lo - 1), min(len(sents_n), hi + 2)))

    # 잡음·원고에 없는 말
    noise, adlib, para = [], [], []
    for i, u in enumerate(units):
        toks = re.findall(r'\w+', u['text'])
        if u['end'] - u['start'] <= 1.5 and (NOISE.match(u['text'].strip()) or (len(toks) >= 3 and len(set(toks)) == 1)):
            noise.append(i)
        elif not u['loc'] or u['loc'][3] < 0.35:
            adlib.append(i)
        elif u['loc'][3] < 0.85:
            para.append(i)
    # 재테이크: 뒤 클립이 앞 클립(3개 · 20초 안)과 원고의 같은 글자를 다시 말함. 겹침은 실제로 맞은 원고 글자로 잰다
    # (처음~끝 범위로 재면 "5세트"·"입니다" 같은 흔한 말 때문에 다른 내용도 겹쳐 보인다). 둘 중 하나일 때만 재테이크로 본다:
    #   - 앞 테이크의 40% 이상을 다시 말했고 첫머리(두 낱말) 소리가 비슷함("그런데 우리처럼" → "그러나 우리처럼").
    #     다시 말할 때 줄여 말하기도 해서("회사 다니면서"를 뺌) 절반보다 낮게 잡는다.
    #     첫머리가 다르면 같은 낱말을 많이 쓴 다른 문장이다("목요일 … 회의 3번" ↔ "일요일 … 회의 3번").
    #   - 앞 클립 중간에서 뒤 테이크 첫머리로 다시 시작했고, 뒤 테이크의 60% 이상이 앞과 같음(→ 그 낱말부터만 지움,
    #     "그 시기와 | 바쁜 하루가…" → "바쁜 하루가…")
    # 사이에 원고의 다른 문장을 말한 클립이 있으면 이미 넘어간 것이라 재테이크가 아니다.
    retake, flagged = [], set()
    for j, u in enumerate(units):
        q = u['loc']
        if j in noise or not q or q[3] < 0.5:
            continue
        for k in range(j - 1, max(-1, j - 4), -1):
            p = units[k]['loc']
            if k in noise or k in flagged or not p or p[0] != q[0] or p[3] < 0.5 or u['start'] - units[k]['end'] > 20:
                continue
            if any(units[x]['loc'] and units[x]['loc'][3] >= 0.5 and units[x]['loc'][0] != q[0]
                   for x in range(k + 1, j) if x not in noise):
                continue
            inter = len(p[4] & q[4])
            cut_from = restart_at(units[k]['words'], u['text'])
            head = [norm(' '.join(x.split()[:2]))[:8] for x in (units[k]['text'], u['text'])]
            same_head = sounds_alike(*head) >= 0.6
            if (inter >= 0.4 * len(p[4]) and same_head) or (cut_from is not None and inter >= 0.6 * len(q[4])):
                retake.append((k, j, cut_from))
                flagged.add(k)
    retake.sort()
    rcut = {k: (c if c is not None else units[k]['start'], units[k]['end']) for k, _, c in retake}   # 지울 원본 구간
    # 말하지 않은 원고 문장(촬영 구간 안에서만)
    cover = [[False] * len(s) for s in sents_n]
    for k, u in enumerate(units):
        if u['loc'] and u['loc'][3] >= 0.5 and not (k in rcut and rcut[k][0] == u['start']):
            si, b0, b1 = u['loc'][:3]
            for i in range(b0, b1):
                cover[si][i] = True
    para = [i for i in para if i not in rcut]
    said = [si for si, c in enumerate(cover) if c and sum(c) / len(c) >= 0.3]
    missing = [si for si in range(min(said), max(said) + 1) if si not in said] if said else []

    # 받아쓰기가 환각 문구로 뺀 문장("구독과 좋아요 부탁드리고요")이 원고에 있으면 실제로 말한 것이라 되살린다.
    # 낱말 시각은 없어서 그 문장 시간을 낱말 수로 나눈다.
    restored = []
    meta = wp.with_name('transcribe_meta.json')
    for d in (C.read_json(meta).get('dropped', []) if meta.exists() else []):
        n = norm(d['text'])
        # 맞는 글자 합으로 본다: 말하면서 "이"를 끼워 넣으면("오늘 이 영상이 도움이") 이어진 한 덩어리는 짧아진다
        if len(n) >= 4 and any(sum(b.size for b in difflib.SequenceMatcher(None, n, s, autojunk=False).get_matching_blocks())
                               >= 0.75 * len(n) for s in sents_n):
            toks = d['text'].split()
            step = (d['end'] - d['start']) / max(1, len(toks))
            W = W + [[round(d['start'] + i * step, 3), round(d['start'] + (i + 1) * step, 3), ' ' + t] for i, t in enumerate(toks)]
            restored.append(d)
    W = sorted(W, key=lambda w: w[0])
    W2, fixed, cue_at = fix_words([list(w) for w in W], S_text, cues)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    C.write_json(out / 'words_script.json', W2, compact=True)
    cuts = [f'--cut {rcut[k][0]:.2f}-{rcut[k][1]:.2f}' for k, _, _ in retake] + \
           [f'--cut {units[k]["start"]:.2f}-{units[k]["end"]:.2f}' for k in noise]
    (out / 'cut_suggest.txt').write_text(' '.join(cuts) + '\n', 'utf-8')

    def clip(i):
        u = units[i]
        return f'원본 {C.mmss(u["start"])}~{C.mmss(u["end"])} "{u["text"].strip()}"'

    def sent(si):
        return f'원고 {si + 1}번: {sents[si]}'

    rng = f'{min(said) + 1}~{max(said) + 1}번' if said else '없음'
    L = [f'# 원고 교차검증 · {sp.name}', '',
         f'- 원고 문장 {len(sents)}개 · 이 촬영 구간이 말한 원고 {rng} · 문장 클립 {len(units)}개({src})',
         f'- 재테이크 후보 {len(retake)}곳 · 잡음 후보 {len(noise)}곳 · 말하지 않은 원고 문장 {len(missing)}개 · '
         f'원고에 없는 말 {len(adlib)}곳 · 말을 바꿔 한 곳 {len(para)}곳 · 원고 표기로 고친 낱말 {len(fixed)}개',
         '- 자막은 실제로 한 말이 기준이다. 원고 표기로 바꾸는 건 발음이 거의 같은 받아쓰기 오류뿐이다.', '',
         '## 재테이크 후보 (앞 테이크를 지우고 뒤 테이크를 남김)', '']
    L += [f'- {clip(k)}\n  - 뒤 테이크: {clip(j)}\n  - {sent(units[j]["loc"][0])}\n'
          f'  - `--cut {rcut[k][0]:.2f}-{rcut[k][1]:.2f}`'
          + (f' · 클립 중간 {C.mmss(c)}부터 다시 시작 — 낱말 사이를 자르니 들어 보고 확인' if c is not None else '')
          for k, j, c in retake] or ['- 없음']
    L += ['', '## 잡음 후보', '']
    L += [f'- {clip(k)} · `--cut {units[k]["start"]:.2f}-{units[k]["end"]:.2f}`' for k in noise] or ['- 없음']
    L += ['', '## 말하지 않은 원고 문장 (빠뜨렸는지, 받아쓰기가 놓쳤는지 들어 보기)', '']
    L += [f'- {sent(si)}' for si in missing] or ['- 없음']
    L += ['', '## 원고에 없는 말 (즉흥 멘트 · 자막은 그대로)', '']
    L += [f'- {clip(i)}' for i in adlib] or ['- 없음']
    L += ['', '## 말을 바꿔 한 곳 (자막은 실제로 한 말 그대로)', '']
    L += [f'- {clip(i)}\n  - {sent(units[i]["loc"][0])}' for i in para] or ['- 없음']
    L += ['', '## 원고 표기로 고친 낱말 (words_script.json)', '']
    L += [f'- {C.mmss(f["start"])} "{f["asr"]}" → "{f["script"]}"' for f in fixed] or ['- 없음']
    L += ['', '## 받아쓰기 환각 거르기에서 되살린 문장 (원고에 있어 실제로 말한 것으로 봄 · 낱말 시각은 어림값)', '']
    L += [f'- 원본 {C.mmss(d["start"])}~{C.mmss(d["end"])} "{d["text"]}"' for d in restored] or ['- 없음']
    L += ['', '## 원고의 연출 지시 → 실제 시각 (덧입히기 후보 · overlays.json 에 `"src": 원본 초`로 쓴다)', '']
    L += [(f'- 원본 {C.mmss(c["at"])} (`"src": {c["at"]:.2f}`) · ({c["cue"]}) · 말한 낱말 "{c["word"]}" · 원고 "{c["script"]}…"'
           if c['at'] is not None else f'- 못 찾음 · ({c["cue"]}) · 원고 "{c["script"]}…" — 이 구간을 안 찍었거나 다르게 말함')
          for c in cue_at] or ['- 없음']
    (out / 'script_check.md').write_text('\n'.join(L) + '\n', 'utf-8')
    C.write_json(out / 'script_check.json', dict(
        script=str(sp), units_from=src, sentences=sents,
        retake=[dict(cut=list(rcut[k]), partial=c is not None, text=units[k]['text'], keep=units[j]['text'],
                     sentence=units[j]['loc'][0] + 1) for k, j, c in retake],
        noise=[dict(cut=[units[k]['start'], units[k]['end']], text=units[k]['text']) for k in noise],
        missing=[dict(sentence=si + 1, text=sents[si]) for si in missing],
        adlib=[dict(at=[units[i]['start'], units[i]['end']], text=units[i]['text']) for i in adlib],
        paraphrase=[dict(at=[units[i]['start'], units[i]['end']], text=units[i]['text'],
                         sentence=units[i]['loc'][0] + 1) for i in para],
        fixed=fixed, cues=cue_at, restored=restored))
    print(f'원고 {len(sents)}문장 · 클립 {len(units)}개 → 재테이크 {len(retake)} · 잡음 {len(noise)} · '
          f'빠진 문장 {len(missing)} · 원고에 없는 말 {len(adlib)} · 바꿔 말함 {len(para)} · 표기 고침 {len(fixed)} · '
          f'연출 지시 {sum(c["at"] is not None for c in cue_at)}/{len(cue_at)}')
    print(f'  {out / "script_check.md"}')
    if cuts:
        print('  제안 컷: ' + ' '.join(cuts))


if __name__ == '__main__':
    main()
