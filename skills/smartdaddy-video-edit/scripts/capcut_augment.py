"""사용자가 CapCut에서 다듬은 프로젝트를 새 이름으로 복사하고, 컷·자막·카드는 그대로 둔 채 덧입히기만 더합니다.

capcut_build.py 는 컷 계획으로 프로젝트를 처음부터 만들어서, 사용자가 CapCut에서 자른 곳·고친 자막이 사라진다.
이 도구는 기존 프로젝트(--base)를 읽기만 하고, 복사본(--name)에
  - 덧입히기(사진 영상·모션 카드·스톡)를 원본 시각(src) 기준으로 얹는다. 메인 트랙 클립의 원본 구간으로 편집 시각을 찾으므로
    사용자가 컷을 바꿔도 같은 대사에 붙는다. 대사가 잘려 나갔으면 넣지 않고 알린다
  - 채널 범퍼를 원본 --bumper src 자리 메인 트랙에 끼우고 뒤를 모두 민다
  - 같은 장면의 미디어를 바꾼다(예: 저화질 인용 클립 → 1080p, 크롭·길이·위치 유지)
  - --loudness-off: 클립마다 걸린 CapCut '음량 정규화'를 끈다(전체 음량은 master_audio.py 로 맞춤)
새 덧입히기 트랙은 기존 영상 트랙 위·자막 아래에 둔다. 기존 프로젝트·원본은 바꾸지 않는다.

덧입히기 목록(JSON):
  {"bumper": {"file": "...mp4", "src": 107.7, "db": -8},
   "replace_media": [{"match": "파일 이름 일부", "file": "새 파일", "volume": 0}],   ← 불투명 카드 → 알파 MOV 교체도 이것으로
   "remove_media": ["파일 이름 일부"],            ← 메인이 아닌 트랙에서 그 클립을 지운다
   "track_order": ["v005 사진"],                 ← 메인 바로 위(카드 아래)에 둘 트랙. 카드가 사진 위에 보인다
   "items": [{"id": "NB03", "file": "...mp4", "src": 9.11, "dur": 1.5, "kind": "full|alpha", "track": "v004 사진",
              "src_in": 0, "line": "붙일 대사"}]}
  file 은 작업 폴더 기준 상대 경로도 된다. 같은 트랙의 다음 덧입히기·기존 카드가 시작하면 거기서 자른다.

사용 예:
  python capcut_augment.py --base 내영상_초벌_v003 --name 내영상_초벌_v004 \\
      --spec 편집/시각자료_v004/v004_덧입히기.json --staging 편집/02_cut/capcut_staging --loudness-off [--install]
"""
import argparse
import copy
import json
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
SNAP = 1.5          # 대사 시작이 컷 안이면 이 초 안의 다음 클립 시작에 붙인다. 더 멀면 잘린 대사로 본다


def us(t):
    return int(round(t * C.US))


def resolve(p):
    p = Path(p).expanduser()
    if p.is_absolute():
        return p
    for base in (Path.cwd(), ROOT):
        if (base / p).exists():
            return (base / p).resolve()
    C.die(f'파일이 없습니다: {p}')


def seg_range(s):
    t = s['target_timerange']
    return t['start'], t['start'] + t['duration']


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='다듬은 CapCut 프로젝트 복사본에 덧입히기 더하기')
    ap.add_argument('--base', required=True, help='사용자가 다듬은 기존 프로젝트 이름(읽기만 함)')
    ap.add_argument('--name', required=True, help='새 프로젝트 이름(기존 이름과 겹치면 안 됨)')
    ap.add_argument('--spec', required=True, help='덧입히기 목록 JSON')
    ap.add_argument('--staging', required=True, help='스테이징 폴더')
    ap.add_argument('--capcut-dir')
    ap.add_argument('--loudness-off', action='store_true', help="클립별 CapCut '음량 정규화'를 끈다")
    ap.add_argument('--install', action='store_true', help='CapCut 목록에 등록(CapCut을 끈 상태에서만)')
    a = ap.parse_args()

    cc = C.find_capcut_dir(a.capcut_dir)
    base_dir = C.resolve_project(a.base, a.capcut_dir)
    spec = C.read_json(a.spec)
    tpl = B.Template(base_dir)
    seg0, mat0, refs0 = tpl.vid
    tpl.vid = (seg0, mat0, {r: v for r, v in refs0.items() if v[0] != 'loudnesses'})   # 새 클립에 음량 정규화를 옮기지 않는다
    b = B.Builder(tpl)
    D = b.D = copy.deepcopy(tpl.D)
    b.M = D['materials']
    mats = C.material_index(D)
    vtracks = [t for t in D['tracks'] if t['type'] == 'video']
    if not vtracks:
        C.die('기존 프로젝트에 영상 트랙이 없습니다.')
    main_t = vtracks[0]
    main_t.setdefault('name', '메인')
    for t in D['tracks']:
        b.tracks[t.get('name') or t['id']] = t
    old_ids = {t['id'] for t in D['tracks']}
    cv = D.get('canvas_config') or dict(width=1920, height=1080)
    path_of = lambda s: mats.get(s['material_id'], (None, {}))[1].get('path', '')
    src_path = Counter(path_of(s) for s in main_t['segments']).most_common(1)[0][0]
    report = dict(base=a.base, name=a.name, items=[], warnings=[])

    def main_segs():
        return sorted((s for s in main_t['segments'] if path_of(s) == src_path), key=lambda s: s['target_timerange']['start'])

    # 1) 범퍼: 원본 src 이후 첫 클립 앞에 끼우고 뒤를 모두 민다
    bm = spec.get('bumper')
    if bm and any(Path(bm['file']).stem in path_of(s) or '범퍼' in path_of(s) or 'bumper' in path_of(s).lower()
                  for s in main_t['segments']):
        report['warnings'].append('메인 트랙에 이미 범퍼가 있어 다시 넣지 않음')
        bm = None
    if bm:
        segs = main_segs()
        nxt = next((s for s in segs if s['source_timerange']['start'] / C.US >= bm['src'] - 0.05), None)
        if nxt is None:
            report['warnings'].append(f"범퍼 자리(원본 {bm['src']}초 이후 클립)를 찾지 못해 넣지 않음")
        else:
            T = nxt['target_timerange']['start']
            bp = resolve(bm['file'])
            info = C.media_info(bp)
            sh = us(info['duration'])
            for t in D['tracks']:
                for s in t['segments']:
                    s0, s1 = seg_range(s)
                    if s0 >= T - 1000 or (s1 > T + 1000 and s1 - T >= T - s0):   # 자막은 말보다 조금 일찍 뜬다: 대부분이 뒤면 같이 민다
                        s['target_timerange']['start'] += sh
                    elif s1 > T + 1000:
                        report['warnings'].append(f"범퍼 자리({T / C.US:.2f}초)를 가로지르는 클립: {t.get('name') or t['type']} "
                                                  f"{s0 / C.US:.2f}–{s1 / C.US:.2f}초 (그대로 둠)")
            b.put_video(main_t['name'], bp, T, sh, 0, B.cover_scale(info, cv), 10 ** (bm.get('db', -8.0) / 20))
            D['duration'] = D.get('duration', 0) + sh
            report['bumper'] = dict(at=round(T / C.US, 3), dur=round(sh / C.US, 3), file=bp.name)

    segs = main_segs()

    def to_tl(src):
        """원본 초 → 편집 시각(us). 대사가 잘렸으면 None."""
        for s in segs:
            s0, d = s['source_timerange']['start'] / C.US, s['source_timerange']['duration'] / C.US
            if s0 <= src < s0 + d:
                return s['target_timerange']['start'] + us((src - s0) / (s.get('speed') or 1.0)), 'in'
        later = [s for s in segs if s['source_timerange']['start'] / C.US > src]
        if later:
            n = min(later, key=lambda s: s['source_timerange']['start'])
            if n['source_timerange']['start'] / C.US - src <= SNAP:
                return n['target_timerange']['start'], 'snap'
        return None, 'cut'

    # 2) 미디어 바꾸기(크롭·길이·자리는 그대로)
    for r in spec.get('replace_media', []):
        newp = C.capcut_media(resolve(r['file']))
        info = C.media_info(newp)
        hit = [m for m in b.M.get('videos', []) if r['match'] in m.get('path', '')]
        for m in hit:
            m.update(path=newp.as_posix(), material_name=newp.name, width=info['width'], height=info['height'],
                     duration=us(info['duration']), has_audio=info['has_audio'])
            for t in D['tracks']:
                for s in t['segments']:
                    if s['material_id'] != m['id']:
                        continue
                    if 'volume' in r:
                        s['volume'] = r['volume']
                    src_end = s['source_timerange']['start'] + s['source_timerange']['duration']
                    if src_end > us(info['duration']) + 40000:
                        report['warnings'].append(f"{newp.name}: 새 파일({info['duration']:.2f}초)이 쓰던 구간"
                                                  f"({src_end / C.US:.2f}초까지)보다 짧음")
        report.setdefault('replaced', []).append(dict(match=r['match'], file=newp.name, materials=len(hit)))
        if not hit:
            report['warnings'].append(f"바꿀 미디어를 찾지 못함: {r['match']}")

    # 2-1) 미디어 빼기: 메인이 아닌 영상 트랙에서 파일 이름이 맞는 클립을 지운다(사용자가 별로라고 한 자료)
    for pat in spec.get('remove_media', []):
        n = 0
        for t in vtracks[1:]:
            keep = [s for s in t['segments'] if pat not in path_of(s)]
            n += len(t['segments']) - len(keep)
            t['segments'] = keep
        report.setdefault('removed', []).append(dict(match=pat, segments=n))
        if not n:
            report['warnings'].append(f'뺄 미디어를 찾지 못함: {pat}')

    # 3) 덧입히기: 같은 트랙의 다음 덧입히기·기존 영상 덧입히기(메인·사진 트랙 제외)가 시작하면 거기서 자른다
    under = set(spec.get('track_order', []))       # 메인 바로 위(카드 아래)에 둘 트랙: 카드가 사진 위에 보인다
    existing = sorted(seg_range(s) for t in vtracks[1:] if t.get('name') not in under for s in t['segments'])
    total = D['duration']
    placed = []
    items = spec.get('items', [])
    starts = {}
    for it in items:
        st, how = to_tl(it['src'])
        starts[it['id']] = (st, how)
    for k, it in enumerate(items):
        st, how = starts[it['id']]
        row = dict(id=it['id'], line=it.get('line', ''), src=it['src'], status=how)
        if st is None:
            row['status'] = 'cut'
            report['items'].append(row)
            report['warnings'].append(f"{it['id']}: 붙일 대사(원본 {it['src']}초 '{it.get('line', '')[:20]}')가 잘려 넣지 않음")
            continue
        end = st + us(it['dur'])
        nexts = [starts[x['id']][0] for x in items[k + 1:] if x.get('track') == it.get('track') and starts[x['id']][0] is not None
                 and starts[x['id']][0] > st]
        nexts += [e0 for e0, _ in existing if e0 > st + 100000]
        cap = min(nexts + [end, total])
        if cap < end:
            row['trimmed_from'] = round(it['dur'], 3)
        dur = cap - st
        if dur < 400000:
            row['status'] = 'too_short'
            report['items'].append(row)
            report['warnings'].append(f"{it['id']}: 들어갈 자리가 0.4초보다 짧아 넣지 않음")
            continue
        over = [(round(e0 / C.US, 2), round(e1 / C.US, 2)) for e0, e1 in existing if e0 < cap and e1 > st]
        if over:
            row['over_existing'] = over
        p = resolve(it['file'])
        info = C.media_info(p)
        tr = b.free_track(it.get('track', '덧입히기'), 'video', st, dur)
        b.put_video(tr, p, st, dur, us(it.get('src_in', 0.0)), B.cover_scale(info, cv), 0.0)
        row.update(at=round(st / C.US, 3), dur=round(dur / C.US, 3), track=tr, file=p.name)
        placed.append(row)
        report['items'].append(row)

    # 4) 클립별 음량 정규화 끄기
    if a.loudness_off:
        n = 0
        for l in b.M.get('loudnesses', []):
            if l.get('enable'):
                l['enable'] = False
                n += 1
        report['loudness_off'] = n

    # 트랙 순서: 메인 → track_order(사진: 카드 아래) → 기존 영상 → 새 영상 → 자막·글자 → 소리. 영상이 자막을 가리지 않게
    vids = [t for t in D['tracks'] if t['type'] == 'video' and t is not main_t]
    first = [t for name in spec.get('track_order', []) for t in vids if t.get('name') == name]
    old_v = [t for t in vids if t['id'] in old_ids and t not in first]
    new_v = [t for t in vids if t['id'] not in old_ids and t not in first]
    rest = [t for t in D['tracks'] if t['type'] != 'video']
    order = {'text': 0, 'audio': 1}
    D['tracks'] = [main_t] + first + old_v + new_v + sorted(rest, key=lambda t: order.get(t['type'], 2))
    for i, t in enumerate(D['tracks']):
        t['segments'].sort(key=lambda s: s['target_timerange']['start'])
        for s in t['segments']:
            s['track_render_index'] = i
            s['render_index'] = i if t['type'] in ('video', 'text') else 0

    dest = cc / a.name
    now = int(time.time())
    D.update(id=B.uid(), name=a.name, path=dest.as_posix(), create_time=now, update_time=now)
    stage_root = Path(a.staging).resolve()
    stage_root.mkdir(parents=True, exist_ok=True)
    stage = stage_root / a.name
    media_paths = sorted({m.get('path') for m in b.M.get('videos', []) + b.M.get('audios', []) if m.get('path')})
    first = segs[0] if segs else None
    B.write_staging(b, tpl, stage, a.name, dest, media_paths,
                    (Path(src_path), first['source_timerange']['start'] / C.US + 0.5) if first else None)
    # write_staging 은 미디어 목록을 새 재료로만 채운다 → 기존 목록을 앞에 되살린다
    for fn, typ in (('draft_meta_info.json', 0), ('draft_virtual_store.json', 1)):
        old_p, new_p = base_dir / fn, stage / fn
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

    rp = stage_root / f'{a.name}_augment.json'
    C.write_json(rp, report)
    ntr = [f"{t.get('name') or t['type']} {len(t['segments'])}" for t in D['tracks']]
    print(f"덧입히기 완료: {a.name} · 길이 {C.mmss(D['duration'] / C.US)} · 넣음 {len(placed)}/{len(items)} · 트랙 {ntr}")
    if report.get('bumper'):
        print(f"  범퍼 {report['bumper']['at']:.2f}초에 {report['bumper']['dur']:.1f}초")
    for r in report.get('replaced', []):
        print(f"  미디어 바꿈: {r['match']} → {r['file']} ({r['materials']}개)")
    if 'loudness_off' in report:
        print(f"  클립별 음량 정규화 끔: {report['loudness_off']}개")
    for w in report['warnings']:
        print('  [주의]', w)
    print(f'  스테이징: {stage}\n  기록: {rp}')
    if a.install:
        sys.exit(B.install(stage, cc, a.name, stage_root / 'backups'))
    print('  CapCut 등록은 아직 안 했습니다. CapCut을 끈 뒤 같은 명령에 --install 을 붙이면 등록합니다.')


if __name__ == '__main__':
    main()
