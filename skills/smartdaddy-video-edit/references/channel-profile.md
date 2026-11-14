# 채널 프로필 연결

이 스킬의 규칙(`rules.md` 본문)은 원작자의 화면녹화 채널에서 나왔다. 정면 토킹헤드 채널처럼 화면 구성이 다르면 **작업 폴더 루트의 `profile.md`**와 이 문서가 `rules.md` 본문보다 우선한다.

우선순위: 사용자 최신 지시 > `rules.md`의 `내 규칙` > `profile.md` > 이 문서 > `rules.md` 본문.

`profile.md`가 없으면 먼저 `claude-edit/references/onboarding.md`대로 채널 링크나 소개 문서를 받고 취향을 몇 개만 물어 만든다. 키 목록은 `claude-edit/references/profile.template.md`.

## 실행 환경

- Python 3.10 이상. 작업 폴더에 가상환경을 두고 `scripts/requirements.txt`를 설치하는 것을 권한다.
- 스크립트는 **작업 폴더에서** 실행한다. 작업 폴더는 환경변수 `PROJECT_ROOT`가 있으면 그것, 없으면 현재 폴더다. 프로필 위치는 `CHANNEL_PROFILE`로 바꿀 수 있다.
- **받아쓰기:** `transcribe.py`·`cut_plan.py`·`check_cuts.py`의 `--backend auto`(기본)는 Apple Silicon Mac에 `mlx-whisper`가 깔려 있고 모델을 받아 두었으면 Apple GPU(mlx), 아니면 faster-whisper(CPU)를 쓴다. mlx 준비가 실패해도 CPU로 돌아간다. 모델은 사용자 허락 없이 내려받지 않는다.
  - 되돌리기: 각 스크립트 `--backend faster`(`claude-edit` `rough_cut.py`는 `--asr-backend faster`).
  - 자막·낱말 시각의 기준인 전체 받아쓰기는 `large-v3`. 컷 계획은 GPU면 `large-v3`, CPU면 `--model medium`.
  - mlx 감싸개는 클립 끝에 짧게 욱여넣은 환각 끝인사("감사합니다." 등, 글자당 0.08초보다 짧은 것)를 버린다. 진짜 끝인사는 소리 크기로 확인한다.
- **CapCut(Mac 9.x)**는 `draft_content.json` 대신 `draft_info.json`을 쓴다. 스크립트는 둘 다 읽고 템플릿과 같은 이름으로 쓴다.
- **CapCut 미디어는 `~/Movies` 아래에 있어야 한다.** Mac CapCut은 샌드박스 앱이라 작업 폴더 파일을 경로만 적어 넣으면 '미디어 연결' 오류가 난다. 조립 스크립트가 `~/Movies/CapCut_편집미디어/`에 APFS 복제(공간을 더 쓰지 않음)해서 그 경로를 쓴다.
- **투명 MOV:** CapCut 9.x(Mac)는 알파 ProRes 4444 MOV를 투명하게 보여 준다. 목차 전환은 알파 MOV를 쓴다.
- **템플릿 프로젝트:** 자막 글꼴·색은 CapCut 템플릿 프로젝트(영상 1, 로컬 소리 1, 자막 1 이상이 든 사용자 프로젝트, `profile.md`의 `capcut_template`)에서 따라온다.

## 영상 폴더

영상 한 편은 작업 폴더 안 `<영상 이름>/` 폴더 하나다(`profile.md`의 `videos_dir`로 모아 둘 곳을 바꿀 수 있음). 안쪽 폴더 이름은 `tools/topic_paths.py`가 정한다.

| 무엇 | 위치 |
|---|---|
| 촬영본·원고(읽기만) | `<영상 폴더>/` 바로 안 |
| 편집 작업 폴더(01_asr, 02_cut, overlays.json, HANDOFF, edit_state) | `<영상 폴더>/편집/` |
| 목차 전환 등 화면 자료 | `<영상 폴더>/편집/화면자료/` |
| CapCut 드래그용 일반 파일 | `<영상 폴더>/편집/캡컷_가져오기/` |
| 내보낸 영상·업로드 초안 | `<영상 폴더>/업로드/` |

명령의 `편집/…`은 `<영상 폴더>/편집/…`을 줄여 쓴 것이다.

## 다른 스킬과의 경계

| 작업 | 쓰는 것 |
|---|---|
| 컷·자막·CapCut 조립·덧입히기·강조 자막·효과음·배경음·음량 | 이 스킬 |
| 편집 전체 지휘(단계·확인 지점·업로드 묶음), 모션 카드 목록 렌더(`motion_cards.py`)·스타일 목업(`mockups.py`)·목차 전환(`chapter_frost.py`) | `claude-edit` |
| 모션 카드 템플릿·렌더러(`motion/cards.html`·`cards_channel.html`, `scripts/render_motion.py`) | 이 스킬 |
| 완성 영상 챕터 | `youtube-chapter-timestamps` |

## 원작 기본값과 다르게 쓰는 것

토킹헤드 채널을 기준으로 바꾼 기본값이다. `profile.md`나 사용자 지시가 다르면 그쪽을 따른다.

1. **화면 가운데는 얼굴이다.** 강조 글자·스티커는 1920×1080 기준 얼굴 안전영역(x 520–1400, y 0–620)과 하단 자막(y 950–1080)을 피한다.
2. **실제 화면이 주인공이다.** 진행자 얼굴·시연·본인 촬영본을 먼저 쓰고, 덧입힌 영상이 편집본의 35%를 넘으면 조립 출력에 `[규칙 점검]`이 나온다.
3. **받아쓰기 고유명사:** `profile.md`의 `asr_prompt`에 영상별 용어를 더해 `--prompt`에 짧게 넣는다.
4. **쉼:** 확정한 컷 계획에서 `cut_tempo`대로 쉼을 줄인다(`tighten.py`). 원작 기본값(1.5초 → 0.6초)은 `cut_plan.py`의 첫 단계일 뿐이다.
5. **고쳐 말한 문장은 원고 교차검증으로 찾는다.** `cut_plan.py`는 같은 말로 다시 시작한 경우만 스스로 지운다. 말을 조금 바꿔 다시 한 곳은 `script_check.py`로 찾고(원고가 있을 때), 후보는 그대로 믿지 말고 하나씩 확인한다.
6. **자막에 원고를 쓸 때 `--script`를 쓰지 않는다.** 다르게 말한 곳까지 원고 문구로 바꾸는 일이 있다. 대신 `script_check.py`가 만든 `words_script.json`을 `--edit-words`로 준다.
7. **화면에 출처·라이선스를 넣지 않는다.** 출처는 설명란에 모은다. 제3자 유튜브 영상을 인용하는 화면만 채널명을 화면에 둔다.
8. **화면 맞춤:** 조립 전에 `frame_check.py`로 가운데·수평을 재고 `--crop`·`--rotate`로 넣는다. 0.2° 미만 기울기는 돌리지 않는다.
9. **컷을 확정한 뒤의 순서:** `tighten.py` → 경계를 소리 골로 옮기기 → `listen_check.py`로 다시 듣기 → 편집본 wav를 `transcribe.py`(원고가 있으면 `script_check.py`)로 받아써 `capcut_build.py --edit-words` → 덧입히기마다 화면 내용과 대사 대조.

## 채널 범퍼

`profile.md`에 `bumper`(작업 폴더 기준 파일 경로)가 있으면 롱폼은 도입부가 끝난 직후, 본문 첫 문장 앞에 넣는다. 없거나 `없음`이면 이 절을 건너뛴다.

1. **자리 찾기.** 원고에 `(편집 - 범퍼)` 지시가 있으면 `script_check.py`의 '연출 지시 → 실제 시각'이 원본 초를 준다. 없으면 도입 다음 첫 본문 문장을 실제로 말한 원본 초를 찾는다.
2. **조립.** 평소 조립 명령에 `--bumper <범퍼 파일> --bumper-src <원본 초>`를 붙인다(소리 기본 `--bumper-db -8`). 뒤 클립·자막·덧입히기가 범퍼 길이만큼 밀린다. 범퍼 위에는 자막·카드를 두지 않는다.
3. **확인.** 출력의 `범퍼:` 줄을 보고 `preview.py <스테이징> <mp4> --start <범퍼-4> --end <범퍼+7>`로 그 구간만 렌더해 본다.

## 모션 카드

`profile.md`의 `motion`이 `안 씀`이 아니면 숫자·단계·판정·비교·기록판·목차·도입 질문·챕터 제목 카드를 쓴다. 스타일은 `motion_style`(`dark` = 원작 `motion/cards.html` 검정 유리, `light` = `motion/cards_channel.html` 밝은 카드), 키 컬러 `brand_color_1`, 보조색 `brand_color_2`, 글꼴 `motion_font`. 처음에는 `claude-edit/scripts/mockups.py`로 조합별 목업을 만들어 고르게 한다(onboarding.md 3-1). 예시는 `motion/examples_channel.md`.

## 목차 전환

`profile.md`의 `chapter_transition`이 `안 씀`이 아니면 장이 바뀌는 곳에 3초 목차 전환을 넣는다. `claude-edit` `scripts/chapter_frost.py`가 화면 전체를 어두운 반투명 막으로 덮고 번호·부제·제목·키 컬러 밑줄을 띄우는 알파 MOV(`motion/chapter_frost.html`이 글자 층)를 만들고, `augment_items.json`을 `capcut_augment.py`로 얹는다. 키 컬러는 `chapter_color`, 글꼴은 `chapter_font`, 라벨은 `channel_name`.

## 강조 자막과 효과음

기준 문서는 [emphasis.md](emphasis.md)다. 후보는 `scripts/emphasis_candidates.py`로 뽑고, 고른 목록을 표로 사용자에게 보여 준 뒤 `scripts/emphasis.py`로 넣는다.

### 기본 자막

- 문장이 의미 단위로 이어지게 나눈다. 연결된 말이 갈라지면 안 된다("첫 / 번째", "할 / 수 있다", "세 / 가지" 금지).
- `capcut_build.py`가 꾸밈말 뒤(`NEVER`·`ATTR_END`)와 앞말에 붙는 말 앞(`BOUND`)에서는 끊지 않는다. 새로 갈린 예를 찾으면 그 낱말을 `BOUND`나 `NEVER`에 더한다.
- 조립 뒤 자막 목록을 훑어, 줄 끝이 관형어·수 관형사이거나 줄 처음이 의존명사·보조용언인 줄이 없는지 확인한다.
