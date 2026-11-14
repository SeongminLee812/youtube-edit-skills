#!/usr/bin/env python3
"""모션 카드 스타일 목업: 키 컬러 후보 × 스타일(어두운 유리 / 밝은) 조합마다 대표 카드 4장을 PNG로 만들고,
한 화면에서 비교하는 mockups.html 을 씁니다(첫 실행 온보딩의 '목업 컨펌' 단계).

카드 4장: ① 챕터 제목(title) ② 숫자(number) ③ 단계(steps) ④ 목차 전환(chapter_frost).
  - 어두운 유리 = 원작 motion/cards.html(검정 유리, 강조색 + 보조색), 밝은 = motion/cards_channel.html(밝은 카드, 강조색).
  - 목차 전환은 두 스타일 모두 같은 흐림 막(chapter_frost.html) 위 글자 층이고, 밑줄·진행 칸이 키 컬러다.
이 스크립트는 HTML·PNG까지만 만든다. 사용자가 고른 조합을 profile.md(motion_style·brand_color_1 …)에 쓰는 일은 에이전트가 한다.

사용 예(작업 폴더에서):
  python <스킬 폴더>/claude-edit/scripts/mockups.py --colors "#E8590C,#1C7ED6" --styles dark,light \\
      --topic "홈카페" --channel "작은방 홈카페" --out 내영상/편집/목업/
  카드 글자를 직접 주려면:
      --title "집에서 내리는 첫 드립" --steps "원두 갈기|뜸 들이기|나눠 붓기|마무리" --number "추출 시간,4,2,분" \\
      --chapter "1|시작하기 전에|도구 세 가지"
결과: <out>/mockups.html · <out>/<조합 번호>_<스타일>_<색>/1_title.png · 2_number.png · 3_steps.png · 4_chapter.png
"""
import argparse
import html
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE.parents[1] / 'smartdaddy-video-edit'          # 옆 스킬(엔진)
RENDER = SK / 'scripts' / 'render_motion.py'
STYLE = {'dark': ('motion/cards.html', '어두운 유리'), 'light': ('motion/cards_channel.html', '밝은')}
W, H = 1920, 1080


def parse_args():
    ap = argparse.ArgumentParser(description='모션 카드 스타일 목업(키 컬러 × 스타일) → PNG + mockups.html')
    ap.add_argument('--colors', required=True, help='키 컬러 후보 2~3개, 쉼표로("#E8590C,#1C7ED6")')
    ap.add_argument('--styles', default='dark,light', help='dark(어두운 유리) · light(밝은), 쉼표로. 기본 dark,light')
    ap.add_argument('--combos', type=int, default=4, help='만들 조합 수(기본 4, 색 순서대로 스타일을 번갈아)')
    ap.add_argument('--topic', default='', help='채널 주제(카드 글자 기본값에 쓴다). 예: "홈카페"')
    ap.add_argument('--channel', default='', help='채널 이름(목차 전환 라벨)')
    ap.add_argument('--title', help='① 챕터 제목 카드 글자')
    ap.add_argument('--sub', help='① 챕터 제목 아래 한 줄(밝은 스타일)')
    ap.add_argument('--number', help='② 숫자 카드 "제목,처음,지금,단위"(예: "추출 시간,4,2,분")')
    ap.add_argument('--steps', help='③ 단계 카드 항목 "가|나|다|라"(3~4개)')
    ap.add_argument('--steps-title', help='③ 단계 카드 제목')
    ap.add_argument('--chapter', help='④ 목차 전환 "번호|부제|제목"')
    ap.add_argument('--accent2', default='', help='보조색(선택). 어두운 유리의 두 번째 빛, 밝은 카드의 체크 색')
    ap.add_argument('--font', default='', help='카드 글꼴 이름(선택, 설치된 글꼴)')
    ap.add_argument('--jobs', type=int, default=3, help='동시에 렌더할 수(기본 3)')
    ap.add_argument('--out', required=True, help='출력 폴더(예: <영상 폴더>/편집/목업/)')
    return ap.parse_args()


def texts(a):
    t = a.topic.strip()
    title = a.title or (f'{t}, 처음부터 차근차근' if t else '처음부터 차근차근')
    sub = a.sub or (f'{t} 이야기를 세 단계로 정리합니다' if t else '세 단계로 정리합니다')
    n = [x.strip() for x in (a.number or '준비 시간,30,10,분').split(',')]
    n += ['', '', '', ''][len(n):]
    steps = a.steps or '준비|시작|정리|마무리'
    st_title = a.steps_title or (f'{t} 순서' if t else '오늘의 순서')
    ch = [x.strip() for x in (a.chapter or f'1|시작하기 전에|{t + " 기본" if t else "기본 세 가지"}').split('|')]
    ch += ['', '', ''][len(ch):]
    return dict(title=title, sub=sub, number=n[:4], steps=steps, steps_title=st_title, chapter=ch[:3])


def combos(a):
    colors = [c.strip() for c in a.colors.split(',') if c.strip()]
    styles = [s.strip() for s in a.styles.split(',') if s.strip() in STYLE]
    if not colors or not styles:
        sys.exit('--colors 와 --styles(dark·light)를 주세요.')
    out = [(c, s) for c in colors for s in styles]
    return out[:max(1, a.combos)]


def qjoin(pairs):
    return '&'.join(f'{k}={v}' for k, v in pairs if v not in (None, ''))


def render(html_rel, query, png, t, dur, alpha=False, bg=None):
    """render_motion.py 로 한 프레임을 찍어 png 로 옮긴다."""
    tmp = Path(tempfile.mkdtemp(prefix='mock_'))
    cmd = [sys.executable, str(RENDER), html_rel, str(tmp), '--frames', f'{t}', '--dur', f'{dur}', '--query', query]
    if alpha:
        cmd += ['--alpha'] + (['--background-image', str(bg)] if bg else [])
    r = subprocess.run(cmd, cwd=str(SK), capture_output=True, text=True)
    if r.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f'{html_rel} 렌더 실패: {(r.stderr or r.stdout)[-400:]}')
    files = sorted(tmp.glob('*_preview.jpg' if (alpha and bg) else '*.png'))
    if not files:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f'{html_rel}: 결과 그림이 없습니다')
    from PIL import Image
    Image.open(files[0]).convert('RGB').save(png)
    shutil.rmtree(tmp, ignore_errors=True)
    return png


def veil_background(path):
    """목차 전환 미리보기 바탕: 흐린 실내 같은 그러데이션 + chapter_frost.py 와 같은 어두운 막(#0D111A, .58, 왼쪽 아래 +.16)."""
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new('RGB', (W, H), (120, 112, 104))
    d = ImageDraw.Draw(im)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=(int(150 - 60 * k), int(140 - 55 * k), int(128 - 50 * k)))
    d.ellipse((760, 160, 1160, 560), fill=(185, 160, 140))              # 얼굴 자리(흐릿한 형태만)
    d.rounded_rectangle((640, 520, 1280, 1080), radius=160, fill=(70, 78, 92))
    im = im.filter(ImageFilter.GaussianBlur(26)).convert('RGBA')
    veil = Image.new('RGBA', (W, H))
    vd = ImageDraw.Draw(veil)
    for x in range(0, W, 8):
        for y in range(0, H, 8):
            g = .16 * max(0.0, (1 - x / W) * (y / H))
            vd.rectangle((x, y, x + 8, y + 8), fill=(13, 17, 26, int(255 * (.58 + g))))
    im.alpha_composite(veil)
    im.convert('RGB').save(path, quality=92)
    return path


def build(a):
    out = Path(a.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    T = texts(a)
    bg = veil_background(out / '_목차전환_바탕.jpg')
    jobs, rows = [], []
    for i, (color, style) in enumerate(combos(a), 1):
        tpl, label = STYLE[style]
        d = out / f'{i:02d}_{style}_{color.lstrip("#")}'
        d.mkdir(exist_ok=True)
        theme = [('theme_accent', color), ('theme_accent2', a.accent2), ('theme_font', a.font)]
        full = [('place', 'full'), ('exit', '0'), ('noscale', '1'), ('bgin', '0')] if style == 'light' else []
        nt, nf, nto, nu = T['number']
        cards = [
            ('1_title.png', tpl, qjoin([('kind', 'title'), ('title', T['title']),
                                        ('sub' if style == 'light' else 'label', T['sub'] if style == 'light' else 'CHAPTER 1')] + full + theme), 3.4, 4),
            ('2_number.png', tpl, qjoin([('kind', 'number'), ('title', nt), ('from', nf), ('to', nto), ('unit', nu)] + full + theme), 5.4, 6),   # 막대·배지가 다 나온 뒤
            ('3_steps.png', tpl, qjoin([('kind', 'steps'), ('title', T['steps_title']), ('items', T['steps'])] + full + theme), 3.6, 4),
        ]
        no, kicker, ctitle = T['chapter']
        cards.append(('4_chapter.png', 'motion/chapter_frost.html',
                      qjoin([('no', no), ('total', '3'), ('kicker', kicker), ('title', ctitle), ('label', a.channel)] + theme), 1.6, 3))
        for name, h, q, t, dur in cards:
            jobs.append((h, q, d / name, t, dur, name.startswith('4_')))
        rows.append(dict(no=i, style=style, label=label, color=color, dir=d.name))
    errors = []

    def run(j):
        h, q, png, t, dur, is_ch = j
        try:
            render(h, q, png, t, dur, alpha=is_ch, bg=bg if is_ch else None)
            print('만듦', png.relative_to(out), flush=True)
        except Exception as e:      # noqa: BLE001
            errors.append(str(e))
    with ThreadPoolExecutor(max(1, a.jobs)) as pool:
        list(pool.map(run, jobs))
    write_html(out, rows, T, a)
    if errors:
        print('\n'.join('[실패] ' + e for e in errors))
        sys.exit(1)
    print(f'완료: {out / "mockups.html"} (조합 {len(rows)}개 × 4장)')


def write_html(out, rows, T, a):
    names = [('1_title.png', '챕터 제목'), ('2_number.png', '숫자'), ('3_steps.png', '단계'), ('4_chapter.png', '목차 전환')]
    body = []
    for r in rows:
        imgs = ''.join(f'<figure><img src="{html.escape(r["dir"])}/{n}" alt="{html.escape(t)}" loading="lazy"><figcaption>{t}</figcaption></figure>'
                       for n, t in names)
        body.append(f'<section><h2><span class="no">{r["no"]}</span> {html.escape(r["label"])} · '
                    f'<i style="background:{html.escape(r["color"])}"></i> {html.escape(r["color"])}</h2><div class="row">{imgs}</div></section>')
    page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>모션 카드 목업</title><style>
:root{{color-scheme:light dark;--bg:#f4f5f7;--fg:#1d2433;--sub:#5c6370;--card:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111318;--fg:#eceef2;--sub:#9aa0aa;--card:#1b1e25}}}}
body{{margin:0;padding:24px 16px 48px;background:var(--bg);color:var(--fg);font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif}}
h1{{font-size:22px;margin:0 0 6px}} p{{margin:0 0 20px;color:var(--sub);font-size:14px;line-height:1.5}}
section{{background:var(--card);border-radius:14px;padding:14px 14px 10px;margin:0 0 16px}}
h2{{font-size:16px;margin:0 0 10px;display:flex;align-items:center;gap:8px}}
h2 .no{{display:inline-flex;width:26px;height:26px;border-radius:50%;background:var(--fg);color:var(--bg);align-items:center;justify-content:center;font-size:14px}}
h2 i{{display:inline-block;width:16px;height:16px;border-radius:4px}}
.row{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}}
@media (max-width:760px){{.row{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
figure{{margin:0}} img{{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:8px;display:block;background:#000}}
figcaption{{font-size:12px;color:var(--sub);margin-top:4px}}
</style></head><body>
<h1>모션 카드 목업</h1>
<p>주제: {html.escape(a.topic or '(중립 예시)')} · 조합 {len(rows)}개. 마음에 드는 조합 번호를 알려 주세요. 고른 스타일과 키 컬러로 이후 영상의 카드와 목차 전환을 만듭니다.</p>
{''.join(body)}
</body></html>'''
    (out / 'mockups.html').write_text(page, encoding='utf-8')


if __name__ == '__main__':
    build(parse_args())
