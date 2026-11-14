#!/usr/bin/env python3
"""CapCut 프로젝트 전체를 배속한 새 버전을 만든다(기본 1.1배속, 선택 도구).

- 바탕 프로젝트를 capcut_augment(빈 덧입히기 목록)로 스테이징에 복사한 뒤 스테이징 draft만 고친다. 바탕 폴더는 읽기만 한다.
- 메인·덧입힌 영상 클립: speed=배속, is_tone_modify=False(목소리 높낮이 유지), 속도 재질(materials.speeds)도 같은 값.
- 자막·카드·사진: 시작·길이를 같은 시각표로 줄인다.
- 범퍼(메인 트랙에서 촬영본이 아닌 클립 하나): 원래 속도·길이 그대로(효과음·로고 애니메이션 유지).
- 효과음(BGM 이 아닌 오디오 클립, 2026-11-15): 시작만 시각표로 옮기고 길이·속도 1.0·원본 범위는 그대로(소리 모양 유지).
- 배경음악('BGM' 트랙, emphasis.BGM_TRACK, 음악은 배속하지 않음): 배속 전 BGM 클립을 지우고, 이어 붙어 있던
  구간마다 시작·끝을 시각표로 옮긴 새 구간에 곡 처음부터 원래 빠르기로 다시 깐다(emphasis.bgm_layout 과 같은 규칙: 곡보다 길면 반복,
  구간 처음 페이드인·끝 페이드아웃·이음매 페이드·클립 볼륨은 배속 전 값). 곡 빠르기·음높이는 그대로이고 깔리는 구간만 짧아진다.
- 강조 확대·스티커(영상 덧입히기): 다른 영상 클립과 같이 speed=배속, 원본 시작 그대로(메인과 같은 원본 시각).
- 검증: 길이·트랙별 segment 수(BGM 트랙 제외)·메인 클립 원본 시작·target 공식·자막/자료 시작의 원본 초(차이 0.05초 미만)·속도 재질·
  미디어 누락·오디오(효과음 길이·원본·시작, BGM 속도 1.0·길이=원본·구간·범퍼 위 없음·빈틈/겹침 없음).
  하나라도 어긋나면 등록하지 않는다.


실행(프로젝트 루트):
  python <스킬 폴더>/claude-edit/scripts/speed_version.py --video 내영상 --base 내영상_초벌_v006 \
      --name 내영상_v008_1.1배속 --speed 1.1 [--footage <촬영본 이름>] [--install]
  --base 는 CapCut 프로젝트 이름 또는 프로젝트 폴더(스테이징 폴더 포함) 경로.
결과: <편집 폴더>/08_speed/<이름>/(스테이징) · <편집 폴더>/08_speed/<이름>_배속.json(보고) · 등록 백업 <편집 폴더>/08_speed/backups/
"""
import argparse
import json
import subprocess
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(os.environ.get('PROJECT_ROOT') or os.getcwd()).resolve()     # 프로젝트 루트(PROJECT_ROOT 또는 작업 폴더)
SK = Path(__file__).resolve().parents[2] / 'smartdaddy-video-edit/scripts'
sys.path[:0] = [str(SK), str(ROOT / 'tools')]
import _common as C          # noqa: E402
import capcut_build as B     # noqa: E402
import emphasis as E         # noqa: E402  (BGM_TRACK, bgm_layout, add_fade)
import topic_paths as TP     # noqa: E402

PY = str(ROOT / '.venv/bin/python') if (ROOT / '.venv/bin/python').exists() else sys.executable
US = 1_000_000
TOL_SRC = 0.05


def tr(s): return s['target_timerange']['start'] / US, s['target_timerange']['duration'] / US


def vmats(D): return {m['id']: m for m in D['materials'].get('videos', [])}


def main_track(D): return max((t for t in D['tracks'] if t['type'] == 'video'), key=lambda t: len(t['segments']))


def is_foot(D, s, foot): return foot in (vmats(D).get(s['material_id'], {}).get('path') or '')


def src_of_edit(D, t_us, foot):
    """편집 시각 t_us(마이크로초 정수)에 화면에 나오는 촬영본의 원본 초(범퍼 등 촬영본이 아니면 None).
    경계에서 부동소수 오차로 앞 클립을 고르지 않도록 정수로 비교한다."""
    for s in main_track(D)['segments']:
        a, d = s['target_timerange']['start'], s['target_timerange']['duration']
        if a <= t_us < a + d:
            if not is_foot(D, s, foot): return None
            return s['source_timerange']['start'] / US + (t_us - a) / US * (s.get('speed') or 1.0)
    return None


def save_draft(stage, D):
    """capcut_build.write_staging 과 같은 곳들에 같은 내용으로 쓴다."""
    js = json.dumps(D, ensure_ascii=False, separators=(',', ':'))
    paths = [stage / 'draft_info.json', stage / 'template-2.tmp', stage / 'template.tmp']
    for d in (stage / 'Timelines').iterdir() if (stage / 'Timelines').exists() else []:
        if d.is_dir(): paths += [d / 'draft_info.json', d / 'template-2.tmp', d / 'template.tmp']
    for i, p in enumerate(paths):
        if i < 2 or p.exists() or p.name == 'draft_info.json': p.write_text(js, 'utf-8')


def edit_dir(video):
    if TP.TOPIC_ID.match(video):
        V = TP.topic_folder(video, ROOT)
    else:
        V = Path(video) if Path(video).is_absolute() else ROOT / video
    return TP.part(V.resolve(), 'edit')


def is_bgm(t): return t['type'] == 'audio' and (t.get('name') or '').startswith(E.BGM_TRACK)


def bgm_runs(D):
    """BGM 클립을 이어 붙은 구간으로 묶는다: [dict(start, end, fade_in, fade_out, seam, proto, clips)] (초)."""
    fades = {m['id']: m for m in D['materials'].get('audio_fades', [])}
    segs = sorted((s for t in D['tracks'] if is_bgm(t) for s in t['segments']), key=lambda s: s['target_timerange']['start'])
    runs = []
    for s in segs:
        a, d = tr(s)
        fd = next((fades[r] for r in s.get('extra_material_refs', []) if r in fades), {})
        fi, fo = fd.get('fade_in_duration', 0) / US, fd.get('fade_out_duration', 0) / US
        if runs and abs(a - runs[-1]['end']) < 0.01:
            r = runs[-1]
            r.update(end=a + d, fade_out=fo, clips=r['clips'] + 1)
            r['seam'] = fi
        else:
            runs.append(dict(start=a, end=a + d, fade_in=fi, fade_out=fo, seam=0.15, proto=s, clips=1))
    return runs


def relay_bgm(D, runs, f):
    """배속 전 BGM 구간(runs)을 시각표 f 로 옮긴 새 구간에 원래 빠르기로 다시 깐다."""
    tracks = [t for t in D['tracks'] if is_bgm(t)]
    if not tracks: return []
    for t in tracks: t['segments'] = []
    M = C.material_index(D)
    amats = {m['id']: m for m in D['materials'].get('audios', [])}
    fades = {m['id'] for m in D['materials'].get('audio_fades', [])}
    out = []
    for r in runs:
        p = r['proto']
        fdur = amats[p['material_id']]['duration'] / US
        na, nb = f(r['start']), f(r['end'])
        for t0, du, fi, fo in E.bgm_layout([(na, nb)], fdur, r['fade_in'], r['fade_out'], r['seam']):
            s = json.loads(json.dumps(p))
            refs = []
            for ref in p.get('extra_material_refs', []):
                if ref in fades or ref not in M: continue
                kk, m = M[ref]
                nm = json.loads(json.dumps(m)); nm['id'] = B.uid()
                D['materials'][kk].append(nm); refs.append(nm['id'])
            s.update(id=B.uid(), extra_material_refs=refs, speed=1.0, desc=f'BGM {len(out) + 1}',
                     target_timerange={'start': int(round(t0 * US)), 'duration': int(round(du * US))},
                     source_timerange={'start': 0, 'duration': int(round(du * US))})
            E.add_fade(D, s, fi, fo)
            tracks[0]['segments'].append(s)
            out.append(dict(start=round(t0, 3), dur=round(du, 3), fade_in=fi, fade_out=fo, volume=s.get('volume')))
    for i, t in enumerate(D['tracks']):
        for s in t['segments']:
            s['track_render_index'] = i
    return out


def apply_speed(D, k, foot):
    mt = main_track(D)
    runs = bgm_runs(D)
    # 메인 트랙의 촬영본이 아닌 클립(범퍼·CTA 등 자체 소리가 있는 끼워 넣은 자료)은 원래 속도·길이 그대로 둔다(2026-11-15:
    # v006 에 CTA 카드가 더해져 '하나만' 가정이 깨짐). 클립이 하나면 이전 공식과 똑같은 계산 순서다.
    bums = sorted((s for s in mt['segments'] if not is_foot(D, s, foot)), key=lambda s: s['target_timerange']['start'])
    fixed = [(tr(s)[0], tr(s)[0] + tr(s)[1]) for s in bums]
    b0, b1 = fixed[0] if fixed else (None, None)

    def f(t):
        new, prev = 0.0, 0.0
        for x0, x1 in fixed:
            if t <= x0: return new + (t - prev) / k if prev else t / k
            new = (new + (x0 - prev) / k) if prev else x0 / k
            if t <= x1: return new + (t - x0)
            new += (x1 - x0); prev = x1
        return new + (t - prev) / k if prev else t / k

    spd = {m['id']: m for m in D['materials'].get('speeds', [])}
    n_sp = 0
    for t in D['tracks']:
        if is_bgm(t): continue                  # 아래에서 원래 빠르기로 다시 깐다
        for s in t['segments']:
            a0, d0 = tr(s)
            if t['type'] == 'audio':            # 효과음: 시작만 옮기고 길이·속도·원본 그대로
                s['target_timerange']['start'] = int(round(f(a0) * US))
                continue
            is_bum = t is mt and any(abs(a0 - x0) < 1e-3 for x0, _ in fixed)
            na, nb = f(a0), f(a0 + d0)
            s['target_timerange'] = {'start': int(round(na * US)), 'duration': int(round((nb - na) * US))}
            if t['type'] == 'video' and not is_bum:
                s['speed'] = k; s['is_tone_modify'] = False; n_sp += 1
                for r in s.get('extra_material_refs', []):
                    if r in spd: spd[r]['speed'] = k; spd[r]['mode'] = 0
                if s.get('source_timerange'):   # 원본 길이 = 새 길이 × 배속(반올림 오차를 원본 쪽에 맞춤)
                    s['source_timerange']['duration'] = int(round((nb - na) * k * US))
    D['duration'] = int(round(f(D['duration'] / US) * US))
    for t in D['tracks']: t['segments'].sort(key=lambda s: s['target_timerange']['start'])
    bgm = relay_bgm(D, runs, f)
    names = [Path(vmats(D)[x['material_id']]['path']).name for x in bums]
    return f, n_sp, (fixed, names), dict(base_runs=[dict(start=round(r['start'], 3), end=round(r['end'], 3), clips=r['clips'],
                                                          fade_in=r['fade_in'], fade_out=r['fade_out'], seam=r['seam']) for r in runs],
                                          new_clips=bgm)


def verify(B0, D, f, k, foot, bum):
    """B0=바탕, D=배속판. 결과 dict(ok, 항목별)."""
    fixed, _ = bum
    res = {}
    exp = f(B0['duration'] / US)
    res['a_length'] = dict(base=round(B0['duration'] / US, 3), new=round(D['duration'] / US, 3), expected=round(exp, 3),
                           ok=abs(D['duration'] / US - exp) < 0.01)
    cnt0 = [(t.get('name') or t['type'], len(t['segments'])) for t in B0['tracks'] if not is_bgm(t)]   # BGM 은 조각 수가 달라질 수 있음
    cnt1 = [(t.get('name') or t['type'], len(t['segments'])) for t in D['tracks'] if not is_bgm(t)]
    res['b_segments'] = dict(base=cnt0, new=cnt1, ok=cnt0 == cnt1)
    m0, m1 = main_track(B0)['segments'], main_track(D)['segments']
    bad = []
    for s0, s1 in zip(m0, m1):
        a0, d0 = tr(s0); a1, d1 = tr(s1)
        if s0['source_timerange']['start'] != s1['source_timerange']['start'] or abs(a1 - f(a0)) > 2e-6 \
                or abs(d1 - (f(a0 + d0) - f(a0))) > 2e-6:
            bad.append(round(a0, 3))
    res['c_main'] = dict(n=len(m1), bad=bad, ok=len(m0) == len(m1) and not bad)
    mt0, mt1 = main_track(B0), main_track(D)
    worst, bad, checked = 0.0, [], 0
    for t0, t1 in zip(B0['tracks'], D['tracks']):
        if t0 is mt0 or is_bgm(t0): continue
        for s0, s1 in zip(t0['segments'], t1['segments']):
            a0 = tr(s0)[0]
            p0 = src_of_edit(B0, s0['target_timerange']['start'], foot)
            p1 = src_of_edit(D, s1['target_timerange']['start'], foot)
            checked += 1
            if (p0 is None) != (p1 is None):
                bad.append(dict(track=t0.get('name'), at=round(a0, 3), base=p0, new=p1)); continue
            if p0 is None: continue
            e = abs(p0 - p1); worst = max(worst, e)
            if e >= TOL_SRC: bad.append(dict(track=t0.get('name'), at=round(a0, 3), base=round(p0, 3), new=round(p1, 3)))
    res['d_source_at_start'] = dict(checked=checked, worst_sec=round(worst, 4), bad=bad[:20], n_bad=len(bad), ok=not bad)
    spd = {m['id']: m for m in D['materials'].get('speeds', [])}
    bad, n = [], 0
    for t in D['tracks']:
        if t['type'] != 'video': continue
        for s in t['segments']:
            a = tr(s)[0]
            want = 1.0 if (t is mt1 and any(abs(a - f(x0)) < 1e-3 for x0, _ in fixed)) else k
            refs = [spd[r] for r in s.get('extra_material_refs', []) if r in spd]
            n += 1
            if abs((s.get('speed') or 1.0) - want) > 1e-9 or not refs or any(abs(r['speed'] - want) > 1e-9 for r in refs) \
                    or (want != 1.0 and s.get('is_tone_modify') is not False):
                bad.append(round(a, 3))
    res['e_speed_materials'] = dict(video_segments=n, bad=bad, ok=not bad)
    paths = {m.get('path') for m in D['materials'].get('videos', []) + D['materials'].get('audios', []) if m.get('path')}
    missing = sorted(p for p in paths if not Path(p).exists())
    res['f_media_missing'] = dict(files=len(paths), missing=missing, ok=not missing)
    # 오디오: 효과음은 시작만 옮김, BGM 은 원래 빠르기로 다시 깔림
    bad = []
    for t0, t1 in zip(B0['tracks'], D['tracks']):
        if t0['type'] != 'audio' or is_bgm(t0): continue
        for s0, s1 in zip(t0['segments'], t1['segments']):
            a0, d0 = tr(s0); a1, d1 = tr(s1)
            if abs(d1 - d0) > 2e-6 or s0['source_timerange'] != s1['source_timerange'] or abs(a1 - f(a0)) > 2e-6 \
                    or abs((s1.get('speed') or 1.0) - (s0.get('speed') or 1.0)) > 1e-9:
                bad.append(dict(track=t0.get('name'), at=round(a0, 3)))
    nsfx = sum(len(t['segments']) for t in D['tracks'] if t['type'] == 'audio' and not is_bgm(t))
    res['g_sfx'] = dict(segments=nsfx, bad=bad, ok=not bad)
    r0, r1 = bgm_runs(B0), bgm_runs(D)
    bad = []
    for t in D['tracks']:
        if not is_bgm(t): continue
        for s in t['segments']:
            a, d = tr(s)
            if abs((s.get('speed') or 1.0) - 1.0) > 1e-9 or abs(s['target_timerange']['duration'] - s['source_timerange']['duration']) > 2:
                bad.append(dict(at=round(a, 3), why='속도 1.0·길이=원본 아님'))
            if any(a < f(x0) + (x1 - x0) - 1e-3 and a + d > f(x0) + 1e-3 for x0, x1 in fixed):
                bad.append(dict(at=round(a, 3), why='범퍼·CTA 위'))
    if len(r0) != len(r1):
        bad.append(dict(why=f'구간 수 {len(r0)} → {len(r1)}'))
    for x, y in zip(r0, r1):
        if abs(f(x['start']) - y['start']) > 0.05 or abs(f(x['end']) - y['end']) > 0.05:
            bad.append(dict(why='구간 어긋남', base=[round(x['start'], 3), round(x['end'], 3)], new=[round(y['start'], 3), round(y['end'], 3)]))
    segs = sorted((s for t in D['tracks'] if is_bgm(t) for s in t['segments']), key=lambda s: s['target_timerange']['start'])
    for p, q in zip(segs, segs[1:]):                       # 같은 구간 안 이음매: 빈틈·겹침 없음(구간 사이 빈칸은 runs 로 이미 비교)
        gap = q['target_timerange']['start'] - (p['target_timerange']['start'] + p['target_timerange']['duration'])
        if gap < -2:
            bad.append(dict(at=round(tr(q)[0], 3), why=f'겹침 {gap / US:.4f}초'))
    res['h_bgm'] = dict(base_runs=[[round(x['start'], 3), round(x['end'], 3)] for x in r0],
                        new_runs=[[round(y['start'], 3), round(y['end'], 3)] for y in r1], clips=len(segs), bad=bad, ok=not bad)
    res['ok'] = all(v['ok'] for v in res.values() if isinstance(v, dict))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--video', required=True, help='영상 폴더')
    ap.add_argument('--base', required=True, help='바탕 CapCut 프로젝트 이름(읽기만 함)')
    ap.add_argument('--name', required=True, help='새 프로젝트 이름')
    ap.add_argument('--speed', type=float, default=1.1)
    ap.add_argument('--footage', help='촬영본 파일명 조각(기본: edit_state inputs.footage 의 파일 이름)')
    ap.add_argument('--out', help='출력 폴더(기본: <편집 폴더>/08_speed)')
    ap.add_argument('--capcut-dir')
    ap.add_argument('--install', action='store_true', help='검증을 통과하면 CapCut 목록에 등록(CapCut을 끈 상태에서만)')
    a = ap.parse_args()

    W = edit_dir(a.video)
    foot = a.footage
    if not foot:
        st = C.read_json(W / 'edit_state.json')
        fp = (st.get('inputs') or {}).get('footage')
        if not fp: C.die('edit_state.json 에 inputs.footage 가 없습니다. --footage 로 알려 주세요.')
        foot = Path(fp).stem
    cc = C.find_capcut_dir(a.capcut_dir)
    base_dir = C.resolve_project(a.base, a.capcut_dir).resolve()      # 이름 또는 폴더 경로(스테이징 폴더도 됨)
    if not (base_dir / 'draft_info.json').exists(): C.die(f'바탕 프로젝트가 없습니다: {base_dir}')
    OUT = Path(a.out).resolve() if a.out else W / '08_speed'
    if Path(cc).resolve() in OUT.parents or OUT == Path(cc).resolve(): C.die('[거부] 출력 폴더가 CapCut 프로젝트 폴더 안입니다.')
    stage = OUT / a.name
    if stage.exists(): C.die(f'스테이징 폴더가 이미 있습니다(덮어쓰지 않음): {stage}')
    OUT.mkdir(parents=True, exist_ok=True)
    B0 = json.loads((base_dir / 'draft_info.json').read_text('utf-8'))
    if not any(is_foot(B0, s, foot) for s in main_track(B0)['segments']):
        C.die(f'바탕 메인 트랙에 촬영본 조각 "{foot}" 이 들어간 클립이 없습니다.')

    spec = OUT / f'{a.name}_spec.json'
    spec.write_text(json.dumps(dict(_note=f'{a.name}: {a.base} 전체 {a.speed}배속(speed_version.py)', items=[]), ensure_ascii=False))
    r = subprocess.run([PY, str(SK / 'capcut_augment.py'), '--base', str(base_dir), '--name', a.name, '--spec', str(spec),
                        '--staging', str(OUT), '--loudness-off'] + (['--capcut-dir', a.capcut_dir] if a.capcut_dir else []),
                       capture_output=True, text=True)
    print('\n'.join(l for l in r.stdout.splitlines() if 'CapCut 미디어' not in l)[-1500:])
    if r.returncode:
        print(r.stderr[-2000:]); C.die('capcut_augment 실패')

    D = json.loads((stage / 'draft_info.json').read_text('utf-8'))
    # 스테이징 직후(배속 전) 구조가 바탕과 같은지부터
    if [len(t['segments']) for t in D['tracks']] != [len(t['segments']) for t in B0['tracks']]:
        C.die('스테이징 복사본의 트랙 구성이 바탕과 다릅니다. 멈춥니다.')
    f, n_sp, bum, bgm = apply_speed(D, a.speed, foot)
    save_draft(stage, D)
    mp = stage / 'draft_meta_info.json'
    if mp.exists():
        meta = C.read_json(mp)
        if 'tm_duration' in meta:
            meta['tm_duration'] = D['duration']; C.write_json(mp, meta, compact=True)

    chk = verify(B0, D, f, a.speed, foot, bum)
    fixed, names = bum
    rep = dict(video=a.video, base=a.base, name=a.name, speed=a.speed, footage=foot, segments_sped=n_sp,
               bumper=[dict(file=nm, orig=[round(x0, 3), round(x1, 3)], new=[round(f(x0), 3), round(f(x0) + (x1 - x0), 3)]) for (x0, x1), nm in zip(fixed, names)], bumper_note='범퍼·CTA 등 메인 트랙의 촬영본 아닌 클립은 원래 속도 유지',
               duration=round(D['duration'] / US, 3), staging=str(stage.relative_to(ROOT) if ROOT in stage.parents else stage), bgm=bgm, checks=chk)
    rp = OUT / f'{a.name}_배속.json'
    rp.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print(json.dumps({k: (v if k not in ('checks', 'bgm') else (dict(base_runs=v['base_runs'], new_clips=len(v['new_clips'])) if k == 'bgm' else {kk: vv.get('ok') if isinstance(vv, dict) else vv for kk, vv in v.items()}))
                      for k, v in rep.items()}, ensure_ascii=False, indent=1))
    print(f'보고: {rp.relative_to(ROOT) if ROOT in rp.parents else rp}')
    if not chk['ok']:
        C.die('검증 실패 — 등록하지 않습니다. 보고 JSON의 checks 를 보세요.')
    if a.install:
        sys.exit(B.install(stage, cc, a.name, OUT / 'backups'))
    print('스테이징·검증만 함. 등록은 --install')


if __name__ == '__main__':
    main()
