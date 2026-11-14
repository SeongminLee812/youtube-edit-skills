"""무거운 계산(렌더·받아쓰기) 중임을 알리는 표시 파일 도우미입니다. 직접 실행하지 않습니다.

프로젝트 루트의 .edit_busy 가 있으면 백그라운드 작업(받아쓰기 속도 시험 등)이 기다린다.
표시가 없을 때만 만들고, 끝나면(오류가 나도) 내가 만든 표시만 지운다. 다른 작업이 먼저 만든 표시는 그대로 둔다.

사용 예:
  from _busy import busy
  with busy('chapter_frost 렌더'):
      ...
"""
import contextlib
import os
import time
from pathlib import Path

ROOT = Path(os.environ.get('PROJECT_ROOT') or os.getcwd()).resolve()     # 프로젝트 루트(PROJECT_ROOT 또는 작업 폴더)
FLAG = ROOT / '.edit_busy'


@contextlib.contextmanager
def busy(what):
    mine = False
    try:
        with open(FLAG, 'x', encoding='utf-8') as f:
            f.write(f'{what} · pid {os.getpid()} · {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
        mine = True
    except FileExistsError:
        print(f'[안내] {FLAG.name} 가 이미 있습니다(다른 무거운 작업 중). 표시는 그대로 두고 진행합니다.', flush=True)
    try:
        yield mine
    finally:
        if mine:
            try:
                FLAG.unlink()
            except FileNotFoundError:
                pass
