"""편집 진행 상황(autopilot): 영상별 상태 파일을 읽고 지금 단계·다음 할 일·사용자에게 물을 것을 알려 줍니다.

claude-edit 스킬 references/pipeline.md 의 S0~S5 와 게이트 A·B·C 를 따른다. 이 도구는 기록과 안내만 한다.
CapCut 등록·렌더는 하지 않고, 사용자 CapCut 프로젝트는 수정 시각만 읽는다.

상태 파일: <영상 폴더>/편집/edit_state.json(tools/topic_paths.py 가 정함). 경로는 작업 폴더 기준, 시각은 로컬 'YYYY-MM-DDTHH:MM:SS'
  {"schema": "claude-edit/edit_state@1",
   "video": "<영상 이름>",                          ← CapCut 프로젝트 이름 앞머리(이 이름으로 시작하는 프로젝트만 본다)
   "folder": "<영상 폴더>", "created": "…", "updated": "…",
   "inputs": {"footage", "script", "template", "crop", "rotate", "bumper_src", "sources"},   ← 모르면 null(원고는 선택)
   "stage": "S2",                                   ← 지금 단계(S0~S5)
   "stages": {"S0": {"status": "todo|doing|done", "at", "note"}, … "S5": {…}},
   "gates": {"A": {"status": "pending|asked|passed", "at", "note"}, "B": {…}, "C": {…}},   ← A는 S1 뒤, B는 S2 뒤, C는 S4 뒤
   "versions": [{"name": "<영상 이름>_초벌_v004", "registered": "…", "base": "<영상 이름>_초벌_v003", "base_saved": "…",
                 "tool": "capcut_augment.py", "length": "6:56", "draft_mtime": "…", "note": "…"}],   ← 클로드가 등록한 것만
   "decisions": {"key_content": {"url", "title"}, "video_type": "<해시태그 표의 행>"},
   "final": {"project", "saved", "export", "uploaded": true, "description", "pinned", "retro"},
   "log": [{"at", "what"}]}
  사용자 편집본 판정: draft_info.json 수정 시각이 클로드 등록 시각(또는 등록 때 잰 draft_mtime)보다 60초 넘게 늦으면 사용자 편집본.
  CapCut으로 열기만 해도 시각이 바뀔 수 있으니 애매하면 바탕 이름·시각을 보여 주고 묻는다. 기록이 없는 프로젝트는 사용자 것으로 본다.

명령(작업 폴더에서. --video 는 영상 폴더):
  init      --video V [--name <영상 이름>] [--footage …] [--script …] [--template <CapCut 템플릿>] [--crop …] [--rotate …]
  status    --video V                    지금 단계, 다음 할 일과 명령, 사용자에게 물을 것, 바탕(최신 사용자 편집본)
  set       --video V <키> <값> [--note …] [--add]
            키는 점 경로(gates.A.status) 또는 줄임말: stage · S0~S5 · A·B·C · key_url · key_title · type(해시태그 행)
            · uploaded · export · final · footage · script · template · crop · rotate · bumper_src · sources
            'set stage S3' 은 앞 단계를 완료로, S3 을 진행 중으로 바꾼다. 값은 JSON(숫자·true·null)으로 읽히면 그 값, 아니면 글자.
  register  --video V <버전> --base <바탕> [--tool capcut_augment.py] [--length 6:56] [--at ISO] [--note …]
            클로드가 CapCut에 등록한 버전을 기록한다(등록 자체는 하지 않음). <버전>은 전체 이름 또는 'v007'.
  latest    --video V [--quiet]          이 영상 이름으로 시작하는 CapCut 프로젝트 중 클로드 등록 뒤에 수정된 가장 최근 사용자 편집본

예(작업 폴더에서):
  python <스킬 폴더>/claude-edit/scripts/autopilot.py init --video 내영상 --footage 내영상/촬영본.mp4 --template "내 템플릿"
  python <스킬 폴더>/claude-edit/scripts/autopilot.py status --video 내영상
"""
import argparse
import datetime as dt
import json
import re
import os
import sys
import unicodedata
from pathlib import Path

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
ROOT = Path(os.environ.get('PROJECT_ROOT') or os.getcwd()).resolve()     # 프로젝트 루트(PROJECT_ROOT 또는 작업 폴더)
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / 'smartdaddy-video-edit' / 'scripts'), str(ROOT / 'tools')]
import _common as C  # noqa: E402
import topic_paths as TP  # noqa: E402   영상 폴더 안 단계 폴더(편집·화면자료·캡컷_가져오기 …)

SCHEMA = 'claude-edit/edit_state@1'
STAGES = ['S0', 'S1', 'S2', 'S3', 'S4', 'S5']
TITLE = {'S0': '준비', 'S1': '러프컷', 'S2': '덧입히기 계획', 'S3': '모션 카드·목차 전환·소리', 'S4': '조립', 'S5': '마감'}
GATE_AFTER = {'S1': 'A', 'S2': 'B', 'S4': 'C'}
STAGE_ST = ('todo', 'doing', 'done')
GATE_ST = ('pending', 'asked', 'passed')
KO = {'todo': '시작 전', 'doing': '진행 중', 'done': '완료', 'pending': '대기', 'asked': '물어봄', 'passed': '통과'}
TOL = 60            # 등록 뒤 이 초 안의 수정은 등록 때 쓴 것으로 본다
ALIAS = {'A': 'gates.A.status', 'B': 'gates.B.status', 'C': 'gates.C.status',
         **{s: f'stages.{s}.status' for s in STAGES},
         'key_url': 'decisions.key_content.url', 'key_title': 'decisions.key_content.title',
         'type': 'decisions.video_type', 'uploaded': 'final.uploaded', 'export': 'final.export',
         'final': 'final.project',
         **{k: f'inputs.{k}' for k in ('footage', 'script', 'template', 'crop', 'rotate', 'bumper_src', 'thumbnails', 'sources')}}

# 단계별 할 일: (설명, 명령 또는 None). 명령의 {…}은 상태 값으로 채운다(pipeline.md 표기와 같음).
GUIDE = {
    'S0': [('입력 확인: 영상 파일(필수), 원고(선택), 채널 링크 또는 소개 문서. profile.md 가 없으면 references/onboarding.md 로 만든다', None),
           ('모션 카드를 쓰면(profile.md motion) 목업 컨펌: 키 컬러 × 스타일 조합 → mockups.html 에서 고른 것을 profile.md 에',
            '{PY} {E}/mockups.py --colors "<#색1,#색2>" --styles dark,light --topic "<주제>" --out {W}/목업/'),
           ('화면 맞춤: grid.jpg로 인물 중심을 정하고 --center-x 로 다시 돌려 --crop·--rotate 값을 얻는다',
            '{PY} {S}/frame_check.py {footage} --out {W}/00_frame'),
           ('HANDOFF.md 시작: 사용자 지시·목표 길이·profile.md 의 취향(템포·강조·효과음·배경음·목차 전환)·CapCut 템플릿 이름', None),
           ('값 기록(영상·원고·템플릿·크롭)', '{PY} {E}/autopilot.py set --video {V} crop <값>'),
           ('끝나면', '{PY} {E}/autopilot.py set --video {V} stage S1')],
    'S1': [('러프컷 한 번에(받아쓰기 → 컷 계획 → 원고 대조 → 쉼 줄이기[profile.md cut_tempo] → 경계 → 다시 듣기 → 편집본 자막 → 조립). '
            '재테이크 판독 JSON이 없으면 요청서를 쓰고 멈춘다',
            '{PY} {E}/rough_cut.py --video {V} --media {footage} [--script {script}] --template "{template}" --crop {crop} --rotate {rotate} --prompt "<고유명사>"'),
           ('재테이크 판독(하위 에이전트) → 편집/03_review/retake_review.json, high·medium 자동, low는 게이트 A 표', None),
           ('이어서 조립(등록은 사용자 허락 + CapCut 꺼짐일 때만 --install)', '{PY} {E}/rough_cut.py --video {V} … --from tighten'),
           ('등록했으면 기록', '{PY} {E}/autopilot.py register --video {V} {next} --base "템플릿 {template}" --tool capcut_build.py'),
           ('끝나면', '{PY} {E}/autopilot.py set --video {V} S1 done')],
    'S2': [('바탕 고르기: 아래 "바탕" 줄(latest). 보고에 "바탕: <이름>(<시각>)"', '{PY} {E}/autopilot.py latest --video {V}'),
           ('강조 후보(profile.md emphasis 가 안 씀이면 건너뜀)', '{PY} {S}/emphasis_candidates.py "{base}" --out {W}/강조_후보.csv'),
           ('모션 카드 목록(profile.md motion 이 안 씀이면 건너뜀) → {W}/화면자료/모션카드_v1/cards.json(templates/motion_cards.example.json 형식)', None),
           ('목차 전환 목록(profile.md chapter_transition 이 안 씀이면 건너뜀): 장 번호·제목·원본 초 → {W}/화면자료/챕터전환/chapters.json', None),
           ('효과음·배경음(profile.md sfx·bgm): 쓸 소리와 배경음 파일 확인', None),
           ('끝나면', '{PY} {E}/autopilot.py set --video {V} S2 done')],
    'S3': [('모션 카드 렌더(스타일·색은 profile.md motion_style·brand_color_1)', '{PY} {E}/motion_cards.py {W}/화면자료/모션카드_v1/cards.json'),
           ('목차 전환 렌더(키 컬러는 profile.md brand_color_1)', '{PY} {E}/chapter_frost.py {W}/화면자료/챕터전환/chapters.json --variants A'),
           ('효과음 폴더가 없으면 기본음 만들기(profile.md sfx_dir, 기본 sfx)', '{PY} {S}/make_sfx.py sfx'),
           ('끝나면', '{PY} {E}/autopilot.py set --video {V} stage S4')],
    'S4': [('강조 자막·효과음·배경음 → 새 스테이징', '{PY} {S}/emphasis.py --project "{base}" --spec {W}/강조.json --out {W}/02_cut/capcut_staging/{next} --audio-template "{template}"'),
           ('모션 카드·목차 전환 MOV 얹기(motion_cards.py·chapter_frost.py 가 만든 augment_items.json)',
            '{PY} {S}/capcut_augment.py --base "{base}" --name "{next}" --spec {W}/화면자료/챕터전환/augment_items.json '
            '--staging {W}/02_cut/capcut_staging --loudness-off'),
           ('미리보기 확인', '{PY} {S}/preview.py "<스테이징 폴더>" {W}/preview.mp4 --h 540'),
           ('등록(사용자 허락 + CapCut 꺼짐, 한 세션만) 뒤 기록', '{PY} {E}/autopilot.py register --video {V} {next} --base "{base}" --tool capcut_augment.py'),
           ('끝나면', '{PY} {E}/autopilot.py set --video {V} S4 done')],
    'S5': [('음량(사용자가 클립별 음량 정규화를 끄고 내보낸 파일)', '{PY} {S}/master_audio.py <내보낸.mp4> --out <내보낸>_음량.mp4'),
           ('최종 점검', '{PY} {S}/verify_render.py <파일>'),
           ('업로드 묶음(챕터·설명란·고정댓글 초안, 해시태그는 --type 을 줄 때만)',
            '{PY} {E}/upload_pack.py "{final}" --video {V} [--type {vtype}] [--key-url {key_url}]'),
           ('챕터 실제 발화 기준: youtube-chapter-timestamps 스킬(내보낸 파일) → upload_pack.py --chapters 로 검사', None),
           ('끝나면', '{PY} {E}/autopilot.py set --video {V} S5 done')],
}
GATE = {
    'A': dict(do=['낮은 신뢰도 컷을 표(원본 초·대사·자를 이유·남길 이유)로 보여 주고 한 번에 정한다',
                  '반영해 새 이름으로 다시 조립·등록 → "{next}을 등록했습니다. 지루한 구간을 다듬어 저장하시면 그 편집본 위에 강조·목차 전환을 얹겠습니다."',
                  '사용자가 "다듬었다"고 하면 통과 → S2'],
              ask=['낮은 신뢰도 컷 표(남길지·자를지)', 'CapCut에서 내용 컷을 마치고 저장했나요?'],
              done='{PY} {E}/autopilot.py set --video {V} A passed --note "<사용자 답 요약>"'),
    'B': dict(do=['강조 목록(유형·문장·효과음), 모션 카드 목록(종류·글자·시각), 목차 전환 목록(번호·제목·시각)을 표로 한 번에 보여 준다'],
              ask=['강조 목록 승인', '모션 카드 목록 승인', '목차 전환 목록 승인', '배경음 파일(쓸 때)'],
              done='{PY} {E}/autopilot.py set --video {V} B passed --note "<승인 내용>"'),
    'C': dict(do=['바탕 이름·시각, 새 버전 이름, 넣은 것·뺀 것(사용자가 자른 대사의 자료), 미리보기를 보여 준다'],
              ask=['CapCut에서 확인하고 전환 효과 등을 넣어 마무리했나요?',
                   '클립별 음량 정규화를 끄고 내보낸 파일 경로를 알려 주세요'],
              done='{PY} {E}/autopilot.py set --video {V} C passed --note "<마무리 프로젝트·시각>"'),
}


def now():
    return dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


def iso(t):
    return dt.datetime.fromtimestamp(t).strftime('%Y-%m-%dT%H:%M:%S')


def ts(s):
    return dt.datetime.fromisoformat(s).timestamp() if s else None


def hm(s):
    return s.replace('T', ' ')[:16] if s else '—'


def nfc(s):
    return unicodedata.normalize('NFC', s or '')


def rel(p):
    p = Path(p).expanduser()
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def state_path(video):
    V = Path(video).expanduser()
    if TP.TOPIC_ID.match(str(video)):
        try:
            V = TP.topic_folder(str(video), ROOT)
        except ValueError as e:
            C.die(str(e))
    elif not V.is_absolute():
        V = (Path.cwd() / V) if (Path.cwd() / V).is_dir() else ROOT / V
    if not V.is_dir():
        C.die(f'영상 폴더가 없습니다: {video}')
    return V.resolve(), TP.part(V.resolve(), 'edit') / 'edit_state.json'


def load(video):
    V, sp = state_path(video)
    if not sp.exists():
        C.die(f'{rel(sp)} 이 없습니다. 먼저: autopilot.py init --video {rel(V)}')
    st = C.read_json(sp)
    if st.get('schema') != SCHEMA:
        print(f"[주의] 상태 파일 형식이 {st.get('schema')} 입니다(이 도구는 {SCHEMA}).")
    return V, sp, st


def save(sp, st, what=None):
    st['updated'] = now()
    if what:
        st.setdefault('log', []).append(dict(at=st['updated'], what=what))
    C.write_json(sp, st)


def new_state(V, name, a):
    return {'schema': SCHEMA, 'video': name, 'folder': rel(V), 'created': now(), 'updated': now(),
            'inputs': dict(footage=rel(a.footage) if a.footage else None, script=rel(a.script) if a.script else None,
                           template=a.template, crop=a.crop, rotate=a.rotate, bumper_src=None, thumbnails=None, sources=None),
            'stage': 'S0',
            'stages': {s: dict(status='doing' if s == 'S0' else 'todo', at=None, note=None) for s in STAGES},
            'gates': {g: dict(status='pending', at=None, note=None) for g in 'ABC'},
            'versions': [],
            'decisions': dict(credit_cap=None, character=None, key_content=dict(url=None, title=None), video_type=None),
            'credits': dict(used=0, log=[]),
            'final': dict(project=None, saved=None, export=None, uploaded=False, description=None, pinned=None, retro=None),
            'log': []}


def next_version(st):
    vs = [v['name'] for v in st.get('versions', [])]
    nums = [int(m.group(1)) for v in vs for m in [re.search(r'v(\d+)$', v)] if m]
    prefix = re.sub(r'v\d+$', '', vs[-1]) if vs and re.search(r'v\d+$', vs[-1]) else f"{st['video']}_초벌_"
    return f'{prefix}v{(max(nums) if nums else 0) + 1:03d}'


# ── CapCut 프로젝트 판정 ──────────────────────────────
def scan(st, cc_arg=None):
    cc = C.find_capcut_dir(cc_arg, required=False)
    if not cc:
        return None, []
    reg = {nfc(v['name']): v for v in st.get('versions', [])}
    rows = []
    for p in sorted(cc.iterdir()):
        name = nfc(p.name)
        if not p.is_dir() or not name.startswith(st['video']):
            continue
        f = C.draft_file(p)
        if not f:
            continue
        mt = f.stat().st_mtime
        v = reg.get(name)
        if v:
            base_t = max(ts(v.get('registered')) or 0, ts(v.get('draft_mtime')) or 0)
            user = mt > base_t + TOL
            kind = '등록 뒤 저장됨 → 사용자 편집본' if user else '클로드 등록 그대로'
        else:
            user, kind = True, '등록 기록 없음 → 사용자 프로젝트로 봄'
        rows.append(dict(name=name, mtime=mt, registered=v.get('registered') if v else None, user=user, kind=kind))
    return cc, rows


def pick_latest(st, rows):
    edited = [r for r in rows if r['user']]
    latest = max(edited, key=lambda r: r['mtime']) if edited else None
    last_reg = max((r for r in rows if r['registered']), key=lambda r: ts(r['registered']), default=None)
    note = ''
    if latest and last_reg and ts(last_reg['registered']) > latest['mtime']:
        note = (f"마지막 등록본 {last_reg['name']}({hm(last_reg['registered'])}) 뒤로는 사용자 저장이 없다 — "
                '사용자가 아직 다듬지 않았으면 그 등록본이 바탕이다. 애매하면 묻는다')
    elif not latest and last_reg:
        note = f"사용자 편집본이 없다 — 마지막 등록본 {last_reg['name']}({hm(last_reg['registered'])})이 그대로다"
    return latest, note


def fill(s, st, V, latest):
    i, d = st.get('inputs', {}), st.get('decisions', {})
    vals = dict(PY='python', S='<스킬 폴더>/smartdaddy-video-edit/scripts', E='<스킬 폴더>/claude-edit/scripts',
                V=rel(V), W=rel(TP.part(V, 'edit')), footage=i.get('footage') or '<촬영본>', script=i.get('script') or '<원고>',
                template=i.get('template') or '<템플릿>', crop=i.get('crop') or '<크롭>',
                rotate=i.get('rotate') if i.get('rotate') is not None else '0', bumper_src=i.get('bumper_src') or '<원본 초>',
                next=next_version(st), base=latest['name'] if latest else '<사용자 최신 프로젝트>',
                final=(st.get('final') or {}).get('project') or (latest['name'] if latest else '<최종 프로젝트>'),
                key_url=(d.get('key_content') or {}).get('url') or '<관련 영상 URL>', vtype=d.get('video_type') or '<영상 종류>',
                sources=i.get('sources') or '{W}/<최신>_자료목록.md'.format(W=rel(TP.part(V, 'edit'))))
    return s.format(**vals)


def missing(st, stage):
    """그 단계 전에 정해 둬야 하는데 비어 있는 값(원고·범퍼·관련 영상은 선택)."""
    i = st.get('inputs', {})
    need = []
    order = STAGES.index(stage)
    if order <= 1:
        need += [(k, f'inputs.{k}') for k in ('footage', 'template') if not i.get(k)]
    if order == 1 and i.get('crop') in (None, ''):
        need.append(('crop', 'inputs.crop'))
    return need


# ── 명령 ─────────────────────────────────────────────
def cmd_init(a):
    V, sp = state_path(a.video)
    if sp.exists():
        C.die(f'{rel(sp)} 이 이미 있습니다. status·set·register 를 쓰세요(덮어쓰지 않음).')
    name = nfc(a.name or TP.display_name(V))
    st = new_state(V, name, a)
    save(sp, st, f'init (영상 {name})')
    print(f'만듦: {rel(sp)} · 영상 이름 "{name}"(CapCut 프로젝트 앞머리) · 단계 S0 진행 중')
    if (TP.part(V, 'edit') / 'HANDOFF.md').exists():
        print('[안내] HANDOFF.md 가 있습니다. 진행 기록을 읽고 set·register 로 상태를 맞추세요.')


def cmd_status(a):
    V, sp, st = load(a.video)
    cc, rows = scan(st, a.capcut_dir)
    latest, lnote = pick_latest(st, rows)
    cur = st.get('stage', 'S0')
    cs = st['stages'][cur]['status']
    gates, fin = st['gates'], st.get('final', {})
    gate = GATE_AFTER.get(cur)
    todo, ask, done_cmd, guide_stage = [], [], None, None
    if cur == 'S5' and cs == 'done':
        if fin.get('uploaded'):
            head = 'S5 완료(업로드됨)'
            if fin.get('retro'):
                todo.append(('이 영상은 끝났다. 새 영상은 그 영상 폴더에서 init 부터', None))
            else:
                todo.append(('회고: 마무리 프로젝트와 마지막 등록본을 비교(뺀 자료·더한 소리) → preferences 에 넣을지 묻는다', None))
                todo.append(('기록', '{PY} {E}/autopilot.py set --video {V} final.retro <회고 문서 경로>'))
        else:
            head = 'S5 완료(업로드 묶음 준비됨, 업로드 전)'
            todo.append(('사용자가 업로드하면 기록', '{PY} {E}/autopilot.py set --video {V} uploaded true'))
            ask.append('업로드했나요? (제목·썸네일 선택, AI 고지 설정 확인)')
    elif cs == 'done' and gate and gates[gate]['status'] != 'passed':
        head = f"{cur} {TITLE[cur]} 완료 → 게이트 {gate} {KO[gates[gate]['status']]}"
        todo = [(x, None) for x in GATE[gate]['do']]
        ask += GATE[gate]['ask']
        done_cmd = GATE[gate]['done']
    elif cs == 'done':
        nxt = STAGES[STAGES.index(cur) + 1]
        head = f'{cur} {TITLE[cur]} 완료 → 다음 {nxt} {TITLE[nxt]}'
        todo = [('시작 기록', '{PY} {E}/autopilot.py set --video {V} stage ' + nxt)] + GUIDE[nxt]
        guide_stage = nxt
    else:
        head = f'{cur} {TITLE[cur]} {KO[cs]}'
        todo = GUIDE[cur]
        guide_stage = cur
    for k, key in (missing(st, guide_stage) if guide_stage else []):
        ask.append(f'{k} 값이 없다 → set {key} <값>')
    if guide_stage == 'S3' and gates['B']['status'] != 'passed':
        ask.append('게이트 B(강조·모션 카드·목차 전환 목록) 승인 전에는 렌더·조립하지 않는다')

    print(f"영상: {st['video']} ({st['folder']}) · 상태 파일 {rel(sp)} · 갱신 {hm(st.get('updated'))}")
    print(f'지금: {head}')
    print('단계: ' + ' '.join(f"{s}{'✓' if st['stages'][s]['status'] == 'done' else ('…' if st['stages'][s]['status'] == 'doing' else '·')}" for s in STAGES)
          + ' | 게이트: ' + ' '.join(f"{g} {KO[gates[g]['status']]}" for g in 'ABC'))
    vs = st.get('versions', [])
    if vs:
        lv = vs[-1]
        print(f"버전: {len(vs)}개 등록 · 마지막 {lv['name']}({hm(lv.get('registered'))}, 바탕 {lv.get('base') or '—'}, {lv.get('tool') or '—'})")
    if cc is None:
        print('바탕: CapCut 프로젝트 폴더를 찾지 못함')
    elif latest:
        print(f"바탕: {latest['name']}({hm(iso(latest['mtime']))}) — {latest['kind']}")
    else:
        print('바탕: 사용자 편집본 없음')
    if lnote:
        print('  [주의] ' + lnote)
    d = st.get('decisions', {})
    kc = d.get('key_content') or {}
    print(f"결정: 관련 영상 {kc.get('url') or '미정'}" + (f" 「{kc['title']}」" if kc.get('title') else ''))
    if fin.get('project') or fin.get('export'):
        print(f"마무리: {fin.get('project') or '—'}({hm(fin.get('saved'))}) · 내보낸 파일 {fin.get('export') or '—'}")
        fr = next((r for r in rows if r['name'] == nfc(fin.get('project'))), None)
        if fr and fin.get('saved') and fr['mtime'] > ts(fin['saved']) + TOL:
            print(f"  [주의] 마무리 기록 뒤에 다시 저장됨({hm(iso(fr['mtime']))}) — CapCut에서 열었거나 고쳤다. "
                  '컷이 바뀌었으면 챕터·출처를 다시 뽑는다')
    print('\n다음 할 일:')
    for desc, c in todo:
        print(f'  - {fill(desc, st, V, latest)}')
        if c:
            print(f'      {fill(c, st, V, latest)}')
    if done_cmd:
        print(f'  - 통과하면: {fill(done_cmd, st, V, latest)}')
    print('\n사용자에게 물을 것:' + ('' if ask else ' 없음'))
    for q in ask:
        print(f'  - {fill(q, st, V, latest)}')


def parse_value(v):
    try:
        return json.loads(v)
    except ValueError:
        return v


def cmd_set(a):
    V, sp, st = load(a.video)
    key = ALIAS.get(a.key, a.key)
    val = parse_value(a.value)
    if key == 'stage':
        if val not in STAGES:
            C.die(f'stage 는 {" ".join(STAGES)} 중 하나입니다.')
        i = STAGES.index(val)
        back = i < STAGES.index(st.get('stage', 'S0'))
        for s in STAGES[:i]:
            if st['stages'][s]['status'] != 'done':
                st['stages'][s].update(status='done', at=now())
        st['stages'][val].update(status='doing', at=now())
        reset = []
        if back:        # 되돌아가면(예: 새 시각 자료 회차) 뒤 단계와 그 뒤 게이트를 다시 한다
            for s in STAGES[i + 1:]:
                st['stages'][s].update(status='todo', at=now())
            for s, g in GATE_AFTER.items():
                if STAGES.index(s) >= i and st['gates'][g]['status'] != 'pending':
                    st['gates'][g].update(status='pending', at=now())
                    reset.append(g)
        st['stage'] = val
        if a.note:
            st['stages'][val]['note'] = a.note
        save(sp, st, f'stage → {val}' + (' (되돌림: 뒤 단계 시작 전' + (f", 게이트 {'·'.join(reset)} 대기" if reset else '') + ')' if back else '')
             + (f' ({a.note})' if a.note else ''))
        print(f'단계: {val} {TITLE[val]} 진행 중' + (f" · 뒤 단계를 시작 전으로{', 게이트 ' + '·'.join(reset) + ' 대기로' if reset else ''} 되돌림" if back else ''))
        return
    parts = key.split('.')
    if parts[0] == 'stages' and parts[-1] == 'status' and val not in STAGE_ST:
        C.die(f'단계 상태는 {"|".join(STAGE_ST)} 입니다.')
    if parts[0] == 'gates' and parts[-1] == 'status' and val not in GATE_ST:
        C.die(f'게이트 상태는 {"|".join(GATE_ST)} 입니다.')
    node = st
    for p in parts[:-1]:
        if not isinstance(node.get(p), dict):
            node[p] = {}
        node = node[p]
    old = node.get(parts[-1])
    if a.add:
        if not isinstance(val, (int, float)):
            C.die('--add 는 숫자 값에만 씁니다.')
        val = round((old or 0) + val, 3)
        if key == 'credits.used':
            st['credits'].setdefault('log', []).append(dict(at=now(), amount=parse_value(a.value), what=a.note or ''))
    node[parts[-1]] = val
    if parts[-1] == 'status':
        node['at'] = now()
        if a.note:
            node['note'] = a.note
    save(sp, st, f'{key}: {json.dumps(old, ensure_ascii=False)} → {json.dumps(val, ensure_ascii=False)}' + (f' ({a.note})' if a.note else ''))
    print(f'{key} = {json.dumps(val, ensure_ascii=False)}')


def cmd_register(a):
    V, sp, st = load(a.video)
    vs = st.setdefault('versions', [])
    name = nfc(a.version)
    if re.fullmatch(r'v\d+', name):
        prefix = re.sub(r'v\d+$', '', vs[-1]['name']) if vs and re.search(r'v\d+$', vs[-1]['name']) else f"{st['video']}_초벌_"
        name = prefix + name
    cc = C.find_capcut_dir(a.capcut_dir, required=False)
    proj = cc / name if cc else None
    rec = dict(name=name, registered=a.at or now(), base=a.base, base_saved=a.base_saved, tool=a.tool,
               length=a.length, draft_mtime=None, note=a.note)
    if proj and C.draft_file(proj):
        if not a.at:
            rec['draft_mtime'] = iso(C.draft_file(proj).stat().st_mtime)
    else:
        print(f'[주의] CapCut 목록에 "{name}"이(가) 아직 없습니다(스테이징만 했거나 이름이 다름). 기록은 남깁니다.')
    bdir = cc / a.base if cc and a.base else None
    if bdir and C.draft_file(bdir) and not a.base_saved and not a.at:
        rec['base_saved'] = iso(C.draft_file(bdir).stat().st_mtime)
    old = next((v for v in vs if v['name'] == name), None)
    if old:
        old.update({k: v for k, v in rec.items() if v is not None})
        print(f'[안내] {name} 기록이 이미 있어 고쳤습니다.')
    else:
        vs.append(rec)
    vs.sort(key=lambda v: ts(v['registered']) or 0)
    save(sp, st, f"register {name} (바탕 {a.base or '—'}, {a.tool or '—'})")
    print(f"기록: {name} · 등록 {hm(rec['registered'])} · 바탕 {a.base or '—'}"
          + (f"({hm(rec['base_saved'])})" if rec.get('base_saved') else '') + f" · {a.tool or '도구 미기록'}")
    print('HANDOFF.md 에도 등록 이름과 시각을 적습니다.')


def cmd_latest(a):
    V, sp, st = load(a.video)
    cc, rows = scan(st, a.capcut_dir)
    if cc is None:
        C.die('CapCut 프로젝트 폴더를 찾지 못했습니다(--capcut-dir).')
    latest, note = pick_latest(st, rows)
    if a.quiet:
        if latest:
            print(latest['name'])
        return
    print(f"CapCut 프로젝트 중 '{st['video']}'(으)로 시작하는 것 {len(rows)}개:")
    for r in sorted(rows, key=lambda r: r['mtime']):
        mark = '→' if latest and r['name'] == latest['name'] else ' '
        print(f" {mark} {r['name']}  저장 {hm(iso(r['mtime']))}  등록 {hm(r['registered'])}  {r['kind']}")
    if latest:
        print(f"바탕: {latest['name']}({hm(iso(latest['mtime']))})")
    else:
        print('바탕: 사용자 편집본 없음')
    if note:
        print('[주의] ' + note)


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='claude-edit 편집 진행 상황(S0~S5·게이트·버전) 기록과 다음 할 일')
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--video', required=True, help='영상 폴더(작업 폴더 안 <영상 이름>/)')
    common.add_argument('--capcut-dir')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('init', parents=[common], help='상태 파일 만들기')
    p.add_argument('--name', help='CapCut 프로젝트 이름 앞머리(기본: 폴더 이름에서 날짜를 뺀 것)')
    for k in ('footage', 'script', 'template', 'crop', 'rotate'):
        p.add_argument(f'--{k}')
    sub.add_parser('status', parents=[common], help='지금 단계·다음 할 일·물을 것')
    p = sub.add_parser('set', parents=[common], help='값 바꾸기')
    p.add_argument('key')
    p.add_argument('value')
    p.add_argument('--note')
    p.add_argument('--add', action='store_true', help='숫자를 더한다(credits)')
    p = sub.add_parser('register', parents=[common], help='클로드가 등록한 버전 기록')
    p.add_argument('version')
    p.add_argument('--base', required=True, help="바탕 프로젝트 이름(처음 조립이면 '템플릿 <이름>')")
    p.add_argument('--base-saved', help='바탕의 사용자 저장 시각(ISO). 없으면 지금 draft 수정 시각')
    p.add_argument('--tool', help='capcut_build.py | capcut_augment.py')
    p.add_argument('--length', help='길이(예: 6:56)')
    p.add_argument('--at', help='등록 시각(ISO). 지난 기록을 옮길 때')
    p.add_argument('--note')
    p = sub.add_parser('latest', parents=[common], help='가장 최근 사용자 편집본')
    p.add_argument('--quiet', action='store_true', help='이름만 출력')
    a = ap.parse_args()
    dict(init=cmd_init, status=cmd_status, set=cmd_set, register=cmd_register, latest=cmd_latest)[a.cmd](a)


if __name__ == '__main__':
    main()
