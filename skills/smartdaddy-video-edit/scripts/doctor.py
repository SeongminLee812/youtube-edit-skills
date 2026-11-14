"""편집 스킬을 쓰기 전에 필요한 것들이 준비됐는지 확인합니다(--fix 를 주지 않으면 아무것도 설치하거나 바꾸지 않음).

확인하는 것:
  - Python 3.10 이상
  - ffmpeg / ffprobe (영상·음성 처리)
  - Python 패키지: faster-whisper, numpy, soundfile, Pillow, opencv-python (+ 모션 카드·목차 전환용 playwright는 선택)
  - GPU(CUDA): 있으면 받아쓰기가 빠르고, 없으면 CPU로 느리게 동작
  - Whisper 모델 내려받기 여부(처음 한 번 약 3GB)
  - CapCut 프로젝트 폴더 위치(Windows/Mac), 가장 최근 프로젝트 파일을 읽을 수 있는지(암호화 여부)
  - 미리보기용 한글 글꼴

사용 예:
  python doctor.py
  python doctor.py --gpu-test        # 작은 모델(약 75MB)을 내려받아 GPU 받아쓰기를 실제로 한 번 돌려 본다
  python doctor.py --capcut-dir "<CapCut 프로젝트 폴더 경로>"
  python doctor.py --fix             # 사용자가 설치를 맡겼을 때: pip 패키지 · 크로미움 · (없으면) ffmpeg 설치 후 다시 확인

끝에 '필수 항목 모두 준비됨' 또는 없는 것과 설치 방법을 알려 준다. 필수 항목이 빠지면 종료 코드 1.
"""
import argparse
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

HERE = Path(__file__).resolve().parent
ENCRYPTED_MSG = ('이 CapCut 버전은 프로젝트 파일을 읽을 수 없어 캡컷 조립 기능을 쓸 수 없습니다. '
                 '받아쓰기·컷 목록·자막(SRT)·모션 카드는 쓸 수 있습니다.')


class Report:
    def __init__(self):
        self.missing = []     # 필수 항목 없음
        self.warns = []

    def ok(self, item, msg=''):
        print(f'[OK]   {item}' + (f' · {msg}' if msg else ''))

    def bad(self, item, msg, fix):
        print(f'[없음] {item} · {msg}\n       → {fix}')
        self.missing.append(item)

    def warn(self, item, msg, fix=''):
        print(f'[주의] {item} · {msg}' + (f'\n       → {fix}' if fix else ''))
        self.warns.append(item)


def ffmpeg_fix():
    s = platform.system()
    if s == 'Windows':
        return 'PowerShell에서: winget install Gyan.FFmpeg  (설치 후 터미널을 새로 열기)'
    if s == 'Darwin':
        return '터미널에서: brew install ffmpeg'
    return 'sudo apt install ffmpeg'


def fix():
    """빠진 것을 설치한다: Python 패키지, 모션 카드용 크로미움, (없으면) ffmpeg. 사용자가 설치를 맡겼을 때만 쓴다."""
    def sh(args):
        print('  $ ' + ' '.join(str(x) for x in args))
        return subprocess.run([str(x) for x in args]).returncode == 0

    print('설치를 시작합니다(사용자가 맡긴 범위: Python 패키지 · 크로미움 · ffmpeg).')
    ok = sh([sys.executable, '-m', 'pip', 'install', '-r', HERE / 'requirements.txt'])
    if ok:
        ok = sh([sys.executable, '-m', 'playwright', 'install', 'chromium']) and ok
    if not shutil.which('ffmpeg'):
        s = platform.system()
        if s == 'Windows' and shutil.which('winget'):
            sh(['winget', 'install', '--id', 'Gyan.FFmpeg', '-e', '--silent',
                '--accept-package-agreements', '--accept-source-agreements'])
        elif s == 'Darwin' and shutil.which('brew'):
            sh(['brew', 'install', 'ffmpeg'])
        else:
            print('  ffmpeg는 자동 설치 방법을 찾지 못했습니다 → ' + ffmpeg_fix())
        for d in C.find_ffmpeg_dirs():           # 방금 깔았으면 PATH가 안 바뀌었어도 이번 실행에서 찾게
            os.environ['PATH'] = str(d) + os.pathsep + os.environ.get('PATH', '')
            break
    print('설치 단계 끝. 아래에서 다시 확인합니다.')
    print('=' * 64)


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='편집 스킬 준비물 확인')
    ap.add_argument('--capcut-dir', help='CapCut 프로젝트 폴더(자동으로 못 찾을 때)')
    ap.add_argument('--gpu-test', action='store_true', help='작은 Whisper 모델로 GPU 받아쓰기를 실제로 시험')
    ap.add_argument('--fix', action='store_true', help='빠진 Python 패키지·크로미움·ffmpeg를 설치한 뒤 다시 확인')
    a = ap.parse_args()
    if a.fix:
        fix()
    r = Report()
    print(f'운영체제: {platform.system()} {platform.release()} · Python {platform.python_version()}')
    print('-' * 64)

    # 1) Python
    if sys.version_info >= (3, 10):
        r.ok('Python', platform.python_version())
    else:
        r.bad('Python', f'{platform.python_version()} (3.10 이상 필요)', 'python.org 에서 3.10 이상(3.11·3.12 권장)을 설치')

    # 2) ffmpeg
    for tool in ('ffmpeg', 'ffprobe'):
        p = shutil.which(tool)
        if p:
            try:
                ver = subprocess.run([tool, '-version'], capture_output=True).stdout.decode('utf-8', 'replace').split('\n')[0]
                r.ok(tool, ' '.join(ver.split()[:3]))
            except Exception:
                r.ok(tool, p)
        else:
            r.bad(tool, 'PATH에서 찾을 수 없음', ffmpeg_fix())
    if shutil.which('ffmpeg'):
        try:
            C.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=256x144:d=0.2', '-c:v', 'h264_nvenc', '-f', 'null', '-'])
            r.ok('GPU 영상 인코딩(NVENC)', '미리보기를 빠르게 만든다')
        except Exception:
            print('[참고] GPU 영상 인코딩(NVENC) 없음 · 미리보기는 libx264(CPU)로 만든다')

    # 3) 패키지
    req = [('faster_whisper', 'faster-whisper'), ('numpy', 'numpy'), ('soundfile', 'soundfile'), ('PIL', 'Pillow'), ('cv2', 'opencv-python')]
    for mod, pkg in req:
        try:
            m = importlib.import_module(mod)
            r.ok(pkg, getattr(m, '__version__', ''))
        except Exception as e:
            r.bad(pkg, f'불러오기 실패({str(e)[:60]})', f'pip install -r "{HERE / "requirements.txt"}"')
    try:
        importlib.import_module('playwright')
        r.ok('playwright(모션 카드·목차 전환용, 선택)')
    except Exception:
        print('[참고] playwright 없음(모션 카드·목차 전환 렌더할 때만 필요) → pip install playwright && python -m playwright install chromium')

    # 4) GPU
    n = C.cuda_count()
    if n > 0:
        vram = ''
        if shutil.which('nvidia-smi'):
            try:
                out = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], capture_output=True).stdout.decode()
                vram = out.strip().split('\n')[0]
            except Exception:
                pass
        r.ok('GPU(CUDA)', f'{n}개 {vram}'.strip() + ' · 받아쓰기는 GPU로. 8GB 이하면 Whisper는 한 번에 하나만 돌린다')
    else:
        r.warn('GPU(CUDA)', '없음 → 받아쓰기는 CPU(int8)로 자동 전환(느림, 긴 영상은 --model medium 권장)',
               'NVIDIA 그래픽카드가 있으면 최신 드라이버를 설치. 없어도 쓸 수 있음')
    if a.gpu_test and n > 0:
        code = ('import numpy as np; from faster_whisper import WhisperModel; '
                'm = WhisperModel("tiny", device="cuda", compute_type="float16"); '
                'list(m.transcribe(np.zeros(16000, np.float32), beam_size=1)[0]); print("OK")')
        p = subprocess.run([sys.executable, '-c', code], capture_output=True, timeout=600)
        if p.returncode == 0 and b'OK' in p.stdout:
            r.ok('GPU 받아쓰기 시험', 'tiny 모델로 성공')
        else:
            r.warn('GPU 받아쓰기 시험', '실패(cuBLAS/cuDNN 라이브러리 문제일 수 있음). 스크립트는 자동으로 CPU로 전환한다',
                   (p.stderr.decode('utf-8', 'replace').strip().split('\n') or [''])[-1][:200])

    # 5) Whisper 모델 캐시
    hub = Path(os.environ.get('HF_HUB_CACHE') or (Path(os.environ.get('HF_HOME', Path.home() / '.cache' / 'huggingface')) / 'hub'))
    have = sorted(p.name.replace('models--Systran--faster-whisper-', '') for p in hub.glob('models--Systran--faster-whisper-*')) if hub.exists() else []
    if have:
        r.ok('Whisper 모델', '내려받음: ' + ', '.join(have))
    else:
        print('[참고] Whisper 모델 아직 없음 · 첫 받아쓰기 때 자동으로 내려받음(large-v3 약 3GB, 인터넷 필요)')

    # 6) CapCut
    cc = C.find_capcut_dir(a.capcut_dir, required=False)
    if cc is None:
        r.warn('CapCut 프로젝트 폴더', '찾지 못함',
               'CapCut을 설치하고 프로젝트를 한 번 만든 뒤 다시 확인하거나 --capcut-dir 로 알려 주기. '
               '(Windows: %LOCALAPPDATA%\\CapCut\\User Data\\Projects\\com.lveditor.draft, '
               'Mac: ~/Movies/CapCut/User Data/Projects/com.lveditor.draft)')
    else:
        projs = [p for p in cc.iterdir() if p.is_dir() and C.draft_file(p)]
        r.ok('CapCut 프로젝트 폴더', f'{cc} · 프로젝트 {len(projs)}개')
        if not (cc / 'root_meta_info.json').exists():
            r.warn('CapCut 프로젝트 목록', 'root_meta_info.json 없음 → --install(자동 등록)은 못 씀')
        if C.capcut_running():
            print('[참고] CapCut이 지금 켜져 있음 · 프로젝트 등록(--install)과 자막 시간 수정 전에는 꺼야 함')
        if projs:
            latest = max(projs, key=lambda p: C.draft_file(p).stat().st_mtime)
            try:
                d = json.loads(C.draft_file(latest).read_bytes().decode('utf-8-sig'))
                ver = (d.get('last_modified_platform') or d.get('platform') or {}).get('app_version', '?')
                M = C.material_index(d)
                kinds = set()
                for t in d.get('tracks', []):
                    for s in t.get('segments', []):
                        kinds.add((t['type'], M.get(s['material_id'], (0, {}))[1].get('type')))
                has = lambda tt, mt: any(k == (tt, mt) for k in kinds)
                r.ok('최근 프로젝트 읽기', f'"{latest.name}" JSON 읽힘 · CapCut {ver}')
                lack = []
                if not has('video', 'video'):
                    lack.append('영상 클립')
                if not has('audio', 'extract_music'):
                    lack.append('로컬 음성 파일 클립')
                if not any(k[0] == 'text' for k in kinds):
                    lack.append('텍스트(자막) 클립')
                if lack:
                    print(f'[참고] 이 프로젝트를 템플릿으로 쓰려면 {", ".join(lack)}이(가) 필요함 · 자막·영상이 든 평소 프로젝트를 템플릿으로 고르기')
            except Exception:
                r.warn('최근 프로젝트 읽기', ENCRYPTED_MSG)

    # 7) 한글 글꼴(미리보기)
    fonts = {'Windows': ['C:/Windows/Fonts/malgun.ttf', 'C:/Windows/Fonts/malgunbd.ttf'],
             'Darwin': ['/System/Library/Fonts/AppleSDGothicNeo.ttc', '/System/Library/Fonts/Supplemental/AppleGothic.ttf']}.get(platform.system(), [])
    f = next((x for x in fonts if Path(x).exists()), None)
    if f:
        r.ok('한글 글꼴(미리보기)', Path(f).name)
    elif fonts:
        r.warn('한글 글꼴(미리보기)', '기본 한글 글꼴을 못 찾음 · 미리보기 자막이 깨질 수 있음(CapCut 프로젝트에는 영향 없음)')

    print('-' * 64)
    if r.missing:
        print(f'필수 항목 {len(r.missing)}개가 없습니다: {", ".join(r.missing)}. 위 → 안내대로 설치한 뒤 다시 실행해 주세요.'
              + ('' if a.fix else ' (설치를 맡기려면: python doctor.py --fix)'))
        sys.exit(1)
    print('필수 항목 모두 준비됨' + (f' (주의 {len(r.warns)}개: {", ".join(r.warns)})' if r.warns else ''))


if __name__ == '__main__':
    main()
