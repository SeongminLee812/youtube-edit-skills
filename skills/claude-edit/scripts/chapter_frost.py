"""목차 전환(챕터 전환) '흐림 막' 모션을 만듭니다(claude-edit S3).

화면 전체가 어두운 반투명 막으로 덮이며(B안은 실제 블러까지) 왼쪽에 큰 번호·부제·큰 제목·키 컬러 밑줄·진행 칸이 순서대로
들어왔다가 다시 밝고 또렷해지는 전체 화면 알파 MOV. 키 컬러는 profile.md 의 chapter_color(없으면 #3B5BDB), 라벨은 channel_name.

세기(--variants, 쉼표):
  A        어두운 막만(블러 없음). 아래 영상이 어둡게 비친다. 알파 MOV 하나로 어디에나 얹힌다 = 대체판
  Bmid     어두운 막 + 블러 sigma 10px(1080p 기준): 얼굴 윤곽이 남는다
  Bstrong  어두운 막 + 블러 sigma 26px: 얼굴 윤곽이 뭉개진다
  B<숫자>  블러 sigma 직접 지정(예: B16)
B안의 블러 판은 그 시각 촬영본 구간(src~src+dur)을 편집 화면과 같은 크롭·회전·덮기 배율(capcut_build.py와 같은 계산)로 잘라
프레임마다 흐린 것이다. CapCut에서 메인 영상 위에 얹으면 '또렷 → 흐림 → 또렷'으로 보인다. 그 자리 컷을 크게 옮기면 A안을 쓴다.

알파 박자(기본 3초): 막·블러 0→1 0.35초(sine) → 유지 → 마지막 0.45초 1→0. 글자는 막보다 먼저(퇴장 앞 65%) 빠진다. 첫·끝 프레임 알파 0.
글자 층: smartdaddy motion/chapter_frost.html(Playwright). 막 색 #0D111A, 농도는 --veil(기본 .58), 왼쪽 아래로 +--veil-grad(기본 .16) 더 진하게.

목록 JSON:
  {"video": "내영상", "total": 4, "dur": 3.0,
   "times": "편집/챕터_시각.json",           (선택) items[].src 를 순서대로 장에 붙인다(장에 src 가 있으면 그것이 이긴다)
   "track": "v001 챕터전환",
   "chapters": [{"id": "C01", "no": 1, "kicker": "시작하기 전에", "title": "준비물 세 가지", "src": 120.0, "cue": "첫 번째, …"}]}
  장 칸: id · no · kicker · title · src(원본 초) · time_id(times 의 items[].id, 예: "ch1") · dur · cue · numtext(번호 대신 글자)
        · variants · compare(true면 비교용: augment_items 에 넣지 않음)

사용 예(작업 폴더에서):
  python <스킬 폴더>/claude-edit/scripts/chapter_frost.py $W/화면자료/챕터전환_frost_v1/chapters.json \
      --variants Bstrong,A [--only C01] [--dur 3] [--no-preview]
산출(출력 = JSON 폴더): <id>_<세기>_alpha.mov(ProRes 4444) · _black.mp4 · _preview.mp4(앞뒤 1초 또렷한 구간 포함, 실제 촬영 합성)
  · _frames/(+0.2·+0.6·+1.5·끝−0.5·끝−0.1초 합성 프레임) · 연락표.jpg · _render_log.json · augment_items.json(capcut_augment.py 형식)
.edit_busy 가 있으면 기다린다(--wait 초, 기본 1800). 렌더 동안 직접 .edit_busy 를 둔다.
"""
import argparse
import functools
import http.server
import io
import json
import math
import os
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.dont_write_bytecode = True
ROOT = Path(os.environ.get('PROJECT_ROOT') or os.getcwd()).resolve()     # 프로젝트 루트(PROJECT_ROOT 또는 작업 폴더)
HTML = Path(__file__).resolve().parents[2] / 'smartdaddy-video-edit' / 'motion' / 'chapter_frost.html'
sys.path.insert(0, str(ROOT / 'tools'))
import topic_paths as _TP  # noqa: E402   채널 프로필(profile.md)
W, H, FPS = 1920, 1080, 30
INK = np.array([13, 17, 26], np.float32)
BT709 = ['-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709']
SIGMA = {'A': 0, 'Bmid': 10, 'Bstrong': 26}
BUSY = ROOT / '.edit_busy'
FORBID = ['설명용', '예시', '참고용', '출처', 'DOI', '라이선스', ] + [x.strip() for x in _TP.load_profile().get('old_channel_names', '').split(',') if x.strip()]


def sigma_of(v):
    if v in SIGMA:
        return SIGMA[v]
    if v.startswith('B') and v[1:].replace('.', '').isdigit():
        return float(v[1:])
    sys.exit(f'모르는 세기: {v} (A · Bmid · Bstrong · B<숫자>)')


def find_video(v, base):
    try:
        import topic_paths as TP
        p = TP.resolve(v) if hasattr(TP, 'resolve') else None
        if p:
            return Path(p)
    except Exception:
        pass
    for d in [base, *base.parents]:
        if d.name == str(v) or d.name.startswith(str(v) + '_'):
            return d
    hits = list(_TP.videos_home(ROOT).glob(f'{v}*'))
    if hits:
        return hits[0]
    sys.exit(f'영상 폴더를 찾지 못했습니다: {v}')


def frame_filter(crop, rot):
    """capcut_build.py 와 같은 화면 맞춤: 크롭 → 캔버스 덮기 → 회전(+ = 시계 방향) 빈 모서리를 덮는 배율."""
    vf = []
    x0, y0, x1, y1 = crop
    if (x0, y0, x1, y1) != (0, 0, 1, 1):
        vf.append(f'crop=iw*{x1 - x0:.5f}:ih*{y1 - y0:.5f}:iw*{x0:.5f}:ih*{y0:.5f}')
    th = math.radians(abs(rot))
    k = math.cos(th) + max(W, H) / min(W, H) * math.sin(th)
    sw, sh = round(W * k / 2) * 2, round(H * k / 2) * 2
    vf.append(f'scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={sw}:{sh}')
    if rot:
        vf.append(f'rotate={math.radians(rot):.6f}:ow={W}:oh={H}:bilinear=1')
    else:
        vf.append(f'crop={W}:{H}')
    vf.append('format=rgb24')
    return ','.join(vf)


def read_frames(footage, t0, n, vf):
    cmd = ['ffmpeg', '-v', 'error', '-nostdin', '-ss', f'{max(0, t0):.3f}', '-i', str(footage), '-frames:v', str(n),
           '-vf', vf + f',fps={FPS}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    got = len(raw) // (W * H * 3)
    fr = np.frombuffer(raw[:got * W * H * 3], np.uint8).reshape(got, H, W, 3)
    if got < n:   # 촬영본 끝: 마지막 프레임을 늘린다
        fr = np.concatenate([fr, np.repeat(fr[-1:], n - got, 0)])
    return fr


def blur(img, sigma):
    if sigma <= 0.3:
        return img.astype(np.float32)
    f = 4 if sigma >= 6 else 2
    im = Image.fromarray(img).resize((W // f, H // f), Image.BILINEAR).filter(ImageFilter.GaussianBlur(sigma / f))
    return np.asarray(im.resize((W, H), Image.BICUBIC), np.float32)


def ease_sine(x):
    x = min(1.0, max(0.0, x))
    return -(math.cos(math.pi * x) - 1) / 2


def veil_alpha(t, dur, tin, tout):
    """막·블러 세기 0~1: 들어옴 tin초, 마지막 tout초 빠짐. 첫·끝 프레임 0."""
    if t <= 0 or t >= dur - 1e-6:
        return 0.0
    return ease_sine(t / tin) * (1 - ease_sine((t - (dur - tout)) / (tout - 1 / FPS)))


def veil_map(v, grad):
    """막 농도 지도: 기본 v, 왼쪽 아래(글자 자리)로 +grad."""
    x = np.linspace(1, 0, W, dtype=np.float32)[None, :]
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    g = np.clip(0.55 * x + 0.65 * y - 0.25, 0, 1) ** 1.2
    return np.clip(v + grad * g, 0, 0.95)[..., None]


class Typo:
    def __init__(self):
        from playwright.sync_api import sync_playwright
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
            type('Q', (http.server.SimpleHTTPRequestHandler,), {'log_message': lambda *a: None}), directory=str(HTML.parent)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.srv, self.pw = srv, sync_playwright().start()
        self.browser = self.pw.chromium.launch()
        self.page = self.browser.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
        self.err = []
        self.page.on('pageerror', lambda e: self.err.append(str(e)))

    def load(self, q):
        qs = urllib.parse.urlencode({**_TP.theme_pairs(), **q}, quote_via=urllib.parse.quote)
        self.page.goto(f'http://127.0.0.1:{self.srv.server_address[1]}/{HTML.name}?{qs}')
        self.page.wait_for_load_state('networkidle')
        self.page.evaluate('document.fonts.ready')
        if self.err:
            raise RuntimeError('HTML 오류: ' + '; '.join(self.err))

    def frame(self, t, dur):
        self.page.evaluate(f'window.render({t}, {dur})')
        im = Image.open(io.BytesIO(self.page.screenshot(type='png', omit_background=True))).convert('RGBA')
        return np.asarray(im, np.float32) / 255.0

    def close(self):
        self.browser.close(); self.pw.stop(); self.srv.shutdown()


def enc(path, alpha):
    if alpha:
        args = ['-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{W}x{H}', '-framerate', str(FPS), '-i', '-', '-an',
                '-c:v', 'prores_ks', '-profile:v', '4', '-pix_fmt', 'yuva444p10le', '-alpha_bits', '16', '-vendor', 'apl0']
    else:
        args = ['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-framerate', str(FPS), '-i', '-', '-an',
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                '-vf', 'scale=out_color_matrix=bt709:out_range=tv']
    return subprocess.Popen(['ffmpeg', '-v', 'error', '-y'] + args + BT709 + [str(path)], stdin=subprocess.PIPE)


def render_one(ch, var, S, typo, out, preview=True):
    dur, src = ch['dur'], ch['src']
    sig = sigma_of(var)
    n = round(dur * FPS)
    stem = out / f"{ch['id']}_{var}"
    typo.load({k: v for k, v in dict(no=ch['no'], total=S['total'], kicker=ch.get('kicker', ''), title=ch['title'],
                                     label=ch.get('label', _TP.load_profile().get('channel_name', '')), numtext=ch.get('numtext', ''), exit=S['tout']).items() if v != ''})
    vf = S['vf']
    pad = 1.0 if preview else 0.0
    npad = round(pad * FPS)
    sharp = read_frames(S['footage'], src - pad, n + 2 * npad, vf) if (preview or sig > 0) else None
    vm = veil_map(S['veil'], S['grad'])
    pa, pb = enc(stem.with_name(stem.name + '_alpha.mov'), True), enc(stem.with_name(stem.name + '_black.mp4'), False)
    pp = enc(stem.with_name(stem.name + '_preview.mp4'), False) if preview else None
    if pp:
        for i in range(npad):
            pp.stdin.write(sharp[i].tobytes())
    fdir = out / '_frames'; fdir.mkdir(exist_ok=True)
    stills = {round(x * FPS) for x in (0.2, 0.6, 1.5, dur - 0.5, dur - 0.1)}
    rec = dict(first_alpha=None, last_alpha=None, sub_max_alpha_text=0.0, frames=n)
    for i in range(n):
        t = i / FPS
        a = veil_alpha(t, dur, S['tin'], S['tout'])
        txt = typo.frame(t, dur)
        ta = txt[..., 3:4]
        if sig > 0:
            plate = blur(sharp[npad + i], sig * (0.35 + 0.65 * a))     # 블러도 막과 함께 세진다
            base = plate * (1 - vm) + INK * vm                           # 불투명 판
            ba = np.full((H, W, 1), a, np.float32)
        else:
            base = np.broadcast_to(INK, (H, W, 3)).astype(np.float32)
            ba = vm * a
        # 글자(프리멀티 아님) over 판
        oa = ta + ba * (1 - ta)
        oc = (txt[..., :3] * 255 * ta + base * ba * (1 - ta)) / np.maximum(oa, 1e-6)
        rgba = np.concatenate([oc, oa * 255], -1).clip(0, 255).astype(np.uint8)
        pa.stdin.write(rgba.tobytes())
        black = (oc * oa).clip(0, 255).astype(np.uint8)
        pb.stdin.write(black.tobytes())
        if pp:
            comp = (oc * oa + sharp[npad + i].astype(np.float32) * (1 - oa)).clip(0, 255).astype(np.uint8)
            pp.stdin.write(comp.tobytes())
            if i in stills:
                Image.fromarray(comp).save(fdir / f"{ch['id']}_{var}_{t:04.2f}.jpg", quality=90)
        mx = int(rgba[..., 3].max())
        if i == 0: rec['first_alpha'] = mx
        if i == n - 1: rec['last_alpha'] = mx
        rec['sub_max_alpha_text'] = max(rec['sub_max_alpha_text'], float(ta[S['sub_top']:].max()))
    if pp:
        for i in range(npad):
            pp.stdin.write(sharp[npad + n + i].tobytes())
    for p in (pa, pb, pp):
        if p:
            p.stdin.close(); p.wait()
            if p.returncode:
                sys.exit(f'ffmpeg 실패: {stem}')
    rec['sub_max_alpha_text'] = round(rec['sub_max_alpha_text'] * 255)
    return rec


def contact(out, rows, path):
    files = sorted((out / '_frames').glob('*.jpg'))
    keys = sorted({f.stem.rsplit('_', 1)[0] for f in files})
    if not keys:
        return
    cw, chh, lab = 384, 216, 30
    sheet = Image.new('RGB', (cw * 5, (chh + lab) * len(keys)), (24, 26, 32))
    d = ImageDraw.Draw(sheet)
    try:
        ft = ImageFont.truetype('/System/Library/Fonts/AppleSDGothicNeo.ttc', 20)
    except Exception:
        ft = ImageFont.load_default()
    for r, k in enumerate(keys):
        fs = sorted([f for f in files if f.stem.rsplit('_', 1)[0] == k], key=lambda f: float(f.stem.rsplit('_', 1)[1]))
        d.text((8, r * (chh + lab) + 4), k, font=ft, fill=(255, 255, 255))
        for c, f in enumerate(fs[:5]):
            im = Image.open(f).resize((cw, chh), Image.LANCZOS)
            sheet.paste(im, (c * cw, r * (chh + lab) + lab))
            d.text((c * cw + 6, r * (chh + lab) + lab + chh - 26), f.stem.rsplit('_', 1)[1] + 's', font=ft, fill=(255, 255, 255))
    sheet.save(path, quality=88)


def wait_free(limit):
    t0 = time.time()
    while BUSY.exists():
        try:
            pid = int(BUSY.read_text().split('pid')[1].split()[0])
            os.kill(pid, 0)
        except (IndexError, ValueError, ProcessLookupError):
            print('끝난 작업의 .edit_busy 표시를 지웁니다'); BUSY.unlink(missing_ok=True); break
        except PermissionError:
            pass
        if time.time() - t0 > limit:
            sys.exit(f'.edit_busy 가 {limit}초 넘게 남아 있어 멈춥니다')
        time.sleep(20)


def main():
    ap = argparse.ArgumentParser(description='챕터 전환 흐림 막 모션')
    ap.add_argument('spec')
    ap.add_argument('--variants', default='Bstrong,A')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--dur', type=float)
    ap.add_argument('--out')
    ap.add_argument('--veil', type=float, default=0.58)
    ap.add_argument('--veil-grad', type=float, default=0.16)
    ap.add_argument('--tin', type=float, default=0.35)
    ap.add_argument('--tout', type=float, default=0.45)
    ap.add_argument('--no-preview', action='store_true')
    ap.add_argument('--wait', type=int, default=1800)
    ap.add_argument('--no-busy', action='store_true', help='.edit_busy 를 확인·표시하지 않는다(한두 편 시험 렌더용)')
    a = ap.parse_args()
    sp = Path(a.spec).resolve()
    spec = json.loads(sp.read_text())
    out = Path(a.out).resolve() if a.out else sp.parent
    out.mkdir(parents=True, exist_ok=True)
    V = find_video(spec.get('video', ''), sp.parent)
    es_p = _TP.part(V, 'edit') / 'edit_state.json'
    es = json.loads(es_p.read_text()).get('inputs', {}) if es_p.exists() else {}
    footage = Path(spec.get('footage') or es['footage'])
    footage = footage if footage.is_absolute() else ROOT / footage
    crop = [float(x) for x in str(spec.get('crop') or es.get('crop') or '0,0,1,1').split(',')]
    rot = float(spec.get('rotate', es.get('rotate') or 0))
    times, times_status = [], ''
    if spec.get('times'):
        tp = V / spec['times']
        if tp.exists():
            tj = json.loads(tp.read_text())
            times, times_status = tj.get('items', []), tj.get('status', '')
    chs = spec['chapters']
    for i, c in enumerate(chs):
        c.setdefault('dur', a.dur or spec.get('dur', 3.0))
        if a.dur: c['dur'] = a.dur
        if c.get('src') is None and times:
            hit = next((x for x in times if x.get('id') == c.get('time_id')), None) if c.get('time_id') else (times[i] if i < len(times) else None)
            if hit:
                c['src'] = float(hit['src']); c['src_status'] = hit.get('status') or times_status
        text = ' '.join(str(c.get(k, '')) for k in ('kicker', 'title', 'numtext', 'label'))
        bad = [w for w in FORBID if w in text]
        if bad: sys.exit(f"{c['id']}: 금지 낱말 {bad}")
        if c.get('src') is None: sys.exit(f"{c['id']}: src(원본 초)가 없습니다")
    if a.only:
        chs = [c for c in chs if c['id'] in a.only]
    S = dict(total=spec.get('total', len(spec['chapters'])), footage=footage, vf=frame_filter(crop, rot), veil=a.veil,
             grad=a.veil_grad, tin=a.tin, tout=a.tout, sub_top=spec.get('subtitle_top', 886))
    if not a.no_busy:
        wait_free(a.wait)
        BUSY.write_text(f'chapter_frost · pid {os.getpid()} · {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
    logp = out / '_render_log.json'
    log = json.loads(logp.read_text()) if logp.exists() else []
    typo = Typo()
    try:
        for c in chs:
            for var in (c.get('variants') or a.variants.split(',')):
                t0 = time.time()
                r = render_one(c, var, S, typo, out, preview=not a.no_preview)
                ok = r['first_alpha'] == 0 and r['last_alpha'] == 0 and r['sub_max_alpha_text'] <= 8
                row = dict(id=c['id'], variant=var, src=c['src'], src_status=c.get('src_status', ''), dur=c['dur'],
                           sigma=sigma_of(var), veil=a.veil, grad=a.veil_grad, tin=a.tin, tout=a.tout, ok=ok,
                           at=time.strftime('%Y-%m-%d %H:%M:%S'), sec=round(time.time() - t0, 1), **r)
                log.append(row)
                print(f"{c['id']} {var}: 첫/끝 알파 {r['first_alpha']}/{r['last_alpha']} · 자막 띠 글자 알파 {r['sub_max_alpha_text']} → {'통과' if ok else '실패'} ({row['sec']}초)")
    finally:
        typo.close()
        if not a.no_busy:
            BUSY.unlink(missing_ok=True)
    logp.write_text(json.dumps(log, ensure_ascii=False, indent=1))
    contact(out, log, out / '연락표.jpg')
    # augment 목록: 장마다 마지막으로 통과한 기본 세기(목록 첫 세기) 하나
    first = a.variants.split(',')[0]
    items, seen = [], {}
    for r in log:
        if r['ok'] and r['variant'] == first:
            seen[r['id']] = r
    for c in spec['chapters']:
        if c.get('compare'):
            continue
        r = seen.get(c['id'])
        if r:
            f = out / f"{c['id']}_{first}_alpha.mov"
            f = f.relative_to(ROOT).as_posix() if f.is_relative_to(ROOT) else str(f)
            items.append(dict(id=f"{c['id']}_챕터전환", file=f, src=r['src'], dur=r['dur'], kind='alpha',
                              track=spec.get('track', '챕터전환'), line=c.get('cue', '')))
    (out / 'augment_items.json').write_text(json.dumps(
        {'note': f'chapter_frost.py 가 만듦({time.strftime("%Y-%m-%d %H:%M")}). 기본 세기 {first}. 그 자리 컷을 크게 옮기면 같은 이름의 _A_alpha.mov 로 바꾼다',
         'replace_media': [], 'items': items}, ensure_ascii=False, indent=1))
    print('완료', out)


if __name__ == '__main__':
    main()
