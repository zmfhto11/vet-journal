# Vet Journal — Veterinary Clinical Journal Digest

개·고양이 임상 수의사를 위한 외과, 내과, 종양학 논문 다이제스트. 매일 새 논문을 찾고 영어 원제목과 짧은 한국어 요약을 보여줍니다. 연구 결과와 AI 임상 해석을 구분하며, 모든 요약에는 분석에 사용한 근거와 원문 링크를 남깁니다.

## 현재 상태

- 실제 PubMed / Europe PMC 수집, DOI/PMID 중복 병합, 저장, JSON 검증 구현.
- 의미 기반 OpenAI 분류·요약, 일일 호출 한도, 실패 재시도 구현.
- 검색, 복수 분야·종·저널·연구 유형·근거 필터, 추천 이유, 펼쳐보기, Today's Picks 구현.
- 실제 논문 8편(초록 기반 7편, 공개 전문 검토 1편)으로 만든 **초기 검증용 참고 요약** 제공. 자동 OpenAI API 분석 결과가 아니며 화면에 구분 표시됩니다. 자동 분석 데이터가 생기면 실제 데이터를 기본으로 표시합니다.
- GitHub Actions / Pages 배포 설정 제공. **원격 저장소 연결, Secrets 등록, Pages 활성화 전에는 자동 운영·온라인 배포가 시작되지 않습니다.**
- OpenAI API 키가 없는 환경에서 유료 호출의 실제 성공 여부와 모델 분류 정확도는 검증하지 않았습니다. 모의 응답 테스트를 라이브 모델 평가로 해석하지 마세요.

## Architecture

```text
journals.json
    ↓
GitHub Actions (08:17 KST)
    ├─ PubMed ESearch → EFetch
    ├─ Europe PMC search/core (보조 수집·보완)
    └─ 설정한 공식 publisher RSS (선택)
    ↓
DOI / PMID alias reconciliation → data/state.json
    ↓ pending / failed만 처리, 하루 최대 12회
OpenAI Responses API + Structured Outputs
    ↓ Pydantic + 원문 인용문·숫자 검증
검증된 관련 논문 → data/papers.json
    ↓
Python static build → dist/ → GitHub Pages
```

서버·DB·프론트엔드 프레임워크 없이 유지합니다. 추후 데이터가 매우 커지면 연도별 JSON 분할을 먼저 고려하면 됩니다. 전체 설계와 Phase별 결정은 [docs/architecture.md](docs/architecture.md)에 있습니다.

```text
config/journals.json           저널·ISSN·별칭·공식 RSS 설정
 data/state.json              수집 원본 메타데이터, 상태, 분석, 일일 예산
 data/papers.json             공개 화면용 검증 데이터
 data/reference-papers.json   초기 참고 샘플 (자동 분석과 별도)
 digest/models.py             메타데이터·분석 스키마
 digest/sources.py            API / XML / RSS / OA 전문
 digest/store.py              중복 병합·원자적 저장
 digest/analyze.py            의미 분류·요약·근거 검증
 digest/pipeline.py           수집 → 분석 → 저장
 digest/build.py              공개 정적 사이트 생성
 web/                        HTML, CSS, ES modules
 tests/                      오프라인 테스트, 실제 논문 fixture, 라이브 검사
 .github/workflows/           CI, 일일 갱신, Pages 배포
```

## Local setup

Python 3.11 이상(권장 3.12). Python 외 런타임은 운영에 필요하지 않습니다. JavaScript 문법 검사와 단위 테스트에는 Node.js 20 이상(권장 22)을 사용합니다. `npm install`은 필요 없습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
node --test tests/frontend.test.mjs
python -m digest.build
python -m http.server 4173 --bind 127.0.0.1 --directory dist
```

브라우저에서 `http://127.0.0.1:4173`을 엽니다. HTML 파일을 더블클릭하면 브라우저의 fetch 제한으로 JSON을 읽을 수 없으므로 HTTP 서버를 사용하세요. 소스 변경 후 `python -m digest.build`를 다시 실행하고 새로고침합니다.

macOS/Linux에서는 `source .venv/bin/activate`로 가상환경을 켭니다.

## Environment variables / API setup

`.env.example`은 설정 예시입니다. 프로그램은 `.env`를 자동으로 읽지 않습니다. PowerShell의 `$env:변수이름`, Bash의 `export`, 또는 GitHub Secrets/Variables로 주입하세요. 실제 키를 파일·채팅·커밋에 붙여 넣지 마세요.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | 없음 | 분석 시 필수. GitHub Secret 사용 |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Structured Outputs를 지원하는 모델 |
| `NCBI_API_KEY` | 없음 | 선택. 기본 요청 속도는 키 없이도 제한 내에서 동작 |
| `NCBI_EMAIL` | 없음 | NCBI 연락용 이메일. Secret 권장 |
| `MAX_AI_PAPERS` | `12` | KST 날짜당 최대 유료 분석 시도 수 |
| `MAX_INPUT_CHARS` | `120000` | 입력 근거 최대 문자 수, 초과 전문은 초록으로 폴백 |
| `MAX_OUTPUT_TOKENS` | `4800` | 호출당 출력 상한 |
| `LOOKBACK_DAYS` | `45` | 최근 수집 범위; 마지막 성공 시점이 더 오래되면 확대 |
| `USE_FULL_TEXT` | `true` | `true`이면 Europe PMC의 합법적인 OA 전문을 시도 |

OpenAI 플랫폼에서 프로젝트 API 키를 만들고 결제·사용량 한도를 설정합니다. 모델은 [공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-4.1-mini)의 지원 범위와 계정 접근 권한을 확인해 변경하세요. [Structured Outputs 공식 문서](https://developers.openai.com/api/docs/guides/structured-outputs)를 기준으로 `/v1/responses`의 strict JSON schema를 사용합니다. Python SDK 없이 표준 라이브러리 HTTPS 호출을 사용합니다.

NCBI 키는 NCBI 계정 Settings에서 발급합니다. 필수는 아닙니다. [E-utilities 공식 문서](https://www.ncbi.nlm.nih.gov/books/NBK25499/)를 따르며 NCBI 요청은 기본적으로 약 0.36초 이상 간격을 둡니다. Europe PMC는 [공식 REST API](https://europepmc.org/RestfulWebService)를 사용합니다.

## 수집 / 분석 실행

```sh
# 키와 과금 없이 최근 메타데이터만 수집
python -m digest.pipeline --collect-only --days 14

# 환경에 키가 설정된 상태에서 수집 + 신규/실패 논문 분석
python -m digest.pipeline

# 보관 데이터를 건드리지 않는 별도 검증 실행
python -m digest.pipeline --collect-only --data-dir artifacts/live --days 7

python -m digest.build
```

기본적으로 활성 저널 전체를 검색합니다. 종양 키워드에만 검색을 제한하지 않습니다. title + abstract의 의미를 AI가 판단해 개/고양이 실제 진료와 무관한 연구, 사람·실험동물·세포주만 다룬 연구를 제외합니다. 관련성이 간접적인 연구는 추천하지 않습니다. 저널별 키워드나 저널 명성으로 추천을 결정하지 않습니다.

Surgery와 Oncology처럼 여러 분야에 걸친 논문은 primary_category와 tags를 통해 양쪽 탭에 노출됩니다. 추천에는 별점 점수가 없고 추천 여부와 이유만 있습니다. Today's Picks는 **현재 KST 날짜에 최초 발견된 추천 논문** 중 최대 3편입니다. 오늘 발견된 논문이 없으면 비워 둡니다. 백로그 논문을 늦게 분석했다고 발견일을 오늘로 바꾸지 않습니다.

## GitHub Actions / GitHub Pages deployment

1. 사용자 GitHub 저장소를 준비하고 이 프로젝트를 기본 브랜치에 푸시합니다.
2. 저장소 **Settings → Secrets and variables → Actions → Secrets**에 `OPENAI_API_KEY`를 등록합니다. 필요하면 `NCBI_API_KEY`, `NCBI_EMAIL`도 등록합니다.
3. 같은 화면의 **Variables**에서 `OPENAI_MODEL`, `MAX_AI_PAPERS`, `USE_FULL_TEXT`를 선택적으로 설정합니다.
4. **Settings → Pages → Build and deployment → Source → GitHub Actions**로 설정합니다.
5. **Settings → Actions → General**에서 워크플로 실행과 봇의 contents 쓰기가 허용되어야 합니다. 브랜치 보호가 봇의 데이터 커밋을 차단하면 해당 정책에 맞게 워크플로/봇 접근을 구성해야 합니다.
6. **Actions → Validate and deploy website → Run workflow**를 실행합니다. 완료된 `github-pages` environment의 URL을 엽니다.
7. **Actions → Daily clinical digest → Run workflow**를 한 번 실행해 자동 갱신을 검증합니다. `collect_only=true`를 선택하면 과금 없이 수집만 확인할 수 있습니다.

GitHub 원격 저장소를 처음 연결하는 경우(아래 주소는 본인 저장소로 교체):

```sh
git add .
git commit -m "Build veterinary clinical journal digest"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

`update.yml`은 UTC `23:17`, 즉 다음 날 **08:17 Asia/Seoul**에 실행됩니다. GitHub의 예약 실행은 지연될 수 있으며 정확한 시각을 보장하는 서비스가 아닙니다. 스케줄은 기본 브랜치에 워크플로가 있어야 동작합니다. 저장소의 스케줄 비활성화 알림도 확인하세요.

업데이트 워크플로가 데이터 커밋 후 직접 Pages 배포까지 수행합니다. `GITHUB_TOKEN`으로 만든 커밋이 다른 push 워크플로를 자동 실행할 것으로 가정하지 않습니다. 동시 실행은 한 그룹으로 직렬화합니다. PR은 검사만 수행하고 배포하지 않습니다.

GitHub Pages는 접근 제한이 없는 공개 웹사이트가 될 수 있습니다. 개인용 사용 목적이 로그인 보호를 의미하지는 않습니다. 공개 무료 저장소가 가장 단순한 저비용 선택이며, 비공개 저장소의 Pages 제공 여부·요금은 계정 플랜에 따라 다릅니다. 환자 정보나 API 키는 어떤 공개 산출물에도 넣지 마세요.

## 비용과 재시도

- 단일 소형 모델 호출로 분류 + 요약을 처리합니다. 소규모 개인용에서는 모든 논문에 screening/summary 두 번을 호출하는 비용을 피할 수 있습니다.
- 이미 성공한 논문은 재분석하지 않습니다. 제외 판정을 받은 논문도 processed로 남겨 재과금을 막습니다.
- DOI를 우선 식별자로, PMID를 보조 식별자로 병합합니다. 식별자가 전혀 없는 경우에만 정규화한 title + journal을 보조 대조에 사용합니다.
- 일일 사용량은 `state.json`에 기록하고 유료 요청 **이전**에 예약합니다. 같은 날 워크플로를 수동 재실행해도 일일 한도가 초기화되지 않습니다.
- 실패한 논문은 다음 KST 날짜 실행에서 재시도합니다. 새 논문 3편과 실패 논문 1편을 번갈아 배치해 실패 항목이 영구적으로 뒤로 밀리지 않게 합니다.
- API 타임아웃은 서버가 이미 과금했는지 알 수 없으므로 다음 실행에서 재시도 시 중복 과금 가능성이 있습니다. 성공 결과가 저장된 논문은 다시 호출하지 않습니다. 키 제공자의 프로젝트 사용 한도도 설정하세요.
- 원문이 너무 길면 초록만 분석합니다. 전문을 일부만 잘라 읽고 `Full-text reviewed`를 붙이지 않습니다. 실사용 금액은 신규 건수·모델·입출력 길이에 따라 달라집니다.
- v1은 고가 모델로의 자동 2차 분석을 실행하지 않습니다. 추후 명시적인 추가 예산·평가가 필요할 때만 확장합니다.

## Journals / categories 변경

`config/journals.json`에서 `enabled`를 바꾸거나 항목을 추가합니다. 저널 이름, short, ISSN, PubMed 별칭, 고유 id를 입력합니다. 새 저널은 코드 수정 없이 수집됩니다.

기본: Veterinary Surgery, VCOT, JSAP, JAVMA, JVIM, Veterinary and Comparative Oncology.

선택 확장: Journal of Veterinary Cardiology(심장질환 임상 연구), Journal of Veterinary Emergency and Critical Care(응급·중환자 진료)는 설정에 비활성 상태로 포함했습니다. 필요할 때 `enabled: true`로 바꿀 수 있습니다.

공식 publisher RSS가 실제로 사용 가능함을 확인한 뒤 해당 저널의 `feeds` 배열에 HTTPS 주소를 추가합니다. v1에는 확인되지 않은 feed URL을 넣지 않았습니다. RSS description은 teaser일 수 있으므로 자동으로 초록처럼 요약하지 않습니다. DOI/PMID로 정식 초록을 확보할 때까지 failed/missing_abstract로 보존합니다. 이후 PubMed 등에서 발견되면 병합됩니다. paywall 우회나 웹페이지 무단 대량 스크래핑은 하지 않습니다.

분야를 추가할 때는 `digest/models.py`의 Category/TAGS, `digest/analyze.py`의 분류 지침, `web/core.mjs`의 labels, `web/index.html`의 탐색 버튼을 함께 수정하고 테스트 사례를 추가합니다. tags 추가는 TAGS와 프롬프트/표시 라벨을 수정합니다.

## 데이터와 안전한 요약

메타데이터는 API 값이며 AI가 DOI·PMID·날짜를 생성하지 않습니다. 완전한 날짜가 없으면 null과 원본 날짜 문자열을 보존합니다. AI 분석은 `Analysis`로 strict boolean, 양의 정수/nullable 표본 수, enum 등을 검증합니다.

key_results에는 `result`와 정확한 `evidence_quote`가 있습니다. 출처에 없는 인용문이나 인용문에 없는 수치를 거부합니다. sample_size도 직접 명시된 전체 동물 수와 근거를 요구하며, 군별 수를 더해 추정하지 않습니다. 숫자 검사는 의미적 정확성을 완전히 증명하지 못합니다. 사용 전 근거 인용문과 원문을 함께 확인해야 합니다.

`Abstract-based summary`는 초록만 분석한 경우, `Full-text reviewed`는 합법적인 Europe PMC fullTextXML 본문을 실제로 확보해 입력한 경우만 표시합니다. 원문 전문은 공개 JSON에 복사하지 않습니다. 요약 생성 시각, 모델, 근거 URL·종류, 내부 근거 hash를 남깁니다.

상태 파일이 손상되면 실행을 중단하며 빈 파일로 덮어쓰지 않습니다. 기존 정상 파일을 백업한 뒤 버전 관리에서 복원하세요. `state.json`이 원본이고 `papers.json`은 공개 projection이므로 분석 데이터를 수동 편집하려면 상태 스키마도 지켜야 합니다.

## Tests / validation

```sh
python -m unittest discover -s tests -v
node --test tests/frontend.test.mjs
node --check web/app.mjs
python -m digest.build

# 네트워크 필요, 실제 API 호출, OpenAI 과금 없음
python -m tests.live_sources
python -m tests.live_e2e

# OPENAI_API_KEY 필수, 실제 분석 과금 발생
python -m tests.live_ai
```

오프라인 테스트는 PubMed/Europe PMC 파싱, DOI/PMID 병합, 별칭 보완, 저널 매핑, 분류 출력 계약, 숫자·추천·schema 검증, 초록 누락, 실패 재시도, 일일 예산, 소스 장애, 실제 논문 fixture를 통한 전체 저장/공개 변환을 검증합니다. frontend 테스트는 KST 날짜, 추천 최대 3개, 분야 중복, 검색 필드, 필터, HTML escaping, 발행일 정렬을 검증합니다.

**분류 mock 테스트는 모델 정확도를 보장하지 않습니다.** TPLO, 만성 장질환, 비만세포종 절제연, 림프종 항암, 혈관육종 수술+항암 예시는 `live_ai`에서 유료 API로 별도 평가할 수 있습니다. synthetic eval 입력은 운영 데이터에 저장하지 않습니다.

실행 결과와 제한 사항은 [docs/validation.md](docs/validation.md)에 기록합니다.

## Troubleshooting

| 증상 | 확인 / 조치 |
|---|---|
| 자동 분석이 안 됨 | Secret `OPENAI_API_KEY`, 모델 접근 권한, 프로젝트 잔액 확인. 키가 없으면 수집은 저장하고 setup_required로 표시 |
| PubMed / Europe PMC timeout | stage=collect 로그와 소스별 결과 확인. 한 API 실패 시 나머지 API·기존 데이터 보존 |
| API 반환 형식 변경 | stage=parse / source 로그 확인, fixture 추가 후 parser 수정 |
| missing_abstract | 비용 없이 보류. 다음 실행에서 메타데이터 보완·재시도. 실제 초록이 영구히 없을 수도 있음 |
| 실패 논문이 같은 날 다시 안 됨 | 중복 비용 방지를 위해 같은 KST 날짜에는 재시도하지 않음 |
| malformed AI output / schema 오류 | 실패 상태만 저장하고 화면에 노출하지 않음. 모델의 Structured Outputs 지원 여부 확인 |
| DOI / PMID 없음 | title + journal fallback. 나중에 공식 식별자가 들어오면 alias 병합 |
| conflicting identifiers | 자동 병합 중단·로그 기록. 동일 제목만으로 알려진 상충 DOI를 합치지 않음 |
| source window exceeds 9999 | `--days`를 줄여 기간별 수집. 장기 백필은 작은 날짜 창으로 실행 |
| Pages 404 | Pages Source=GitHub Actions, deploy job 성공, 기본 브랜치 확인 |
| git push rejected | 브랜치 보호와 bot 쓰기 권한 확인. 동시 수동 푸시가 있었다면 현재 state를 보존하고 충돌 해결 |
| 사이트가 업데이트되지 않음 | Pages 배포 실패, 마지막 성공 수집 날짜, 예약 워크플로 활성 여부 확인 |
| No major clinical papers selected today | 정상적인 빈 상태. 오늘 최초 발견된 추천 논문이 없거나 필터에 맞지 않음 |
| 화면에 참고 샘플 표시 | 완료된 live 요약이 아직 0개. 안내 버튼으로 실제 수집 화면을 볼 수 있음 |

OpenAI 요청 실패 로그에는 키/요청 전체를 출력하지 않습니다. GitHub Actions의 실행 요약과 `collection-health` artifact에서 단계별 상태를 확인하세요.


## 읽음 표시

논문 카드의 `읽음 표시`를 누르면 `✓ 읽음`으로 바뀌고, 다시 누르면 취소됩니다. 같은 브라우저·사이트 주소의 localStorage에 저장되므로 새로고침하거나 검색·필터를 바꿔도 유지됩니다. DOI/PMID 별칭을 함께 저장해 식별자가 보완된 논문에도 표시를 유지합니다. 다른 기기·브라우저·주소(로컬 미리보기와 배포 주소 포함)로 자동 동기화되지는 않으며 사이트 데이터를 지우면 초기화됩니다. 저장소를 사용할 수 없는 경우 현재 화면에서만 유지됨을 안내합니다.

한글 본문은 맑은 고딕을 우선 사용하며, 해당 글꼴이 없는 기기에서는 Apple SD Gothic Neo 또는 기본 sans-serif로 표시합니다. 외부 폰트 다운로드는 필요하지 않습니다.

## 요약의 내용 충실도

출처에 있는 문장·수치를 쓰는 것만으로 충분한 요약이 되지는 않습니다. `key_results`에는 주요 연구 질문별 실제 결과와 중요한 무차이 결과를 포함하고, 한줄 요약·임상 해석이 그 결과에 연결되도록 합니다. 하위군, 투약 시점, 비교군, 평가 지표, 각 수치의 분모를 유지합니다. '차이가 관찰되지 않음'을 동등성이나 효과 없음의 입증으로 바꾸지 않습니다. 샘플 작성 방식은 출처 안내에 표시하며 연구 자체의 한계와 섞지 않습니다.

화면 결과에 없는 숫자를 한줄 요약·takeaway에서 사용하면 검증을 거부합니다. 다만 이러한 검사와 참고 샘플 회귀 테스트는 자동 생성 문장 전체의 의미적 정확성·충실도를 보증하지 않습니다. 실제 모델에 대한 추가 평가가 필요합니다.

## 상세 요약 구성 (업데이트)

- 카드의 `연구 요약`은 대상·설계·주요 수치·적용 범위를 담는 2~4문장입니다. 기존 데이터와의 호환을 위해 JSON의 `one_sentence_summary` 필드명은 유지하지만, 더 이상 한 문장으로 제한하지 않습니다.
- 펼친 상세에는 연구 목적, `study_methods`(대상·중재·대조군·추적·평가 지표), 구체적인 주요 결과, 저자 결론, 근거별 한계를 표시합니다. 초록만 확보한 경우 그 범위에서 요약합니다.
- Clinical takeaway 바로 위에 **AI가 자의적으로 해석한 내용이며, 논문 저자의 결론이 아닙니다.**라는 문구를 표시합니다. AI 해석도 제시된 근거를 벗어나도록 허용하는 것은 아닙니다.
- 신규 분석 프롬프트에 모호한 표현 대신 보고된 절대 수·분모·효과·추적 결과를 제시하도록 명시했습니다. 출력 토큰 기본 상한은 4800이며, 일일 논문 수 한도는 유지합니다.
- `study_methods`가 없는 과거 데이터도 읽을 수 있습니다. 이미 처리된 논문의 유료 자동 재분석은 실행하지 않습니다.

## 전문 우선 검토와 임상 해석

- 기본적으로 전문을 우선 시도합니다. PMCID가 없는 논문은 DOI 또는 PMID로 Europe PMC를 조회한 뒤, 공개 JATS XML 본문·표·포함된 부록을 확보합니다. 유료 전문에 접근하거나 접근 제한을 우회하지 않습니다. 현재 자동 확보 범위는 Europe PMC이며 모든 출판사의 공개 PDF를 수집하는 기능은 아닙니다.
- 본문을 실제 분석 입력에 모두 넣은 경우에만 `Full-text reviewed`로 표시합니다. 전문 확보 실패 또는 입력 상한 초과 시 초록으로 돌아가고 초록 기반으로 표시합니다. 전문을 잘라 넣고 전문 검토로 표시하지 않습니다. 기본 입력 상한은 120000자입니다.
- `AI 임상 해석 보기 ＋`를 누르면 Clinical takeaway가 독립적으로 펼쳐집니다. 적용 가능한 환자, 구체적인 판단에 주는 의미, 일반화의 한계를 담는 3~5문장(약 250~450자 목표)으로 작성합니다. 상세 연구 요약과 AI 해석은 각각 열고 닫을 수 있습니다.
- 전문 참고 사례: Yasuda et al., DOI `10.1093/jvimsj/aalag198`, PMCID `PMC13549437`. 본문·결과표·부록 텍스트를 검토했으며 영상 자체를 정량 재분석하지 않았습니다. 기존 7편은 공개 저장소에서 전문을 확보하지 못했으므로 초록 기반입니다.
- 자동 OpenAI 분석은 API 연결 후 실행됩니다. 화면의 참고 요약은 현재 작업에서 출처를 검토해 작성한 별도 데이터입니다.
