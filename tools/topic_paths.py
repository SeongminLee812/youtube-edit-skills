#!/usr/bin/env python3
"""영상 폴더 안 단계별 폴더를 정한다(편집 스킬들이 폴더 이름을 직접 쓰지 않고 여기서 받는다).

영상 한 편 = 작업 폴더 안 `<영상 이름>/` 폴더 하나. 원본과 결과를 그 안에 둔다.
  <영상 이름>/
    촬영본.mp4 · 원고.txt          원본(읽기만). 이름은 자유
    편집/                         받아쓰기·컷 계획·덧입히기·HANDOFF.md·edit_state.json
    편집/화면자료/                  목차 전환 MOV 등 화면에 얹을 파일
    편집/캡컷_가져오기/              CapCut에 끌어 넣을 일반 파일
    업로드/                        내보낸 영상·설명란·고정댓글 초안

`profile.md`의 `videos_dir`를 주면 `--video 이름`을 그 폴더 아래에서 찾는다(기본: 작업 폴더 바로 아래).

  python3 tools/topic_paths.py <영상 폴더>            단계별 폴더를 보여 준다
  python3 tools/topic_paths.py <영상 폴더> edit
"""
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]

# 단계별 하위 폴더. 빈 값은 영상 폴더 바로 안이다.
LAYOUT = {'script': '', 'footage': '', 'research': '편집/research', 'edit': '편집', 'screen': '편집/화면자료',
          'capcut': '편집/캡컷_가져오기', 'upload': '업로드', 'retro': '편집'}
TOPIC = LEGACY = LAYOUT          # 예전 이름(다른 스크립트 호환)
TOPIC_ID = re.compile(r'^[TI]\d{3}$')     # 번호로 부르는 폴더(T###_이름처럼 앞에 번호를 붙였을 때)
TOPIC_NAME = re.compile(r'^[TI]\d{3}_')
LEGACY_HOME = 'videos'


def nfc(text):
    return unicodedata.normalize('NFC', str(text))


# ── 채널 프로필(profile.md) ──
def load_profile(root=None):
    """작업 폴더 루트의 profile.md(채널 프로필)에서 `키: 값` 줄을 읽는다. 없거나 비면 {}.

    위치: 환경변수 CHANNEL_PROFILE > <root>/profile.md (root 기본: PROJECT_ROOT 또는 현재 폴더).
    `<…>`로 남은 자리표시와 빈 값은 없는 것으로 본다. 키 목록은 claude-edit references/profile.template.md.
    """
    import os as _os
    path = _os.environ.get('CHANNEL_PROFILE') or str(Path(root or _os.environ.get('PROJECT_ROOT') or _os.getcwd()) / 'profile.md')
    try:
        text = Path(path).read_text(encoding='utf-8')
    except OSError:
        return {}
    out = {}
    for line in text.splitlines():
        m = re.match(r'^\s*[-*]?\s*`?([A-Za-z][A-Za-z0-9_]*)`?\s*:\s*(.*?)\s*$', line)
        if not m:
            continue
        val = m.group(2).strip().strip('`').strip()
        if val and not (val.startswith('<') and val.endswith('>')):
            out[m.group(1)] = val
    return out


def theme_pairs(root=None):
    """모션 카드·목차 전환 HTML에 넘길 스타일(theme_accent·theme_accent2·theme_font). 프로필에 없으면 빈 dict."""
    p = load_profile(root)
    pick = lambda *ks: next((p[k] for k in ks if p.get(k)), None)
    out = {'theme_accent': pick('brand_color_1', 'chapter_color'), 'theme_accent2': pick('brand_color_2'),
           'theme_font': pick('motion_font', 'chapter_font')}
    return {k: v for k, v in out.items() if v}


def is_topic(folder):
    return bool(TOPIC_NAME.match(nfc(Path(folder).name)))


def layout(folder):
    return LAYOUT


def part(folder, key):
    """영상 폴더 안 단계 폴더. key: script·footage·research·edit·screen·capcut·upload·retro."""
    sub = LAYOUT[key]
    return Path(folder) / sub if sub else Path(folder)


def display_name(folder):
    """CapCut 프로젝트 앞머리: 앞의 날짜(YYYY-MM-DD_)나 번호(T###_)를 뺀 폴더 이름."""
    return re.sub(r'^(\d{4}-\d{2}-\d{2}|[TI]\d{3})_', '', nfc(Path(folder).name))


def topic_id(folder):
    m = re.match(r'^([TI]\d{3})_', nfc(Path(folder).name))
    return m.group(1) if m else None


def videos_home(root=ROOT):
    return Path(root) / (load_profile(root).get('videos_dir') or '.')


def topic_folder(tid, root=ROOT):
    """번호(T###) → 영상 폴더(<videos_dir>/T###_*)."""
    hits = [p for p in sorted(videos_home(root).glob(tid + '_*')) if p.is_dir()]
    if len(hits) > 1:
        raise ValueError('{} 폴더가 둘 이상입니다: {}'.format(tid, ', '.join(p.name for p in hits)))
    if not hits:
        raise ValueError('{} 로 시작하는 영상 폴더가 없습니다. 영상 폴더 경로를 그대로 주세요.'.format(tid))
    return hits[0]


def resolve(value, root=ROOT):
    """번호, 영상 폴더 이름, 작업 폴더 기준 경로, 절대 경로 → 영상 폴더 Path(있는지는 부르는 쪽이 본다)."""
    value = nfc(value).strip().rstrip('/')
    if TOPIC_ID.match(value):
        return topic_folder(value, root)
    p = Path(value).expanduser()
    if p.is_absolute():
        return p
    for base in (Path(root), videos_home(root)):
        if (base / p).exists():
            return base / p
    return Path(root) / p


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    folder = resolve(sys.argv[1])
    keys = sys.argv[2:] or list(LAYOUT)
    print('{} (영상 폴더)'.format(folder))
    for k in keys:
        print('  {:<10} {}'.format(k, part(folder, k)))


if __name__ == '__main__':
    main()
