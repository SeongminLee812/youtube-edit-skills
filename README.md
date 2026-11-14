# youtube-edit-skills

토킹헤드 유튜브 롱폼을 Claude Code가 **CapCut 프로젝트로 편집**하도록 돕는 에이전트 스킬 세 개입니다. 영상과 채널 정보만 주면, 취향을 몇 개만 물어보고 그에 맞게 컷·자막·강조 자막·효과음·배경음·모션 카드·목차 전환을 넣은 CapCut 프로젝트와 업로드용 설명란·챕터 초안까지 만듭니다. 마무리(전환 효과·내보내기·업로드)는 사람이 CapCut에서 합니다.

## 사용 흐름

1. **영상을 넣는다.** 편집할 영상 파일(필수)과 원고(선택)를 작업 폴더 안 `<영상 이름>/` 폴더에 둡니다.
2. **채널 정보를 넣는다.** 채널 페이지 링크(`https://www.youtube.com/@핸들`) **또는** 채널 소개 문서 하나.
3. **취향 질문에 답한다.** 처음 한 번만, 5개 안팎을 2~3개씩 묻습니다. 답은 작업 폴더의 `profile.md`에 저장되고 다음 영상부터는 다시 묻지 않습니다.
4. **(모션을 쓰면) 목업을 고른다.** 채널 썸네일에서 뽑은 키 컬러 후보 × 스타일(어두운 유리 / 밝은) 조합 3~4개를 카드 4장(챕터 제목·숫자·단계·목차 전환)씩 만든 `mockups.html`에서 하나를 고릅니다.
5. **편집을 맡긴다.** "이 영상 편집해줘" → 러프컷 CapCut 프로젝트 → (사람이 CapCut에서 지루한 구간을 자름) → 강조 자막·효과음·배경음·모션 카드·목차 전환을 그 위에 얹은 새 버전 → 음량 맞추기 → 설명란·챕터 초안.
6. **CapCut에서 마무리한다.** 확인 지점 세 곳(신뢰도 낮은 컷, 강조·목차 목록, 최종 확인)에서만 판단하면 됩니다.

### 취향 질문 (첫 실행)

| # | 질문 | 고를 것(굵게 = 기본값) |
|---|---|---|
| 1 | 컷 템포 | 촘촘 / **보통** / 여유 |
| 2 | 자막 스타일 | 지금 쓰는 CapCut 프로젝트 이름(그 자막 모양을 그대로 씀) 또는 글꼴·색·외곽선 |
| 3 | 강조 자막 | 안 씀 / 적게 / **보통** |
| 4 | 효과음·배경음 | 효과음 **씀**/안 씀, 배경음 씀/**안 씀**(쓰면 파일) |
| 5 | 모션 카드·목차 전환 | **씀**/안 씀. 쓰면 목업(키 컬러 × 어두운 유리/밝은)에서 조합 번호 하나 |

채널 링크로는 채널 이름·최근 영상 제목과 길이·말투·썸네일 색 후보를 읽습니다(`yt-dlp --flat-playlist -J`, 안 되면 웹 페이지, 그것도 안 되면 질문). 소개 문서를 주면 그 문서에서 읽습니다. 자세한 순서는 [onboarding.md](skills/claude-edit/references/onboarding.md), 저장 형식은 [profile.template.md](skills/claude-edit/references/profile.template.md).

### profile.md 예시 (가상의 채널)

```
channel_name: 작은방 홈카페
channel_url: https://www.youtube.com/@example-homecafe
tone: 존댓말
cut_tempo: 보통
capcut_template: 내 자막 템플릿
emphasis: 적게
sfx: 씀
bgm: 안 씀
motion: 씀
motion_style: light
brand_color_1: #E8590C
chapter_transition: 씀
asr_prompt: 드리퍼, 모카포트, 에스프레소
```

## 스킬

| 스킬 | 하는 일 |
|---|---|
| [claude-edit](skills/claude-edit/SKILL.md) | 편집 지휘. 첫 실행 온보딩과 모션 목업(`mockups.py`), 단계 S0~S5와 확인 지점 3곳, 모션 카드 목록 렌더(`motion_cards.py`), 목차 전환(`chapter_frost.py`), 업로드 묶음(설명란·챕터·고정댓글) |
| [smartdaddy-video-edit](skills/smartdaddy-video-edit/SKILL.md) | 편집 엔진. 받아쓰기, 재테이크·쉼 컷, 자막, 강조 자막·효과음·배경음·줌, 모션 카드 템플릿·렌더러, CapCut 조립·덧입히기, 음량 마스터 |
| [youtube-chapter-timestamps](skills/youtube-chapter-timestamps/SKILL.md) | 완성 영상을 받아써 실제 발화 시작 기준의 유튜브 챕터 작성 |

## 설치

1. `skills/` 아래 세 폴더를 `~/.claude/skills/`(모든 프로젝트) 또는 작업 폴더의 `.claude/skills/`에 **나란히** 복사하거나 링크합니다. `claude-edit` 스크립트가 옆 폴더의 `smartdaddy-video-edit/scripts`를 찾습니다.
2. `tools/`는 작업 폴더 루트의 `tools/`에 둡니다(`topic_paths.py`: 영상 폴더 구조와 profile.md 읽기).
3. 스크립트는 **작업 폴더에서** 실행합니다. 다른 곳에서 돌리면 환경변수 `PROJECT_ROOT=<작업 폴더>`, 프로필을 다른 곳에 두면 `CHANNEL_PROFILE=<경로>`.

```
<작업 폴더>/
├─ profile.md                 채널 프로필(첫 실행 때 생성)
├─ tools/topic_paths.py
├─ subtitle_dictionary.json   (선택) 채널 공용 자막 고침 사전
└─ <영상 이름>/
    ├─ 촬영본.mp4 · 원고.txt     원본(읽기만)
    ├─ 편집/                   받아쓰기·컷 계획·HANDOFF·상태 파일
    │   ├─ 화면자료/            목차 전환 MOV
    │   └─ 캡컷_가져오기/        CapCut에 끌어 넣을 파일
    └─ 업로드/                 내보낸 영상·설명란·고정댓글 초안
```

## 필요한 프로그램

- Python 3.10 이상, `pip install -r skills/smartdaddy-video-edit/scripts/requirements.txt`(faster-whisper, numpy, soundfile, Pillow, opencv-python, playwright) 후 `python -m playwright install chromium`(목차 전환 렌더용)
- ffmpeg · ffprobe
- (선택) Apple Silicon Mac GPU 받아쓰기: mlx-whisper
- whisper.cpp(`whisper-cli`)와 다국어 GGML 모델 — youtube-chapter-timestamps. 모델 경로는 `--model` 또는 `WHISPER_MODEL`
- yt-dlp — 채널 정보 읽기, 관련 영상 제목 확인
- CapCut(데스크톱). Mac CapCut 9.x에서 시험했습니다.

## 포함하지 않은 것

- 특정 주제에 묶인 모션 카드 종류(몸 그림·그림 타일·비유 그림, 논문 요약, 기간 구간, 변화 곡선, 고정 댓글)와 논문 인용·픽토그램 모션.
- 이미지 생성(장면 사진·캐릭터시트), 스톡·본인 영상 DB와 B롤 자동 배치.

## 모션 카드

| 스타일 | 템플릿 | 종류 |
|---|---|---|
| 어두운 유리(원작) | `motion/cards.html` | title · number · steps · verdict · score · compare (전체 화면) |
| 밝은 | `motion/cards_channel.html` | 위 여섯 + toc(목차) · hook(도입 질문), 배치 side · glass · split · full |
| 목차 전환 | `motion/chapter_frost.html` + `claude-edit/scripts/chapter_frost.py` | 어두운 막 + 번호·부제·제목·키 컬러 밑줄 |

키 컬러(`brand_color_1`)·보조색(`brand_color_2`)·글꼴(`motion_font`)은 profile.md에서 쿼리(`theme_accent`·`theme_accent2`·`theme_font`)로 넘어갑니다. 원작 기본값(검정 유리·주황·민트·Pretendard)은 값이 없을 때의 어두운 스타일 기본입니다.

## 원작 표기

`smartdaddy-video-edit`은 유튜버 **스마트대디**가 배포한 편집 스킬(v2 · 2026-10-21 배포본)을 토킹헤드 채널용으로 고친 것입니다. 원작의 편집 규칙(`references/rules.md` 본문)·도구 구조·원작 README는 원작자의 것이며 그대로 두었습니다.

배포본과 비교해 고친 것과 더한 것:

- **더한 것:** `scripts/capcut_augment.py`(사용자가 다듬은 CapCut 프로젝트에 자료 덧입히기), `frame_check.py`(가운데·수평 재기), `listen_check.py`(편집본 다시 듣기), `master_audio.py`(전체 음량 −14 LUFS), `script_check.py`(원고 교차검증), `tighten.py`(쉼 줄이기), `emphasis.py`·`emphasis_candidates.py`(강조 자막·효과음·배경음), `motion/cards_channel.html`(밝은 모션 카드)·`examples_channel.md`, `motion/chapter_frost.html`(목차 전환 글자 층), `references/channel-profile.md`·`emphasis.md`.
- **고친 것:** `SKILL.md`(단계 정리, 모션 카드 스타일·프로필 연결), `references/rules.md`('내 규칙'은 비움), `references/capcut.md`(Mac CapCut 9.x `draft_info.json`, 덧입히기 형식), `scripts/_common.py`(Mac CapCut 미디어 복제, Apple GPU 받아쓰기, 채널 프로필 읽기), `transcribe.py`·`cut_plan.py`·`check_cuts.py`(받아쓰기 백엔드·묶음 옵션), `capcut_build.py`(범퍼·크롭·회전·편집본 자막·자막 사전), `motion/cards.html`(색·글꼴을 쿼리로 바꿀 수 있게), `scripts/render_motion.py`(투명 납품 옵션), `subs_shift.py`·`preview.py`·`doctor.py`(Mac CapCut 파일 이름 대응), `requirements.txt`, `make_sfx.py`(효과음 종류).
