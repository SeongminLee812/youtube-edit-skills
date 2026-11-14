# 편집 단계 S0~S5

[SKILL.md](../SKILL.md)의 단계별 입력·출력·완료 기준·명령이다. 지금 단계와 다음 명령은 `autopilot.py status`가 알려 준다.

## 표기 약속

- 모든 명령은 **작업 폴더**(영상 폴더와 `profile.md`가 있는 곳)에서 실행한다. 다른 곳에서 돌리면 환경변수 `PROJECT_ROOT=<작업 폴더>`.
- `PY=python`(가상환경을 쓰면 그 python) · `S=<스킬 폴더>/smartdaddy-video-edit/scripts`(엔진) · `CE=<스킬 폴더>/claude-edit/scripts`(이 스킬) · `V=<영상 폴더>` · `W=$V/편집`
- 영상 폴더 구조(`tools/topic_paths.py`가 정함):

  | 무엇 | 위치 |
  |---|---|
  | 촬영본·원고(읽기만) | `<영상 폴더>/` 바로 안(이름 자유) |
  | 편집 작업(01_asr, 02_cut, 03_script, 03_review, 04_check, 05_edit_asr, HANDOFF.md, edit_state.json) | `<영상 폴더>/편집/` |
  | 목차 전환 등 화면 자료 | `<영상 폴더>/편집/화면자료/` |
  | CapCut에 끌어 넣을 일반 파일 | `<영상 폴더>/편집/캡컷_가져오기/` |
  | 내보낸 영상·업로드 초안 | `<영상 폴더>/업로드/` |

- CapCut 미디어는 Mac에서 `~/Movies` 아래에 있어야 한다. 조립 스크립트가 `~/Movies/CapCut_편집미디어/`에 복제해 그 경로를 쓴다.

## S0 준비

- **입력:** 영상 파일(필수), 원고(선택), 채널 링크 또는 채널 소개 문서, CapCut 템플릿 프로젝트 이름(자막 스타일이 든 사용자 프로젝트).
- `profile.md`가 없으면 [onboarding.md](onboarding.md)를 한다. 모션 카드·목차 전환을 쓰면 3-1 목업(`$PY $CE/mockups.py … --out $W/목업/` → `$W/목업/mockups.html`)으로 스타일과 키 컬러를 정한다.
- 화면 맞춤: `$PY $S/frame_check.py <촬영본> --out $W/00_frame` → `grid.jpg`로 인물 중심을 정하고 `--center-x`로 다시 돌려 `--crop`·`--rotate` 값을 얻는다. 0.2° 미만 기울기는 돌리지 않는다.
- `$PY $CE/autopilot.py init --video $V --footage <촬영본> [--script <원고>] --template "<CapCut 템플릿>" --crop <값> --rotate <값>`
- `HANDOFF.md`를 시작한다: 사용자 지시, 목표 길이, profile.md 취향 요약, 템플릿 이름.

## S1 러프컷

```
$PY $CE/rough_cut.py --video $V --media <촬영본> [--script <원고>] --template "<CapCut 템플릿>" \
    --crop <값> --rotate <값> --prompt "<고유명사, profile.md asr_prompt>"
```

- 단계: 받아쓰기 → 컷 계획 → 원고 대조(원고가 있을 때. 없으면 받아쓰기 낱말을 그대로 씀) → 재테이크 판독 → 쉼 줄이기 → 경계 검사 → 다시 듣기 → 편집본 자막 → CapCut 스테이징.
- **쉼 줄이기 값은 profile.md `cut_tempo`**: 촘촘(0.25초 넘는 쉼 → 0.15초), 보통(0.4초 → 0.24초, 기본), 여유(0.6초 → 0.4초).
- 재테이크 판독 JSON(`$W/03_review/retake_review.json`)이 없으면 요청서를 쓰고 멈춘다. 하위 에이전트가 판독하면 `--from tighten`으로 이어 간다. low 항목은 `03_review/게이트A_낮은신뢰도.md`에 모인다.
- 자막 고침: 이 영상만 틀린 말은 `$W/03_script/subtitle_replace.json`, 채널 공통이면 작업 폴더 `subtitle_dictionary.json`(`profile.md`의 `subtitle_dictionary`로 위치 변경 가능).
- 범퍼(`profile.md`의 `bumper`)가 있으면 본문 첫 문장의 원본 초를 찾아 `--bumper-src <초>`로 조립한다.
- 등록(`--install`)은 사용자 허락 + CapCut 꺼짐일 때만. 등록했으면 `autopilot.py register`.
- **게이트 A:** 신뢰도 낮은 컷 표 → 반영해 다시 조립·등록 → 사용자가 CapCut에서 내용 컷을 마치고 저장할 때까지 기다린다.

## S1-대신. 이미 편집된 영상(컷 안 함)

`profile.md`의 `cut_tempo`가 `컷 안 함`이면 S1 러프컷 대신 아래로 자막만 만든다(재테이크·쉼 컷 없음). 게이트 A는 건너뛴다.

```
$PY $S/transcribe.py <영상> --out $W/01_asr --model large-v3 --prompt "<고유명사>"
$PY $CE/nocut_plan.py $W/01_asr --media <영상> --out $W/02_cut/plan_nocut.json        # 문장 경계로만 나눈 연속 구간
$PY $S/capcut_build.py --template "<CapCut 템플릿>" --plan $W/02_cut/plan_nocut.json --media <영상> \
    --words $W/01_asr/words.json --subtitles [--overlays $W/overlays.json] --staging $W/02_cut/capcut_staging --name "<이름>_v001"
```

- 원본에 자막이 이미 구워져 있으면 새 자막과 겹친다. 원본 자막이 없는 마스터 파일을 받는 것이 가장 좋고, 없으면 등록 전에 `$PY $CE/subs_move.py <스테이징> --dy 0.16`으로 새 자막을 위로 올린다(강조 자막을 넣기 전에).
- 모션 카드·목차 전환은 `overlays.json`의 `{"type": "motion", "at": <초>, "file": "<알파 MOV>", "fade": 0}`로 조립 때 함께 넣을 수 있다(컷이 없으므로 편집 초 = 원본 초).

## S2 덧입히기 계획

바탕은 사용자 최신 편집본(`$PY $CE/autopilot.py latest --video $V`).

- **강조 자막**(`profile.md` `emphasis`가 `안 씀`이 아닐 때): `$PY $S/emphasis_candidates.py "<바탕>" --out $W/강조_후보.csv` → 6유형 점수표에서 `emphasis` 정도(적게: 1분 1~2개, 보통: 2~4개)만큼 고른다. 기준은 smartdaddy `references/emphasis.md`.
- **효과음·배경음**(`sfx`·`bgm`): 강조 유형별 효과음을 쓸지, 배경음 파일과 크기(목소리보다 15dB 아래 기본).
- **모션 카드**(`motion`): 숫자·단계·판정·비교·기록판·도입 질문·챕터 제목을 말로 길게 설명하는 곳에. 카드 목록을 `$W/화면자료/모션카드_v1/cards.json`에 쓴다(형식은 `templates/motion_cards.example.json`). 종류·키는 smartdaddy `motion/examples_channel.md`(밝은)·`motion/examples.md`(어두운 유리).
- **목차 전환**(`chapter_transition`): 장 번호·제목·원본 초 목록 → `$W/화면자료/챕터전환/chapters.json`(형식은 `chapter_frost.py` 맨 위 설명).
- **게이트 B:** 강조 목록, 모션 카드 목록, 목차 전환 목록을 표로 한 번에 보여 주고 승인받는다.

## S3 만들기

```
$PY $CE/motion_cards.py $W/화면자료/모션카드_v1/cards.json                     # 스타일·색: profile.md motion_style·brand_color_1
$PY $CE/chapter_frost.py $W/화면자료/챕터전환/chapters.json --variants A      # 키 컬러: profile.md brand_color_1(또는 chapter_color)
$PY $S/make_sfx.py sfx                                                     # 효과음 폴더가 없을 때 기본음
```

- 모션 카드: 알파 카드(`glass`·`side`·`split`)는 알파 MOV, 전체 화면(`full`, 어두운 유리 스타일은 모두)은 MP4. 연락표와 `augment_items.json`이 같은 폴더에 생긴다.
- 세기: `A`(어두운 막만, 어디에나 얹힘), `Bmid`·`Bstrong`(그 구간 촬영본을 흐림). 연락표(`연락표.jpg`)를 직접 보고 글자 잘림·색을 확인한다.

## S4 조립

```
$PY $S/emphasis.py --project "<바탕>" --spec $W/강조.json --out $W/02_cut/capcut_staging/<새 이름> --audio-template "<CapCut 템플릿>"
$PY $S/capcut_augment.py --base "<위 결과 또는 바탕>" --name "<새 이름>" --spec <모션 카드·목차 전환 augment_items.json 을 합친 덧입히기 JSON> \
    --staging $W/02_cut/capcut_staging --loudness-off
$PY $S/preview.py "<스테이징 폴더>" $W/preview.mp4 --h 540
```

- 원본 프로젝트는 읽기만 하고 새 스테이징에 쓴다. 출력의 `[규칙 점검]`·`[겹침 확인]`·`[못 넣음]`을 보고 고친다.
- 사용자가 자른 대사의 자료는 넣지 않고 알린다.
- 등록은 사용자 허락 + CapCut 꺼짐일 때만, 한 세션만. 등록했으면 `autopilot.py register`.
- **게이트 C:** 바탕·새 버전 이름·넣은 것·뺀 것·미리보기를 보여 준다. 사용자가 CapCut에서 전환 효과 등을 넣고 클립별 음량 정규화를 끈 채 내보낸다.
- 배속 판이 필요하면 `$PY $CE/speed_version.py --video $V --base <바탕> --name <새 이름> --speed 1.1`(선택).

## S5 마감

```
$PY $S/master_audio.py <내보낸.mp4> --out <내보낸>_음량.mp4        # −14 LUFS·최대 −1.5 dBTP
$PY $S/verify_render.py <내보낸>_음량.mp4
$PY $CE/upload_pack.py "<최종 프로젝트>" --video $V [--type <해시태그 행>] [--key-url <관련 영상 URL>]
```

- 챕터는 `youtube-chapter-timestamps` 스킬로 내보낸 파일에서 실제 발화 시작 기준으로 뽑고, `upload_pack.py --chapters <파일>`로 검사한다.
- 결과: `$V/업로드/업로드_초안/`(설명란·고정댓글 초안, 챕터 검사). 남은 `{자리표시}`는 에이전트가 채운다.
- 회고: 사용자 마무리본과 마지막 등록본을 비교해 선호를 preferences.md에, 손으로 고친 자막은 `subtitle_dict.py learn`으로 사전 후보로 남긴다.
