# 채널 프로필 (profile.md 템플릿)

이 파일을 작업 폴더 루트에 `profile.md`로 복사해 채운다. 처음에는 [onboarding.md](onboarding.md) 순서대로 클로드가 채널 링크나 소개 문서를 읽고, 취향을 몇 개 물어 대신 채운다.

- 형식: 한 줄에 `키: 값`. 스크립트는 이 줄만 읽는다(`<…>`로 남은 값과 빈 값은 없는 것으로 본다).
- 값이 없으면 스크립트는 기본값을 쓴다(컷 템포 보통, 모션 카드 밝은 스타일·키 컬러 `#3B5BDB`, 범퍼 없음).
- 다른 위치에 두려면 환경변수 `CHANNEL_PROFILE=/경로/profile.md`, 작업 폴더를 바꾸려면 `PROJECT_ROOT`.

## 채널 (링크·소개 문서에서 읽음)

channel_name: <채널 이름>
channel_url: <https://www.youtube.com/@핸들 — 소개 문서를 줬으면 비움>
channel_doc: <채널 소개 문서 경로 — 링크를 줬으면 비움>
channel_summary: <채널 소개 한 줄>
typical_length: <예: 8~12분>
tone: <존댓말 | 반말>
old_channel_names: <예전 채널 이름이 있으면 쉼표로. 화면에 나오면 안 되는 이름>

## 취향 (온보딩 질문)

cut_tempo: <촘촘 | 보통 | 여유 | 컷 안 함(이미 편집된 영상)>
capcut_template: <자막 스타일이 든 CapCut 프로젝트 이름>
subtitle_font: <템플릿이 없을 때 글꼴, 예: Pretendard Bold>
subtitle_color: <예: #FFFFFF>
subtitle_outline: <예: #000000>
emphasis: <안 씀 | 적게 | 보통>
sfx: <씀 | 안 씀>
bgm: <씀 | 안 씀>
bgm_file: <배경음 파일(작업 폴더 기준 경로)>
motion: <씀 | 안 씀 — 모션 카드>
motion_style: <dark(어두운 유리) | light(밝은) — 목업에서 고름>
brand_color_1: <키 컬러, 예: #E8590C — 모션 카드·목차 전환>
brand_color_2: <보조색(선택)>
motion_font: <모션 카드 글꼴(선택, 설치된 이름)>
chapter_transition: <씀 | 안 씀>
chapter_color: <목차 전환만 다른 색을 쓸 때(선택). 없으면 brand_color_1>
chapter_font: <목차 전환 글꼴, 비우면 시스템 한글 고딕>

## 필요할 때만

bumper: <채널 범퍼 파일(작업 폴더 기준 경로) | 없음>
asr_prompt: <받아쓰기가 자주 틀리는 고유명사, 쉼표로>
chapter_style: <챕터 표기, 예: "키워드: 답" | 질문형 | 짧은 명사>
subtitle_dictionary: <채널 공용 자막 고침 사전, 기본 subtitle_dictionary.json>
sfx_dir: <효과음 폴더, 기본 sfx(make_sfx.py sfx 로 만듦)>
videos_dir: <영상 폴더들이 모인 곳(작업 폴더 기준), 기본 작업 폴더 바로 아래>
hashtag_table: <해시태그 표가 있는 파일, 기본 profile.md>

### 설명란 해시태그

`upload_pack.py --type <행 이름>`이 아래 표에서 그 행을 읽는다(선택. 표가 없으면 해시태그를 넣지 않는다). `(부위)`처럼 괄호 자리표시가 있으면 `--part` 값으로 바꾼다.

| 영상 종류 | 해시태그(최대 5개) |
|---|---|
| <예: 입문 가이드> | `#<채널키워드>` `#<주제>` `#<주제>입문` |

- 쓰지 않는 해시태그: `#<쓰지 않을 태그>`

## 메모

- 확인일: <YYYY-MM-DD>
- 링크·문서에서 읽은 것과 사용자에게 물어 정한 것을 구분해 적는다.
