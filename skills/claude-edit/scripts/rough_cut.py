"""S1 러프컷을 단계별로 이어서 실행합니다(claude-edit). 촬영 원본·원고·CapCut 프로젝트는 읽기만 합니다.

결과는 영상 폴더의 편집 폴더(편집/ = 영상 폴더 안 편집/ · tools/topic_paths.py)에 쓴다.
단계(순서대로, --from/--to 로 고른다):
  asr      전체 받아쓰기 transcribe.py large-v3                 → 편집/01_asr/words.json
  plan     컷 계획 cut_plan.py --model large-v3(Apple GPU) / medium(CPU) → 편집/02_cut/plan.json · audio16k.wav
  check    원고 대조 script_check.py(사람 컷 전 컷 계획)           → 편집/03_script/words_script.json · script_check.md
  tighten  재테이크 판독 high·medium 컷 + 쉼 0.15초 tighten.py     → 편집/02_cut/plan_tight.json
  edges    경계 검사 edge_check.py --apply(끝 잘림·이음매 쉼)      → 편집/02_cut/plan_edge.json  ← 최종 컷 계획
  listen   다시 듣기 listen_check.py                            → 편집/04_check/rough.wav · rough.txt · rough_report.json
  subs     편집본 받아쓰기 transcribe.py large-v3 + script_check  → 편집/05_edit_asr/words_script.json · 사라진_원고문장.json
  build    CapCut 스테이징 capcut_build.py(줌·효과음 없음)         → 편집/02_cut/capcut_staging/<이름>/

재테이크 판독은 이 스크립트가 하지 않는다(하위 에이전트가 한다).
  - tighten 앞에서 편집/03_review/retake_review.json 이 없으면 하위 에이전트 요청서(03_review/재테이크_판독_요청.md)를 쓰고
    입력 목록·JSON 형식을 출력한 뒤 멈춘다(종료 코드 3). 판독을 쓴 뒤 --from tighten 으로 이어 간다.
  - low 항목은 자르지 않고 게이트 A 표(03_review/게이트A_낮은신뢰도.md: 원본 초·편집 초·대사·자를 이유·남길 이유)로 모은다.
    같은 파일에 쉼 줄이기 [확인 필요], 경계 검사에서 적용하지 않은 것, 다시 듣기 결과, 편집으로 사라진 원고 문장도 모은다.
    자르기로 정하면 retake_review.json의 그 항목 confidence를 "high"로 바꾸고(또는 --cut 시작-끝) 다시 돌린다. 바뀐 파일은 저절로 다시 계산한다.
이어 하기: 단계의 결과 파일이 있고 지난번 실행과 명령·입력 파일 내용이 같으면 건너뛴다(--force 면 범위 안 단계를 모두 다시).
  입력이 바뀐 단계와 그 뒤 단계만 다시 계산한다(50MB 넘는 촬영본은 크기·수정 시각으로 본다).
  결과 파일이 있는데 rough_cut 기록에 없으면(손으로 만든 결과일 수 있음) 덮어쓰지 않고 멈춘다.
.edit_busy: 무거운 단계(asr·plan·listen·subs) 동안 프로젝트 루트에 만들고 끝나거나 실패하면 지운다(이미 있던 파일은 건드리지 않음).
기록: 단계마다 명령·시각·걸린 시간·산출·알림을 편집/rough_cut_log.json 에 쌓는다.
등록(--install)은 기본으로 하지 않는다. 켜도 CapCut이 켜져 있으면 거부한다(이 스크립트는 CapCut을 끄지 않는다). 사용자가 허락했을 때만 쓴다.

사용 예(작업 폴더에서):
  python rough_cut.py --video 내영상 --media 내영상/촬영본.mp4 [--script 내영상/원고.txt] \
      --template "내 템플릿" --crop 0.034,0.017,1.0,0.983 --prompt "<고유명사>" --to tighten     # 판독 요청서에서 멈춤
  python rough_cut.py --video 내영상 … --from tighten [--bumper-src 31.8]                     # 판독 뒤 이어서 스테이징까지
  python rough_cut.py --video 내영상 … --from build --install                                   # 사용자 허락 + CapCut 끈 뒤 등록
  python rough_cut.py --video 내영상 … --dry-run                                                 # 단계별 할 일·명령만 보기
쉼 줄이기 값은 profile.md 의 cut_tempo(촘촘|보통|여유, 기본 보통)를 따른다.
"""
import argparse
import contextlib
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('PROJECT_ROOT') or os.getcwd()).resolve()     # 프로젝트 루트(PROJECT_ROOT 또는 작업 폴더)
NO_SCRIPT_COPY = 'import pathlib,shutil,sys; pathlib.Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True); shutil.copy(sys.argv[1], sys.argv[2])'
ENGINE = Path(__file__).resolve().parents[2] / 'smartdaddy-video-edit' / 'scripts'
sys.path[:0] = [str(ENGINE), str(HERE), str(ROOT / 'tools')]
import _common as C  # noqa: E402
import topic_paths as TP  # noqa: E402   영상 폴더 안 단계 폴더
from _busy import busy  # noqa: E402   .edit_busy 표시(내가 만든 것만 지움)
CHANNEL_DICT = ROOT / (C.load_profile(ROOT).get('subtitle_dictionary') or 'subtitle_dictionary.json')   # 채널 공용 자막 고침 사전(있을 때만)

STAGES = ['asr', 'plan', 'check', 'tighten', 'edges', 'listen', 'subs', 'build']
HEAVY = {'asr', 'plan', 'listen', 'subs'}
BUMPER = ROOT / (C.load_profile(ROOT).get('bumper') or 'bumper.mp4')     # 채널 범퍼(profile.md 의 bumper, 있을 때만)
PY = ROOT / '.venv' / 'bin' / 'python'
if not PY.exists():
    PY = Path(sys.executable)     # 작업 폴더 가상환경이 없으면 지금 python
WAIT_REVIEW = 3     # 재테이크 판독을 기다리며 멈춘 종료 코드


class Stop(Exception):
    """단계가 사람·하위 에이전트를 기다리며 멈춤."""


# ── 경로 ─────────────────────────────────────────────
class Paths:
    def __init__(s, video):
        s.V = video
        s.E = TP.part(video, 'edit')
        s.asr, s.cut, s.scr = s.E / '01_asr', s.E / '02_cut', s.E / '03_script'
        s.rev, s.chk, s.sub = s.E / '03_review', s.E / '04_check', s.E / '05_edit_asr'
        s.words, s.wav, s.plan = s.asr / 'words.json', s.cut / 'audio16k.wav', s.cut / 'plan.json'
        s.wscript, s.sc_json = s.scr / 'words_script.json', s.scr / 'script_check.json'
        s.replace = s.scr / 'subtitle_replace.json'
        s.review, s.brief, s.gate = s.rev / 'retake_review.json', s.rev / '재테이크_판독_요청.md', s.rev / '게이트A_낮은신뢰도.md'
        s.tight, s.edge_dir, s.final = s.cut / 'plan_tight.json', s.cut / 'edge_check', s.cut / 'plan_edge.json'
        s.lwav, s.ltxt, s.lrep = s.chk / 'rough.wav', s.chk / 'rough.txt', s.chk / 'rough_report.json'
        s.ewords, s.ewscript, s.esc_json = s.sub / 'words.json', s.sub / 'words_script.json', s.sub / 'script_check.json'
        s.lost = s.sub / '사라진_원고문장.json'
        s.staging = s.cut / 'capcut_staging'
        s.log = s.E / 'rough_cut_log.json'


def rel(p):
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(p).as_posix()


def cell(s, n=80):
    s = re.sub(r'\s+', ' ', str(s or '')).replace('|', '\\|').strip()
    return s if len(s) <= n else s[:n - 1] + '…'


# ── 기록 ─────────────────────────────────────────────
def read_log(P):
    try:
        L = C.read_json(P.log)
        return L if isinstance(L, list) else []
    except Exception:
        return []


def add_log(P, entry):
    L = read_log(P)
    L.append(entry)
    C.write_json(P.log, L)


def last_ok(log, stage):
    return next((e for e in reversed(log) if e.get('stage') == stage and e.get('status') == 'ok'), None)


# ── 실행 ─────────────────────────────────────────────
def run_cmd(cmd, out_lines):
    print('$ ' + ' '.join(shlex.quote(str(c)) for c in cmd), flush=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
    p = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding='utf-8', errors='replace', env=env, cwd=str(ROOT))
    try:
        for line in p.stdout:
            sys.stdout.write('  │ ' + line)
            sys.stdout.flush()
            out_lines.append(line.rstrip('\n'))
        p.wait()
    except BaseException:
        p.terminate()
        try:
            p.wait(10)
        except Exception:
            p.kill()
        raise
    return p.returncode


# ── 재테이크 판독 ─────────────────────────────────────
REVIEW_FORMAT = '''[
  {"cut": [시작초, 끝초], "removed_text": "지울 말", "kept_take": {"at": 남길 테이크 시작초, "text": "남길 말"},
   "kind": "retake | partial_retake | stutter | aside | noise", "confidence": "high | medium | low",
   "reason": "소리 크기(dB)와 경계 근거(낱말 사이 소리 골 위치)", "keep_reason": "low일 때 남길 이유(게이트 A 표에 씀)"}
]'''


def write_brief(P, a, write=True):
    L = ['# 재테이크 판독 요청 (하위 에이전트용 · claude-edit S1-2)', '',
         '## 입력', '',
         f'- 컷 계획(남긴 문장 클립, 원본 초): `{rel(P.plan)}` · 지운 곳 목록 `{rel(P.cut / "cuts.md")}`',
         f'- 촬영 원고: `{rel(a.script) if a.script else "(없음)"}`',
         f'- 원고 대조: `{rel(P.scr / "script_check.md")}` · 재테이크·잡음 후보 `{rel(P.scr / "cut_suggest.txt")}`',
         f'- 전체 받아쓰기: `{rel(P.words)}` · `{rel(P.asr / "transcript.txt")}`',
         f'- 오디오: `{rel(P.wav)}` (16kHz 모노, 파일 초 = 원본 초)', '',
         '## 할 일', '',
         '- 컷 계획에 남은 재테이크(같은 말을 다시 한 앞 테이크, 버린 테이크의 끝 조각, 말 더듬기)와 말 아닌 소리(긴 공백 속 헛기침 등)를 찾는다.',
         '- 같은 말이 두 번이면 뒤 테이크를 남기고 앞 테이크를 지운다. 세 번 이상 반복·숫자 읽기·일부러 한 강조는 남긴다.',
         '- 컷 경계는 낱말 사이 소리 골(10ms 프레임 dB가 바닥 잡음 근처)에 둔다. 남길 말의 끝·처음을 자르지 않는다.',
         '- 지루한 구간 자르기(내용 컷)는 하지 않는다. 사용자가 CapCut에서 한다.', '',
         f'## 출력: `{rel(P.review)}`', '',
         '최상위는 리스트다(지울 곳이 없으면 `[]`).', '', '```json', REVIEW_FORMAT, '```', '',
         '- high: 같은 말을 분명히 다시 함 → 자동으로 자름',
         '- medium: 대부분 맞음(오탐 가능 — 시험에서 12곳 중 4곳) → 자동으로 자르고, 뒤에서 원고 대조로 사라진 문장을 확인',
         '- low: 강조·의도일 수 있음 → 자르지 않고 게이트 A 표로 사용자에게 묻는다', '',
         '## 다 쓰면', '',
         '편집 세션이 같은 rough_cut.py 명령에 `--from tighten`을 붙여 이어 간다.']
    if write:
        P.rev.mkdir(parents=True, exist_ok=True)
        P.brief.write_text('\n'.join(L) + '\n', 'utf-8')
    return L


def check_review(P):
    try:
        R = C.read_json(P.review)
    except Exception as e:
        C.die(f'재테이크 판독 JSON을 읽지 못했습니다: {P.review} ({str(e)[:120]})')
    if not isinstance(R, list):
        C.die(f'재테이크 판독 JSON의 최상위는 리스트여야 합니다: {P.review}')
    bad = []
    for n, r in enumerate(R, 1):
        c = r.get('cut') if isinstance(r, dict) else None
        if not (isinstance(c, list) and len(c) == 2 and all(isinstance(v, (int, float)) for v in c) and c[0] < c[1]) \
                or r.get('confidence') not in ('high', 'medium', 'low'):
            bad.append(n)
    if bad:
        C.die(f'재테이크 판독 JSON 항목 {bad}번의 형식이 틀렸습니다("cut": [시작, 끝], "confidence": high|medium|low).')
    return R


# ── 게이트 A 표 ───────────────────────────────────────
def edit_mapper(plan_path):
    segs = sorted(C.read_json(plan_path)['segments'], key=lambda s: s['src_in'])

    def f(src):
        t = 0.0
        for s in segs:
            if src < s['src_in']:
                return t
            if src <= s['src_out']:
                return t + src - s['src_in']
            t += s['src_out'] - s['src_in']
        return t
    return f


def write_gate(P):
    """게이트 A에서 사람이 정할 것을 한 파일에 모은다(있는 결과만)."""
    plan = P.final if P.final.exists() else P.tight if P.tight.exists() else None
    if not plan:
        return None
    et = edit_mapper(plan)
    L = ['# 게이트 A · 사람이 정할 것', '',
         f'- 만든 시각 {time.strftime("%Y-%m-%d %H:%M")} · 편집 초 기준 `{rel(plan)}`(범퍼 없음)',
         '- 자르기로 정하면 `retake_review.json`의 그 항목 `confidence`를 `"high"`로 바꾸거나 `--cut 시작-끝`을 주고 rough_cut.py를 다시 돌린다'
         '(바뀐 파일부터 저절로 다시 계산). 남기면 그대로 둔다.', '']
    R = C.read_json(P.review) if P.review.exists() else []
    low = [r for r in R if isinstance(r, dict) and r.get('confidence') == 'low']
    L += [f'## 1. 판독 신뢰도 낮음 {len(low)}곳 (자르지 않고 남김)', '']
    if low:
        L += ['| # | 원본 초 | 편집 초 | 대사 | 자를 이유 | 남길 이유 |', '|---|---|---|---|---|---|']
        for n, r in enumerate(low, 1):
            c0, c1 = r['cut']
            L.append(f'| {n} | {c0:.2f}–{c1:.2f} | {C.mmss(et(c0))} | {cell(r.get("removed_text"), 50)} | '
                     f'{cell(r.get("reason"))} | {cell(r.get("keep_reason") or "—")} |')
    else:
        L.append('- 없음')
    rv = (C.read_json(P.tight).get('tighten') or {}).get('review', []) if P.tight.exists() else []
    L += ['', f'## 2. 쉼 줄이기가 남긴 확인 필요 {len(rv)}곳', '']
    for r in rv:
        if 'speech' in r:
            L.append(f'- 원본 {r["src_in"]:.2f}–{r["src_out"]:.2f} (편집 {C.mmss(et(r["src_in"]))}) 말소리 {r["speech"]:.2f}초인데 낱말 없음 '
                     f'→ 숨·웃음·재테이크 조각이면 `--cut {r["src_in"]:.2f}-{r["src_out"]:.2f}`')
        else:
            L.append(f'- 원본 {r["src_in"]:.2f}–{r["src_out"]:.2f} (편집 {C.mmss(et(r["src_in"]))}) 뺀 조각에 늘어 붙은 낱말 {r["words"]} · '
                     f'다음 클립 "{r.get("next_text", "")}"' + (' · 되풀이(지워도 됨)' if r.get('repeat') else
                                                          f' → 진짜 말이면 `--keep {r["src_in"]:.2f}-{r["src_out"]:.2f}`'))
    if not rv:
        L.append('- 없음')
    ej = P.edge_dir / 'edge_check.json'
    er = [r for r in C.read_json(ej).get('rows', []) if not r.get('apply')] if ej.exists() else []
    L += ['', f'## 3. 경계 검사에서 적용하지 않은 것 {len(er)}곳 (`{rel(P.edge_dir / "edge_check.md")}`)', '']
    for r in er:
        if r['side'] == 'start':
            ext = f'살리기 {r["new"]:.2f}' if r.get('new') is not None else '살리기 골 없음'
            trim = f'조각 빼기 {r["alt"]:.2f}' if r.get('alt') is not None else '조각 빼기 골 없음'
            L.append(f'- [{r["kind"]}] 원본 {r["src"]:.2f} · "{r.get("prev_text", "")}" ‖ "{r["text"]}" · {ext} / {trim} '
                     '(지운 테이크의 끝 조각이 남은 경우가 많다 → 들어 보고 `--cut`)')
        else:
            prop = f'끝 → {r["new"]:.2f}' if r.get('new') is not None else '골 없음'
            L.append(f'- [{r["kind"]}] 원본 {r["src"]:.2f} · "{r["text"]}" ‖ "{r.get("next_text", "")}" · {prop}')
    if not er:
        L.append('- 없음')
    lr = C.read_json(P.lrep) if P.lrep.exists() else []
    L += ['', f'## 4. 다시 듣기 {len(lr)}곳 (`{rel(P.ltxt)}`)', '']
    L += [f'- {x}' for x in lr] or ['- 없음']
    lost = C.read_json(P.lost) if P.lost.exists() else []
    L += ['', f'## 5. 편집으로 사라진 원고 문장 {len(lost)}개 (재테이크 오탐 확인 · 바꿔 말한 곳이면 무시)', '']
    L += [f'- 원고 {m["sentence"]}번: {m["text"]}' for m in lost] or ['- 없음']
    P.gate.parent.mkdir(parents=True, exist_ok=True)
    P.gate.write_text('\n'.join(L) + '\n', 'utf-8')
    return dict(low=len(low), tighten=len(rv), edges=len(er), listen=len(lr), lost=len(lost))


# ── 단계 뒤처리 ───────────────────────────────────────
def post_listen(P, out):
    rep = [ln.strip() for ln in out if ln.strip().startswith(('[빈 구간]', '[이어진 같은 말]'))]
    C.write_json(P.lrep, rep)
    return [f'다시 듣기 알림 {len(rep)}곳'] + rep[:10]


def post_subs(P):
    notes = []
    if not P.sc_json.exists():
        C.write_json(P.lost, [])
        return [f'원고 대조 원본({rel(P.sc_json)})이 없어 사라진 원고 문장을 비교하지 못함']
    m0 = {m['sentence'] for m in C.read_json(P.sc_json).get('missing', [])}
    lost = [m for m in C.read_json(P.esc_json).get('missing', []) if m['sentence'] not in m0]
    C.write_json(P.lost, lost)
    if lost:
        print(f'[경고] 편집으로 사라진 원고 문장 {len(lost)}개 — 재테이크 오탐인지 들어 보세요(바꿔 말한 곳이면 무시):')
        for m in lost:
            print(f'  - 원고 {m["sentence"]}번: {m["text"]}')
    notes.append(f'편집으로 사라진 원고 문장 {len(lost)}개')
    return notes + [f'원고 {m["sentence"]}번: {m["text"][:40]}' for m in lost[:10]]


# ── 단계 정의 ─────────────────────────────────────────
def plan_model(a):
    """컷 계획 모델: Apple GPU(mlx)로 large-v3를 바로 쓸 수 있으면 large-v3, 아니면 CPU용 medium(예전 그대로)."""
    return 'large-v3' if a.asr_backend != 'faster' and C.mlx_ready('large-v3') else 'medium'


def stage_spec(st, P, a):
    eng = lambda n: ENGINE / n  # noqa: E731
    prompt = ['--prompt', a.prompt] if a.prompt else []
    be = [] if a.asr_backend == 'auto' else ['--backend', a.asr_backend]      # 받아쓰기 엔진(기본 auto는 넘기지 않음)
    if st == 'asr':
        return dict(cmds=[[PY, eng('transcribe.py'), a.media, '--out', P.asr, '--model', 'large-v3'] + prompt + be],
                    inputs=[a.media], outputs=[P.words], need=dict(media=a.media))
    if st == 'plan':
        return dict(cmds=[[PY, eng('cut_plan.py'), a.media, '--out', P.cut, '--model', plan_model(a)] + be],
                    inputs=[a.media], outputs=[P.plan, P.wav], need=dict(media=a.media))
    if st == 'check' and not a.script:     # 원고 없음: 받아쓰기 낱말을 그대로 자막 기준으로 쓴다
        return dict(cmds=[[PY, '-c', NO_SCRIPT_COPY, P.words, P.wscript]], inputs=[P.words], outputs=[P.wscript])
    if st == 'check':
        return dict(cmds=[[PY, eng('script_check.py'), '--script', a.script, '--words', P.words, '--plan', P.plan, '--out', P.scr]],
                    inputs=[a.script, P.words, P.plan], outputs=[P.wscript, P.sc_json], need=dict(script=a.script))
    if st == 'tighten':
        extra = [x for c in a.cut for x in ('--cut', c)] + [x for k in a.keep for x in ('--keep', k)]
        return dict(cmds=[[PY, eng('tighten.py'), P.plan, P.wav, '--words', P.wscript, '--cut-file', P.review,
                           '--out', P.tight] + C.tempo_args(ROOT) + extra],
                    inputs=[P.plan, P.wav, P.wscript, P.review], outputs=[P.tight])
    if st == 'edges':
        return dict(cmds=[[PY, HERE / 'edge_check.py', P.tight, P.wav, '--out', P.edge_dir, '--apply', '--out-plan', P.final,
                           '--force']],
                    inputs=[P.tight, P.wav], outputs=[P.final, P.edge_dir / 'edge_check.json'])
    if st == 'listen':
        return dict(cmds=[[PY, eng('listen_check.py'), P.final, P.wav, '--out', P.chk, '--name', 'rough'] + prompt],
                    inputs=[P.final, P.wav], outputs=[P.lwav, P.ltxt, P.lrep])
    if st == 'subs' and not a.script:      # 원고 없음: 편집본 받아쓰기만
        return dict(cmds=[[PY, eng('transcribe.py'), P.lwav, '--out', P.sub, '--model', 'large-v3'] + prompt + be,
                          [PY, '-c', NO_SCRIPT_COPY, P.ewords, P.ewscript]], inputs=[P.lwav], outputs=[P.ewscript])
    if st == 'subs':
        return dict(cmds=[[PY, eng('transcribe.py'), P.lwav, '--out', P.sub, '--model', 'large-v3'] + prompt + be,
                          [PY, eng('script_check.py'), '--script', a.script, '--words', P.ewords, '--out', P.sub]],
                    inputs=[P.lwav, a.script], outputs=[P.ewscript, P.esc_json, P.lost], need=dict(script=a.script))
    if st == 'build':
        cmd = [PY, eng('capcut_build.py'), '--template', a.template, '--plan', P.final, '--media', a.media,
               '--words', P.wscript, '--edit-words', P.ewscript, '--subtitles', '--staging', P.staging, '--name', a.name]
        inputs = [P.final, a.media, P.wscript, P.ewscript]
        if a.crop:
            cmd += ['--crop', a.crop]
        if a.rotate:
            cmd += ['--rotate', str(a.rotate)]
        for f in (P.replace, CHANNEL_DICT):     # 영상 고침 사전이 채널 공용 사전보다 앞(이긴다)
            if f.exists():
                cmd += ['--replace', f]
                inputs.append(f)
        if a.bumper_src is not None:
            cmd += ['--bumper', a.bumper, '--bumper-src', str(a.bumper_src)]
            inputs.append(a.bumper)
        if a.install:
            cmd.append('--install')
        return dict(cmds=[cmd], inputs=inputs, outputs=[P.staging / f'{a.name}_timeline.json', P.staging / a.name],
                    need=dict(media=a.media, template=a.template))
    raise ValueError(st)


def cmd_key(cmds):
    return [[str(c) for c in cmd] for cmd in cmds]


def sigs(paths):
    """입력 파일 표식: 50MB 넘는 파일(촬영본 등)은 크기·수정 시각, 작은 파일은 내용 해시. 내용이 같으면 다시 계산하지 않는다."""
    out = {}
    for p in paths:
        if not p:
            continue
        p = Path(p)
        if not p.exists():
            out[rel(p)] = None
            continue
        st = p.stat()
        out[rel(p)] = f'{st.st_size}:{st.st_mtime_ns}' if st.st_size > 50_000_000 else C.sha256(p)[:16]
    return out


def decide(st, spec, P, a, log):
    """('run' | 'skip', 이유)"""
    outs = spec['outputs']
    have = [p for p in outs if Path(p).exists()]
    if a.force:
        return 'run', '--force'
    if st == 'build' and a.install:
        return 'run', '--install(등록은 매번 새로 조립)'
    prev = last_ok(log, st)
    if have and not prev:
        C.die(f'[{st}] 결과가 이미 있는데 rough_cut 기록에 없습니다(손으로 만든 결과일 수 있음): {rel(have[0])}\n'
              f'  덮어쓰려면 --force, 그대로 쓰려면 다음 단계부터(--from {STAGES[STAGES.index(st) + 1] if st != STAGES[-1] else st}).')
    if len(have) < len(outs):
        return 'run', '결과 없음'
    if prev.get('cmds') != cmd_key(spec['cmds']):
        return 'run', '명령이 지난번과 다름'
    cur, old = sigs(spec['inputs']), prev.get('inputs') or {}
    changed = [k for k in cur if cur[k] != old.get(k)]
    if changed:
        return 'run', f'입력이 바뀜: {Path(changed[0]).name}'
    return 'skip', '결과가 최신'


def run_stage(st, P, a, log):
    spec = stage_spec(st, P, a)
    for k, v in (spec.get('need') or {}).items():
        if not v:
            C.die(f'[{st}] --{k} 를 주세요.')
        if k in ('media', 'script') and not Path(v).exists():
            C.die(f'[{st}] 파일이 없습니다: {v}')
    if st == 'tighten' and not P.review.exists():
        L = write_brief(P, a, write=not a.dry_run)
        print('\n'.join(['', '━' * 60, f'[멈춤] 재테이크 판독 JSON이 없습니다: {rel(P.review)}',
                         f'하위 에이전트에게 요청서 `{rel(P.brief)}`를 주고 판독을 맡기세요. 요청서 내용:', ''] + L + ['━' * 60]),
              flush=True)
        if not a.dry_run:
            add_log(P, dict(stage=st, status='stop', started=time.strftime('%Y-%m-%d %H:%M:%S'), seconds=0,
                            cmds=[], outputs=[rel(P.brief)], notes=['재테이크 판독 JSON 기다림']))
        raise Stop()
    if st == 'tighten':
        R = check_review(P)
        n = {c: sum(r['confidence'] == c for r in R) for c in ('high', 'medium', 'low')}
        print(f'[판독] {len(R)}곳 · high {n["high"]} · medium {n["medium"]} · low {n["low"]}(게이트 A 표로)', flush=True)
    missing_in = [p for p in spec['inputs'] if p and not Path(p).exists() and p != P.review]
    what, why = decide(st, spec, P, a, log)
    if missing_in and what == 'run':
        if not a.dry_run:
            C.die(f'[{st}] 앞 단계 결과가 없습니다: {rel(missing_in[0])} (앞 단계부터 --from 으로 돌리세요)')
        why += f' · 앞 단계 결과 아직 없음({Path(missing_in[0]).name})'
    print(f'\n▶ {st}: {"건너뜀" if what == "skip" else "실행"} ({why})', flush=True)
    if a.dry_run:
        for cmd in spec['cmds']:
            print('  $ ' + ' '.join(shlex.quote(str(c)) for c in cmd))
        return
    started, t0 = time.strftime('%Y-%m-%d %H:%M:%S'), time.time()
    entry = dict(stage=st, started=started, cmds=cmd_key(spec['cmds']), outputs=[rel(p) for p in spec['outputs']],
                 inputs=sigs(spec['inputs']))
    if what == 'skip':
        add_log(P, dict(entry, status='skip', seconds=0, notes=[why]))
        return
    if st == 'build' and a.install and C.capcut_running():
        add_log(P, dict(entry, status='fail', seconds=0, notes=['CapCut이 켜져 있어 등록 거부']))
        C.die('CapCut이 켜져 있어 등록하지 않습니다. 사용자에게 CapCut을 끄라고 요청한 뒤 다시 하세요(클로드가 끄지 않음).')
    out, notes, status = [], [], 'fail'
    try:
        with busy(f'rough_cut {st}') if st in HEAVY else contextlib.nullcontext():
            for cmd in spec['cmds']:
                rc = run_cmd(cmd, out)
                if rc:
                    notes.append(f'종료 코드 {rc}: {Path(str(cmd[1])).name}')
                    raise RuntimeError(f'[{st}] 명령이 실패했습니다(종료 코드 {rc}).')
        if st == 'listen':
            notes += post_listen(P, out)
        elif st == 'subs':
            notes += post_subs(P)
        elif st == 'edges':
            ej = C.read_json(P.edge_dir / 'edge_check.json')
            notes.append(f'고친 경계 {len(ej.get("changes", []))}곳 · 검사 {ej.get("counts")} · 적용 뒤 {ej.get("after_counts")}')
        elif st == 'tighten':
            notes += [ln.strip() for ln in out if '[확인 필요]' in ln or '[되풀이' in ln][:10]
        status = 'ok'
    finally:
        add_log(P, dict(entry, status=status, seconds=round(time.time() - t0, 1), notes=notes, tail=out[-40:]))
    print(f'■ {st} 끝 · {time.time() - t0:.0f}초', flush=True)


def summary(P, a, ran):
    print('\n' + '━' * 60)
    plan = P.final if P.final.exists() else P.tight if P.tight.exists() else P.plan if P.plan.exists() else None
    if plan:
        Q = C.read_json(plan)
        d = sum(s['src_out'] - s['src_in'] for s in Q['segments'])
        print(f'현재 컷 계획: {rel(plan)} · {C.mmss(d)} · 클립 {len(Q["segments"])}개')
    g = write_gate(P)
    if g:
        print(f'게이트 A 표: {rel(P.gate)} · 판독 낮음 {g["low"]} · 쉼 확인 {g["tighten"]} · 경계 미적용 {g["edges"]} · '
              f'다시 듣기 {g["listen"]} · 사라진 원고 문장 {g["lost"]}')
    stage = P.staging / a.name
    if 'build' in ran and stage.exists():
        print(f'스테이징: {rel(stage)}')
        print(f'  미리보기: {rel(PY)} {rel(ENGINE / "preview.py")} "{rel(stage)}" {rel(P.chk / (a.name + "_360p.mp4"))} --h 360')
        if not a.install:
            print('  CapCut 등록은 하지 않았습니다. 사용자가 허락하고 CapCut을 끈 뒤 같은 명령에 --from build --install 을 붙입니다.')
    if 'build' in ran and a.bumper_src is None:
        print('[알림] 범퍼를 넣지 않았습니다. smartdaddy references/channel-profile.md "채널 범퍼" 1단계로 본문 첫 문장의 원본 초를 찾아 '
              '--bumper-src 로 주고 --from build 로 다시 조립하세요.')
    print(f'기록: {rel(P.log)}')


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='claude-edit S1 러프컷 묶음(받아쓰기 → 컷 계획 → 원고 대조 → 쉼 줄이기 → 경계 → 다시 듣기 → 자막 → 스테이징)')
    ap.add_argument('--video', required=True, help='영상 폴더(작업 폴더 안 <영상 이름>/)'
                    '결과는 그 안 편집 폴더(편집/ 또는 편집/)')
    ap.add_argument('--media', help='촬영본(asr·plan·build에 필요). 외장하드로 옮겼으면 그 절대 경로')
    ap.add_argument('--script', help='촬영 원고(선택). 없으면 받아쓰기 낱말로 자막을 만든다. 사용자가 고친 원고는 새 이름으로 저장해 그것을 준다')
    ap.add_argument('--template', help='CapCut 템플릿 프로젝트 이름(build에 필요, 읽기만 함. profile.md 의 capcut_template)')
    ap.add_argument('--crop', help='메인 원본 잘라내기 "x0,y0,x1,y1"(frame_check.py 값)')
    ap.add_argument('--rotate', type=float, default=0.0, help='메인 원본 회전(도, frame_check.py 값)')
    ap.add_argument('--prompt', default='', help='고유명사 힌트(쉼표로 짧게) — 받아쓰기·다시 듣기에 쓴다')
    ap.add_argument('--bumper-src', type=float, help='범퍼를 끼울 원본 초(본문 첫 문장 시작). 없으면 범퍼 없이 조립')
    ap.add_argument('--bumper', default=str(BUMPER), help='채널 범퍼 파일(기본: profile.md 의 bumper)')
    ap.add_argument('--name', help='새 CapCut 프로젝트 이름(기본: <영상 폴더 이름에서 날짜·T### 뺀 것>_초벌_v001)')
    ap.add_argument('--cut', action='append', default=[], help='tighten에 함께 줄 원본 컷 "시작-끝"(게이트 A에서 자르기로 정한 곳)')
    ap.add_argument('--keep', action='append', default=[], help='tighten에 줄 지키기 구간 "시작-끝"')
    ap.add_argument('--from', dest='start', choices=STAGES, default=STAGES[0], help='이 단계부터')
    ap.add_argument('--to', dest='end', choices=STAGES, default=STAGES[-1], help='이 단계까지')
    ap.add_argument('--force', action='store_true', help='범위 안 단계를 결과가 있어도 다시 실행')
    ap.add_argument('--install', action='store_true', help='CapCut에 등록(사용자 허락 + CapCut 꺼짐일 때만. 기본: 하지 않음)')
    ap.add_argument('--dry-run', action='store_true', help='실행하지 않고 단계별 판단·명령만 보여 준다')
    ap.add_argument('--asr-backend', default='auto', choices=['auto', 'faster', 'mlx'],
                    help='받아쓰기 엔진(transcribe·cut_plan에 넘김). auto: Apple GPU(mlx)가 있으면 GPU, 없으면 CPU · faster: 예전 CPU 방식')
    a = ap.parse_args()

    try:
        video = (TP.topic_folder(a.video, ROOT) if TP.TOPIC_ID.match(a.video) else Path(a.video).expanduser()).resolve()
    except ValueError as e:
        C.die(str(e))
    if not video.is_dir():
        C.die(f'영상 폴더가 없습니다: {video}')
    i0, i1 = STAGES.index(a.start), STAGES.index(a.end)
    if i0 > i1:
        C.die(f'--from {a.start} 가 --to {a.end} 보다 뒤입니다.')
    for k in ('media', 'script'):
        if getattr(a, k):
            setattr(a, k, Path(getattr(a, k)).expanduser().resolve())
    a.bumper = Path(a.bumper).expanduser().resolve()
    if a.bumper_src is not None and not a.bumper.exists():
        C.die(f'범퍼 파일이 없습니다: {a.bumper}')
    if not a.name:
        a.name = TP.display_name(video) + '_초벌_v001'
    if not PY.exists():
        C.die(f'실행 Python이 없습니다: {PY} (작업 폴더 .venv 또는 지금 python)')
    for c in a.cut + a.keep:
        if not re.fullmatch(r'\s*\d+(\.\d+)?\s*-\s*\d+(\.\d+)?\s*', c):
            C.die(f'구간 형식이 틀렸습니다: "{c}" (예: 283.0-286.2)')
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))     # 끊겨도 finally(.edit_busy 지우기·기록)가 돌게

    P = Paths(video)
    P.E.mkdir(parents=True, exist_ok=True)
    todo = STAGES[i0:i1 + 1]
    print(f'러프컷 {video.name} · 단계 {todo[0]} → {todo[-1]}' + (' · 미리보기(실행 안 함)' if a.dry_run else ''), flush=True)
    ran, t0 = [], time.time()
    try:
        for st in todo:
            run_stage(st, P, a, read_log(P))
            ran.append(st)
    except Stop:
        if not a.dry_run:
            summary(P, a, ran)
        sys.exit(WAIT_REVIEW)
    except RuntimeError as e:
        C.die(f'{e} 출력은 위와 {rel(P.log)}에 있습니다. 고친 뒤 같은 명령으로 다시 돌리면 끝난 단계는 건너뜁니다.')
    print(f'\n전체 {time.time() - t0:.0f}초')
    if not a.dry_run:
        summary(P, a, ran)


if __name__ == '__main__':
    main()
