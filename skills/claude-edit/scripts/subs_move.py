#!/usr/bin/env python3
"""스테이징 CapCut 프로젝트의 텍스트(자막·강조 자막) 세로 위치를 한 번에 옮깁니다.

원본 영상에 자막이 이미 구워져 있어(이미 편집된 영상) 새 자막과 겹칠 때 쓴다. CapCut 세로 좌표 y는 아래가 −1, 위가 +1이고,
템플릿 자막은 보통 y ≈ −0.8 이다. +0.16 이면 화면 높이의 약 8%만큼 올라간다.
draft_info.json(또는 draft_content.json)·template*.tmp·Timelines/<id>/ 안 사본을 모두 고친다. CapCut에 등록하기 전 스테이징에만 쓴다.
강조 자막(emphasis.py)은 기본 자막 자리를 따라가므로, 이 도구로 먼저 올린 뒤 emphasis.py 를 돌린다.

사용 예(작업 폴더에서):
  python <스킬 폴더>/claude-edit/scripts/subs_move.py 내영상/편집/02_cut/capcut_staging/<이름> --dy 0.16 [--dry-run]
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description='스테이징 CapCut 프로젝트의 텍스트 세로 위치 옮기기')
    ap.add_argument('staging', help='capcut_build.py·emphasis.py 가 만든 스테이징 폴더(등록 전)')
    ap.add_argument('--dy', type=float, required=True, help='세로 이동(CapCut y, + = 위로). 예: 0.16')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    folder = Path(a.staging)
    files = [f for f in [folder / 'draft_info.json', folder / 'draft_content.json', *folder.glob('template*.tmp'),
                         *folder.glob('Timelines/*/draft_info.json'), *folder.glob('Timelines/*/draft_content.json'),
                         *folder.glob('Timelines/*/template*.tmp')] if f.exists()]
    if not files:
        raise SystemExit(f'프로젝트 파일이 없습니다: {folder}')
    for f in files:
        d = json.loads(f.read_text(encoding='utf-8-sig'))
        n, ys = 0, set()
        for t in d.get('tracks', []):
            if t.get('type') != 'text':
                continue
            for s in t['segments']:
                tf = s.setdefault('clip', {}).setdefault('transform', {'x': 0.0, 'y': 0.0})
                ys.add(round(tf.get('y', 0.0), 3))
                tf['y'] = round(tf.get('y', 0.0) + a.dy, 6)
                n += 1
        if not a.dry_run:
            f.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        print(f'{f.relative_to(folder)} · 텍스트 {n}개 · 원래 y {sorted(ys)[:4]} → {a.dy:+g}' + (' (미리보기)' if a.dry_run else ''))


if __name__ == '__main__':
    main()
