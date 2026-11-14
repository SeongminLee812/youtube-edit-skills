"""채널 공용 자막 고침 사전(subtitle_dictionary.json(profile.md 의 subtitle_dictionary))을 검사하고, 사용자가 손으로 고친 자막에서 새 항목 후보를 뽑습니다(claude-edit S1·게이트 C 뒤).

check: 사전 형식(from·to·mode)과 겹침을 검사한다. 영상 고침 사전(03_script/subtitle_replace.json)도 함께 주면 둘 사이의 겹침을 본다.
  - 같은 from이 두 번, from == to, mode가 auto|ask 밖이면 오류
  - 한 항목의 to 안에 다른 항목의 from이 있으면 경고(앞에서 바꾼 말을 뒤에서 또 바꿀 수 있음)
learn: 클로드가 만든 자막(스테이징 _timeline.json 또는 CapCut 프로젝트)과 사용자가 마무리한 CapCut 프로젝트의 자막을 비교해
  낱말 단위로 바뀐 곳을 후보 표로 낸다. CapCut 프로젝트는 읽기만 한다. 줄 나눔·문장 옮기기(넣기·빼기만 한 곳)는 후보에서 뺀다.
  숫자가 바뀐 곳은 내용 고침일 수 있어 따로 표시한다. 후보를 사전에 넣을지는 사람이 정한다(채널 공통이면 공용 사전, 그 영상만이면 영상 사전).

사용 예(프로젝트 루트에서):
  python subtitle_dict.py check [--video-dict <편집>/03_script/subtitle_replace.json]
  python subtitle_dict.py learn --built <편집>/02_cut/capcut_staging/<영상>_초벌_v003_timeline.json \
      --final "<영상>_초벌_v006" --out <편집>/자막_고침_후보.md
  (<편집>·<화면자료>: 영상 폴더 안 편집·편집/화면자료 — tools/topic_paths.py)
"""
import argparse
import difflib
import json
import re
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
ROOT = Path(os.environ.get('PROJECT_ROOT') or os.getcwd()).resolve()     # 프로젝트 루트(PROJECT_ROOT 또는 작업 폴더)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'smartdaddy-video-edit' / 'scripts'))
import _common as C  # noqa: E402

DICT = ROOT / (C.load_profile(ROOT).get('subtitle_dictionary') or 'subtitle_dictionary.json')
MODES = ('auto', 'ask')


def load(path):
    """사전 파일 → [(from, to, mode)]. 영상 사전({"틀린 말": "고칠 말"})이면 모두 auto."""
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(d.get('entries'), list):
        return [(e.get('from'), e.get('to'), e.get('mode', 'auto')) for e in d['entries']]
    return [(k, v, 'auto') for k, v in d.items()]


def check(a):
    errs, warns = [], []
    sets = [('공용', load(a.dict))] + ([('영상', load(a.video_dict))] if a.video_dict else [])
    for name, items in sets:
        seen = set()
        for i, (w, r, mode) in enumerate(items, 1):
            if not w or r is None:
                errs.append(f'{name} {i}번: from·to가 비었음')
                continue
            if w == r:
                errs.append(f'{name} {i}번: from과 to가 같음 "{w}"')
            if mode not in MODES:
                errs.append(f'{name} {i}번: mode "{mode}"는 auto|ask가 아님')
            if w in seen:
                errs.append(f'{name} {i}번: "{w}"가 두 번 있음')
            seen.add(w)
    every = [(name, w, r) for name, items in sets for w, r, _ in items if w and r]
    for n1, w1, r1 in every:
        for n2, w2, r2 in every:
            if (n1, w1) != (n2, w2) and w2 in r1 and w2 not in w1:
                warns.append(f'{n1} "{w1}"→"{r1}"의 결과에 {n2} "{w2}"가 들어 있음(또 바뀔 수 있음)')
    if a.video_dict:
        common = {w for _, w, _ in every if sum(1 for _, x, _ in every if x == w) > 1}
        for w in sorted(common):
            warns.append(f'"{w}"가 공용·영상 사전 모두에 있음(영상 사전이 이김)')
    for x in errs:
        print('[오류]', x)
    for x in warns:
        print('[주의]', x)
    n = sum(len(items) for _, items in sets)
    print(f'검사 끝: 항목 {n}개 · 오류 {len(errs)} · 주의 {len(warns)}')
    return 1 if errs else 0


def draft_texts(name, capcut_dir):
    cc = C.find_capcut_dir(capcut_dir)
    f = C.draft_file(cc / name)
    if not f:
        C.die(f'CapCut 프로젝트를 찾지 못했습니다: {cc / name}')
    out = []
    for t in C.read_draft(f).get('materials', {}).get('texts', []):
        c = t.get('content', '')
        try:
            c = json.loads(c).get('text', c)
        except (ValueError, AttributeError):
            pass
        if str(c).strip():
            out.append(str(c).strip())
    return out


def built_texts(x, capcut_dir):
    p = Path(x)
    if p.suffix == '.json' and p.exists():
        return [s[2] for s in json.loads(p.read_text(encoding='utf-8'))['subtitles']]
    return draft_texts(x, capcut_dir)


def candidates(built, final):
    """낱말 단위로 바뀐 곳 → [(고치기 전 구, 고친 구, 전 자막, 고친 자막)]. 바뀐 낱말 앞 낱말을 붙여 구로 만든다."""
    bset, seen, out = set(built), set(), []
    for f in final:
        if f in bset or f in seen:
            continue
        seen.add(f)
        b = max(built, key=lambda x: difflib.SequenceMatcher(None, x, f).ratio())
        if difflib.SequenceMatcher(None, b, f).ratio() < 0.75:
            continue
        bw, fw = b.split(), f.split()
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, bw, fw).get_opcodes():
            if tag != 'replace' or i2 - i1 > 3 or j2 - j1 > 3:
                continue                   # 넣기·빼기만 한 곳은 줄 나눔·문장 옮기기
            k = 1 if i1 and j1 and bw[i1 - 1] == fw[j1 - 1] else 0
            out.append((' '.join(bw[i1 - k:i2]), ' '.join(fw[j1 - k:j2]), b, f))
    return out


def learn(a):
    built, final = built_texts(a.built, a.capcut_dir), draft_texts(a.final, a.capcut_dir)
    known = {w for w, _, _ in load(a.dict)}
    if a.video_dict:
        known |= {w for w, _, _ in load(a.video_dict)}
    rows = candidates(built, final)
    lines = [f'# 자막 고침 후보: {Path(a.built).name} → {a.final}', '',
             f'클로드 자막 {len(built)}개 · 마무리본 글자 {len(final)}개 · 후보 {len(rows)}개. '
             '채널 공통이면 `subtitle_dictionary.json(profile.md 의 subtitle_dictionary)`(진짜 낱말일 수 있으면 mode ask), 이 영상만이면 영상 사전에 넣는다.', '',
             '| 고치기 전 | 고친 말 | 표시 | 전 자막 | 고친 자막 |', '|---|---|---|---|---|']
    for w, r, b, f in rows:
        tag = '이미 사전에 있음' if any(k in w for k in known) else ('숫자 바뀜(내용 고침?)' if re.search(r'\d', w + r) and re.sub(r'\D', '', w) != re.sub(r'\D', '', r) else '')
        lines.append(f'| {w} | {r} | {tag} | {b} | {f} |')
    text = '\n'.join(lines) + '\n'
    if a.out:
        Path(a.out).write_text(text, encoding='utf-8')
        print(f'후보 {len(rows)}개 → {a.out}')
    else:
        print(text)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('check', 'learn'):
        p = sub.add_parser(name)
        p.add_argument('--dict', default=str(DICT), help=f'채널 공용 사전(기본 {DICT.relative_to(ROOT)})')
        p.add_argument('--video-dict', help='영상 고침 사전 03_script/subtitle_replace.json')
        if name == 'learn':
            p.add_argument('--built', required=True, help='클로드가 만든 자막: 스테이징 _timeline.json 또는 CapCut 프로젝트 이름')
            p.add_argument('--final', required=True, help='사용자가 마무리한 CapCut 프로젝트 이름')
            p.add_argument('--out', help='후보 표 Markdown(없으면 화면에)')
            p.add_argument('--capcut-dir', default='', help='CapCut 프로젝트 폴더(기본: 자동으로 찾음)')
    a = ap.parse_args()
    return check(a) if a.cmd == 'check' else learn(a)


if __name__ == '__main__':
    sys.exit(main())
