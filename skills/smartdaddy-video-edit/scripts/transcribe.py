"""녹화본 전체를 단어 시각까지 받아씁니다(faster-whisper).

결과(--out 폴더):
  words.json      [[시작초, 끝초, "단어"], ...]   ← 자막·검색에 쓴다
  segments.json   문장 덩어리(시작·끝·텍스트·신뢰도)
  transcript.txt  사람이 읽는 받아쓰기([분:초] 문장)
  audio16k.wav    분석용 16kHz 모노 음성

사용 예:
  python transcribe.py 녹화.mp4
  python transcribe.py 녹화.mp4 --out 편집/01_asr --prompt "클로드, 캡컷, 제미나이, 오퍼스"
  python transcribe.py 녹음.wav --model medium --device cpu     # GPU가 없을 때 빠르게
  python transcribe.py 녹화.mp4 --backend faster                 # 예전 방식(faster-whisper, CPU·CUDA) 그대로

알아 둘 것:
- GPU(CUDA)가 없으면 자동으로 CPU int8로 돌린다. large-v3 는 CPU에서 영상 길이의 1~3배쯤 걸린다.
- 기본(--backend auto): Apple Silicon Mac에 mlx-whisper가 있고 모델을 받아 두었으면 Apple GPU(mlx)로, 아니면 faster-whisper로.
  mlx는 빔 검색이 없어 greedy로 받아쓰고, 무음을 잘라 이어 붙이지 않고 VAD로 찾은 말소리 구간만 받아쓴다(--vad-clips 와 같음).
- --vad-clips: faster-whisper의 VAD는 무음을 잘라 이어 붙인 소리를 받아쓴 뒤 시각을 되돌리는데, 쉼 바로 뒤 낱말이
  앞 덩어리 끝으로 몇 초씩 앞당겨지는 일이 생긴다(17분 영상 시험: 낱말 55개가 2초 넘게 앞당겨짐).
  이 옵션은 말소리 구간을 그대로 두고 그 안만 받아써서 이 문제를 막는다.
- --prompt 에는 영상에 나오는 고유명사만 쉼표로 짧게 넣는다. 길게 넣으면 Whisper가 그 문장을 그대로 읊는 환각이 생긴다(자동으로 걸러 낸다).
- "구독과 좋아요", "시청해 주셔서 감사합니다" 같은 무음 구간 환각 문장은 자동으로 뺀다.
- GPU 메모리가 8GB 정도면 Whisper는 한 번에 하나만 돌린다(여러 개 동시에 돌리지 않는다).
"""
import argparse
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True      # 스킬 폴더에 __pycache__ 를 만들지 않는다
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description='녹화본 단어 단위 받아쓰기')
    ap.add_argument('media', help='영상 또는 음성 파일')
    ap.add_argument('--out', help='결과 폴더(기본: 원본 옆 <이름>_edit)')
    ap.add_argument('--model', default='large-v3', help='Whisper 모델(large-v3, medium, small ...)')
    ap.add_argument('--device', default='auto', choices=['auto', 'cuda', 'cpu'])
    ap.add_argument('--compute-type', default=None, help='예: float16, int8_float16, int8 (기본: GPU float16 / CPU int8)')
    ap.add_argument('--prompt', default='', help='고유명사 힌트(쉼표로 구분, 짧게)')
    ap.add_argument('--lang', default='ko', help='언어 코드(기본 ko)')
    ap.add_argument('--backend', default='auto', choices=C.BACKENDS,
                    help='auto(기본): Apple Silicon Mac에 mlx-whisper가 있으면 mlx(GPU), 없거나 실패하면 faster · '
                         'faster: faster-whisper(CPU·CUDA, 예전 방식) · mlx: Apple GPU(빔 검색 없음)')
    ap.add_argument('--vad-clips', action='store_true',
                    help='무음을 잘라 이어 붙이지 않고 말소리 구간만 받아쓰기(쉼 앞뒤 낱말 시각 밀림 방지, mlx는 늘 이렇게 함)')
    ap.add_argument('--threads', type=int, default=0, help='CPU 스레드 수(0=faster-whisper 기본 4)')
    a = ap.parse_args()

    C.need_ffmpeg()
    media = Path(a.media).resolve()
    if not media.exists():
        C.die(f'파일이 없습니다: {media}')
    info = C.media_info(media)
    if not C.probe(str(media)).get('streams') or not info['has_audio']:
        C.die('이 파일에는 소리 트랙이 없습니다. 목소리가 들어 있는 파일을 주세요.')
    out = Path(a.out).resolve() if a.out else C.default_workdir(media)
    out.mkdir(parents=True, exist_ok=True)
    wav = C.extract_wav16k(media, out / 'audio16k.wav')
    print(f'원본 {media.name} · {C.mmss(info["duration"])} → {out}', flush=True)

    model, dev = C.load_whisper(a.model, a.device, a.compute_type, a.backend, a.threads)
    t0 = time.time()
    vad = dict(min_silence_duration_ms=400, speech_pad_ms=150)
    kw = dict(language=a.lang, word_timestamps=True, beam_size=5, condition_on_previous_text=False,
              initial_prompt=a.prompt or None)
    if a.vad_clips and dev != 'mlx':
        import soundfile as sf
        x, _ = sf.read(str(wav), dtype='float32', always_2d=True)
        segs, _ = model.transcribe(x.mean(1), vad_filter=False, clip_timestamps=C.vad_clips(x.mean(1), vad) or [0.0, 0.0], **kw)
    else:
        segs, _ = model.transcribe(str(wav), vad_filter=True, vad_parameters=vad, **kw)
    S, W, dropped = [], [], []
    for s in segs:
        text = s.text.strip()
        why = ''
        if C.is_hallucination(text, a.prompt, exact_too=False):
            why = '환각 문구'
        elif C.norm_text(text) in C.HALLU_EXACT and (s.no_speech_prob > 0.3 or s.avg_logprob < -0.7):
            why = '무음 구간 인사말'
        elif s.no_speech_prob > 0.6 and s.avg_logprob < -0.8:
            why = '말소리 아님'
        elif len(S) >= 2 and len(C.norm_text(text)) >= 6 and S[-1]['text'] == text == S[-2]['text']:
            why = '같은 문장 반복(디코딩 루프)'
        if why:
            dropped.append(dict(start=round(s.start, 3), end=round(s.end, 3), text=text, why=why))
            continue
        S.append(dict(start=round(s.start, 3), end=round(s.end, 3), text=text,
                      no_speech=round(s.no_speech_prob, 3), logprob=round(s.avg_logprob, 3)))
        for w in (s.words or []):
            W.append([round(w.start, 3), round(w.end, 3), w.word])
        if len(S) % 50 == 0:
            print(f'  {C.mmss(s.end)}까지 · 문장 {len(S)}개 · {time.time() - t0:.0f}초', flush=True)

    snapped = 0
    if a.vad_clips or dev == 'mlx':            # 쉼 뒤 낱말 시작이 앞 낱말 끝에 붙은 것을 소리 크기로 바로잡는다
        import soundfile as sf
        x, _ = sf.read(str(wav), dtype='float32', always_2d=True)
        snapped = C.snap_word_starts(W, x.mean(1))
    C.write_json(out / 'segments.json', S)
    C.write_json(out / 'words.json', W, compact=True)
    lines = [f'[{C.mmss(s["start"])}-{C.mmss(s["end"])}] {s["text"]}' for s in S]
    (out / 'transcript.txt').write_text('\n'.join(lines) + '\n', 'utf-8')
    C.write_json(out / 'transcribe_meta.json', dict(media=media.as_posix(), duration=info['duration'], model=a.model,
                                                     device=dev, prompt=a.prompt, lang=a.lang, dropped=dropped,
                                                     **(dict(vad_clips=True, snapped_starts=snapped) if a.vad_clips or dev == 'mlx' else {})))
    print(f'완료: 문장 {len(S)}개, 단어 {len(W)}개, 환각으로 뺀 문장 {len(dropped)}개 · {time.time() - t0:.0f}초')
    for d in dropped[:10]:
        print(f'  - 뺌 {C.mmss(d["start"])} "{d["text"][:40]}" ({d["why"]})')
    print(f'  {out / "words.json"}')


if __name__ == '__main__':
    main()
