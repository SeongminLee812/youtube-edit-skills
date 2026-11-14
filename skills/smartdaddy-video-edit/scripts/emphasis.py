"""CapCut 프로젝트의 자막 가운데 고른 문장을 '강조 자막'으로 바꾸고, 효과음·펀치인 확대·목차 이름표·옆 스티커를 더해
새 스테이징 프로젝트로 씁니다.

기존 프로젝트(--project)는 읽기만 한다. 결과는 --out 스테이징 폴더(새 draft id)에만 쓰고, CapCut 등록은 --install 때만 한다.
수치 기준: references/emphasis.md.

  - 강조 자막: 그 문장 자막 재료 전체를 기본 글자 크기 × size_mult(2.4)로, 굵게·흰 글자·검은 외곽선·옅은 그림자·배경 없음.
    color_word 범위만 유형별 색(정정 보조색, 공감 없음, 나머지 노랑). 등장 애니메이션 없음. 항상 한 줄.
    화면 폭 max_width(80%)를 넘을 것 같으면 넘지 않을 때까지 글자를 줄인다(아래 '폭 추정').
    세로는 기본 자막 자리 그대로, 큰 글자의 아래가 bottom_limit 를 넘으면 그만큼 올린다.
    phrase 를 주면 자막을 둘로 나눠(앞·뒤 구절만 가능) 그 구절만 강조한다(25자 넘는 자막의 핵심 구절).
    재료·애니메이션 재료를 다른 자막과 같이 쓰면 복제해 그 세그먼트만 바꾼다. 1.2초보다 짧으면 다음 자막 시작 전까지 늘린다.
  - 효과음: 유형별 기본(훅·원인지목·핵심 = ding 차임, 공감 = pop 뾱, 결과 = rise, 정정 = 없음)을 '강조 효과음' 트랙에 −20dB로,
    자막 시작(결과는 0.1초 앞)에. 항목에서 sfx: false / "pop" 처럼 바꿀 수 있다. 기존 오디오는 건드리지 않는다.
  - 확대(zoom, 기본 켬): 강조가 뜨는 프레임에 메인 영상을 ×1.2 로 하드컷, 문장이 끝나는 프레임에 원래 구도로 하드컷(램프 없음).
    메인 트랙 바로 위 '강조 확대' 트랙에 같은 원본 구간을 한 번 더 깐다(소리 0, 크롭·회전·효과 그대로). 지우면 원래 화면이 나온다.
    머리 위가 잘리지 않게 y_anchor(0 = 가운데 기준, 1 = 화면 위 가장자리 고정)만큼 아래로 내린다.
    전체 화면 자료(알파 없는 사진·영상 덧입히기, 챕터 전환 막, 메인 트랙의 범퍼·CTA)가 덮는 강조에는 넣지 않는다.
  - 목차 이름표(spec "toc"): 왼쪽 위에 지금 챕터 이름을 CapCut 네이티브 텍스트(+배경 상자)로 띄운다. 전체 화면 자료 위에서는 숨긴다.
  - 옆 스티커(spec "stickers"): 이모지(Apple Color Emoji) 또는 실제 사진을 흰 테두리 둥근 스티커 + 흰 라벨로 만든
    알파 MOV(ProRes 4444, 3프레임 팝인·3프레임 팝아웃)를 오른쪽 위(얼굴 안전영역 x 520–1400 밖)에 얹는다.
  - [규칙 점검]: 분당 강조 수(2~4), 강조 간격 4초 미만, 3문장 이상 연속, 25자 초과, 효과음 1분 3개 초과, 같은 소리 20초 안 재사용,
    연달아 강조의 두 번째에 효과음.

spec(JSON):
  {"style": {...아래 DEFAULT_STYLE 일부 덮어쓰기},
   "items": [{"id": "E01", "match": "자막 문구 일부 또는 전체", "at": 12.7,      ← at: 편집본 초(같은 문구가 여럿이면 가장 가까운 것)
              "kind": "훅|원인지목|공감|정정|결과|핵심"(옛 이름 고민=공감, 기대=결과),
              "color_word": "아니에요"(선택), "sfx": true|false|"ding"|"<wav 경로>", "zoom": true|false(선택),
              "phrase": "자막 앞·뒤 구절"(선택), "split_at": 63.85(선택, phrase 경계 편집본 초. 없으면 글자 비율로 추정),
              "note": "고른 이유"(선택)}],
   "toc": {"items": [{"at": 0, "text": "영상 제목"}, {"at": 50.85, "num": "1", "text": "첫 번째 챕터"}], "end": null},
   "stickers": [{"id": "S1", "at": 59.83, "dur": 6, "image": "<사진 경로>" | "emoji": "🔥", "label": "한 번 더",
                 "pos": "right_top|left_mid"}]}
  match·color_word·phrase 는 띄어쓰기·부호를 빼고 비교한다. 못 찾으면 [못 넣음]으로 알리고 다음 항목을 계속한다.

사용:
  python <스킬 폴더>/smartdaddy-video-edit/scripts/emphasis.py --project <CapCut 프로젝트 이름 또는 폴더> \
      --spec emphasis.json --out <새 스테이징 폴더> [--audio-template <CapCut 템플릿>] [--media-dir <스티커 MOV 폴더>] [--dry-run] \
      [--install --name <새 이름>]
  --audio-template: --project 에 오디오 클립이 없을 때 효과음 클립 형식을 빌릴 프로젝트(읽기만). 조립 때 쓴 --template 과 같게.
  --media-dir: 스티커 MOV 를 만들 곳(기본: --out 옆 '<이름>_media/'). CapCut 은 ~/Movies/CapCut_편집미디어/ 복제본을 쓴다.
  --install: CapCut을 끈 상태에서만, 사용자 허락 뒤에만. 이름은 --out 폴더 이름과 같아야 한다.

CapCut 재료에서 바꾸는 필드:
  강조 자막 content(JSON 문자열) → styles[*].size·bold·fill·strokes·shadows·range(낱말 색 범위는 UTF-16 글자 수), text(phrase 일 때)
  강조 자막 재료 → font_size, text_color, border_color, border_width, border_alpha, has_shadow, shadow_color, shadow_alpha,
         shadow_distance, shadow_smoothing, shadow_angle, shadow_point, background_alpha(0), check_flag(외곽선 8·그림자 32 켜고 배경 16 끔),
         bold_width
  강조 자막 세그먼트 → clip.transform.y(필요할 때만 위로), target_timerange(1.2초 미만 연장·phrase 나누기), extra_material_refs
  확대 세그먼트 → 메인 세그먼트 복제 + clip.scale·uniform_scale(×1.2), clip.transform.y, volume 0
  목차 이름표 → 새 텍스트 재료(type text): styles fill(차콜·번호 키 컬러)·bold·size, background_color·alpha·width·height·round_radius,
         check_flag(배경 16 켜고 외곽선 8·그림자 32 끔), 세그먼트 clip.transform(x, y)
"""
import argparse
import copy
import functools
import json
import math
import subprocess
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402
import capcut_build as B  # noqa: E402

ROOT = Path(os.environ.get('PROJECT_ROOT') or os.getcwd()).resolve()     # 프로젝트 루트(PROJECT_ROOT 또는 작업 폴더)
SFX_DIR = C.load_profile().get('sfx_dir') or 'sfx'     # 효과음 폴더(profile.md 의 sfx_dir, 없으면 make_sfx.py sfx 로 만든다)
KINDS = ('훅', '원인지목', '공감', '정정', '결과', '핵심')
KIND_ALIAS = {'고민': '공감', '기대': '결과'}
YELLOW, CORAL = '#FFE58C', '#FF6B4A'
BGM_TRACK = 'BGM'      # 배경음악 트랙 이름(speed_version.py 도 이 이름으로 BGM 을 찾는다)
BGM_BELOW_VOICE = 15    # BGM 은 목소리 통합 음량보다 이만큼 아래(dB)

DEFAULT_STYLE = {
    'size_mult': 2.4,            # 기본 자막 글자 크기의 배수
    'max_width': 0.80,           # 화면 폭 대비 최대 글줄 폭
    'bold': True,
    'fill': '#FFFFFF',
    'stroke': '#000000',
    'stroke_width': 0.08,        # CapCut 외곽선 두께 값(기본 자막 0.06)
    'shadow': {'color': '#000000', 'alpha': 0.35, 'distance': 4.0, 'smoothing': 0.6, 'angle': -45.0},
    'colors': {'훅': YELLOW, '원인지목': YELLOW, '핵심': YELLOW, '결과': YELLOW, '정정': CORAL, '공감': None},
    # 정정에는 효과음을 넣지 않는다. 핵심 문장은 맑은 차임, 고민·수치는 짧게 떨어지는 소리(references/emphasis.md 1절).
    #   훅·핵심 = 약 0.8초 맑은 차임(ding: 두 음이 0.09초 어긋나 들어옴), 고민·경험 고백 = 0.2초 짧게 떨어지는 '뾱'(pop)
    'sfx_files': {'훅': f'{SFX_DIR}/ding.wav', '원인지목': f'{SFX_DIR}/ding.wav', '핵심': f'{SFX_DIR}/ding.wav',
                  '공감': f'{SFX_DIR}/pop.wav', '결과': f'{SFX_DIR}/rise.wav'},
    'sfx_db': -20.0,
    'sfx_lead': {'결과': 0.1},   # 자막 시작보다 이만큼 앞
    'sfx_track': '강조 효과음',
    'min_hold': 1.2,             # 강조 최소 유지(초)
    'bottom_limit': 0.94,        # 글자 아래(외곽선 포함)가 화면 높이의 이 비율을 넘지 않게(그림자·유튜브 재생바 여유)
    'center_min': 0.86,          # 아무리 올려도 글자 중심은 화면 높이 86% 아래
    'px_per_unit': 11.72,        # 1080p 에서 CapCut 글자 크기 1 = 글꼴 화소(아래 '폭 추정')
    'max_chars': 25,
    'zoom': {'on': True, 'scale': 1.2, 'y_anchor': 0.8, 'track': '강조 확대'},
    # 목차 이름표: 왼쪽 위 흰 상자(x 64–583·y 54–149, 글자 높이 37px), 번호는 키 컬러. 1080p 기준 화소
    'toc': {'track': '목차 이름표', 'glyph_px': 37, 'left': 64, 'center_y': 101.5, 'fill': '#1D2433', 'accent': (C.load_profile().get('brand_color_1') or C.load_profile().get('chapter_color') or '#3B5BDB'),
            'bg': '#FFFFFF', 'bg_w': 0.40, 'bg_h': 0.30, 'radius': 0.45, 'min_piece': 0.5},
    'sticker': {'track': '강조 스티커', 'dur': 6.0, 'box': [460, 500],
                'pos': {'right_top': [1655, 320], 'left_mid': [265, 560]}},
}

# ── 폭 추정 ───────────────────────────────────────────
# CapCut 렌더를 열 수 없어서 글줄 폭은 추정한다.
# 보정: CapCut 내보내기 프레임에서 잰 크기 5 자막
#   '그런데 사실 그렇게 더 먹을 필요가 없었어요'의 흰 글자 폭이 1009px(1920×1080)였다.
#   같은 문장을 Apple SD Gothic Neo 100px 로 재면 1722px → 글꼴 58.6px = 크기 1당 11.72px.
#   CapCut '시스템' 글꼴(SystemFont/en.ttf)은 한글이 없어 Mac 에서 Apple SD 고딕 계열로 대체되므로 같은 글꼴로 잰다.
# 추정식: 폭 = Pillow(Apple SD Gothic Neo Bold, 크기×11.72×캔버스높이/1080).getlength(문장) × 1.04(굵게 여유)
#          + 외곽선 2쪽(stroke_width × 글꼴px × 0.6 × 2).
# 한계: 다른 글꼴·CapCut 의 굵게 처리·자간 설정이면 몇 % 다를 수 있다. Pillow·글꼴이 없으면 글자 종류별 평균 폭
#       (한글 0.86em, 공백 0.25em, 숫자·영문 0.55em, 그 밖 0.4em)으로 대신하며 오차가 더 크다.
#       그래서 max_width 80% 는 여유를 두고 정한 값이며, CapCut 에서 줄바꿈이 생기면 글자 크기를 손으로 줄인다.
BOLD_FONTS = [('/System/Library/Fonts/AppleSDGothicNeo.ttc', 6), ('C:/Windows/Fonts/malgunbd.ttf', 0),
              ('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', 0)]
EMOJI_FONT = '/System/Library/Fonts/Apple Color Emoji.ttc'
GLYPH_H = 0.84          # 한글 글자 높이 / 글꼴 px (보정 프레임: 49px / 58.6px)


@functools.lru_cache(16)
def _font(px):
    try:
        from PIL import ImageFont
    except Exception:
        return None
    for p, idx in BOLD_FONTS:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, px, index=idx)
            except Exception:
                continue
    return None


def text_width_px(text, font_px):
    f = _font(max(4, int(round(font_px))))
    if f is not None:
        return f.getlength(text) * (font_px / max(4, int(round(font_px)))) * 1.04
    w = 0.0
    for ch in text:
        if '가' <= ch <= '힣':
            w += 0.86
        elif ch.isspace():
            w += 0.25
        elif ch.isalnum():
            w += 0.55
        else:
            w += 0.4
    return w * font_px * 1.04


def line_width(text, size, st, canvas_h):
    fpx = size * st['px_per_unit'] * canvas_h / 1080
    return text_width_px(text, fpx) + 2 * st['stroke_width'] * fpx * 0.6, fpx


# ── 도우미 ───────────────────────────────────────────
def u16(s):
    return len(s.encode('utf-16-le')) // 2


def hex01(c):
    c = c.lstrip('#')
    return [round(int(c[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)]


def hex255(c):
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def solid(c):
    return {'content': {'solid': {'color': hex01(c)}, 'render_type': 'solid'}}


def resolve(p):
    p = Path(p).expanduser()
    if p.is_absolute():
        return p
    for base in (Path.cwd(), ROOT):
        if (base / p).exists():
            return (base / p).resolve()
    return (ROOT / p).resolve()


def rng(s):
    r = s['target_timerange']
    return r['start'] / C.US, (r['start'] + r['duration']) / C.US


def merge_style(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_style(out[k], v)
        else:
            out[k] = v
    return out


def norm_map(text):
    """(띄어쓰기·부호를 뺀 글, 그 글의 각 글자가 원문 몇 번째 글자인지)."""
    keep, idx = [], []
    for i, ch in enumerate(text):
        if C.norm_text(ch):
            keep.append(ch)
            idx.append(i)
    return ''.join(keep), idx


def find_range(text, word):
    """원문에서 word(띄어쓰기·부호 무시)의 [시작, 끝) 원문 글자 위치."""
    if not word:
        return None
    if word in text:
        i = text.index(word)
        return i, i + len(word)
    t, idx = norm_map(text)
    w = C.norm_text(word)
    if not w or w not in t:
        return None
    k = t.index(w)
    return idx[k], idx[k + len(w) - 1] + 1


@functools.lru_cache(256)
def has_alpha(path):
    """영상에 알파 채널이 있는지(ffprobe pix_fmt). 사진(PNG)은 알파가 있어도 덮개로 보지 않게 True."""
    p = Path(path)
    if p.suffix.lower() in ('.png', '.webp'):
        return True
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=pix_fmt', '-of',
                        'csv=p=0', str(p)], capture_output=True, text=True)
    pf = r.stdout.strip()
    return any(x in pf for x in ('yuva', 'rgba', 'argb', 'bgra', 'abgr', 'gbrap', 'ya'))


def subtract(iv, cuts):
    """구간 iv=(a,b)에서 cuts 를 뺀 조각들."""
    out = [iv]
    for c0, c1 in sorted(cuts):
        nxt = []
        for a, b in out:
            if c1 <= a or c0 >= b:
                nxt.append((a, b))
                continue
            if c0 > a:
                nxt.append((a, c0))
            if c1 < b:
                nxt.append((c1, b))
        out = nxt
    return out


# ── 강조 한 개 ────────────────────────────────────────
def restyle(m, text, size, st, kind, color_word, log, iid):
    """자막 재료 m 을 강조 모양으로 바꾼다(제자리)."""
    c = json.loads(m['content'])
    base = copy.deepcopy((c.get('styles') or [{}])[0])
    n = u16(text)
    sh = st['shadow']
    base.update(range=[0, n], size=round(size, 2), bold=bool(st['bold']), useLetterColor=True)
    base['fill'] = solid(st['fill'])
    base['strokes'] = [{'width': st['stroke_width'], 'mode': 0, **solid(st['stroke'])}]
    # 그림자: CapCut 사용자 프로젝트에 실제 저장 예가 없어(2026-11-14 확인) 재료 필드와 content shadows 를 함께 넣는다
    base['shadows'] = [{'diffuse': round(sh['smoothing'] / 6, 4), 'alpha': sh['alpha'], 'distance': sh['distance'],
                        'angle': sh['angle'], **solid(sh['color'])}]
    styles = [base]
    col = st['colors'].get(kind)
    if color_word:
        r = find_range(text, color_word)
        if r is None:
            log.append(f"  [못 넣음] {iid} 색 낱말 '{color_word}'이 자막 '{text}'에 없음(색 없이 강조)")
        elif not col:
            log.append(f"  [주의] {iid} 유형 '{kind}'은 낱말 색을 쓰지 않음('{color_word}' 무시)")
        else:
            a, b = u16(text[:r[0]]), u16(text[:r[1]])
            styles = []
            for s0, s1, colr in ((0, a, None), (a, b, col), (b, n, None)):
                if s1 > s0:
                    x = copy.deepcopy(base)
                    x['range'] = [s0, s1]
                    if colr:
                        x['fill'] = solid(colr)
                    styles.append(x)
    c['text'] = text
    c['styles'] = styles
    m['content'] = json.dumps(c, ensure_ascii=False)
    ang = math.radians(sh['angle'])
    m.update(font_size=round(size, 2), text_color=st['fill'].lower(), border_color=st['stroke'], border_alpha=1.0,
             border_width=st['stroke_width'], has_shadow=True, shadow_color=sh['color'], shadow_alpha=sh['alpha'],
             shadow_distance=sh['distance'], shadow_smoothing=sh['smoothing'], shadow_angle=sh['angle'],
             shadow_point={'x': round(math.cos(ang) * 0.9, 6), 'y': round(math.sin(ang) * 0.9, 6)},
             background_alpha=0.0)
    if st['bold'] and 'bold_width' in m:
        m['bold_width'] = 0.008
    if isinstance(m.get('check_flag'), int):
        m['check_flag'] = (m['check_flag'] | 8 | 32) & ~16      # 외곽선·그림자 켬, 배경 끔
    return styles


def set_plain_text(m, text):
    """재료 글만 바꾸고 첫 스타일을 전체 범위로(나눈 자막의 기본 쪽)."""
    c = json.loads(m['content'])
    st0 = copy.deepcopy((c.get('styles') or [{}])[0])
    st0['range'] = [0, u16(text)]
    c['text'] = text
    c['styles'] = [st0]
    m['content'] = json.dumps(c, ensure_ascii=False)


# ── 스티커 MOV ────────────────────────────────────────
def _rounded_mask(size, r):
    from PIL import Image, ImageDraw
    mk = Image.new('L', size, 0)
    ImageDraw.Draw(mk).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=r, fill=255)
    return mk


def sticker_image(spec, box, st):
    """스티커 한 장(RGBA, box 크기): 그림(흰 테두리·그림자) + 바탕색 라벨."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    W, H = box
    toc = st['toc']
    canvas = Image.new('RGBA', (W, H))
    art_h = int(H * 0.74)
    if spec.get('emoji'):
        ef = ImageFont.truetype(EMOJI_FONT, 160)
        em = Image.new('RGBA', (220, 220))
        ImageDraw.Draw(em).text((110, 110), spec['emoji'], font=ef, anchor='mm', embedded_color=True)
        em = em.crop(em.getbbox())
        k = min(W * 0.58 / em.width, art_h * 0.74 / em.height)          # 가로·세로 모두 칸 안에
        em = em.resize((int(em.width * k), int(em.height * k)), Image.LANCZOS)
        pad = 18
        art = Image.new('RGBA', (em.width + pad * 2, em.height + pad * 2))
        art.alpha_composite(em, (pad, pad))
        a = art.getchannel('A').filter(ImageFilter.MaxFilter(23))          # 흰 '오려 낸' 테두리
        border = Image.new('RGBA', art.size, (255, 255, 255, 0))
        border.putalpha(a)
        art = Image.alpha_composite(border, art)
    else:
        ph = Image.open(resolve(spec['image'])).convert('RGB')
        tw, th = int(W * 0.86), art_h - 30
        sc = max(tw / ph.width, th / ph.height)
        ph = ph.resize((int(ph.width * sc), int(ph.height * sc)), Image.LANCZOS)
        x0, y0 = (ph.width - tw) // 2, (ph.height - th) // 2
        ph = ph.crop((x0, y0, x0 + tw, y0 + th)).convert('RGBA')
        bw = 12
        art = Image.new('RGBA', (tw + bw * 2, th + bw * 2), (255, 255, 255, 255))
        art.putalpha(_rounded_mask(art.size, 30))
        ph.putalpha(_rounded_mask(ph.size, 22))
        art.alpha_composite(ph, (bw, bw))
        art = art.rotate(-3, resample=Image.BICUBIC, expand=True)       # 종이 콜라주 느낌으로 살짝 기울임
    shadow = Image.new('RGBA', art.size, (0, 0, 0, 0))
    shadow.putalpha(art.getchannel('A').point(lambda v: int(v * 0.35)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    ax = (W - art.width) // 2
    ay = max(0, (art_h - art.height) // 2)
    canvas.alpha_composite(shadow, (ax + 6, ay + 8))
    canvas.alpha_composite(art, (ax, ay))
    if spec.get('label'):
        f = ImageFont.truetype(BOLD_FONTS[0][0], 40, index=BOLD_FONTS[0][1])
        tb = f.getbbox(spec['label'], anchor='ls')
        lw, lh = tb[2] - tb[0] + 44, 64
        lx, ly = (W - lw) // 2, min(H - lh - 6, ay + art.height - 22)
        lab = Image.new('RGBA', (lw, lh))
        d = ImageDraw.Draw(lab)
        d.rounded_rectangle([0, 0, lw - 1, lh - 1], radius=14, fill=hex255(toc['bg']) + (255,))
        d.text((22 - tb[0], lh / 2 + (-tb[1]) / 2 - 2), spec['label'], font=f, anchor='ls', fill=hex255(toc['fill']) + (255,))
        ls = Image.new('RGBA', (lw, lh), (0, 0, 0, 0))
        ls.putalpha(lab.getchannel('A').point(lambda v: int(v * 0.3)))
        canvas.alpha_composite(ls.filter(ImageFilter.GaussianBlur(5)), (lx + 3, ly + 5))
        canvas.alpha_composite(lab, (lx, ly))
    return canvas


def bgm_layout(pieces, fdur, fin, fout, seam=0.15, loop=True):
    """BGM 클립 배치(emphasis.py 넣기와 speed_version.py 배속 뒤 다시 깔기가 같이 쓴다).
    pieces=[(시작, 끝)] 구간마다 곡 처음부터 깔고, 곡(fdur)보다 길면 반복한다. 구간 처음 fin·끝 fout, 반복 이음매는 seam 페이드.
    돌려주는 것: [(시작, 길이, 페이드인, 페이드아웃)] (초). 클립은 모두 원래 빠르기(speed 1.0), 원본 0초부터."""
    out = []
    for p0, p1 in pieces:
        t = p0
        while t < p1 - 0.05:
            du = min(fdur, p1 - t)
            first, last = t == p0, t + du >= p1 - 0.05
            out.append((t, du, fin if first else seam, fout if last else seam))
            t += du
            if not loop:
                break
    return out


def strip_loudness(D, seg):
    """새 오디오 클립에서 '음량 정규화' 재료를 뗀다. 템플릿(1012) 클립의 loudness 재료는 enable=True·목표 −23 LUFS·
    다른 파일의 측정값을 그대로 들고 와, CapCut 이 클립 볼륨(−20dB 등) 대신 정규화로 크기를 바꿀 수 있다(2026-11-14 발견)."""
    ids = {m['id'] for m in D['materials'].get('loudnesses', [])}
    drop = [r for r in seg.get('extra_material_refs', []) if r in ids]
    seg['extra_material_refs'] = [r for r in seg.get('extra_material_refs', []) if r not in ids]
    if drop:
        D['materials']['loudnesses'] = [m for m in D['materials']['loudnesses'] if m['id'] not in drop]


def add_fade(D, seg, fin, fout):
    """CapCut 오디오 페이드: audio_fades 재료 {type audio_fade, fade_type 0, fade_in_duration, fade_out_duration}(마이크로초)를
    클립 extra_material_refs 에 건다. CapCut 사용자 프로젝트에 실제로 저장된 형식(2026-11-14 확인)."""
    for r in list(seg.get('extra_material_refs', [])):
        if any(m['id'] == r for m in D['materials'].get('audio_fades', [])):
            seg['extra_material_refs'].remove(r)
    if fin <= 0 and fout <= 0:
        return
    m = dict(id=B.uid(), type='audio_fade', fade_type=0, fade_in_duration=int(round(fin * C.US)),
             fade_out_duration=int(round(fout * C.US)))
    D['materials'].setdefault('audio_fades', []).append(m)
    seg['extra_material_refs'].append(m['id'])


def lufs(path, start=None, dur=None):
    """ffmpeg ebur128 통합 음량(LUFS, 게이트 적용 → 말소리 구간 위주)."""
    cmd = ['ffmpeg', '-nostats', '-hide_banner']
    if start is not None:
        cmd += ['-ss', f'{start:.3f}']
    if dur is not None:
        cmd += ['-t', f'{dur:.3f}']
    cmd += ['-i', str(path), '-af', 'ebur128', '-f', 'null', '-']
    err = subprocess.run(cmd, capture_output=True, text=True).stderr
    import re
    v = re.findall(r'I:\s*(-?[\d.]+) LUFS', err)
    return float(v[-1]) if v else None


def voice_lufs(D, start, end):
    """편집본 메인 트랙 원본 클립(목소리)만 섞은 소리의 통합 음량."""
    import tempfile
    import preview as P
    M = {k: v[1] for k, v in C.material_index(D).items()}
    main = next(t for t in D['tracks'] if t['type'] == 'video')
    src = Counter(M.get(s['material_id'], {}).get('path') for s in main['segments']).most_common(1)[0][0]
    only = copy.deepcopy(D)
    only['tracks'] = [dict(main, segments=[s for s in main['segments'] if M.get(s['material_id'], {}).get('path') == src])]
    with tempfile.TemporaryDirectory() as td:
        wp = Path(td) / 'voice.wav'
        P.mix_audio(only, M, start, end, wp)
        return lufs(wp)


def make_sticker_mov(spec, box, st, dur, dest):
    """3프레임 팝인(0.55 → 0.85 → 1.08 → 1.0) · 머묾 · 3프레임 팝아웃, 30fps ProRes 4444 알파 MOV."""
    from PIL import Image
    img = sticker_image(spec, box, st)
    n = max(8, int(round(dur * 30)))
    scales = [0.55, 0.85, 1.08] + [1.0] * (n - 6) + [0.92, 0.7, 0.4]
    W, H = box
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{W}x{H}', '-r', '30',
                          '-i', '-', '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le',
                          '-alpha_bits', '16', str(dest)], stdin=subprocess.PIPE)
    cache = {}
    for s in scales[:n]:
        if s not in cache:
            fr = Image.new('RGBA', (W, H))
            if s == 1.0:
                fr = img
            else:
                sm = img.resize((max(1, int(W * s)), max(1, int(H * s))), Image.LANCZOS)
                if s > 1:
                    x0, y0 = (sm.width - W) // 2, (sm.height - H) // 2
                    fr = sm.crop((x0, y0, x0 + W, y0 + H))
                else:
                    fr.alpha_composite(sm, ((W - sm.width) // 2, (H - sm.height) // 2))
            cache[s] = fr.tobytes()
        p.stdin.write(cache[s])
    p.stdin.close()
    if p.wait() != 0:
        C.die(f'스티커 MOV 만들기 실패: {dest}')
    img.save(dest.with_suffix('.png'))
    return dest


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='CapCut 자막 문장 강조 + 효과음·확대·목차 이름표·스티커(새 스테이징에만 씀)')
    ap.add_argument('--project', required=True, help='읽을 CapCut 프로젝트 이름 또는 폴더(수정하지 않음)')
    ap.add_argument('--spec', required=True)
    ap.add_argument('--out', help='새 스테이징 프로젝트 폴더(CapCut 프로젝트 폴더 밖). --dry-run 이면 생략 가능')
    ap.add_argument('--audio-template', help='효과음 클립 형식을 빌릴 프로젝트(--project 에 오디오 클립이 없을 때)')
    ap.add_argument('--media-dir', help='스티커 MOV 를 만들 폴더(기본: --out 옆 <이름>_media)')
    ap.add_argument('--capcut-dir')
    ap.add_argument('--dry-run', action='store_true', help='무엇을 바꿀지 출력만 하고 아무것도 쓰지 않는다')
    ap.add_argument('--install', action='store_true', help='스테이징을 CapCut 에 등록(CapCut 꺼진 상태, 허락 뒤에만)')
    ap.add_argument('--name', help='등록 이름(= --out 폴더 이름)')
    a = ap.parse_args()

    base_dir = C.resolve_project(a.project, a.capcut_dir).resolve()
    spec = C.read_json(a.spec)
    st = merge_style(DEFAULT_STYLE, spec.get('style'))
    items = spec.get('items', [])
    out = Path(a.out).resolve() if a.out else None
    cc = C.find_capcut_dir(a.capcut_dir, required=False)
    if out:
        if out == base_dir or (cc and Path(cc).resolve() in out.parents):
            C.die(f'[거부] --out 은 원본·CapCut 프로젝트 폴더 밖이어야 합니다: {out}')
        if out.exists() and not (out / B.MARKER).exists():
            C.die(f'[거부] 출력 폴더가 이미 있고 이 도구가 만든 스테이징이 아닙니다(덮어쓰지 않음): {out}')
    elif not a.dry_run:
        C.die('--out 이 필요합니다')
    name = (a.name or out.name) if out else 'dry-run'
    media_dir = Path(a.media_dir).resolve() if a.media_dir else (out.parent / f'{name}_media' if out else None)

    tpl = B.Template(base_dir)
    if not tpl.aud and any(it.get('sfx') for it in items):
        if not a.audio_template:
            C.die('이 프로젝트에 오디오 클립이 없어 효과음 형식을 만들 수 없습니다. --audio-template <조립 때 쓴 템플릿>을 주세요.')
        tpl.aud = B.Template(C.resolve_project(a.audio_template, a.capcut_dir)).aud
        if not tpl.aud:
            C.die(f'--audio-template {a.audio_template} 에도 오디오 클립이 없습니다.')
    b = B.Builder(tpl)
    D = b.D = copy.deepcopy(tpl.D)
    b.M = D['materials']
    for t in D['tracks']:
        b.tracks[t.get('name') or t['id']] = t
    old_track_ids = {t['id'] for t in D['tracks']}
    mats = C.material_index(D)
    cv = D.get('canvas_config') or dict(width=1920, height=1080)
    W, H = cv.get('width', 1920), cv.get('height', 1080)
    total = D['duration'] / C.US
    vtracks = [t for t in D['tracks'] if t['type'] == 'video']
    main_t = vtracks[0]
    path_of = lambda s: mats.get(s['material_id'], (None, {}))[1].get('path', '')
    src_path = Counter(path_of(s) for s in main_t['segments']).most_common(1)[0][0]
    bumpers = [rng(s) for s in main_t['segments'] if '범퍼' in Path(path_of(s)).name or 'bumper' in path_of(s).lower()]
    mains = sorted((s for s in main_t['segments'] if path_of(s) == src_path), key=lambda s: s['target_timerange']['start'])

    # 화면 전체를 덮는 자료: 메인 트랙의 원본 아닌 클립(범퍼·CTA), 알파 없는 덧입히기, 챕터 전환 막
    covers = []
    for s in main_t['segments']:
        if path_of(s) != src_path:
            covers.append((*rng(s), Path(path_of(s)).name))
    for t in vtracks[1:]:
        for s in t['segments']:
            p = path_of(s)
            if '챕터' in (t.get('name') or '') or (p and not has_alpha(p)):
                covers.append((*rng(s), f"{t.get('name')}:{Path(p).name}"))
    cover_iv = [(x0, x1) for x0, x1, _ in covers]

    def covered(a0, a1):
        return [c for c in covers if c[0] < a1 - 0.02 and a0 + 0.02 < c[1]]

    # 자막 목록(자막 재료가 가장 많은 텍스트 트랙)
    sub_tracks = [t for t in D['tracks'] if t['type'] == 'text']
    cues = []
    for t in sub_tracks:
        for s in t['segments']:
            k, m = mats.get(s['material_id'], (None, None))
            if m is not None and m.get('type') in ('subtitle', 'text'):
                cues.append((t, s, m))
    if not cues:
        C.die('자막 텍스트 클립이 없습니다.')
    sub_t = Counter(id(t) for t, _, m in cues if m.get('type') == 'subtitle').most_common(1)
    sub_t = next(t for t in sub_tracks if id(t) == sub_t[0][0]) if sub_t else cues[0][0]
    cues = sorted([(s, m) for t, s, m in cues if t is sub_t], key=lambda x: x[0]['target_timerange']['start'])
    text_of = lambda m: json.loads(m['content']).get('text', '')
    mat_use = Counter(s['material_id'] for t in D['tracks'] for s in t['segments'])

    def clone_text_refs(s):
        refs = []
        for r in s.get('extra_material_refs', []):
            k, rm = mats.get(r, (None, None))
            if rm is None:
                refs.append(r)
                continue
            nm = copy.deepcopy(rm)
            nm['id'] = B.uid()
            if k == 'material_animations':
                nm['animations'] = []
            D['materials'][k].append(nm)
            refs.append(nm['id'])
        return refs

    log, rows, used = [], [], set()
    sfx_rows, zoom_rows = [], []
    zcfg = st['zoom']
    for it in items:
        iid = it.get('id', '?')
        kind = KIND_ALIAS.get(it.get('kind'), it.get('kind'))
        if kind not in KINDS:
            log.append(f"  [못 넣음] {iid}: 유형 '{it.get('kind')}'은 {'/'.join(KINDS)} 가운데 하나여야 함")
            continue
        want = C.norm_text(it.get('match', ''))
        hits = [(i, s, m) for i, (s, m) in enumerate(cues) if want and want in C.norm_text(text_of(m))]
        if not hits:
            log.append(f"  [못 넣음] {iid}: 자막에서 '{it.get('match')}'을 찾지 못함")
            continue
        at = it.get('at')
        i, s, m = min(hits, key=lambda h: abs(rng(h[1])[0] - float(at)) if at is not None else 0)
        e0, e1 = rng(s)
        if at is not None and abs(e0 - float(at)) > 5:
            log.append(f"  [주의] {iid}: 가장 가까운 자막이 at {at}초에서 {abs(e0 - float(at)):.1f}초 떨어져 있음({e0:.2f}초)")
        if len(hits) > 1 and at is None:
            log.append(f"  [주의] {iid}: '{it.get('match')}' 자막이 {len(hits)}개라 첫 번째를 씀(at 을 주면 가장 가까운 것)")
        if s['id'] in used:
            log.append(f"  [못 넣음] {iid}: 같은 자막({e0:.2f}초)을 이미 강조함")
            continue
        if any(b0 < e1 and e0 < b1 for b0, b1 in bumpers):
            log.append(f"  [못 넣음] {iid}: 자막({e0:.2f}~{e1:.2f}초)이 범퍼와 겹침 — 범퍼 위에는 넣지 않음")
            continue
        full = text_of(m).replace('\n', ' ')
        text = full

        # 구절만 강조: 자막을 [앞 | 뒤]로 나눈다
        split = None
        if it.get('phrase'):
            r = find_range(full, it['phrase'])
            head_ok = r is not None and not C.norm_text(full[:r[0]])
            tail_ok = r is not None and not C.norm_text(full[r[1]:])
            if r is None or not (head_ok or tail_ok):
                log.append(f"  [못 넣음] {iid}: 구절 '{it['phrase']}'이 자막 '{full}'의 앞·뒤에 없음(가운데 구절은 나눌 수 없음)")
                continue
            if tail_ok and not head_ok:
                text, rest = full[r[0]:].strip(), full[:r[0]].strip()
            else:
                text, rest = full[:r[1]].strip(), full[r[1]:].strip()
            if 'split_at' in it:
                cut = float(it['split_at'])
            else:                                  # 글자 비율로 추정(받아쓰기 낱말 시각이 있으면 split_at 을 준다)
                pre = C.norm_text(full[:r[0]] if tail_ok and not head_ok else full[:r[1]])
                cut = e0 + (e1 - e0) * len(pre) / max(1, len(C.norm_text(full)))
                log.append(f"  [주의] {iid}: 나눌 시각을 글자 비율로 추정({cut:.2f}초) — 받아쓰기로 split_at 을 주면 정확")
            if not e0 + 0.3 < cut < e1 - 0.3:
                log.append(f"  [못 넣음] {iid}: 나눌 시각 {cut:.2f}초가 자막({e0:.2f}~{e1:.2f}) 안쪽이 아님")
                continue
            split = dict(where='tail' if (tail_ok and not head_ok) else 'head', cut=cut, rest=rest)
            if split['where'] == 'tail':
                e0 = cut
            else:
                e1 = cut
        used.add(s['id'])

        # 크기: 기본 × size_mult, 폭 max_width 를 넘으면 줄임
        c0 = json.loads(m['content'])
        base_size = float(((c0.get('styles') or [{}])[0]).get('size') or m.get('font_size') or 5)
        size = base_size * float(st['size_mult'])
        wpx, fpx = line_width(text, size, st, H)
        shrunk = False
        if wpx > st['max_width'] * W:
            size = math.floor(size * st['max_width'] * W / wpx * 10) / 10
            while size > 0.5 and line_width(text, size, st, H)[0] > st['max_width'] * W:
                size = round(size - 0.1, 1)
            shrunk = True
            wpx, fpx = line_width(text, size, st, H)

        # 세로: 기본 자리, 아래가 넘치면 올림
        tf0 = (s.get('clip') or {}).get('transform') or {'x': 0.0, 'y': 0.0}
        y0 = float(tf0.get('y', 0.0))
        center = H / 2 - y0 * H / 2
        half = GLYPH_H * fpx / 2 + st['stroke_width'] * fpx * 0.6
        new_center = min(center, st['bottom_limit'] * H - half)
        if new_center < st['center_min'] * H:
            log.append(f"  [주의] {iid}: 글자가 커서 중심을 {st['center_min']:.0%} 위로 올려야 맞음 — {st['center_min']:.0%}에 둠")
            new_center = max(new_center, st['center_min'] * H)
        new_y = round((H / 2 - new_center) / (H / 2), 6)

        # 유지: 1.2초 미만이면 다음 자막 전까지 늘림
        new_e1 = e1
        if e1 - e0 < st['min_hold']:
            if split and split['where'] == 'head':
                lim = e1
            else:
                nxt = cues[i + 1][0]['target_timerange']['start'] / C.US if i + 1 < len(cues) else total
                lim = min([nxt] + [b0 for b0, _ in bumpers if b0 >= e1 - 1e-6])
            new_e1 = min(e0 + st['min_hold'], lim)
            if new_e1 < e0 + st['min_hold'] - 1e-3:
                log.append(f"  [주의] {iid}: 다음 자막이 가까워 {new_e1 - e0:.2f}초까지만 늘림(1.2초 미만)")

        cw = it.get('color_word')
        row = dict(id=iid, kind=kind, text=text, chars=len(text.strip()), start=round(e0, 3), end=round(new_e1, 3),
                   cue_index=i, base_size=base_size, size=round(size, 2), shrunk=shrunk,
                   est_width_px=round(wpx), est_width_ratio=round(wpx / W, 3), y=new_y, y_before=y0,
                   center_ratio=round(new_center / H, 4), color_word=cw, color=st['colors'].get(kind) if cw else None,
                   split=split, sfx=None, zoom=None, note=it.get('note', ''))
        if not a.dry_run:
            if split:                                          # 나머지 쪽 자막을 새 세그먼트·재료로
                rs = copy.deepcopy(s)
                rm = copy.deepcopy(m)
                rm['id'] = B.uid()
                set_plain_text(rm, split['rest'])
                D['materials']['texts'].append(rm)
                rs.update(id=B.uid(), material_id=rm['id'], extra_material_refs=clone_text_refs(s), desc=split['rest'][:20])
                s0, s1 = rng(s)
                if split['where'] == 'tail':
                    rs['target_timerange'] = dict(start=int(round(s0 * C.US)), duration=int(round((split['cut'] - s0) * C.US)))
                else:
                    rs['target_timerange'] = dict(start=int(round(split['cut'] * C.US)), duration=int(round((s1 - split['cut']) * C.US)))
                sub_t['segments'].append(rs)
            if split or mat_use[m['id']] > 1:                  # 다른 클립과 같이 쓰는 재료 → 복제
                m = copy.deepcopy(m)
                m['id'] = B.uid()
                D['materials']['texts'].append(m)
                s['material_id'] = m['id']
                row['cloned_material'] = True
            restyle(m, text, size, st, kind, cw, log, iid)
            refs = []
            for r in s.get('extra_material_refs', []):     # 등장·퇴장 애니메이션 없음
                k, rm_ = mats.get(r, (None, None))
                if k == 'material_animations' and rm_.get('animations'):
                    nm = copy.deepcopy(rm_)
                    nm.update(id=B.uid(), animations=[])
                    D['materials'][k].append(nm)
                    refs.append(nm['id'])
                    row['animation_removed'] = True
                else:
                    refs.append(r)
            s['extra_material_refs'] = refs
            s.setdefault('clip', {}).setdefault('transform', {'x': 0.0, 'y': 0.0})['y'] = new_y
            s['target_timerange'] = dict(start=int(round(e0 * C.US)), duration=int(round((new_e1 - e0) * C.US)))
            s['desc'] = text[:20]
        elif cw and find_range(text, cw) is None:
            log.append(f"  [못 넣음] {iid} 색 낱말 '{cw}'이 자막 '{text}'에 없음(색 없이 강조)")
        log.append(f"  강조 {iid} {C.mmss(e0)} ({e0:6.2f}~{new_e1:6.2f}초) [{kind}] '{text}'"
                   f"{f' 색[{cw}]' if cw and st['colors'].get(kind) else ''} 크기 {base_size:g}→{size:g}"
                   f"{' (폭 맞춤)' if shrunk else ''} 폭≈{wpx / W:.0%} 중심 {new_center / H:.1%}"
                   + (f" (나눔: {split['where']} {split['cut']:.2f}초)" if split else ''))

        # 확대(펀치인, 하드컷)
        zon = zcfg.get('on', True) if it.get('zoom') is None else bool(it.get('zoom'))
        if zon:
            cov = covered(e0, new_e1)
            if cov:
                log.append(f"  [확대 안 함] {iid}: 전체 화면 자료가 덮음({', '.join(c[2] for c in cov)[:60]})")
            else:
                pieces = []
                for ms in mains:
                    m0, m1 = rng(ms)
                    x0, x1 = max(e0, m0), min(new_e1, m1)
                    if x1 - x0 > 0.02:
                        pieces.append((ms, x0, x1))
                if not pieces:
                    log.append(f"  [확대 안 함] {iid}: 메인 원본 클립이 없음")
                else:
                    row['zoom'] = dict(scale=zcfg['scale'], y_anchor=zcfg['y_anchor'], pieces=len(pieces))
                    zoom_rows.append((e0, new_e1, iid))
                    log.append(f"  확대 {iid} {e0:6.2f}~{new_e1:6.2f}초 ×{zcfg['scale']} 하드컷 · 조각 {len(pieces)}")
                    if not a.dry_run:
                        ztr = b.track(zcfg['track'], 'video')
                        for ms, x0, x1 in pieces:
                            n_ = copy.deepcopy(ms)
                            m0 = rng(ms)[0]
                            sp = ms.get('speed') or 1.0
                            refs = []
                            for r in ms.get('extra_material_refs', []):
                                k, rm_ = mats.get(r, (None, None))
                                if rm_ is None or k in ('loudnesses', 'audio_fades', 'vocal_separations', 'vocal_beautifys'):
                                    continue
                                nm = copy.deepcopy(rm_)
                                nm['id'] = B.uid()
                                D['materials'][k].append(nm)
                                refs.append(nm['id'])
                            clip = n_.setdefault('clip', {})
                            bs = (clip.get('scale') or {}).get('x', 1.0)
                            tf = clip.setdefault('transform', {'x': 0.0, 'y': 0.0})
                            zs = float(zcfg['scale'])
                            clip['scale'] = {'x': round(bs * zs, 6), 'y': round(bs * zs, 6)}
                            tf['y'] = round(tf.get('y', 0.0) - (zs - 1) * float(zcfg['y_anchor']), 6)   # CapCut y: + = 위
                            if isinstance(n_.get('uniform_scale'), dict):
                                n_['uniform_scale']['value'] = round(bs * zs, 6)
                            src0 = ms['source_timerange']['start'] + int(round((x0 - m0) * sp * C.US))
                            n_.update(id=B.uid(), extra_material_refs=refs, keyframe_refs=[], volume=0.0, group_id='',
                                      raw_segment_id='', desc=f'강조 확대 {iid}',
                                      target_timerange=dict(start=int(round(x0 * C.US)), duration=int(round((x1 - x0) * C.US))),
                                      source_timerange=dict(start=src0, duration=int(round((x1 - x0) * sp * C.US))),
                                      render_timerange=dict(start=0, duration=0))
                            ztr['segments'].append(n_)

        # 효과음
        sv = it.get('sfx')
        f = None
        if sv is True:
            f = st['sfx_files'].get(kind)
            if not f:
                log.append(f"  [주의] {iid}: '{kind}' 강조에는 기본 효과음이 없음(sfx 무시)")
        elif isinstance(sv, str) and sv:
            f = sv if ('/' in sv or sv.endswith('.wav') or sv.endswith('.mp3')) else f'{SFX_DIR}/{sv}.wav'
        if f:
            fp = resolve(f)
            if not fp.exists():
                log.append(f"  [못 넣음] {iid} 효과음: 파일 없음 {fp}")
            else:
                t0 = max(0.0, e0 - float(st['sfx_lead'].get(kind, 0.0)))
                fi = C.media_info(fp)
                du = min(fi['duration'], total - t0)
                if any(b0 < t0 + du and t0 < b1 for b0, b1 in bumpers):
                    log.append(f"  [못 넣음] {iid} 효과음: 범퍼와 겹침")
                else:
                    db = float(st['sfx_db'])
                    row['sfx'] = dict(file=fp.name, at=round(t0, 3), dur=round(du, 3), db=db)
                    sfx_rows.append((t0, fp.name, iid))
                    if not a.dry_run:
                        tn = b.free_track(st['sfx_track'], 'audio', C.us(t0), C.us(du))
                        seg = b.put_audio(tn, fp, C.us(t0), C.us(du), 0, round(10 ** (db / 20), 4))
                        seg['desc'] = f'강조 효과음 {iid}'
                        strip_loudness(D, seg)
                    log.append(f"  효과음 {iid} {t0:6.2f}초 {fp.name} {db:g}dB")
        rows.append(row)

    # ── 목차 이름표 ──
    toc_rows = []
    toc = spec.get('toc')
    if toc and toc.get('items'):
        tc = st['toc']
        tit = sorted(toc['items'], key=lambda x: float(x['at']))
        end_all = float(toc['end']) if toc.get('end') is not None else total
        fpx = tc['glyph_px'] / GLYPH_H * H / 1080
        size = round(fpx / (st['px_per_unit'] * H / 1080), 2)
        for k, x in enumerate(tit):
            a0 = float(x['at'])
            a1 = min(float(tit[k + 1]['at']) if k + 1 < len(tit) else end_all, end_all)
            label = (f"{x['num']}  " if x.get('num') else '') + x['text']
            tw = text_width_px(label, fpx)
            box_w = tw + 2 * tc['bg_w'] * 2.4 * fpx
            cx = tc['left'] * W / 1920 + box_w / 2
            cy = tc['center_y'] * H / 1080
            for p0, p1 in subtract((a0, a1), cover_iv):
                if p1 - p0 < tc['min_piece']:
                    continue
                toc_rows.append(dict(text=label, start=round(p0, 3), end=round(p1, 3), size=size, box_w_px=round(box_w),
                                     center=[round(cx), round(cy)]))
                if a.dry_run:
                    continue
                seg = b.put_text(tc['track'], label, C.us(p0), C.us(p1 - p0), emphasis=(cx / W, cy / H, 1.0))
                tm = next(mm for mm in D['materials']['texts'] if mm['id'] == seg['material_id'])
                c = json.loads(tm['content'])
                stl = copy.deepcopy((c.get('styles') or [{}])[0])
                for kk in ('strokes', 'shadows'):
                    stl.pop(kk, None)
                stl.update(size=size, bold=True, useLetterColor=True, fill=solid(tc['fill']))
                n_all = u16(label)
                if x.get('num'):
                    nn = u16(f"{x['num']}")
                    s1_ = copy.deepcopy(stl)
                    s1_.update(range=[0, nn], fill=solid(tc['accent']))
                    s2_ = copy.deepcopy(stl)
                    s2_['range'] = [nn, n_all]
                    c['styles'] = [s1_, s2_]
                else:
                    stl['range'] = [0, n_all]
                    c['styles'] = [stl]
                tm['content'] = json.dumps(c, ensure_ascii=False)
                tm.update(font_size=size, text_color=tc['fill'].lower(), border_width=0.0, has_shadow=False,
                          background_color=tc['bg'], background_alpha=1.0, background_style=1,
                          background_width=tc['bg_w'], background_height=tc['bg_h'], background_round_radius=tc['radius'])
                if 'bold_width' in tm:
                    tm['bold_width'] = 0.008
                if isinstance(tm.get('check_flag'), int):
                    tm['check_flag'] = (tm['check_flag'] | 16) & ~8 & ~32
                seg['desc'] = f'목차 {label}'[:20]
        log.append(f"  목차 이름표 {len(toc_rows)}조각 (크기 {size:g}, 왼쪽 {tc['left']}px·중심 y {tc['center_y']}px, 덮개 위 숨김)")

    # ── 옆 스티커 ──
    stk_rows = []
    sc = st['sticker']
    for x in spec.get('stickers', []):
        sid = x.get('id', '?')
        a0 = float(x['at'])
        dur = float(x.get('dur', sc['dur']))
        a1 = min(a0 + dur, total)
        nxt = [c0 for c0, c1 in cover_iv if c0 > a0 + 0.05 and c0 < a1]
        if any(c0 <= a0 + 0.05 < c1 for c0, c1 in cover_iv):
            log.append(f"  [못 넣음] 스티커 {sid}: 시작({a0:.2f}초)이 전체 화면 자료 위")
            continue
        if nxt:
            a1 = min(nxt)
            log.append(f"  [주의] 스티커 {sid}: 전체 화면 자료가 {a1:.2f}초에 시작해 거기서 끝냄({a1 - a0:.1f}초)")
        if a1 - a0 < 1.5:
            log.append(f"  [못 넣음] 스티커 {sid}: 들어갈 자리가 1.5초보다 짧음")
            continue
        pos = sc['pos'].get(x.get('pos', 'right_top'), sc['pos']['right_top'])
        bw, bh = sc['box']
        if x.get('pos', 'right_top') == 'right_top' and pos[0] - bw / 2 < 1400 * W / 1920:
            log.append(f"  [주의] 스티커 {sid}: 왼쪽 끝이 얼굴 안전영역(x 1400) 안쪽")
        partial = [f"{t.get('name')}:{Path(path_of(s_)).name}" for t in vtracks[1:] for s_ in t['segments']
                   if rng(s_)[0] < a1 and a0 < rng(s_)[1] and has_alpha(path_of(s_)) and '챕터' not in (t.get('name') or '')]
        if partial:
            log.append(f"  [겹침 확인] 스티커 {sid}: 같은 시간 알파 카드 {partial[:2]} — 자리가 겹치는지 프레임으로 확인")
        row = dict(id=sid, start=round(a0, 3), end=round(a1, 3), pos=list(pos), box=[bw, bh], label=x.get('label'),
                   emoji=x.get('emoji'), image=x.get('image'))
        if not a.dry_run:
            media_dir.mkdir(parents=True, exist_ok=True)
            mov = make_sticker_mov(x, (bw, bh), st, a1 - a0, media_dir / f'{sid}_sticker.mov')
            row['file'] = str(mov)
            info = C.media_info(mov)
            fit = min(W / info['width'], H / info['height'])
            tn = b.free_track(sc['track'], 'video', C.us(a0), C.us(a1 - a0))
            seg = b.put_video(tn, mov, C.us(a0), C.us(a1 - a0), 0, round(1 / fit, 6), 0.0)
            seg['clip']['transform'] = dict(x=round((pos[0] * W / 1920 - W / 2) / (W / 2), 6),
                                            y=round((H / 2 - pos[1] * H / 1080) / (H / 2), 6))
            seg['desc'] = f'스티커 {sid}'
        stk_rows.append(row)
        log.append(f"  스티커 {sid} {a0:6.2f}~{a1:6.2f}초 {x.get('emoji') or Path(x.get('image', '')).name} "
                   f"'{x.get('label', '')}' 중심 {pos}")

    # ── 배경음악 ──
    # spec "bgm": {"file", "start", "end"(null=끝), "db"(클립 볼륨), "fade_in", "fade_out", "loop", "skip": "bumper",
    #              "gaps": [[a, b], ...](더 비울 구간), "seam": 0.15(반복 이음매 페이드), "min_piece": 2.0,
    #              "target_below_voice": 16(목소리보다 이만큼 아래가 기준), "voice_window": [a, b](목소리 음량을 잴 구간)}
    # skip "bumper": 메인 트랙의 원본 아닌 클립(범퍼·CTA — 자체 소리가 있다)을 비운다. 조각마다 처음 fade_in·끝 fade_out.
    bgm_rows, bgm_chk = [], []
    bg = spec.get('bgm')
    if bg:
        fp = resolve(bg['file'])
        if not fp.exists():
            log.append(f"  [못 넣음] BGM: 파일 없음 {fp}")
        else:
            fdur = C.media_info(fp)['duration']
            g0 = float(bg.get('start', 0.0))
            g1 = min(float(bg['end']) if bg.get('end') is not None else total, total)
            holes = [tuple(map(float, x)) for x in bg.get('gaps', [])]
            if bg.get('skip', 'bumper') == 'bumper':
                holes += [rng(s_) for s_ in main_t['segments'] if path_of(s_) != src_path]     # 범퍼·CTA(자체 소리)
            db = float(bg.get('db', -30.0))
            vol = round(10 ** (db / 20), 5)
            fin, fout, seam = float(bg.get('fade_in', 1.0)), float(bg.get('fade_out', 1.5)), float(bg.get('seam', 0.15))
            pieces = [p for p in subtract((g0, g1), holes) if p[1] - p[0] >= float(bg.get('min_piece', 2.0))]
            for k, (t, du, fi_, fo_) in enumerate(bgm_layout(pieces, fdur, fin, fout, seam, bg.get('loop', True))):
                bgm_rows.append(dict(start=round(t, 3), end=round(t + du, 3), src_in=0.0, db=db, fade_in=fi_, fade_out=fo_))
                if not a.dry_run:
                    tn = b.free_track(BGM_TRACK, 'audio', C.us(t), C.us(du))
                    seg = b.put_audio(tn, fp, C.us(t), C.us(du), 0, vol)
                    seg['desc'] = f'BGM {k + 1}'
                    strip_loudness(D, seg)
                    add_fade(D, seg, fi_, fo_)
            log.append(f"  BGM {fp.name} ({fdur:.1f}초) 클립 {len(bgm_rows)}개 · 볼륨 {db:g}dB(×{vol}) · 조각 "
                       + ', '.join(f'{p0:.2f}~{p1:.2f}' for p0, p1 in pieces))
            # 크기 기준: 목소리 통합 음량보다 target_below_voice dB 아래
            try:
                vw = bg.get('voice_window') or [g0, min(g1, g0 + 120)]
                v_l = voice_lufs(D, float(vw[0]), float(vw[1]))
                f_l = lufs(fp)
                want = v_l - float(bg.get('target_below_voice', BGM_BELOW_VOICE)) - f_l
                bg_info = dict(voice_lufs=round(v_l, 2), file_lufs=round(f_l, 2), want_db=round(want, 2), db=db,
                               below_voice=round(v_l - (f_l + db), 2))
                log.append(f"  BGM 크기: 목소리 {v_l:.1f} LUFS({vw[0]:g}~{vw[1]:g}초) · 파일 {f_l:.1f} LUFS → "
                           f"{bg.get('target_below_voice', BGM_BELOW_VOICE)}dB 아래가 되는 볼륨 {want:.1f}dB, 지금 {db:g}dB "
                           f"(목소리보다 {v_l - (f_l + db):.1f}dB 아래)")
                if abs(db - want) > 4:
                    bgm_chk.append(f'BGM 볼륨 {db:g}dB 가 기준 {want:.1f}dB(목소리 −{bg.get("target_below_voice", BGM_BELOW_VOICE)}dB)에서 '
                                   f'{db - want:+.1f}dB 벗어남(±4dB 밖)')
                bgm_rows and bgm_rows[0].update(level=bg_info)
            except Exception as e:
                log.append(f'  [주의] BGM 크기 기준을 재지 못함: {str(e)[:80]}')

    # ── 규칙 점검 ──
    chk = list(bgm_chk)
    rows.sort(key=lambda r: r['start'])
    if rows:
        span_end = max(r['end'] for r in rows)
        for k in range(int(span_end // 60) + 1):
            w0, w1 = k * 60, min((k + 1) * 60, span_end)
            n = sum(1 for r in rows if w0 <= r['start'] < (k + 1) * 60)
            part = w1 - w0
            if part >= 30 and not 2 <= n * 60 / part <= 4 + 1e-9:
                chk.append(f'{k}:00~{k + 1}:00 강조 {n}개(분당 {n * 60 / part:.1f}, 기준 2~4)')
        for x, y in zip(rows, rows[1:]):
            if y['start'] - x['start'] < 4:
                chk.append(f"강조 간격 {y['start'] - x['start']:.2f}초 < 4초: {x['id']}({x['start']:.2f}) → {y['id']}({y['start']:.2f})")
        run = [rows[0]]
        for x, y in zip(rows, rows[1:]):
            run = run + [y] if y['cue_index'] == x['cue_index'] + 1 else [y]
            if len(run) == 3:
                chk.append(f"3문장 이상 연달아 강조: {', '.join(r['id'] for r in run)}")
            if y['cue_index'] == x['cue_index'] + 1 and y.get('sfx'):
                chk.append(f"연달아 강조의 두 번째({y['id']})에 효과음")
        for r in rows:
            if r['chars'] > st['max_chars']:
                chk.append(f"{r['id']} {r['chars']}자 > {st['max_chars']}자: '{r['text']}'")
    sfx_rows.sort()
    for t0, _, iid in sfx_rows:
        n = sum(1 for u, _, _ in sfx_rows if t0 <= u < t0 + 60)
        if n > 3:
            chk.append(f'효과음 {t0:.1f}초부터 1분에 {n}개 > 3개')
            break
    for k, (t0, f, iid) in enumerate(sfx_rows):
        for u, g, jid in sfx_rows[k + 1:]:
            if g == f and u - t0 < 20:
                chk.append(f'같은 소리 {f} 20초 안 재사용: {iid}({t0:.1f}) → {jid}({u:.1f})')
    print('\n'.join(log))
    print(f"{'[dry-run] ' if a.dry_run else ''}강조 {len(rows)}개 · 효과음 {len(sfx_rows)}개 · 확대 {len(zoom_rows)}개 · "
          f"목차 {len(toc_rows)}조각 · 스티커 {len(stk_rows)}개 / 항목 {len(items)}")
    if rows:
        span = max(r['end'] for r in rows)
        print(f'  분당 강조 {len(rows) * 60 / max(span, 1):.2f}개 · 분당 효과음 {len(sfx_rows) * 60 / max(span, 1):.2f}개 '
              f'(0초~{span:.1f}초 기준)')
    for c in chk:
        print('[규칙 점검]', c)
    if not chk:
        print('[규칙 점검] 경고 없음')
    if a.dry_run:
        return 0

    # ── 쓰기(스테이징) ──
    if name != out.name:
        C.die('[거부] --name 은 --out 폴더 이름과 같아야 합니다')
    # 트랙 순서: 메인 → 확대 → 기존 영상 덧입히기 → 새 영상(스티커) → 기존 글자 → 새 글자(목차) → 소리
    zt = [t for t in D['tracks'] if t.get('name') == zcfg['track'] and t['id'] not in old_track_ids]
    vids = [t for t in D['tracks'] if t['type'] == 'video' and t is not main_t and t not in zt]
    texts = [t for t in D['tracks'] if t['type'] == 'text']
    rest = [t for t in D['tracks'] if t['type'] not in ('video', 'text')]
    D['tracks'] = ([main_t] + zt + [t for t in vids if t['id'] in old_track_ids] + [t for t in vids if t['id'] not in old_track_ids]
                   + [t for t in texts if t['id'] in old_track_ids] + [t for t in texts if t['id'] not in old_track_ids] + rest)
    for i, t in enumerate(D['tracks']):
        t['segments'].sort(key=lambda s: s['target_timerange']['start'])
        for s in t['segments']:
            s['track_render_index'] = i
            s['render_index'] = i if t['type'] in ('video', 'text') else 0
    cc_root = Path(cc) if cc else out.parent
    dest = cc_root / name
    now = int(time.time())
    D.update(id=B.uid(), name=name, path=dest.as_posix(), create_time=now, update_time=now)
    media_paths = sorted({m.get('path') for m in b.M.get('videos', []) + b.M.get('audios', []) if m.get('path')})
    out.parent.mkdir(parents=True, exist_ok=True)
    B.write_staging(b, tpl, out, name, dest, media_paths,
                    (Path(src_path), mains[0]['source_timerange']['start'] / C.US + 0.5) if mains else None)
    # write_staging 은 미디어 목록을 새 재료로만 채운다 → 기존 목록을 앞에 되살린다(capcut_augment 와 같은 방식)
    for fn, typ in (('draft_meta_info.json', 0), ('draft_virtual_store.json', 1)):
        old_p, new_p = base_dir / fn, out / fn
        if not (old_p.exists() and new_p.exists()):
            continue
        old, new = C.read_json(old_p), C.read_json(new_p)
        key = 'draft_materials' if fn.startswith('draft_meta') else 'draft_virtual_store'
        prev = {g.get('type'): g.get('value', []) for g in old.get(key, [])}
        for g in new.get(key, []):
            if g.get('type') == typ:
                seen = {json.dumps(v, sort_keys=True) for v in g.get('value', [])}
                g['value'] = [v for v in prev.get(typ, []) if json.dumps(v, sort_keys=True) not in seen] + g.get('value', [])
        C.write_json(new_p, new, compact=True)

    # 검증: draft 사본이 모두 같은 JSON 이고, 바꾼 수가 맞는지
    dn = C.draft_file(out)
    copies = [dn, out / 'template-2.tmp'] + sorted(p for p in (out / 'Timelines').glob('*/*')
                                                   if p.name in (dn.name, 'template-2.tmp', 'template.tmp'))
    js = [C.read_draft(p) for p in copies if p.exists()]
    same = all(x == js[0] for x in js)
    R = js[0]
    RM = C.material_index(R)
    emph = sum(1 for t in R['tracks'] if t['type'] == 'text' for s in t['segments']
               if '"shadows"' in RM[s['material_id']][1].get('content', ''))
    aud = [s for t in R['tracks'] if t['type'] == 'audio' and t.get('name', '').startswith(st['sfx_track']) for s in t['segments']]
    bad = [RM[s['material_id']][1].get('type') for s in aud
           if RM[s['material_id']][1].get('type') != 'extract_music' or RM[s['material_id']][1].get('effect_id')]
    nz = sum(len(t['segments']) for t in R['tracks'] if t.get('name') == zcfg['track'])
    ntoc = sum(len(t['segments']) for t in R['tracks'] if t.get('name') == st['toc']['track'])
    nstk = sum(len(t['segments']) for t in R['tracks'] if (t.get('name') or '').startswith(sc['track']))
    nbgm = sum(len(t['segments']) for t in R['tracks'] if t['type'] == 'audio' and (t.get('name') or '').startswith(BGM_TRACK))
    rep = out.parent / f'{name}_emphasis.json'
    C.write_json(rep, dict(source=str(base_dir), spec=str(Path(a.spec).resolve()), style=st, rows=rows, toc=toc_rows,
                           stickers=stk_rows, bgm=bgm_rows, covers=[list(c) for c in covers], log=log, checks=chk,
                           verify=dict(draft_copies=len(js), identical=same, emphasized_segments=emph, sfx_segments=len(aud),
                                       sfx_bad_materials=bad, zoom_segments=nz, toc_segments=ntoc, sticker_segments=nstk, bgm_segments=nbgm,
                                       track_order=[t.get('name') or t['type'] for t in R['tracks']])))
    print(f'스테이징: {out}\n  draft 사본 {len(js)}개 {"모두 같음" if same else "[확인 실패] 서로 다름"} · '
          f'강조 세그먼트 {emph}개 · 효과음 클립 {len(aud)}개 · 확대 클립 {nz}개 · 목차 {ntoc}개 · 스티커 {nstk}개 · BGM {nbgm}개'
          f'{" · [확인 실패] 효과음 재료 " + str(bad) if bad else ""}\n  트랙 순서: {[t.get("name") or t["type"] for t in R["tracks"]]}'
          f'\n  기록: {rep}')
    if a.install:
        if not cc:
            C.die('CapCut 프로젝트 폴더를 찾지 못했습니다(--capcut-dir).')
        return B.install(out, Path(cc), name, out.parent / 'backups')
    print('  CapCut 등록은 하지 않았습니다. CapCut을 끈 뒤 같은 명령에 --install --name', name, '을 붙이면 등록합니다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
