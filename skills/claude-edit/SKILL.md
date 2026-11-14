---
name: claude-edit
description: 클로드가 편집해준다 — 유튜브 토킹헤드 롱폼 한 편을 영상 파일(+원고 선택)과 채널 정보(채널 링크 또는 소개 문서)만 받아 편집하는 지휘 스킬. 처음에는 채널을 읽고 취향을 몇 개만 물어 profile.md에 저장한 뒤, 러프컷 CapCut 프로젝트를 만들고, 사용자가 CapCut에서 내용을 다듬으면 그 위에 강조 자막·효과음·배경음·모션 카드·목차 전환을 얹고, 음량 마스터와 업로드 묶음(설명란·챕터·고정댓글)까지 낸다. "클로드가 편집해줘", "이 영상 편집해줘", "초벌부터 업로드 준비까지", "다음 편집 단계 진행", "강조 자막·모션 카드·목차 전환 넣어줘", "모션 카드 목업 보여줘", "업로드 본문 뽑아줘" 같은 요청이나 영상 파일을 주며 편집 전체를 맡길 때 쓴다. 컷·자막·조립 엔진은 smartdaddy-video-edit, 챕터는 youtube-chapter-timestamps를 부른다.
---

# 클로드가 편집해준다

토킹헤드 롱폼 한 편을 **영상 → CapCut 편집 → 업로드 묶음**까지 끌고 가는 지휘 스킬이다. 사람은 확인 지점 세 곳에서 판단하고, 나머지는 클로드가 명령과 하위 세션으로 처리한다.

## 사용 흐름

1. **영상을 넣는다.** 영상 파일(필수)과 원고(선택). 작업 폴더 안 `<영상 이름>/` 폴더에 둔다.
2. **채널 정보를 넣는다.** 채널 페이지 링크 **또는** 채널 소개 문서(파일) 하나.
3. **취향을 몇 개만 묻는다.** [references/onboarding.md](references/onboarding.md) — 처음 한 번만. 모션 카드·목차 전환을 쓰면 키 컬러 × 스타일 목업(`scripts/mockups.py`)을 보여 주고 고르게 한다. 답은 작업 폴더 루트 `profile.md`에 저장하고, 다음 영상부터는 다시 묻지 않는다.
4. **그에 맞게 편집한다.** 아래 단계 S0~S5. 마무리(전환 효과·최종 내보내기)는 사용자가 CapCut에서 한다.

## 누가 무엇을 하나

| 클로드가 한다 | 사용자가 한다 |
|---|---|
| 채널 읽기·취향 질문·모션 카드 목업·profile.md 저장 | 영상·원고·채널 정보 넣기, 취향 답하기, 목업 조합 고르기 |
| 받아쓰기·재테이크·쉼 줄이기·자막·조립·등록(새 이름) | **A. 지루한 구간을 자르는 내용 컷**(CapCut에서 직접) |
| 강조 자막 후보·모션 카드 목록·목차 전환 목록 작성 | **B. 강조·모션 카드·목차 전환 목록 확인** |
| 강조 자막·효과음·배경음·모션 카드·목차 전환을 사용자 편집본 위에 얹기, 미리보기 확인 | **C. CapCut 최종 확인·전환 효과·내보내기** |
| 음량 마스터, 설명란·챕터·고정댓글 초안 | 제목·썸네일 선택, 업로드 |

## 시작하기 전에 (매번)

1. **작업 폴더 루트의 `profile.md`를 읽는다.** 없으면 [onboarding.md](references/onboarding.md)부터 한다(채널 링크나 소개 문서를 받아 읽고, 취향을 2~3개씩 묻는다).
2. **[references/preferences.md](references/preferences.md)를 읽는다.** 편집하며 쌓인 사용자 선호다(처음에는 비어 있다).
3. `python <스킬 폴더>/claude-edit/scripts/autopilot.py status --video <영상 폴더>`로 지금 단계·다음 명령·물을 것을 본다. 상태 파일이 없으면 `init`부터 한다(S0). 편집 폴더(`<영상 폴더>/편집/`)의 `HANDOFF.md`도 읽는다. 폴더 구조는 [pipeline.md](references/pipeline.md) 표기 약속.
4. CapCut 프로젝트 목록에서 **이 영상 이름으로 시작하는 프로젝트만** 보고, 사용자가 가장 최근에 저장한 버전을 찾는다(`autopilot.py latest`). **사용자 편집본이 있으면 그것이 바탕이다.** 보고에는 "바탕: <이름>(<시각>)"을 쓰고, 애매하면 묻는다.
5. 엔진 스크립트는 옆 스킬 `smartdaddy-video-edit/scripts/`에 있다. 채널 연결 규칙은 그 스킬의 `references/channel-profile.md`, 엔진 규칙은 `references/rules.md`다.

## 단계 (상세: [references/pipeline.md](references/pipeline.md))

| 단계 | 하는 일 | 주로 쓰는 도구 | 끝나면 |
|---|---|---|---|
| S0 준비 | 입력 확인, profile.md(없으면 온보딩, 모션을 쓰면 목업 컨펌), 화면 맞춤(`frame_check.py`), HANDOFF 시작 | `autopilot.py init`, `mockups.py` | 바로 S1 |
| S1 러프컷(이미 편집된 영상이면 `nocut_plan.py`로 자막만) | 받아쓰기 → 컷 계획 → (원고가 있으면) 원고 대조 → 재테이크 판독(하위 에이전트) → 쉼 줄이기(`cut_tempo`) → 경계 검사 → 다시 듣기 → 편집본 자막 → 조립·등록 v001 | `rough_cut.py`·`edge_check.py` | 신뢰도 낮은 컷만 한 번에 묻는다 → **게이트 A** |
| S2 덧입히기 계획 | 사용자 편집본을 바탕으로 강조 후보(`emphasis`), 모션 카드 목록(`motion`, `templates/motion_cards.example.json` 형식), 목차 전환 목록(`chapter_transition`), 효과음·배경음(`sfx`·`bgm`) | smartdaddy `emphasis_candidates.py` | **게이트 B** |
| S3 만들기 | 모션 카드 렌더(`motion_style`·`brand_color_1`), 목차 전환 MOV 렌더(같은 키 컬러), 효과음 폴더 | `motion_cards.py`, `chapter_frost.py`, smartdaddy `make_sfx.py` | 연락표 확인 |
| S4 조립 | 사용자 최신 편집본 위에 강조 자막·효과음·배경음(`emphasis.py`)과 모션 카드·목차 전환(`capcut_augment.py`) → 미리보기 → CapCut 꺼짐 확인 → 새 이름 등록 | smartdaddy `emphasis.py`·`capcut_augment.py`·`preview.py` | **게이트 C** |
| S5 마감 | 내보낸 영상에 `master_audio.py` → `verify_render.py` → 업로드 묶음(설명란·챕터·고정댓글) | `upload_pack.py`, [upload_pack.md](references/upload_pack.md), `youtube-chapter-timestamps` | 업로드 파일 묶음 |

profile.md에서 `emphasis`·`sfx`·`bgm`·`motion`·`chapter_transition`이 `안 씀`이면 그 일을 건너뛴다.

### 게이트에서 묻는 법
- **A:** 신뢰도 낮은 컷은 위치·대사·선택지를 표로 보여 주고 한 번에 묻는다. 반영해 새 이름으로 다시 조립한 뒤 알린다: "v00N을 등록했습니다. 지루한 구간을 다듬어 저장하시면 그 편집본 위에 강조·목차 전환을 얹겠습니다."
- **B:** 강조 목록(유형·문장·효과음), 모션 카드 목록(종류·글자·시각), 목차 전환 목록(번호·제목·시각)을 표로 한 번에 보여 주고 승인받는다. 배경음을 쓰면 파일을 받는다.
- **C:** 바탕 이름·시각, 새 버전 이름, 넣은 것·뺀 것(사용자가 자른 대사의 자료), 미리보기를 보여 준다.
- **게이트 밖에서 묻는 것:** CapCut 등록 허락과 CapCut 끄기.

## 하위 세션 분담
- **재테이크 판독:** 하위 에이전트가 JSON(구간·판정·신뢰도·경계 근거)을 쓴다. 높음·중간은 자동 적용하고 낮음만 사용자에게 묻는다.
- **모션 카드·목차 전환 렌더:** 오래 걸리면 하위 세션에 장 목록 JSON과 출력 폴더를 주고 맡긴다.
- 하위 세션 결과는 편집 세션이 파일을 직접 열어 검수한 뒤 사용자에게 알린다.

## 지킬 것
- **덮어쓰지 않는다:** 사용자 CapCut 프로젝트와 촬영 원본은 덮어쓰지 않는다. 등록은 새 이름(`_v00N`)으로만 한다.
- **등록 허락:** 등록(`--install`)은 사용자가 허락하고 CapCut이 꺼져 있을 때만 한다. 켜져 있으면 끄라고 요청한다(클로드가 직접 끄지 않는다). 등록은 한 세션만 한다.
- **사용자 편집본이 기준이다:** 사용자가 CapCut에서 다듬은 뒤에는 `capcut_build.py`로 다시 만들지 않는다. `capcut_augment.py`·`emphasis.py`로 그 편집본 위에 얹는다.
- **무거운 계산 중 표시:** 받아쓰기·렌더 같은 무거운 계산 중에는 작업 폴더 루트에 `.edit_busy`를 만들고, 끝나면 지운다(스크립트가 한다).
- **결제·로그인은 사용자가 한다.** API 키는 입력·출력·기록하지 않는다.

## 피드백 저장 (어디에 쓰나)
- **취향 값(템포·자막 스타일·강조·효과음·배경음·모션 스타일·키 컬러·목차 전환):** `profile.md`를 고친다.
- **그 밖의 선호(화면 구성·소리·업로드·함께 일하는 방식):** [references/preferences.md](references/preferences.md)에 **숫자 규칙 + 날짜 + 이유 한 줄**로 쌓는다.
- **컷·자막·조립 스크립트가 지켜야 할 수치:** smartdaddy `references/rules.md`의 '내 규칙'에 쌓는다.
- 시행착오와 방지책은 [references/lessons.md](references/lessons.md)에 한 줄씩 더한다.

## 참고 문서
- [onboarding.md](references/onboarding.md): 채널 정보 읽기와 취향 질문
- [profile.template.md](references/profile.template.md): profile.md 키 목록
- [preferences.md](references/preferences.md): 사용자 선호(쌓이는 곳)
- [pipeline.md](references/pipeline.md): S0~S5 입력·출력·명령
- [upload_pack.md](references/upload_pack.md): 설명란·챕터·고정댓글
- [lessons.md](references/lessons.md): 시행착오 → 방지책
- 템플릿 `templates/`: 설명란, 고정댓글, 모션 카드 목록 예시
- **스크립트** `scripts/`

  | 스크립트 | 단계 | 하는 일 |
  |---|---|---|
  | `autopilot.py` | 전체 | `init`·`status`(지금 단계·다음 명령·물을 것)·`set`·`register`(등록 기록)·`latest`(사용자 편집본) — 상태 파일 `<영상 폴더>/편집/edit_state.json` |
  | `rough_cut.py` | S1 | 받아쓰기 → 컷 계획 → 원고 대조(원고가 있을 때) → 쉼 → 경계 → 다시 듣기 → 편집본 자막 → 스테이징을 이어서. 판독 JSON이 없으면 요청서를 쓰고 멈춤 |
  | `edge_check.py` | S1 | 컷 경계 잘림 검사(소리 골). `--apply`로 끝 늘린 새 plan |
  | `mockups.py` | S0 | 키 컬러 후보 × 스타일(어두운 유리/밝은) 조합마다 카드 4장(챕터 제목·숫자·단계·목차 전환) PNG + 비교 화면 `mockups.html` |
  | `motion_cards.py` | S3 | 카드 목록 JSON → 모션 카드 렌더(알파 MOV·전체 화면 MP4). 금지 낱말·필수 값 검사, 그 시각 촬영 프레임 합성, 안전영역 검사, 연락표·`augment_items.json`. 예시 `templates/motion_cards.example.json` |
  | `nocut_plan.py` | S1 대신 | 이미 편집된 영상(`cut_tempo: 컷 안 함`): 받아쓰기 문장 경계로만 나눈 연속 컷 계획 |
  | `subs_move.py` | S1·S4 | 원본에 자막이 구워져 있을 때 새 자막(텍스트) 세로 위치를 스테이징에서 옮김 |
  | `chapter_frost.py` | S3 | 목차 전환(흐림 막 + 번호·제목·키 컬러 밑줄) 알파 MOV, `augment_items.json`(capcut_augment용) |
  | `subtitle_dict.py` | S1·S5 | `check` 공용 자막 고침 사전 검사, `learn` 사용자가 손으로 고친 자막 → 사전 후보 표 |
  | `speed_version.py` | 선택 | 고른 최종본 전체를 배속한 새 버전(배경음은 원래 빠르기로 다시 깖) |
  | `upload_pack.py` | S5 | 챕터 후보·검사, 설명란·고정댓글 초안 |
  | `_busy.py` | — | `.edit_busy` 공용 처리 |
