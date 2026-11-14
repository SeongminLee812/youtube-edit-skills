"""촬영본의 수평(기울기)을 재고, 인물을 가운데로 옮길 16:9 잘라내기 값을 계산합니다(원본은 읽기만 함).

- 수평: 여러 장면에서 정면 벽 몰딩·문틀·가구 모서리처럼 긴 직선을 찾아 기울기를 잰다. 화면 가운데 띠(가로 20~80%)의
  선만 쓴다. 옆벽 몰딩·침대 모서리처럼 가장자리에서 비스듬한 선은 원근 때문에 기울어 보이는 것이라 회전으로 못 고친다.
  0.2° 미만이면 0으로 본다.
- 가운데: 얼굴 자동 인식은 하지 않는다. 격자 사진(grid.jpg, 5% 간격·10%마다 숫자)을 보고 인물 중심 x를 정해
  --center-x 로 다시 돌리면 잘라내기 값과 보정 전후 비교 사진(before_after.jpg)을 만든다.
- 결과 값은 capcut_build.py 의 --crop, --rotate 로 넘긴다. CapCut에서는 잘라내기(16:9)와 변형 → 회전·배율로 보이고 고칠 수 있다.

결과(--out 폴더): frame_check.json, grid.jpg, lines.jpg, before_after.jpg(--center-x 를 줬을 때)

사용 예:
  python frame_check.py 촬영본.MOV --out 편집/00_frame
  python frame_check.py 촬영본.MOV --out 편집/00_frame --center-x 0.525          # → --crop, --rotate 값과 전후 비교
  python frame_check.py 촬영본.MOV --out 편집/00_frame --center-x 0.525 --zoom 1.1   # 조금 더 당겨 잡기
"""
import argparse
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

MIN_ROLL = 0.2          # 이보다 작은 기울기는 보정하지 않는다(도)


def frames(media, dur, out, n):
    ts = [dur * (0.05 + 0.9 * i / max(1, n - 1)) for i in range(n)]
    paths = []
    for i, t in enumerate(ts):
        p = out / f'frame_{i:02d}.png'
        C.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', str(media), '-frames:v', '1', str(p)])
        paths.append(p)
    return ts, paths


def measure(paths):
    """가운데 띠의 긴 직선으로 기울기를 잰다. 돌려주는 것: (기울기 도, + = 화면이 시계 방향으로 기움, 쓴 선 목록)"""
    import cv2
    import numpy as np
    used = []
    for k, p in enumerate(paths):
        g = cv2.cvtColor(cv2.imread(str(p)), cv2.COLOR_BGR2GRAY)
        H, W = g.shape
        e = cv2.Canny(cv2.GaussianBlur(g, (5, 5), 0), 40, 120)
        L = cv2.HoughLinesP(e, 1, np.pi / 1800, 100, minLineLength=int(min(W, H) * 0.15), maxLineGap=8)
        for x1, y1, x2, y2 in (L.reshape(-1, 4).tolist() if L is not None else []):
            if not 0.2 <= (x1 + x2) / 2 / W <= 0.8:
                continue
            if abs(x2 - x1) >= abs(y2 - y1):            # 가로선: 오른쪽이 내려가면 +
                if x2 < x1:
                    x1, y1, x2, y2 = x2, y2, x1, y1
                dev = math.degrees(math.atan2(y2 - y1, x2 - x1))
            else:                                        # 세로선: 위가 오른쪽으로 가면 +(화면이 시계 방향으로 기움)
                if y2 < y1:
                    x1, y1, x2, y2 = x2, y2, x1, y1
                dev = -math.degrees(math.atan2(x2 - x1, y2 - y1))
            if abs(dev) < 5:
                used.append(dict(frame=k, dev=round(dev, 3), len=round(math.hypot(x2 - x1, y2 - y1)), xy=[x1, y1, x2, y2]))
    if not used:
        return 0.0, used
    s = sorted(used, key=lambda u: u['dev'])             # 길이 가중 중앙값
    half, acc = sum(u['len'] for u in s) / 2, 0
    for u in s:
        acc += u['len']
        if acc >= half:
            return u['dev'], used
    return s[-1]['dev'], used


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='촬영본 수평·가운데 맞춤 값 계산')
    ap.add_argument('media')
    ap.add_argument('--out', required=True)
    ap.add_argument('--frames', type=int, default=8, help='잴 장면 수')
    ap.add_argument('--center-x', type=float, help='인물 중심 가로 위치(0~1, grid.jpg 로 정함)')
    ap.add_argument('--center-y', type=float, default=0.5, help='잘라낼 영역의 세로 중심(기본 0.5 = 위아래 그대로)')
    ap.add_argument('--zoom', type=float, default=1.0, help='가운데 맞춤에 필요한 것보다 더 당길 배율(기본 1.0)')
    a = ap.parse_args()

    C.need_ffmpeg()
    media = Path(a.media).resolve()
    info = C.media_info(media)
    if not info['has_video']:
        C.die('영상 파일이 아닙니다.')
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ts, paths = frames(media, info['duration'], out, a.frames)
    roll, used = measure(paths)
    rotate = 0.0 if abs(roll) < MIN_ROLL else round(-roll, 2)

    import cv2
    mid = paths[len(paths) // 2]
    im = cv2.imread(str(mid))
    H, W = im.shape[:2]
    g = im.copy()
    for i in range(1, 20):                       # 5% 격자, 10%마다 숫자
        x, y = int(W * i / 20), int(H * i / 20)
        col, th = ((0, 255, 255), 2) if i % 2 == 0 else ((0, 200, 200), 1)
        cv2.line(g, (x, 0), (x, H), col, th)
        cv2.line(g, (0, y), (W, y), col, th)
        if i % 2 == 0:
            cv2.putText(g, f'{i * 5}', (x + 4, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            cv2.putText(g, f'{i * 5}', (4, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
    cv2.imwrite(str(out / 'grid.jpg'), cv2.resize(g, (1280, int(1280 * H / W))))
    ln = im.copy()
    for u in used:
        if u['frame'] == len(paths) // 2:
            x1, y1, x2, y2 = u['xy']
            cv2.line(ln, (x1, y1), (x2, y2), (0, 0, 255), 3)
            cv2.putText(ln, f'{u["dev"]:+.1f}', (min(x1, x2) + 6, (y1 + y2) // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
    cv2.imwrite(str(out / 'lines.jpg'), cv2.resize(ln, (1280, int(1280 * H / W))))

    res = dict(media=str(media), size=[W, H], frames=[round(t, 2) for t in ts], lines=len(used),
               roll=round(roll, 3), rotate=rotate)
    print(f'기울기 {roll:+.2f}°(가운데 띠 직선 {len(used)}개, 길이 가중 중앙값) → 회전 {rotate:+.2f}°'
          + ('  (0.2° 미만이라 보정 안 함)' if rotate == 0 and roll else ''))
    if a.center_x is not None:
        cx, cy = a.center_x, a.center_y
        w = min(2 * min(cx, 1 - cx), 1.0) / max(1.0, a.zoom)
        h = min(w * (W / H) / (16 / 9), 1.0)
        w = h * (16 / 9) / (W / H)
        x0 = min(max(cx - w / 2, 0.0), 1 - w)
        y0 = min(max(cy - h / 2, 0.0), 1 - h)
        crop = [round(x0, 4), round(y0, 4), round(x0 + w, 4), round(y0 + h, 4)]
        th = math.radians(abs(rotate))
        cover = math.cos(th) + (16 / 9) * math.sin(th)
        res.update(center_x=cx, center_y=cy, zoom=a.zoom, crop=crop, cover_scale=round(cover, 4),
                   args=f'--crop {",".join(str(v) for v in crop)}' + (f' --rotate {rotate}' if rotate else ''))
        cw, ch = int(W * w) // 2 * 2, int(H * h) // 2 * 2
        vf = (f'crop={cw}:{ch}:{int(W * x0)}:{int(H * y0)},scale=1920:1080,'
              f'rotate={math.radians(rotate):.6f}:c=black,scale={int(1920 * cover) // 2 * 2}:-2,crop=1920:1080')
        guide = 'drawgrid=w=iw/2:h=ih/3:t=2:c=white@0.6'
        C.run(['ffmpeg', '-v', 'error', '-y', '-i', str(mid), '-filter_complex',
               f'[0]scale=1920:1080,{guide}[a];[0]{vf},{guide}[b];[a][b]hstack,scale=1920:-2',
               '-frames:v', '1', str(out / 'before_after.jpg')])
        print(f'잘라내기 {crop}(가로 {w:.1%}) · 회전 {rotate:+.2f}° · 덮기 배율 {cover:.3f}')
        print(f'  capcut_build.py 에: {res["args"]}')
        print(f'  전후 비교(왼쪽 원본 · 오른쪽 보정, 흰 선 = 가운데·3등분): {out / "before_after.jpg"}')
    C.write_json(out / 'frame_check.json', res)
    print(f'  격자 사진: {out / "grid.jpg"} · 직선: {out / "lines.jpg"}')


if __name__ == '__main__':
    main()
