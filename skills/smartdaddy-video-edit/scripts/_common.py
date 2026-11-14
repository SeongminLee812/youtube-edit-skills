"""여러 스크립트가 같이 쓰는 도구 모음입니다. 직접 실행하지 않습니다.

- 콘솔 한글 출력, ffmpeg/ffprobe 호출, 미디어 정보 읽기
- Whisper 모델 불러오기(GPU가 없으면 CPU int8로 자동 전환), 환각 문장 거르기
- CapCut 프로젝트 폴더 찾기(Windows/Mac), CapCut 실행 여부, 프로젝트 읽기
"""
import difflib
import functools
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

US = 1_000_000          # CapCut 시간 단위(마이크로초)


# ── 콘솔 ─────────────────────────────────────────────
def setup_console():
    """Windows 콘솔에서도 한글이 깨지지 않게 UTF-8로 맞춘다."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8')
        except Exception:
            pass


def die(msg, code=1):
    print('[오류] ' + msg, file=sys.stderr, flush=True)
    sys.exit(code)


def mmss(t):
    """초 → 'MM:SS.ss' (한 시간이 넘으면 'H:MM:SS.ss')."""
    t = max(0.0, float(t))
    h, rest = divmod(t, 3600)
    m, s = divmod(rest, 60)
    return f'{int(h)}:{int(m):02d}:{s:05.2f}' if h >= 1 else f'{int(m):02d}:{s:05.2f}'


def us(sec):
    return int(round(sec * US))


def read_json(p):
    return json.loads(Path(p).read_text('utf-8-sig'))


def write_json(p, obj, compact=False):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    if compact:
        Path(p).write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')), 'utf-8')
    else:
        Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), 'utf-8')


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ── ffmpeg ───────────────────────────────────────────
def find_ffmpeg_dirs():
    """PATH에 없을 때 ffmpeg가 흔히 깔리는 곳(winget·brew 등). 방금 설치해서 PATH가 아직 안 바뀐 경우를 위해."""
    home = Path.home()
    cands = [Path(os.environ.get('LOCALAPPDATA', home / 'AppData' / 'Local')) / 'Microsoft' / 'WinGet' / 'Links',
             Path('C:/ffmpeg/bin'), Path('C:/Program Files/ffmpeg/bin'), Path('/opt/homebrew/bin'), Path('/usr/local/bin')]
    pk = Path(os.environ.get('LOCALAPPDATA', home / 'AppData' / 'Local')) / 'Microsoft' / 'WinGet' / 'Packages'
    if pk.exists():
        cands += sorted(pk.glob('Gyan.FFmpeg*/ffmpeg-*/bin'))
    exe = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
    return [d for d in cands if (d / exe).exists()]


if not shutil.which('ffmpeg'):
    for _d in find_ffmpeg_dirs():
        os.environ['PATH'] = str(_d) + os.pathsep + os.environ.get('PATH', '')
        break


def need_ffmpeg():
    miss = [x for x in ('ffmpeg', 'ffprobe') if not shutil.which(x)]
    if miss:
        die(f'{", ".join(miss)}을(를) 찾을 수 없습니다. ffmpeg를 설치하고 PATH에 넣어 주세요. (python doctor.py 로 확인)')


def run(args, check=True):
    """명령 실행 → stdout(bytes). 실패하면 stderr 끝부분을 담아 예외."""
    p = subprocess.run([str(a) for a in args], capture_output=True)
    if check and p.returncode:
        raise RuntimeError(p.stderr.decode('utf-8', 'replace')[-3000:])
    return p.stdout


@functools.lru_cache(256)
def probe(path):
    out = run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)])
    return json.loads(out)


IMAGE_EXT = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')


def media_info(path):
    """영상/음성/사진 기본 정보."""
    path = str(path)
    if Path(path).suffix.lower() in IMAGE_EXT:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        return dict(kind='photo', duration=0.0, width=w, height=h, has_video=True, has_audio=False, fps=0.0)
    j = probe(path)
    st = j.get('streams', [])
    v = next((s for s in st if s.get('codec_type') == 'video' and not (s.get('disposition') or {}).get('attached_pic')), None)
    a = next((s for s in st if s.get('codec_type') == 'audio'), None)
    dur = float((j.get('format') or {}).get('duration') or 0)
    fps = 0.0
    if v:
        try:
            n, d = v.get('avg_frame_rate', '0/1').split('/')
            fps = float(n) / float(d) if float(d) else 0.0
        except Exception:
            fps = 0.0
    w, h = (v or {}).get('width', 0), (v or {}).get('height', 0)
    rot = 0
    for sd in (v or {}).get('side_data_list', []) or []:
        if 'rotation' in sd:
            rot = int(sd['rotation'])
    if abs(rot) % 180 == 90:       # 세로로 찍은 휴대폰 영상
        w, h = h, w
    return dict(kind='video' if v else 'audio', duration=dur, width=w, height=h,
                has_video=bool(v), has_audio=bool(a), fps=fps)


def extract_wav16k(src, dst):
    """분석용 16kHz 모노 WAV. 이미 있고 원본보다 새것이면 그대로 쓴다."""
    src, dst = Path(src), Path(dst)
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime and dst.stat().st_size > 1000:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix('.tmp.wav')
    run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', src, '-vn', '-ac', '1', '-ar', '16000',
         '-c:a', 'pcm_s16le', tmp])
    os.replace(tmp, dst)
    return dst


def default_workdir(media):
    """--out 을 안 주면: 원본 옆 '<원본이름>_edit' 폴더."""
    m = Path(media).resolve()
    return m.parent / f'{m.stem}_edit'


# ── Whisper ──────────────────────────────────────────
def cuda_count():
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count()
    except Exception:
        return 0


BACKENDS = ('auto', 'faster', 'mlx')


def mlx_available():
    """Apple Silicon Mac이고 mlx-whisper가 깔려 있으면 True."""
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        return False
    import importlib.util
    return importlib.util.find_spec('mlx_whisper') is not None


def mlx_model_path(model):
    """받아 둔 mlx 모델 폴더(없으면 None). 내려받지 않는다."""
    repo = MLX_REPOS.get(model, model)
    if Path(repo).is_dir():
        return repo
    try:
        from huggingface_hub import snapshot_download
        return snapshot_download(repo, local_files_only=True)
    except Exception:
        return None


def mlx_ready(model='large-v3'):
    """이 컴퓨터에서 그 모델로 mlx(Apple GPU) 받아쓰기를 바로 할 수 있으면 True(rough_cut.py가 모델을 고를 때 쓴다)."""
    return mlx_available() and mlx_model_path(model) is not None


def pick_backend(backend='auto'):
    """auto → Apple Silicon Mac에 mlx-whisper가 있으면 mlx(GPU), 아니면 faster(CPU·CUDA)."""
    if backend == 'auto':
        return 'mlx' if mlx_available() else 'faster'
    if backend == 'mlx' and not mlx_available():
        print('[안내] mlx-whisper(Apple GPU)를 쓸 수 없어 faster-whisper로 받아씁니다(pip install mlx-whisper, Apple Silicon Mac만).', flush=True)
        return 'faster'
    return backend


def load_whisper(model='large-v3', device='auto', compute_type=None, backend='faster', cpu_threads=0):
    """faster-whisper 모델. GPU(CUDA)가 없거나 실패하면 CPU int8로 자동 전환.
    backend='mlx'(또는 auto로 고른 mlx)면 Apple GPU(Metal)로 도는 mlx-whisper를 같은 모양(model.transcribe)으로 감싸서 돌려준다.
    mlx를 불러오지 못하면 faster-whisper로 돌아간다(돌려주는 dev가 'mlx'가 아니게 됨).
    cpu_threads: CPU로 돌 때 쓸 스레드 수(0이면 faster-whisper 기본값 4)."""
    if pick_backend(backend) == 'mlx':
        try:
            return MlxWhisper(model), 'mlx'
        except Exception as e:
            print(f'[주의] mlx-whisper 준비 실패: {str(e)[:200]} → faster-whisper(CPU)로 받아씁니다.', flush=True)
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        die('faster-whisper 가 없습니다. pip install -r requirements.txt 를 먼저 실행해 주세요.')
    import numpy as np
    tries = []
    if device in ('auto', 'cuda'):
        if cuda_count() > 0:
            tries.append(('cuda', compute_type or 'float16'))
        else:
            tip = ' Apple Silicon Mac이면 --backend mlx(GPU)가 훨씬 빠릅니다.' if platform.machine() == 'arm64' and platform.system() == 'Darwin' else ''
            print('[안내] CUDA GPU를 찾지 못해 CPU(int8)로 받아씁니다. 느릴 수 있습니다(긴 영상은 --model medium 권장).' + tip, flush=True)
    tries.append(('cpu', compute_type if (compute_type and device == 'cpu') else 'int8'))
    last = None
    for dev, ct in tries:
        try:
            m = WhisperModel(model, device=dev, compute_type=ct, cpu_threads=cpu_threads)
            # 짧은 무음으로 한 번 돌려 본다(cuDNN 등 GPU 라이브러리 문제를 여기서 잡는다)
            list(m.transcribe(np.zeros(16000, np.float32), language='ko', beam_size=1, vad_filter=False)[0])
            print(f'Whisper {model} · {dev} · {ct}', flush=True)
            return m, dev
        except Exception as e:
            last = e
            print(f'[주의] Whisper {dev}/{ct} 준비 실패: {str(e)[:200]} → 다른 방식으로 다시 시도', flush=True)
    die(f'Whisper 모델을 불러오지 못했습니다: {last}')


MLX_REPOS = {'large-v3': 'mlx-community/whisper-large-v3-mlx', 'large-v3-turbo': 'mlx-community/whisper-large-v3-turbo',
             'turbo': 'mlx-community/whisper-large-v3-turbo', 'medium': 'mlx-community/whisper-medium-mlx',
             'small': 'mlx-community/whisper-small-mlx', 'base': 'mlx-community/whisper-base-mlx',
             'tiny': 'mlx-community/whisper-tiny-mlx'}


def vad_clips(x, vad_parameters=None, join=2.0, sr=16000):
    """silero VAD(faster-whisper에 든 것)로 말소리 구간을 찾아 [시작, 끝, 시작, 끝, ...](초)로 돌려준다.
    join초보다 짧은 쉼은 이어 붙인다(구간마다 30초 창을 하나씩 쓰므로 너무 잘게 나누면 느려진다)."""
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    ts = get_speech_timestamps(x, VadOptions(**(vad_parameters or {})), sampling_rate=sr)
    out = []
    for t in ts:
        a, b = t['start'] / sr, t['end'] / sr
        if out and a - out[-1] < join:
            out[-1] = b
        else:
            out += [a, b]
    return out


def has_speech(au, sr=16000):
    """-40dB 넘는 소리가 0.25초 이상 있으면 True(말소리가 든 구간)."""
    import numpy as np
    hop = sr // 100
    n = len(au) // hop
    if not n:
        return False
    e = 20 * np.log10(np.sqrt((au[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    return (e > -40).sum() >= 25


class MlxWhisper:
    """mlx-whisper(Apple GPU·Metal)를 faster-whisper의 model.transcribe와 같은 모양으로 쓰게 하는 감싸개.
    - 빔 검색이 없어 beam_size는 무시하고 항상 탐욕(greedy) 디코딩을 한다.
    - vad_filter=True면 silero VAD로 찾은 말소리 구간만 clip_timestamps로 받아쓴다. faster-whisper처럼 무음을 잘라
      이어 붙이지 않으므로, 쉼 앞뒤 낱말이 다른 문장 끝으로 몇 초씩 옮겨 가는 일이 없다."""

    def __init__(self, model):
        import mlx_whisper
        import numpy as np
        self.mw, self.model_name = mlx_whisper, model
        repo = MLX_REPOS.get(model, model)
        self.repo = mlx_model_path(model)      # 이 컴퓨터에 받아 둔 모델만 쓴다(몰래 수 GB를 내려받지 않게)
        if not self.repo:
            raise RuntimeError(f'mlx 모델 {repo} 이(가) 이 컴퓨터에 없습니다(large-v3 약 3GB, medium 약 1.5GB). 쓰려면 한 번 받아 두세요: '
                               f'python -c "from huggingface_hub import snapshot_download as d; d(\'{repo}\')"')
        list(self.transcribe(np.zeros(16000, np.float32), language='ko')[0])   # 불러오기·Metal 준비(실패하면 예외)
        print(f'Whisper {model} · mlx(Apple GPU) · {repo}', flush=True)

    def transcribe(self, audio, language=None, beam_size=None, condition_on_previous_text=True, initial_prompt=None,
                   word_timestamps=False, vad_filter=False, vad_parameters=None, temperature=None, **_):
        from types import SimpleNamespace as NS
        import numpy as np
        if not isinstance(audio, np.ndarray):
            import soundfile as sf
            audio, sr = sf.read(str(audio), dtype='float32', always_2d=True)
            if sr != 16000:
                die(f'mlx 받아쓰기는 16kHz 음성만 받습니다({sr}Hz).')
            audio = audio.mean(1)
        clips = '0'
        if vad_filter:
            clips = vad_clips(audio, vad_parameters) or [0.0, 0.0]
        kw = dict(path_or_hf_repo=self.repo, language=language, word_timestamps=word_timestamps,
                  condition_on_previous_text=condition_on_previous_text, initial_prompt=initial_prompt,
                  clip_timestamps=clips, verbose=None, **({} if temperature is None else dict(temperature=temperature)))
        r = self.mw.transcribe(audio.astype(np.float32), **kw)
        segs = []
        for s in r.get('segments', []):
            ws = s.get('words') or []
            a0, a1 = (ws[0]['start'], ws[-1]['end']) if ws else (s['start'], s['end'])
            if too_short_to_say(a0, a1, s['text']) and is_hallucination(s['text']):
                continue        # 클립 끝에 0.1초로 욱여넣은 "다음 영상에서 만나요." 같은 문장(이것 때문에 cut_plan이 클립 글 전체를 지웠다)
            words = None
            if word_timestamps:
                ws = s.get('words', [])
                words = [NS(start=w['start'], end=w['end'], word=w['word'], probability=w.get('probability', 0.0))
                         for w in ws if not fake_signoff(w['start'], w['end'], w['word'])]
                if len(words) < len(ws):
                    s = dict(s, text=''.join(w.word for w in words))
                if not words:
                    continue
            segs.append(NS(start=s['start'], end=s['end'], text=s['text'], no_speech_prob=s.get('no_speech_prob', 0.0),
                           avg_logprob=s.get('avg_logprob', 0.0), temperature=s.get('temperature', 0.0), words=words))
        return iter(segs), NS(language=r.get('language', language), duration=len(audio) / 16000)


def snap_word_starts(W, x, gap=0.2, sr=16000):
    """낱말 [시작, 끝, 글] 안에 gap초 넘는 무음이 있으면 시작을 그 무음 끝으로 옮긴다. 옮긴 수를 돌려준다.
    Whisper 낱말 시각은 쉼 뒤 첫 낱말의 시작을 앞 낱말 끝에 붙여 버려(한 낱말이 1~3초가 됨) 자막이 말보다 먼저 뜬다.
    무음 기준은 cut_plan과 같다(-60dB, 바닥 잡음이 크면 바닥+6dB)."""
    import numpy as np
    hop = sr // 100
    n = len(x) // hop
    e = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12))
    floor = float(np.percentile(e, 5))
    q = e <= (-60.0 if floor <= -66 else min(-35.0, floor + 6))
    need, moved = int(round(gap * 100)), 0
    for w in W:
        i0, i1 = int(w[0] * 100), int(w[1] * 100)
        seg, run, last = q[i0:i1], 0, None
        for k, v in enumerate(seg):
            run = run + 1 if v else 0
            if run >= need and k + 1 < len(seg) - 5:      # 낱말 끝 0.05초 안의 무음은 보지 않는다
                last = k + 1
        if last is not None:
            while last < len(seg) and seg[last]:
                last += 1
            w[0] = round(max(w[0], (i0 + last) / 100 - 0.02), 3)
            moved += 1
    return moved


def pack_transcribe(model, items, max_win=28.0, gap=1.0, min_gap=30.0, label='묶음', **kw):
    """짧은 구간 여러 개를 30초 창 하나에 무음을 두고 이어 붙여 한 번에 받아쓴 뒤, 낱말 시각으로 구간마다 다시 나눈다.
    Whisper는 0.3초 조각도 30초 창으로 처리하므로, 창 수가 줄어드는 만큼 빨라진다.
    items: [(key, 소리, offset, t0, t1)] — 소리는 앞뒤 여유까지 붙인 16kHz 배열, offset은 소리 첫 샘플의 출력 시각,
           t0~t1은 원본 시각(같은 창에 넣을지 정할 때만 쓴다).
    → {key: [[시작, 끝, 낱말], ...]} (offset을 더한 시각, 그 구간 소리 밖으로 나가지 않게 자름)
    - 한 창에는 원본에서 min_gap초 이상 떨어진 구간만 넣는다. 가까운 다시 말하기를 한 창에 넣으면 Whisper가
      둘을 한 번으로 합쳐 버리기 때문이다(조각을 따로 받아쓰는 이유와 같다). 겹치는 구간도 같은 창에 들어가지 않는다.
    - 낱말은 끝 시각이 든 구간에 준다. Whisper 낱말 시각은 쉼 뒤 첫 낱말의 시작을 앞 낱말 끝에 붙여 버리므로
      (예: 유튜브도[3.48-7.48]) 가운데 시각으로 나누면 앞 구간으로 넘어간다. 끝 시각은 실제와 가깝다.
      어느 구간 소리에도 들지 않는 낱말(구간 사이·창 끝 무음에서 지어낸 "감사합니다." 등)은 버린다.
    - 말소리(-40dB 넘는 소리가 0.25초 이상)가 든 구간과 숨·잡음뿐인 구간은 다른 창에 넣는다. 잡음 구간이 이어지면
      Whisper가 "다음 영상에서 만나요." 같은 말을 지어낸 뒤 창의 나머지를 건너뛰어 뒤 구간의 말을 통째로 잃기 때문이다.
      그래도 말소리 구간에 낱말이 하나도 안 나오면 그 구간만 따로 다시 받아쓴다.
    - max_win초보다 긴 구간은 혼자 받아쓴다. kw는 model.transcribe에 그대로 넘긴다."""
    import bisect
    import numpy as np
    sr = 16000

    wins = []
    for key, au, off, t0, t1 in sorted(items, key=lambda it: it[3]):
        d, lo = len(au) / sr, has_speech(au)
        w = None
        if d <= max_win:
            w = next((w for w in wins if not w['solo'] and w['loud'] == lo and w['n'] + gap + d <= max_win
                      and t0 - w['last'] >= min_gap), None)
        if w is None:
            w = dict(parts=[], n=-gap, last=-1e9, solo=d > max_win, loud=lo)
            wins.append(w)
        w['parts'].append((key, au, off, w['n'] + gap, d))
        w['n'] += gap + d
        w['last'] = max(w['last'], t1)
    out = {}
    t0 = time.time()
    retry = 0
    z = np.zeros(int(round(gap * sr)), np.float32)
    for wi, w in enumerate(wins, 1):
        P = w['parts']
        buf = []
        for i, p in enumerate(P):
            if i:
                buf.append(z)
            buf.append(p[1].astype(np.float32))
        segs, _ = model.transcribe(np.concatenate(buf), word_timestamps=True, **kw)
        ws = [(x.start, x.end, x.word) for s in segs for x in (s.words or [])]
        cuts = [(P[i][3] + P[i][4] + P[i + 1][3]) / 2 for i in range(len(P) - 1)]   # 구간 사이 무음 한가운데
        got = {p[0]: [] for p in P}
        for s, e, word in ws:
            r = e - min(0.15, (e - s) / 2)
            i = bisect.bisect_right(cuts, r)
            key, _, off, pos, d = P[i]
            if not pos - 0.3 <= r <= pos + d + 0.3:
                continue
            s2, e2 = min(max(s - pos, 0.0), d), min(max(e - pos, 0.0), d)
            got[key].append([round(off + s2, 3), round(off + e2, 3), word])
        if w['loud'] and len(P) > 1:
            for key, au, off, pos, d in P:
                if not got[key]:              # 창에서 빠진 말소리 구간은 따로
                    segs, _ = model.transcribe(au.astype(np.float32), word_timestamps=True, **kw)
                    got[key] = [[round(off + x.start, 3), round(off + x.end, 3), x.word] for s in segs for x in (s.words or [])]
                    retry += 1
        out.update(got)
        if wi % 10 == 0 or wi == len(wins):
            print(f'  {label} 받아쓰기 창 {wi}/{len(wins)} (구간 {sum(len(v["parts"]) for v in wins[:wi])}/{len(items)}개'
                  + (f', 따로 다시 {retry}개' if retry else '') + f') · {time.time() - t0:.0f}초', flush=True)
    return out


def norm_text(s):
    """비교용: 한글·영문·숫자만 남긴다."""
    return re.sub(r'[^0-9A-Za-z가-힣]', '', s or '')


# 무음·잡음에서 Whisper가 지어내는 문장들(유튜브 자막 학습 흔적)
HALLU_EXACT = {'감사합니다', '네감사합니다', '시청해주셔서감사합니다', '구독과좋아요부탁드립니다',
               'MBC뉴스이덕영입니다', '자막제공배달의민족', '다음영상에서만나요', '고맙습니다'}
HALLU_PART = ('시청해주셔서', '구독과좋아요', '배달의민족', '다음영상에서만나', '자막제공', 'MBC뉴스',
              '이덕영입니다', '한글자막', '자막by', '그대로적어', '반복하면반복')


SIGNOFF = {'감사합니다', '고맙습니다', '시청해주셔서감사합니다'}


def too_short_to_say(start, end, text):
    """글자당 0.08초보다 짧다(사람이 그 길이로 말할 수 없다)."""
    return end - start < 0.08 * max(1, len(re.findall('[가-힣]', text)))


def fake_signoff(start, end, word):
    """mlx(greedy) large-v3는 클립 끝에 "감사합니다."를 붙이곤 한다(17분 영상 시험에서 14곳). 그 낱말은 0.02~0.3초에
    욱여넣어져 사람이 말할 수 없는 길이다(실제 "감사합니다"는 0.5초 넘음) → 글자당 0.08초보다 짧으면 지어낸 것으로 본다."""
    return norm_text(word) in SIGNOFF and too_short_to_say(start, end, word)


def is_hallucination(text, prompt='', exact_too=True):
    n = norm_text(text)
    if not n:
        return False
    if exact_too and n in HALLU_EXACT:
        return True
    if any(h in n for h in HALLU_PART):
        return True
    p = norm_text(prompt)
    if p and len(n) >= 8:
        if n in p or difflib.SequenceMatcher(None, n, p[:len(n) + 10]).ratio() >= 0.75:
            return True       # initial_prompt를 그대로 읊은 것
    return False


# ── CapCut ───────────────────────────────────────────
def capcut_candidates():
    home = Path.home()
    c = []
    la = os.environ.get('LOCALAPPDATA')
    if la:
        c += [Path(la) / 'CapCut' / 'User Data' / 'Projects' / 'com.lveditor.draft',
              Path(la) / 'JianyingPro' / 'User Data' / 'Projects' / 'com.lveditor.draft']
    c += [home / 'Movies' / 'CapCut' / 'User Data' / 'Projects' / 'com.lveditor.draft',
          home / 'Library' / 'Containers' / 'com.lemon.lvoverseas' / 'Data' / 'Movies' / 'CapCut' / 'User Data' / 'Projects' / 'com.lveditor.draft']
    return c


def find_capcut_dir(arg=None, required=True):
    if arg:
        p = Path(arg).expanduser()
        if p.is_dir():
            return p
        if required:
            die(f'--capcut-dir 폴더가 없습니다: {p}')
        return None
    for p in capcut_candidates():
        if p.is_dir():
            return p
    if required:
        die('CapCut 프로젝트 폴더를 찾지 못했습니다. CapCut을 한 번 실행해 프로젝트를 만든 뒤 다시 하거나 --capcut-dir 로 직접 알려 주세요.\n'
            '  Windows 기본: %LOCALAPPDATA%\\CapCut\\User Data\\Projects\\com.lveditor.draft\n'
            '  Mac 기본: ~/Movies/CapCut/User Data/Projects/com.lveditor.draft')
    return None


def capcut_running():
    """CapCut(또는 JianyingPro)이 켜져 있으면 True."""
    sysname = platform.system()
    try:
        if sysname == 'Windows':
            out = subprocess.run(['tasklist', '/NH'], capture_output=True).stdout.decode('utf-8', 'replace').lower()
            return 'capcut.exe' in out or 'jianyingpro.exe' in out
        if sysname == 'Darwin':
            # 앱 실행 파일로 시작하는 프로세스만 본다. 명령줄에 'CapCut.app' 글자만 든 셸·편집기까지 켜진 것으로 보던 오탐 방지.
            r = subprocess.run(['pgrep', '-f', r'^[^ ]*\.app/Contents/MacOS/(CapCut|VideoFusion)'], capture_output=True)
            return r.returncode == 0
    except Exception as e:
        print(f'[주의] CapCut이 켜져 있는지 확인하지 못했습니다({str(e)[:80]}). CapCut을 완전히 껐는지 직접 확인해 주세요.')
        return False
    return False


DRAFT_FILES = ('draft_content.json', 'draft_info.json')    # Windows · Mac(CapCut 9.x)


def draft_file(folder):
    """프로젝트 폴더의 타임라인 파일. Windows는 draft_content.json, Mac CapCut 9.x는 draft_info.json. 없으면 None."""
    for n in DRAFT_FILES:
        if (Path(folder) / n).is_file():
            return Path(folder) / n
    return None


def capcut_platform():
    return 'mac' if platform.system() == 'Darwin' else 'windows'


CAPCUT_MEDIA = Path.home() / 'Movies' / 'CapCut_편집미디어'


def capcut_media(path):
    """CapCut 프로젝트에 넣을 미디어 경로. Mac CapCut은 샌드박스 앱이라 사용자가 CapCut에서 고른 파일과 ~/Movies 안만 읽는다.
    그 밖의 파일은 ~/Movies/CapCut_편집미디어/ 에 APFS 복제(공간을 더 쓰지 않음, 안 되면 복사)해 그 경로를 쓴다.
    이름에 원본 경로·크기·수정 시각의 해시를 붙여, 원본이 바뀌면 새 파일로 복제하고 이미 쓰는 파일은 덮어쓰지 않는다."""
    path = Path(unicodedata.normalize('NFC', str(Path(path).resolve())))
    if platform.system() != 'Darwin':
        return path
    movies = Path(unicodedata.normalize('NFC', str((Path.home() / 'Movies').resolve())))
    if path.is_relative_to(movies):
        return path
    st = path.stat()
    h = hashlib.sha1(f'{path}|{st.st_size}|{st.st_mtime_ns}'.encode()).hexdigest()[:8]
    dst = CAPCUT_MEDIA / f'{path.stem}_{h}{path.suffix}'
    if dst.exists() and dst.stat().st_size == st.st_size:
        return dst
    CAPCUT_MEDIA.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + '.part')
    if subprocess.run(['cp', '-c', str(path), str(tmp)], capture_output=True).returncode != 0:
        shutil.copy2(path, tmp)
    os.replace(tmp, dst)
    print(f'[CapCut 미디어] {path.name} → {dst} (Mac CapCut은 ~/Movies 밖 파일을 못 읽어 복제)')
    return dst


def list_projects(cc):
    return sorted([p.name for p in Path(cc).iterdir() if p.is_dir() and draft_file(p)])


def resolve_project(arg, cc_arg=None):
    """프로젝트 이름, 프로젝트 폴더, 또는 draft_content.json(Mac: draft_info.json) 경로 → 프로젝트 폴더."""
    p = Path(arg).expanduser()
    if p.is_file() and p.suffix.lower() in ('.json', '.tmp'):
        return p.parent
    if p.is_dir() and draft_file(p):
        return p
    cc = find_capcut_dir(cc_arg)
    q = cc / arg
    if draft_file(q):
        return q
    names = list_projects(cc)
    near = difflib.get_close_matches(arg, names, n=5, cutoff=0.4)
    die(f'CapCut 프로젝트 "{arg}"를 찾지 못했습니다.' + (f' 비슷한 이름: {", ".join(near)}' if near else '')
        + f'\n  찾은 위치: {cc}')


def read_draft(path):
    """draft_content.json(Mac: draft_info.json) 읽기. 암호화된 버전이면 알기 쉬운 메시지로 멈춘다."""
    raw = Path(path).read_bytes()
    try:
        return json.loads(raw.decode('utf-8-sig'))
    except Exception:
        die(f'{path} 를 JSON으로 읽을 수 없습니다. 이 CapCut 버전은 프로젝트 파일을 암호화해 저장하는 것 같습니다.\n'
            '  이 경우 CapCut 조립·자막 시간 수정은 쓸 수 없고, 받아쓰기·컷 목록·SRT 자막은 쓸 수 있습니다.')


def material_index(d):
    return {m['id']: (k, m) for k, v in d.get('materials', {}).items() if isinstance(v, list)
            for m in v if isinstance(m, dict) and 'id' in m}


def now_us():
    return int(time.time() * US)


# ── 채널 프로필(profile.md) ──
def load_profile(root=None):
    """작업 폴더 루트의 profile.md(채널 프로필)에서 `키: 값` 줄을 읽는다. 없거나 비면 {}.

    위치: 환경변수 CHANNEL_PROFILE > <root>/profile.md (root 기본: PROJECT_ROOT 또는 현재 폴더).
    `<…>`로 남은 자리표시와 빈 값은 없는 것으로 본다. 키 목록은 claude-edit references/profile.template.md.
    """
    import os as _os
    import re as _re
    from pathlib import Path as _Path
    path = _os.environ.get('CHANNEL_PROFILE') or str(_Path(root or _os.environ.get('PROJECT_ROOT') or _os.getcwd()) / 'profile.md')
    try:
        text = _Path(path).read_text(encoding='utf-8')
    except OSError:
        return {}
    out = {}
    for line in text.splitlines():
        m = _re.match(r'^\s*[-*]?\s*`?([A-Za-z][A-Za-z0-9_]*)`?\s*:\s*(.*?)\s*$', line)
        if not m:
            continue
        val = m.group(2).strip().strip('`').strip()
        if val and not (val.startswith('<') and val.endswith('>')):
            out[m.group(1)] = val
    return out


TEMPO = {   # 컷 템포 → tighten.py 쉼 줄이기 값(이보다 긴 쉼을, 앞말 뒤 + 뒷말 앞만 남김)
    '촘촘': ['--gap', '0.25', '--keep-out', '0.08', '--keep-in', '0.07'],
    '보통': ['--gap', '0.4', '--keep-out', '0.12', '--keep-in', '0.12'],
    '여유': ['--gap', '0.6', '--keep-out', '0.2', '--keep-in', '0.2'],
}


def tempo_args(root=None):
    """profile.md 의 cut_tempo(촘촘|보통|여유, 기본 보통) → tighten.py 인자."""
    return list(TEMPO.get(load_profile(root).get('cut_tempo', '보통'), TEMPO['보통']))


def theme_pairs(root=None):
    """모션 카드·목차 전환 HTML에 넘길 스타일(theme_accent·theme_accent2·theme_font). 프로필에 없으면 빈 dict."""
    p = load_profile(root)
    pick = lambda *ks: next((p[k] for k in ks if p.get(k)), None)
    out = {'theme_accent': pick('brand_color_1', 'chapter_color'), 'theme_accent2': pick('brand_color_2'),
           'theme_font': pick('motion_font', 'chapter_font')}
    return {k: v for k, v in out.items() if v}


def theme_query(query, root=None):
    """쿼리 문자열 뒤에 프로필 스타일을 붙인다(이미 준 값은 그대로). 인코딩은 렌더러가 한다."""
    have = {kv.split('=', 1)[0] for kv in str(query or '').split('&') if kv}
    extra = '&'.join('{}={}'.format(k, v) for k, v in theme_pairs(root).items() if k not in have)
    return '&'.join(x for x in (str(query or ''), extra) if x)


def motion_template(root=None):
    """profile.md 의 motion_style: dark(어두운 유리, 원작 cards.html) | light(밝은, cards_channel.html, 기본)."""
    return 'motion/cards.html' if load_profile(root).get('motion_style', 'light').strip().lower() in ('dark', '어두운', '어두운 유리') \
        else 'motion/cards_channel.html'


def korean_font(size, bold=False):
    """연락표용 한글 글꼴(PIL)."""
    import platform as _pf
    from pathlib import Path as _Path
    from PIL import ImageFont as _IF
    s = _pf.system()
    files = ([('/System/Library/Fonts/AppleSDGothicNeo.ttc', 0, 6), ('/System/Library/Fonts/Supplemental/AppleGothic.ttf', 0, 0)] if s == 'Darwin'
             else [('C:/Windows/Fonts/malgun.ttf', 0, 0), ('C:/Windows/Fonts/malgunbd.ttf', 0, 0)] if s == 'Windows'
             else [('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 0, 0), ('/usr/share/fonts/truetype/nanum/NanumGothic.ttf', 0, 0)])
    for path, reg, bd in files:
        if _Path(path).exists():
            try:
                return _IF.truetype(path, size, index=bd if bold else reg)
            except OSError:
                continue
    return _IF.load_default()


def profile_on(key, default=True, root=None):
    """profile.md 의 '씀/안 씀' 같은 값을 참·거짓으로. 없으면 default."""
    v = load_profile(root).get(key)
    if v is None:
        return default
    return str(v).strip().lower() not in ('안 씀', '안씀', '없음', 'no', 'off', 'false', '0', '안 함', '아니오')



# ── 채널 프로필(profile.md) ──
def load_profile(root=None):
    """작업 폴더 루트의 profile.md(채널 프로필)에서 `키: 값` 줄을 읽는다. 없거나 비면 {}.

    위치: 환경변수 CHANNEL_PROFILE > <root>/profile.md (root 기본: PROJECT_ROOT 또는 현재 폴더).
    `<…>`로 남은 자리표시와 빈 값은 없는 것으로 본다. 키 목록은 claude-edit references/profile.template.md.
    """
    import os as _os
    import re as _re
    from pathlib import Path as _Path
    path = _os.environ.get('CHANNEL_PROFILE') or str(_Path(root or _os.environ.get('PROJECT_ROOT') or _os.getcwd()) / 'profile.md')
    try:
        text = _Path(path).read_text(encoding='utf-8')
    except OSError:
        return {}
    out = {}
    for line in text.splitlines():
        m = _re.match(r'^\s*[-*]?\s*`?([A-Za-z][A-Za-z0-9_]*)`?\s*:\s*(.*?)\s*$', line)
        if not m:
            continue
        val = m.group(2).strip().strip('`').strip()
        if val and not (val.startswith('<') and val.endswith('>')):
            out[m.group(1)] = val
    return out


TEMPO = {   # 컷 템포 → tighten.py 쉼 줄이기 값(이보다 긴 쉼을, 앞말 뒤 + 뒷말 앞만 남김)
    '촘촘': ['--gap', '0.25', '--keep-out', '0.08', '--keep-in', '0.07'],
    '보통': ['--gap', '0.4', '--keep-out', '0.12', '--keep-in', '0.12'],
    '여유': ['--gap', '0.6', '--keep-out', '0.2', '--keep-in', '0.2'],
}


def tempo_args(root=None):
    """profile.md 의 cut_tempo(촘촘|보통|여유, 기본 보통) → tighten.py 인자."""
    return list(TEMPO.get(load_profile(root).get('cut_tempo', '보통'), TEMPO['보통']))


def theme_pairs(root=None):
    """모션 카드·목차 전환 HTML에 넘길 스타일(theme_accent·theme_accent2·theme_font). 프로필에 없으면 빈 dict."""
    p = load_profile(root)
    pick = lambda *ks: next((p[k] for k in ks if p.get(k)), None)
    out = {'theme_accent': pick('brand_color_1', 'chapter_color'), 'theme_accent2': pick('brand_color_2'),
           'theme_font': pick('motion_font', 'chapter_font')}
    return {k: v for k, v in out.items() if v}


def theme_query(query, root=None):
    """쿼리 문자열 뒤에 프로필 스타일을 붙인다(이미 준 값은 그대로). 인코딩은 렌더러가 한다."""
    have = {kv.split('=', 1)[0] for kv in str(query or '').split('&') if kv}
    extra = '&'.join('{}={}'.format(k, v) for k, v in theme_pairs(root).items() if k not in have)
    return '&'.join(x for x in (str(query or ''), extra) if x)


def motion_template(root=None):
    """profile.md 의 motion_style: dark(어두운 유리, 원작 cards.html) | light(밝은, cards_channel.html, 기본)."""
    return 'motion/cards.html' if load_profile(root).get('motion_style', 'light').strip().lower() in ('dark', '어두운', '어두운 유리') \
        else 'motion/cards_channel.html'


def korean_font(size, bold=False):
    """연락표용 한글 글꼴(PIL)."""
    import platform as _pf
    from pathlib import Path as _Path
    from PIL import ImageFont as _IF
    s = _pf.system()
    files = ([('/System/Library/Fonts/AppleSDGothicNeo.ttc', 0, 6), ('/System/Library/Fonts/Supplemental/AppleGothic.ttf', 0, 0)] if s == 'Darwin'
             else [('C:/Windows/Fonts/malgun.ttf', 0, 0), ('C:/Windows/Fonts/malgunbd.ttf', 0, 0)] if s == 'Windows'
             else [('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 0, 0), ('/usr/share/fonts/truetype/nanum/NanumGothic.ttf', 0, 0)])
    for path, reg, bd in files:
        if _Path(path).exists():
            try:
                return _IF.truetype(path, size, index=bd if bold else reg)
            except OSError:
                continue
    return _IF.load_default()


def profile_on(key, default=True, root=None):
    """profile.md 의 '씀/안 씀' 같은 값을 참·거짓으로. 없으면 default."""
    v = load_profile(root).get(key)
    if v is None:
        return default
    return str(v).strip().lower() not in ('안 씀', '안씀', '없음', 'no', 'off', 'false', '0', '안 함', '아니오')
