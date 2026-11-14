# 모션 카드 예시 (밝은 스타일 `cards_channel.html`)

`motion/cards_channel.html`은 원작 `cards.html`과 같은 키를 받고, 색과 화면 위치를 정면 토킹헤드 영상에 맞춘 **밝은 스타일** 템플릿이다. 어두운 유리 스타일은 원작 `cards.html`(예시는 `examples.md`)이다. 어느 쪽을 쓸지는 `profile.md`의 `motion_style`(`light` | `dark`)이 정하고, 처음에는 `claude-edit` `scripts/mockups.py`로 목업을 만들어 사용자가 고른다.

원칙(말과 맞추기, 실제 값만, 한 화면에 한 생각)은 `references/motion.md`, 채널 연결은 `references/channel-profile.md`.

## 종류

| kind | 쓰는 곳 | 주요 키 |
|---|---|---|
| `title` | 챕터 제목·큰 한 줄(`place=full` 권장, `glass`도 됨) | `title`, `sub` |
| `number` | 숫자 굴리기 / `from`이 있으면 전후 막대 | `title`, `from`, `to`, `unit`, `badge`, `fromlabel`·`tolabel`, `at`, `roll` |
| `steps` | 말하는 순서대로 한 칸씩 켜지는 단계 | `title`, `items`, `subs`, `at`, `check=0` |
| `verdict` | 이렇게 하세요 / 피하세요 | `title`, `yes`·`no`(또는 `do`·`dont`), `left`·`right`, `at` |
| `compare` | 전 → 후, 좌우 비교 | `title`, `left`·`right`, `lv`·`rv`(값), `lu`·`ru`(단위), `ln`·`rn`(설명), `mid`, `win`, `lweek`·`rweek`(요일 칸) |
| `score` | 2~3줄 기록판 | `title`, `names`, `scores`, `unit`, `win`, `add` |
| `toc` | 목차(지금 장만 진하게, 지난 장은 체크) | `items`, `subs`, `now` |
| `hook` | 도입 질문(큰 인용 → 보조 문장 → 보기 칸) | `title`, `sub`, `items`, `at` |

원래 채널 주제에 묶여 있던 종류(몸 그림·그림 타일·비유 그림, 논문 요약, 기간 구간, 변화 곡선, 고정 댓글 카드)는 이 판에서 뺐다.

## 배치(`place`)

- `side`(기본): 폭 432px 세로 카드. `side=right`(기본, x 1440–1872) 또는 `left`(x 48–480). 세로 `y=center`(기본)·`top`·`bottom`. 얼굴 안전영역(x 520–1400, y 0–620)과 하단 자막(y 950–1080) 밖이다.
- `full`: 화면 전체를 바탕색으로 덮는다. 말로 길게 설명하는 구간에 2~6초만. 글자는 y 950 위에만.
- `split`: 오른쪽 패널 x 1040–1920. 같은 구간 원본은 CapCut 줌으로 진행자를 왼쪽으로 민다(`toc`용).
- `glass`: 얼굴이 보이는 반투명 카드(`toc`·`hook`·`title`). 왼쪽 아래, 얼굴·아래 18% 비움.

## 스타일(쿼리)

| 쿼리 | 뜻 | profile.md |
|---|---|---|
| `theme_accent` | 키 컬러(강조 상자·밑줄·켜진 칸) | `brand_color_1`(없으면 `chapter_color`) |
| `theme_accent2` | 보조색(지난 칸 체크) | `brand_color_2` |
| `theme_bg` | 카드·전체 화면 바탕 | — |
| `theme_font` | 글꼴(설치된 이름) | `motion_font` |

`claude-edit` `motion_cards.py`는 profile.md에서 이 값을 자동으로 붙인다. 색은 `#RRGGBB`(렌더러가 인코딩한다).

## 렌더와 납품 파일

스킬 폴더(`smartdaddy-video-edit`)에서 실행한다.

```
python scripts/render_motion.py motion/cards_channel.html <출력>/subs --alpha --fps 30 --dur 4 --check-safe \
  --background-image <촬영 프레임.jpg> \
  --query "kind=number&title=구독자&from=120&to=480&unit=명&badge=+360명&theme_accent=#E8590C"
```

| 파일 | 쓰는 곳 |
|---|---|
| `subs_alpha.mov` | **편집용 원본.** ProRes 4444 + 알파. CapCut 덮개 트랙에 그대로 얹는다 |
| `subs_black.mp4` | 알파를 못 읽을 때의 대안(검정 배경, CapCut 혼합 모드 `스크린`) |
| `subs_alpha.png` | 멈춘 장면 투명 PNG(확인용) |
| `subs_preview.mp4` · `_preview.jpg` | `--background-image`에 합성한 확인용. 편집에 쓰지 않는다 |
| `subs_safe.json` | `--check-safe` 결과. 얼굴 영역·자막 띠의 최대 알파. side 카드는 8 이하이면 통과 |

- 첫·끝 프레임 최대 알파가 0이어야 한다(`exit` 기본 0.45초).
- 몇 장면만 볼 때: `--frames 0.35,2,3.5`(+ `--alpha --background-image frame.jpg`).
- 촬영 프레임 뽑기: `ffmpeg -ss 95 -i 촬영본.mp4 -frames:v 1 -q:v 3 frame.jpg`.
- `capcut_build.py`의 `overlays.json`에는 `{"type": "motion", "word": "…", "file": "편집/motion/subs_alpha.mov", "fade": 0}`처럼 넣는다.

## 예시

```
python scripts/render_motion.py motion/cards_channel.html out/title --dur 3 --query "kind=title&place=full&title=집에서 내리는 첫 드립&sub=도구 세 가지면 충분합니다"
python scripts/render_motion.py motion/cards_channel.html out/steps --alpha --dur 6 --query "kind=steps&title=드립 순서&items=원두 갈기|뜸 들이기|나눠 붓기|마무리"
python scripts/render_motion.py motion/cards_channel.html out/verdict --alpha --dur 6 --query "kind=verdict&title=물 온도&yes=90도 안팎|천천히 붓기&no=끓는 물 바로|한 번에 붓기"
python scripts/render_motion.py motion/cards_channel.html out/compare --dur 5 --query "kind=compare&place=full&title=분쇄도&left=굵게&lv=가벼운 맛&right=곱게&rv=진한 맛&mid=VS"
python scripts/render_motion.py motion/cards_channel.html out/score --alpha --dur 3.5 --query "kind=score&title=맛 점수&names=산미|단맛|쓴맛&scores=3|4|2&unit=점"
python scripts/render_motion.py motion/cards_channel.html out/toc --alpha --dur 3 --query "kind=toc&place=glass&items=도구|원두|추출&now=2"
python scripts/render_motion.py motion/cards_channel.html out/hook --alpha --dur 5 --query "kind=hook&place=glass&title=“집에서도 카페 맛이 날까?”&sub=생각보다 쉽습니다&items=하루?|일주일?|한 달?"
```

값 넘기는 규칙(`|` 목록, `data={JSON}`, 값 안의 `&`는 `%26`, `[대괄호]` 강조, 줄바꿈 `\n`)은 `examples.md`와 같다. 화면에 '설명용·예시·참고용' 같은 메타 표시와 출처·라이선스는 넣지 않는다(설명란에 적는다).
