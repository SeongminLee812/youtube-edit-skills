---
name: smartdaddy-video-edit
description: 녹화본(영상·음성)을 받아 다시 말한 곳·긴 쉼을 자르고, 의미 단위 자막(대본이 있으면 대본 표기), 강조 자막, 효과음, 배경음, 줌, 모션 카드를 각각 따로 넣은 CapCut 프로젝트로 만들어 주는 영상 편집 엔진 스킬. "영상 초안 만들어 줘", "편집해 줘", "초벌 만들어 줘", "캡컷 프로젝트로 만들어 줘", "버벅인 데 잘라 줘", "무음 구간 잘라 줘", "자막 달아 줘", "강조 자막 넣어 줘", "효과음·배경음악 깔아 줘", "모션 카드 넣어 줘", "강조 포인트 뽑아 줘", "자막 늦춰 줘", "편집 스킬 점검해 줘", "오늘 고친 거 스킬에 저장해 줘" 같은 요청이나, 녹화 파일을 주며 편집을 맡길 때 쓴다. 유튜버 스마트대디가 석 달 동안 클로드와 영상을 만들며 쌓은 편집 규칙과 도구를 바탕으로 고친 판이다.
---

# 스마트대디 영상 편집 스킬 (v2, 고친 판)

> 이 스킬은 유튜버 **스마트대디**가 배포한 편집 스킬(v2 · 2026-10-21)을 토킹헤드 채널용으로 고친 것이다. 원작의 편집 규칙은 `references/rules.md` 본문에 그대로 있다. 롱폼 한 편을 처음부터 업로드 준비까지 맡으면 지휘 스킬 `claude-edit`을 먼저 읽는다. 이 스킬은 그 아래에서 쓰는 컷·자막·조립 엔진이다.

녹화본을 받아 **사람이 마지막 10%만 손보면 되는 CapCut 초안**을 만든다. 그리고 사람이 준 피드백을 이 스킬의 규칙으로 쌓아, 다음 영상에서 같은 말을 두 번 하지 않게 한다.

## 이 스킬이 하는 것과 하지 않는 것

| 클로드가 한다 | 사람이 한다 |
|---|---|
| 필요한 도구 확인·설치(사용자가 맡겼을 때), 받아쓰기, 다시 말한 곳·긴 쉼 찾기 | 재미있는지 판단, 구성, 어디를 버릴지 최종 결정 |
| 문장 하나 = 클립 하나로 CapCut 프로젝트 조립(앞뒤 여유분 포함) | CapCut에서 마지막 손질(클립 끝 늘리기·줄이기, 컷 디테일, 전환 효과) |
| 의미 단위 자막(대본 표기), 강조 자막·효과음·배경음·줌·모션 카드 배치 | 녹음·녹화, 최종 내보내기, 업로드 |
| 미리보기, 내보낸 영상 점검, 피드백을 규칙으로 저장 | 계정 로그인·결제·인증 코드 같은 계정 작업 |

## 시작하기 전에

0. **작업 폴더 루트의 `profile.md`를 읽는다.** 없으면 `claude-edit/references/onboarding.md`대로 채널 링크나 소개 문서를 받고 취향을 몇 개 물어 만든다. 채널 연결 규칙(실행 환경·폴더·화면 위치·Mac CapCut)은 `references/channel-profile.md`가 이 스킬 본문의 기본값보다 우선한다.
1. **준비물 확인.** 처음이면 `python scripts/doctor.py`를 돌린다(경로는 이 스킬 폴더 기준). 빠진 게 있을 때:
   - 사용자가 "필요한 도구는 알아서 설치해 줘"라고 했으면, 무엇을 설치하는지 한 줄로 알리고 `python scripts/doctor.py --fix`(Python 패키지, 모션 카드·목차 전환용 크로미움, 없으면 ffmpeg).
   - 그런 말이 없었으면 설치 방법을 알려 주고 허락을 받은 뒤 `--fix`.
   - 받아쓰기 모델은 첫 받아쓰기 때 자동으로 내려받는다(large-v3 약 3GB, 몇 분).
2. **규칙을 먼저 읽는다.** `references/rules.md` 전체, 특히 맨 아래 `내 규칙`(사용자가 쌓은 규칙)은 항상 다른 규칙보다 우선한다.
3. **원본은 절대 고치지 않는다.** 결과물은 영상 폴더의 `편집/` 아래에 만든다. 사용자의 CapCut 프로젝트도 덮어쓰지 않고 새 이름으로 만든다.
4. **대본이 있는지 묻는다**(없으면 넘어간다). 대본이 있으면 자막이 대본 표기로 나오고 고유명사 오류가 거의 없어진다. 대본을 고쳐 말하는 촬영본은 `--script` 대신 `scripts/script_check.py`로 교차검증한다(3단계).

## 요청 크기에 맞춰 고른다

| 요청 | 할 일 |
|---|---|
| "버벅인 데 자르고 자막 달아서 캡컷으로" (짧은 연습·훈련) | 1 → 2 → 3 → 6 → 7 |
| "영상 초안 만들어 줘. 컷, 자막, 효과음, 모션 카드까지" (전체 초안) | 1 → 7 전부. 12분 영상 기준 1~2시간 걸린다고 먼저 알린다 |
| "강조 자막·효과음·배경음악 넣어 줘" (컷이 끝난 편집본 위에) | '강조·효과음·배경음악' 절 |
| "몇 초에 뭐가 어떻다" (수정 회차) | 8 |
| "오늘 고친 거 스킬에 저장해 줘" | 9 |
| 내보낸 최종본 점검 | 10 |

## 작업 순서

### 1. 맡긴 파일 확인
길이, 해상도, 프레임 수, 소리 트랙 수를 `ffprobe`로 본다. 고해상도이고 키프레임 간격이 긴 화면 녹화(예: 2,700px, GOP 8초)는 CapCut에서 끊기므로 편집용 사본(약 1,920px, GOP 15)을 만들어 그걸 연결한다. 마이크만 따로 녹음한 파일이 있으면 그걸 컷 판단에 쓴다.

- **화면 맞춤**: `python scripts/frame_check.py <원본> --out 편집/00_frame`으로 기울기를 재고, `grid.jpg`를 보고 인물 중심 x를 정해 `--center-x`로 다시 돌린다. 나온 `--crop`·`--rotate` 값을 6단계 조립에 넘기고, `before_after.jpg`를 사용자에게 보여 준다.

### 2. 받아쓰기
```
python scripts/transcribe.py <원본> --out 편집/01_asr --prompt "영상에 나오는 고유명사들"
```
- 받아쓰기는 **한 번만** 돌린다. 여러 에이전트에게 일을 나누면 GPU가 막히므로, 다른 에이전트에게는 텍스트만 넘긴다.

### 3. 컷 계획 → 사용자 확인
```
python scripts/cut_plan.py <원본> --out 편집/02_cut
```
- GPU(CUDA)가 없는 Mac에서 Apple GPU 받아쓰기(mlx)를 못 쓰면 `--model medium`으로 돌린다. 조각마다 30초 창으로 받아써서 CPU `large-v3`면 17분 영상에 1시간이 넘게 걸린다. 전체 받아쓰기(2단계)는 `large-v3`를 그대로 쓴다.
- 무음으로 나눈 조각을 따로 받아써서 다시 말한 곳을 찾는다. 결과: `plan.json`(남길 구간), `cuts.md`(원문 → 남긴 말, 앞뒤 1초 시각, 확인 필요 표시), `frags.json`(판정 근거).
- **사용자에게 `cuts.md`를 요약해 보여 준다.** "확인 필요"가 붙은 곳은 꼭 짚는다. 전체 초안 요청이면 기다리지 말고 다음 단계로 가되, 설치 전에 같이 보여 준다.
- 고칠 때: `--protect 43.5-45.5`(자르지 마), `--cut 10.9-14.0`(잘라)로 다시 돌린다. 녹음 중 "다시"라고 말한 곳은 받아쓰기에서 찾아 그 앞 테이크를 `--cut`으로 지정한다.
- 원칙: **애매하면 남긴다.** 강조 반복, 반응, 웃음은 남긴다.
- 배경음·게임 소리가 섞인 한 통 녹음은 반복을 잘 못 찾는다. 마이크만 녹음된 파일이 있는지 묻는다.
- 컷 계획이 끝나면 남긴 클립을 하나씩 다시 받아써서 검사한다.
  ```
  python scripts/check_cuts.py 편집/02_cut/plan.json <원본>
  ```
- 대본이 있으면 사람이 `--cut`을 넣기 전의 컷 계획으로 교차검증한다. 재테이크·잡음 후보(`cut_suggest.txt`), 말하지 않은 대본 문장, 대본의 연출 지시가 실제로 나온 원본 시각을 준다.
  ```
  python scripts/script_check.py --script <촬영 원고> --words 편집/01_asr/words.json --plan 편집/02_cut/plan.json --out 편집/03_script
  ```

### 3-1. 쉼 줄이기 → 다시 받아써서 확인
컷 계획을 확정한 뒤(재테이크 `--cut` 반영) 쉼을 줄이고, 편집본 음성을 다시 받아써서 빈 구간·이어진 같은 말을 본다.
```
python scripts/tighten.py 편집/02_cut/plan.json 편집/02_cut/audio16k.wav --words 편집/03_script/words_script.json --out 편집/02_cut/plan_tight.json
python scripts/listen_check.py 편집/02_cut/plan_tight.json 편집/02_cut/audio16k.wav --out 편집/04_check --name tight
```
- 쉼 값은 `profile.md`의 `cut_tempo`를 따른다: 촘촘 `--gap 0.25 --keep-out 0.08 --keep-in 0.07`, 보통 `--gap 0.4 --keep-out 0.12 --keep-in 0.12`(기본), 여유 `--gap 0.6 --keep-out 0.2 --keep-in 0.2`. 남은 재테이크는 `--cut-file 판독.json`이나 `--cut 시작-끝`으로 함께 뺀다.
- `tighten.py` 출력의 `[확인 필요]`는 소리로 확인하고, 진짜 말이면 `--keep 시작-끝`, 지울 소리면 `--cut`.
- 남긴 클립 경계가 말소리 한가운데면 말 잘림이다. 컷 계획의 클립 끝을 소리 골까지 늘린 새 plan을 만든다.

### 3-2. 자막은 편집본 소리로 (권장)
원본 받아쓰기를 편집본 시각으로 옮기면 컷 뒤 첫 낱말이 빠지거나 겹친다. `listen_check.py`가 만든 편집본 wav를 다시 받아써 그대로 자막으로 쓴다.
```
python scripts/transcribe.py 편집/04_check/tight.wav --out 편집/05_edit_asr --model large-v3 --prompt "고유명사"
python scripts/script_check.py --script 촬영원고.txt --words 편집/05_edit_asr/words.json --out 편집/05_edit_asr
python scripts/capcut_build.py ... --plan 편집/02_cut/plan_tight.json --edit-words 편집/05_edit_asr/words_script.json --subtitles --replace 고칠말.json
```
- 편집본 wav는 조립에 쓰는 plan과 같은 컷으로 만든 것이어야 한다(컷을 바꾸면 다시 받아쓴다).
- 남은 받아쓰기 오류는 자막 전체를 한 번 읽고 `--replace` JSON({"틀린 말": "고칠 말"})으로 고친다.

### 4. 장면 계획 (전체 초안일 때)
받아쓰기를 처음부터 읽고 `편집/scene_plan.md`에 장면 계획을 적은 뒤 `편집/overlays.json`으로 옮긴다. 판단 기준은 `references/rules.md` 5~9장.
- **장 나누기**: 주제가 바뀌는 곳을 찾는다. 목차 전환은 `claude-edit`의 `chapter_frost.py`로 만든다(`profile.md`의 `chapter_transition`).
- **모션 카드**: 숫자 비교, 단계 목록, 판정표, 점수판처럼 말로 길게 설명하는 곳(`profile.md` `motion`이 `안 씀`이면 넣지 않는다). 실제 화면 위에 덮어 얹는다. 5단계.
- **줌**: 말로 화면을 가리키는 곳, 웃음 포인트. 후보 시각의 프레임을 `ffmpeg -ss <초> -i <원본> -frames:v 1`로 뽑아 보고 확대할 위치(x, y)를 정한다. 한 장면에 한 번.
- **강조 글자·효과음**: 아래 '강조·효과음·배경음악' 절과 `profile.md`(`emphasis`·`sfx`)를 따른다.
- **시각은 실제로 말한 낱말로** 정한다(받아쓰기에 적힌 대로).
- 형식은 `scripts/capcut_build.py` 맨 위 설명과 `references/capcut.md`의 '덧입히기'.

#### 강조·효과음·배경음악
컷이 끝난 CapCut 프로젝트 위에 강조 자막·1.2배 확대·효과음·목차 이름표·배경음악을 얹는다. 기준과 수치는 **`references/emphasis.md`**를 먼저 읽는다. `profile.md`에서 `emphasis`·`sfx`·`bgm`이 `안 씀`이면 그 부분은 넣지 않는다.
1. 후보 뽑기: `scripts/emphasis_candidates.py <프로젝트> --out 후보.csv` → 6유형(훅·원인지목·공감·정정·결과·핵심) 점수표.
2. 고른 목록을 표로 사용자에게 보여 주고 spec JSON을 쓴다(형식은 `scripts/emphasis.py` 맨 위 설명).
3. 넣기: `scripts/emphasis.py --project <프로젝트> --spec <json> --out <새 스테이징> --audio-template <CapCut 템플릿>`. 원본은 읽기만 하고, `[규칙 점검]`·`[겹침 확인]`·`[못 넣음]`을 보고 고친다.
4. 미리보기를 만들어 프레임과 소리 크기를 확인한 뒤 사용자에게 보낸다. 등록(`--install`)은 사용자가 CapCut을 끄고 허락한 뒤에만.

효과음 폴더가 없으면 기본음을 만든다:
```
python scripts/make_sfx.py 편집/sfx
```

### 5. 모션 카드 렌더 (필요할 때)
스타일은 `profile.md`의 `motion_style`이 정한다: `dark`면 원작 `motion/cards.html`(검정 유리, 전체 화면), `light`면 `motion/cards_channel.html`(밝은 카드, 얼굴 옆·반투명·전체 화면). 색·글꼴은 쿼리 `theme_accent`(키 컬러)·`theme_accent2`(보조색)·`theme_font`로 넘긴다(`profile.md`의 `brand_color_1`·`brand_color_2`·`motion_font`). 처음에는 `claude-edit` `scripts/mockups.py`로 목업을 만들어 사용자가 스타일을 고른다.
```
python scripts/render_motion.py motion/cards.html 편집/motion/time.mp4 --dur 4 --query "kind=number&title=편집 시간&from=30&to=8&unit=시간&theme_accent=#E8590C"
python scripts/render_motion.py motion/cards_channel.html 편집/motion/steps --alpha --dur 5 --query "kind=steps&title=오늘의 순서&items=준비|시작|정리&theme_accent=#E8590C"
```
- 종류: `cards.html`은 title·number·steps·verdict·score·compare, `cards_channel.html`은 그 여섯 + toc(목차)·hook(도입 질문). 예시는 `motion/examples.md`·`motion/examples_channel.md`, 원칙은 `references/motion.md`. 핵심: 실제 화면이 주인공, 모션은 **덮어 얹기**, 같은 효과 반복 금지, 숫자는 실제 값.
- 여러 장은 `claude-edit` `scripts/motion_cards.py`(카드 목록 JSON)로 한 번에 렌더하고 검사한다.
- 렌더 전에 `--frames 0.5,2,3.5`로 PNG 몇 장을 보고 글자가 넘치지 않는지 확인한다.

### 6. CapCut 프로젝트 조립
```
python scripts/capcut_build.py --template "<사용자가 평소 쓰는 CapCut 프로젝트 이름>" \
    --plan 편집/02_cut/plan.json --media <원본> --words 편집/01_asr/words.json \
    --name "<새 프로젝트 이름>" --subtitles [--script <대본>] [--overlays 편집/overlays.json]
```
- 먼저 스테이징 폴더(`<plan 폴더>/capcut_staging/<이름>/`)에 만든다. SRT와 대응표(`<이름>_timeline.json`)도 같은 곳에 생긴다.
- 출력에 `[못 넣음]`이나 `[규칙 점검]`이 나오면 고친 뒤 다시 조립한다.
- `[자막 점검]`은 전체 받아쓰기의 시각이 밀려 옆 문장(지운 테이크 포함)에서 딸려 온 낱말을 자막에서 뺐다는 뜻이다. 뺀 낱말과 원본 시각을 사용자에게 보여 준다.
- 채널 범퍼(`profile.md`의 `bumper`)가 있으면 도입부 직후에 넣는다: `--bumper <범퍼 파일> --bumper-src <본문 첫 문장 원본 초>`. 자리 찾기와 확인은 `references/channel-profile.md` '채널 범퍼'.
- 보이스를 따로 녹음했으면 `--voice <음성 파일>`(필요하면 `--voice-offset 초`). 대본이 없을 때 고칠 표기는 `--replace 고칠말.json`.
- 템플릿은 사용자가 실제로 쓰는 프로젝트(자막 스타일·폰트, 로컬 음성 파일 클립이 들어 있는 것)를 고른다(`profile.md`의 `capcut_template`). 모르면 `doctor.py`가 보여 준 최근 프로젝트 중에서 고르게 한다.
- 구조 규칙(문장 단위 클립, 앞뒤 여유분, 효과음 개별 클립, 텍스트는 CapCut 네이티브)과 함정은 `references/capcut.md`.

### 7. 미리보기 → 사용자에게 보이고 설치
```
python scripts/preview.py "<스테이징 폴더 또는 프로젝트 이름>" 편집/preview.mp4 --h 540
```
- 중간 회차 미리보기는 저화질 하나만 만든다. 덧입힌 시각의 프레임을 몇 장 뽑아 직접 확인한다.
- 사용자에게 보여 줄 것: 길이, 지운 말 개수와 확인 필요한 곳, 덧입힌 것 개수(효과음 N, 줌 N, 강조 N, 모션 N), 미리보기 파일.
- **설치 전에 사용자에게 CapCut을 꺼 달라고 하고, 허락을 받은 뒤** 같은 조립 명령에 `--install`을 붙인다.

### 8. 피드백 반영
- 사용자가 "몇 초에 뭐가 어떻다"로 말하면 그 자리만 고친다.
- 자막 시간, 문구, 텍스트 위치, 클립 삭제·길이 같은 **단순 수정은 프로젝트 파일을 직접 고친다**(렌더 불필요). 예: `python scripts/subs_shift.py "<프로젝트>" --end +0.2 --dry-run`으로 바뀔 내용을 보여 주고, 사용자가 CapCut을 끈 뒤 `--dry-run` 없이 적용한다(자동 백업).
- 효과음·줌·모션을 빼거나 옮기는 수정은 `overlays.json`을 고쳐 새 이름(`_v002`)으로 다시 조립한다.
- 사용자가 CapCut에서 직접 고친 버전이 있으면 **그 버전이 기준**이다. 사용자 편집을 덮어쓰지 말고 그 위에 반영한다.
  - 새 자료(모션 카드·목차 전환 MOV 등)·범퍼·미디어 교체는 `capcut_build.py`로 다시 만들지 않는다. `scripts/capcut_augment.py`로 사용자 프로젝트를 새 이름으로 복사해 얹는다.
  - 덧입히기는 원본 시각(src) 목록으로 준다. 메인 클립의 원본 구간으로 편집 시각을 찾으므로 사용자가 바꾼 컷에도 같은 대사에 붙는다.
  - 사용자가 자른 대사의 자료는 넣지 않고 알린다.
  ```
  python scripts/capcut_augment.py --base <사용자 프로젝트> --name <새 이름> --spec <덧입히기.json> --staging <폴더> [--loudness-off] [--install]
  ```

### 9. 규칙 저장 (가장 중요)
피드백 한 회차가 끝나면, 또는 사용자가 "오늘 고친 거 스킬에 저장해 줘"라고 하면:
1. 이번 회차에서 사용자가 고치라고 한 것 중 **다음 영상에도 적용될 것**만 고른다.
2. `references/rules.md` 맨 아래 `내 규칙`에 아래 형식으로 추가한다. 이미 비슷한 규칙이 있으면 새로 쓰지 말고 그 줄을 고친다. 취향 값(템포·강조·효과음·키 컬러 등)이면 `profile.md`를 고친다.
   ```
   - [2026-10-17] 반복한 말은 항상 앞의 것을 자르고 마지막 것만 남긴다.
     왜: "37초에 여러, 여러, 같은 말 두 번 했잖아" (게임 테스트 영상)
   ```
3. 추가한 줄을 사용자에게 그대로 보여 준다.
- **규칙은 숫자로 쓴다.** "효과음 적게"는 지켜지지 않고 "1분에 1~2개"는 지켜진다.
- 자세한 방법은 `references/feedback-loop.md`.

### 10. 최종 점검
사용자가 CapCut에서 내보낸 영상을 점검한다.
```
python scripts/verify_render.py <내보낸 영상>
```
해상도, 길이, 소리, 검은 화면, 영상 안 긴 무음, 음량(−14 LUFS 근처), 피크를 본다. 업로드는 사용자가 한다.

목소리 크기가 클립마다 오르내리면 CapCut 클립별 '음량 정규화'를 끄고 다시 내보낸 뒤, 영상 전체 기준으로 맞춘다.
```
python scripts/master_audio.py <내보낸 영상> --out <내보낸 영상>_음량.mp4
```
말 덩어리마다 크기를 앞뒤 1초 말소리와 함께 재서 문장끼리의 차이만 메우고(최대 ±6dB, 문장 끝 말투 유지), −14 LUFS·최대 −1.5 dBTP로 맞춘다. 화면은 다시 압축하지 않는다. `--wav`는 CapCut 오디오 교체용 WAV, `--window 0.4`는 더 고르게(문장 끝이 조금 커짐).

## 핵심 규칙 요약

전체와 이유는 `references/rules.md`(원작)에 있다. 작업할 때 최소한 아래는 지킨다.

**컷**
- 애매하면 남긴다. 컷 경계는 무음 골짜기 안, 앞뒤 80ms 이상 여유. 말 끝은 소리가 완전히 줄어들 때까지. 배속으로 줄이지 않는다.
- 반복한 말은 앞의 것을 지우고 마지막 것을 남긴다. 무음으로 나눈 조각마다 따로 받아써서 찾는다.
- 쉼은 `profile.md` `cut_tempo`대로 줄인다(원작 기본: 1.5초 넘는 쉼을 0.6초로).

**자막**
- 의미 단위로 끊는다. "구현을 잘 / 해줬어요"처럼 꾸밈말과 서술어를 떼지 않는다.
- 자막 시작은 목소리 시작 + 0.15초. 한 문장이면 30자를 조금 넘어도 한 줄로 둔다. 대본이 있으면 대본 표기.

**CapCut 구조**
- 보이스·효과음을 한 통짜 파일로 넣지 않는다. 문장 하나 = 클립 하나, 각 클립은 원본 전체를 참조해 가장자리를 끌 수 있게 한다.
- 줌·모션·목차 전환은 원본 위 트랙에 얹어 지우면 원래 화면이 나오게 한다. 텍스트는 CapCut 네이티브 텍스트로.

**화면**
- 실제 화면이 주인공. 강조 텍스트는 흰색 굵은 글꼴 + 검은 테두리. 자주 띄우지 않는다.
- 같은 효과를 되풀이하지 않는다. 장면 박자는 실제로 말한 낱말에 맞춘다.

**소리**
- 효과음은 원본 파일, 클립 볼륨 −20dB 기본. 본편 1분에 보통 1~2개, 많아도 5개를 넘기지 않는다.
- 배경음은 목소리보다 충분히 작게(강조 도구 기준 목소리 −15dB), 시연 구간은 비운다.

**인트로**
- 첫 30초가 이탈을 가른다. 첫 20초 안에 오늘의 질문을 던진다. 가짜 댓글·가짜 차트 금지.

## 하지 말 것
- 원본이나 사용자 CapCut 프로젝트를 덮어쓰기, CapCut이 켜진 상태에서 프로젝트 파일 쓰기
- 사용자 확인 없이 `--install` 하기, 사용자가 맡기지 않았는데 프로그램 설치하기
- 결과를 과장하기("100% 자동", "딸깍이면 끝"). 안 된 부분은 그대로 말한다.
- 계정 로그인·결제·인증 코드 입력·업로드. 이건 사용자가 한다.
- 출처를 모르는 음악·이미지 넣기

## 참고 문서
- `references/channel-profile.md` — 채널 프로필 연결(실행 환경, 영상 폴더, 화면 위치, 다른 스킬과의 경계, Mac CapCut 대응, 범퍼)
- `references/emphasis.md` — 강조 포인트 6유형·특징 점수, 강조 자막·확대·효과음·목차 이름표·배경음악 수치와 도구
- `references/rules.md` — 원작 편집 규칙과 이유, 맨 아래 `내 규칙`(계속 늘어남)
- `references/capcut.md` — CapCut 프로젝트 파일 구조, 조립·설치 방법, 덧입히기 형식, 알려진 함정
- `references/motion.md` — 모션 카드 원칙과 렌더 방법, `motion/examples.md`(어두운 유리)·`motion/examples_channel.md`(밝은) — 카드 종류별 명령
- `references/feedback-loop.md` — 피드백 받는 법, 규칙 저장 형식, 정리 주기
- `references/first-run.md` — 처음 쓰는 사람을 위한 설치와 첫 1분 영상
