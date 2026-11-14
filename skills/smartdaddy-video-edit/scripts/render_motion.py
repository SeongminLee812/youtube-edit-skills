"""HTML 모션 카드를 영상으로 렌더한다 (1920×1080, 기본 30fps, 마지막 0.5초 정지는 HTML이 처리).

HTML 안에 window.render(t, dur) 함수가 있어야 한다. t초 순간의 화면을 그리는 함수다(motion/cards.html 참고).

사용 예:
  python scripts/render_motion.py motion/cards.html 편집/motion/round2.mp4 --dur 3 --query "kind=title&label=ROUND 2&title=자막"
  python scripts/render_motion.py motion/cards.html 편집/motion/time.mp4 --dur 4 --query "kind=number&title=편집 시간&from=30&to=8&unit=시간"
  python scripts/render_motion.py motion/cards.html 편집/motion/check --frames 0.5,1.5,3.5 --query "kind=steps&items=녹음|맡기기|확인"   # PNG 몇 장만
  카드 종류별 예시는 motion/examples.md. 값 안에 & 가 들어가면 %26 으로 쓴다.

투명 납품:
  python scripts/render_motion.py motion/cards_channel.html 편집/motion/subs --alpha --dur 4 --query "kind=number&title=구독자&from=120&to=480&unit=명"
    → subs_alpha.mov(ProRes 4444 알파, CapCut 덮개용) · subs_black.mp4(검정 배경, Screen 혼합 대안) · subs_alpha.png(멈춘 장면)
  --background-image 촬영프레임.jpg 를 더하면 weight_preview.mp4 · weight_preview.jpg(정지 프레임 합성 확인용)도 만든다.
  --check-safe 는 얼굴 안전영역·하단 자막 띠에 그림이 들어갔는지 검사한다(place=side 카드용).
  채널 예시는 motion/examples_channel.md.

필요한 것: pip install playwright  →  playwright install chromium,  그리고 ffmpeg. --alpha·--background-image·--check-safe는 Pillow도 쓴다.
"""
import argparse, functools, http.server, io, json, subprocess, sys, threading, urllib.parse
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ap = argparse.ArgumentParser(description='HTML 모션 카드 → 영상')
ap.add_argument('html', help='render(t, dur) 함수가 있는 HTML 파일')
ap.add_argument('out', help='결과 mp4 경로 (--frames면 PNG를 저장할 폴더, --alpha면 확장자를 뺀 이름으로 여러 파일을 만든다)')
ap.add_argument('--dur', type=float, default=4.0, help='길이(초), 기본 4')
ap.add_argument('--fps', type=int, default=30)
ap.add_argument('--query', default='', help='HTML에 넘길 값, 예: "title=제목&value=10"')
ap.add_argument('--frames', default='', help='이 시각들(초, 쉼표로 구분)만 PNG로 저장')
ap.add_argument('--chromium', default='', help='크로미움 실행 파일 경로(기본: playwright가 설치한 것)')
ap.add_argument('--crf', type=int, default=18, help='화질(낮을수록 좋음), 기본 18')
ap.add_argument('--alpha', action='store_true', help='배경을 투명하게 찍어 _alpha.mov(ProRes 4444) · _black.mp4 · _alpha.png를 만든다')
ap.add_argument('--background-image', default='', help='이 정지 그림(1920×1080) 위에 합성한 _preview.mp4 · _preview.jpg도 만든다(--alpha와 함께)')
ap.add_argument('--check-safe', action='store_true', help='얼굴 안전영역과 하단 자막 띠의 알파를 0.25초마다 검사한다(--alpha와 함께)')
ap.add_argument('--face-safe', default='520,0,1400,620', help='얼굴 안전영역 left,top,right,bottom (기본 520,0,1400,620)')
ap.add_argument('--subtitle-top', type=int, default=950, help='하단 자막 띠 시작 y (기본 950)')
ap.add_argument('--poster', type=float, default=None, help='_alpha.png·_preview.jpg로 남길 시각(기본: 끝 동작 직전)')
ap.add_argument('--asset-dir', default='', help='이 폴더를 HTML에서 _assets/로 읽는다(예: img=_assets/원본/그림.png). 템플릿을 영상 폴더에 복사하지 않아도 된다')
a = ap.parse_args()
if (a.background_image or a.check_safe) and not a.alpha: sys.exit('--background-image와 --check-safe는 --alpha와 함께 씁니다.')

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit('playwright가 없습니다. pip install playwright 한 다음 playwright install chromium 을 실행하세요.')
if a.alpha:
    try:
        from PIL import Image
    except ImportError:
        sys.exit('--alpha에는 Pillow가 필요합니다. pip install pillow')

html = Path(a.html).resolve()
if not html.exists(): sys.exit(f'HTML 파일이 없습니다: {html}')
W, H = 1920, 1080
# 1080p 표준(BT.709)으로 변환·표시해 키 컬러 같은 브랜드 색이 플레이어마다 달라 보이지 않게 한다
BT709 = ['-vf', 'scale=out_color_matrix=bt709:out_range=tv', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709']


ASSET = Path(a.asset_dir).resolve() if a.asset_dir else None
if ASSET and not ASSET.is_dir(): sys.exit(f'--asset-dir 폴더가 없습니다: {ASSET}')


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

    def translate_path(self, path):              # /_assets/… 는 --asset-dir 폴더에서 읽는다(그 폴더 밖은 막음)
        p = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
        if ASSET and p.startswith('/_assets/'):
            f = (ASSET / p[len('/_assets/'):]).resolve()
            return str(f) if f.is_relative_to(ASSET) else str(ASSET / '__없음__')
        return super().translate_path(path)


# HTML 폴더를 로컬 서버로 열어야 주소 뒤 ?값이 넘어가고 같은 폴더의 그림·글꼴을 읽을 수 있다
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(html.parent)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
query = a.query + ('&alpha=1' if a.alpha else '') if a.query else ('alpha=1' if a.alpha else '')
q = urllib.parse.quote(query, safe='=&') if query else ''
url = f'http://127.0.0.1:{srv.server_address[1]}/{urllib.parse.quote(html.name)}' + (f'?{q}' if q else '')

bg = None
if a.background_image:
    bg = Image.open(a.background_image).convert('RGBA')
    if bg.size != (W, H): bg = bg.resize((W, H), Image.LANCZOS); print('배경 그림을 1920×1080으로 맞춤')
face = tuple(int(v) for v in a.face_safe.split(','))
is_full = 'place=full' in a.query
covers_subs = is_full or 'place=split' in a.query   # 패널 바탕이 자막 띠를 덮는 배치(자막은 CapCut 위 트랙)
safe_log = []


def check(im, t):
    """알파 PNG 한 장에서 얼굴 안전영역·자막 띠의 최대 알파(0~255)를 잰다."""
    al = im.getchannel('A')
    fz, sz = al.crop(face).getextrema()[1], al.crop((0, a.subtitle_top, W, H)).getextrema()[1]
    safe_log.append({'t': round(t, 3), 'face_max_alpha': fz, 'subtitle_max_alpha': sz})


def ff(path, alpha_out=False):
    """프레임을 받아 인코딩하는 ffmpeg. 알파 MOV는 PNG를 그대로, 나머지는 RGB 원시 프레임을 받는다."""
    if alpha_out:
        src = ['-f', 'image2pipe', '-framerate', str(a.fps), '-c:v', 'png', '-i', '-']
        enc = ['-c:v', 'prores_ks', '-profile:v', '4', '-pix_fmt', 'yuva444p10le', '-alpha_bits', '16', '-vendor', 'apl0']
    else:
        src = ['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-framerate', str(a.fps), '-i', '-']
        enc = ['-c:v', 'libx264', '-preset', 'medium', '-crf', str(a.crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart']
    return subprocess.Popen(['ffmpeg', '-v', 'error', '-y'] + src + ['-an'] + enc + BT709 + [str(path)], stdin=subprocess.PIPE)


def on(base_rgba, im):
    c = base_rgba.copy(); c.alpha_composite(im); return c.convert('RGB')


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=a.chromium or None)
    page = browser.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(url); page.wait_for_load_state('networkidle')
    page.evaluate('document.fonts.ready')
    if not page.evaluate('typeof window.render === "function"'):
        sys.exit('HTML에 window.render(t, dur) 함수가 없습니다.')
    shot = lambda: page.screenshot(type='png', omit_background=a.alpha)
    black = Image.new('RGBA', (W, H), (0, 0, 0, 255)) if a.alpha else None

    if a.frames:
        outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)
        for t in [float(x) for x in a.frames.split(',') if x.strip()]:
            page.evaluate(f'window.render({t}, {a.dur})')
            p = outdir / f'{html.stem}_{t:05.2f}.png'; data = shot(); p.write_bytes(data); print('저장', p)
            if bg is not None:
                im = Image.open(io.BytesIO(data)).convert('RGBA'); pj = p.with_name(p.stem + '_preview.jpg'); on(bg, im).save(pj, quality=92); print('저장', pj)
    elif a.alpha:
        stem = Path(a.out); stem = stem.with_suffix('') if stem.suffix else stem
        stem.parent.mkdir(parents=True, exist_ok=True)
        outs = {'alpha': stem.with_name(stem.name + '_alpha.mov'), 'black': stem.with_name(stem.name + '_black.mp4')}
        if bg is not None: outs['preview'] = stem.with_name(stem.name + '_preview.mp4')
        procs = {'alpha': ff(outs['alpha'], True), 'black': ff(outs['black'])}
        if bg is not None: procs['preview'] = ff(outs['preview'])
        n = round(a.dur * a.fps)
        exit_s = page.evaluate('typeof window.CARD_EXIT === "number" ? window.CARD_EXIT : 0')
        poster_t = a.poster if a.poster is not None else max(0.0, a.dur - (exit_s if exit_s > 0 else 0.5) - 0.05)
        step = max(1, a.fps // 4)
        for i in range(n):
            t = i / a.fps
            page.evaluate(f'window.render({t}, {a.dur})')
            data = shot()
            procs['alpha'].stdin.write(data)
            im = Image.open(io.BytesIO(data)).convert('RGBA')
            procs['black'].stdin.write(on(black, im).tobytes())
            if bg is not None: procs['preview'].stdin.write(on(bg, im).tobytes())
            if a.check_safe and (i % step == 0 or i == n - 1): check(im, t)
            if i in (0, n - 1):
                ext = im.getchannel('A').getextrema()[1]
                print(f'  {"첫" if i == 0 else "끝"} 프레임 최대 알파 {ext}' + ('' if ext == 0 else ' (0이 아님: exit=0이면 정상)'))
            if i % (a.fps * 2) == 0: print(f'  {t:.1f}/{a.dur:.1f}초', flush=True)
        failed = []
        for k, p in procs.items():
            p.stdin.close(); p.wait()
            if p.returncode: failed.append(k)
        if failed: sys.exit('ffmpeg 인코딩 실패: ' + ', '.join(failed))
        page.evaluate(f'window.render({poster_t}, {a.dur})')
        data = shot(); pp = stem.with_name(stem.name + '_alpha.png'); pp.write_bytes(data)
        if bg is not None: on(bg, Image.open(io.BytesIO(data)).convert('RGBA')).save(stem.with_name(stem.name + '_preview.jpg'), quality=92)
        for k, p in outs.items(): print('완료', p)
        print('완료', pp, f'({n}프레임 · {a.fps}fps · 멈춘 장면 {poster_t:.2f}초)')
        if a.check_safe:
            fz = max(r['face_max_alpha'] for r in safe_log); sz = max(r['subtitle_max_alpha'] for r in safe_log)
            rep = {'face_safe': face, 'subtitle_top': a.subtitle_top, 'samples': len(safe_log), 'face_max_alpha': fz, 'subtitle_max_alpha': sz,
                   'note': 'place=full은 화면 전체를 덮는 카드라 얼굴 검사 대상이 아니다' if is_full else ('place=split 패널 바탕은 자막 띠를 덮는다. 자막은 CapCut 위 트랙' if covers_subs else ''), 'log': safe_log}
            stem.with_name(stem.name + '_safe.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1))
            ok = is_full or (fz <= 8 and (covers_subs or sz <= 8))
            print(f'안전영역 검사: 얼굴 최대 알파 {fz}, 자막 띠 최대 알파 {sz} (0.25초마다 {len(safe_log)}장) → ' + ('통과' if ok else '겹침! 배치를 고치세요'))
    else:
        out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
        n = round(a.dur * a.fps)
        ff_ = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'image2pipe', '-framerate', str(a.fps), '-i', '-',
                                '-c:v', 'libx264', '-preset', 'medium', '-crf', str(a.crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart'] + BT709 + [str(out)],
                               stdin=subprocess.PIPE)
        for i in range(n):
            page.evaluate(f'window.render({i / a.fps}, {a.dur})')
            ff_.stdin.write(page.screenshot(type='png'))
            if i % (a.fps * 2) == 0: print(f'  {i / a.fps:.1f}/{a.dur:.1f}초', flush=True)
        ff_.stdin.close(); ff_.wait()
        if ff_.returncode: sys.exit('ffmpeg 인코딩 실패')
        print('완료', out, f'({n}프레임)')
    browser.close()
    if errors: print('HTML 오류:', *errors, sep='\n  ')
srv.shutdown()
