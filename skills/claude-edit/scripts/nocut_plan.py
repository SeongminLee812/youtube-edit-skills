#!/usr/bin/env python3
"""컷 없이 조립할 컷 계획(plan.json)을 만듭니다 — 이미 편집된 영상에 자막·강조·모션만 얹을 때(profile.md cut_tempo: 컷 안 함).

받아쓰기(transcribe.py)의 문장 경계로만 나눈 연속 구간을 만든다. 구간 사이에 빈 곳이 없으므로 아무것도 잘리지 않는다.
문장마다 클립이 하나라 CapCut에서 클립 끝을 끌어 다듬을 수 있다.

사용 예(작업 폴더에서):
  python <스킬 폴더>/smartdaddy-video-edit/scripts/transcribe.py 내영상/영상.mp4 --out 내영상/편집/01_asr --model large-v3
  python <스킬 폴더>/claude-edit/scripts/nocut_plan.py 내영상/편집/01_asr --media 내영상/영상.mp4 --out 내영상/편집/02_cut/plan_nocut.json
  python <스킬 폴더>/smartdaddy-video-edit/scripts/capcut_build.py --template "<CapCut 템플릿>" --plan 내영상/편집/02_cut/plan_nocut.json \\
      --media 내영상/영상.mp4 --words 내영상/편집/01_asr/words.json --subtitles --staging 내영상/편집/02_cut/capcut_staging --name "<이름>"
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def duration(media):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(media)],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        sys.exit(f'길이를 읽지 못했습니다: {media}')


def main():
    ap = argparse.ArgumentParser(description='컷 없는 컷 계획(문장 경계로만 나눈 연속 구간)')
    ap.add_argument('asr', help='transcribe.py 결과 폴더(segments.json 이 있는 곳)')
    ap.add_argument('--media', required=True, help='원본 영상(길이를 읽는다)')
    ap.add_argument('--out', required=True, help='쓸 plan.json 경로')
    a = ap.parse_args()
    seg = json.loads((Path(a.asr) / 'segments.json').read_text(encoding='utf-8'))
    seg = seg.get('segments', seg) if isinstance(seg, dict) else seg
    total = duration(a.media)
    if not seg:
        out = [dict(src_in=0.0, src_out=round(total, 3), text='')]
    else:
        starts = [0.0] + [float(s['start']) for s in seg[1:]]
        out = [dict(src_in=round(starts[i], 3), src_out=round(starts[i + 1] if i + 1 < len(seg) else total, 3), text=(s.get('text') or '').strip())
               for i, s in enumerate(seg)]
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({'note': '컷 안 함: 문장 경계로만 나눈 연속 구간(nocut_plan.py)', 'segments': out}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'만듦: {p} · 구간 {len(out)}개 · 합계 {sum(o["src_out"] - o["src_in"] for o in out):.2f}초 / 원본 {total:.2f}초')


if __name__ == '__main__':
    main()
