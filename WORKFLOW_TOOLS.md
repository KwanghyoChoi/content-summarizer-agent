# 워크플로우별 도구 매핑

Content Summarizer의 4단계 워크플로우와 각 단계를 자동화하는 도구들을 설명합니다.

---

## 전체 워크플로우

```
┌─────────────────────────────────────────────────────────────────┐
│                    Content Summarizer                            │
│                    4단계 워크플로우                                │
└─────────────────────────────────────────────────────────────────┘

1. 추출 (Extract)
   ↓
   원본 텍스트 + 메타데이터 + 위치 정보

2. 검증 (Validate)
   ↓
   추출 품질 점수 (0-100) + 경고 사항

3. 구조화 (Structure)
   ↓
   섹션 분절 + 토픽 분류

4. 노트 생성 (Generate)
   ↓
   4가지 형식 동시 생성
```

---

## 1단계: 추출 (Extract)

### 담당 모듈
**`extractors/`** - 소스별 추출기

#### YouTube 추출기 (`extractors/youtube.py`)
**기능:**
- YouTube URL에서 video_id 추출
- 자막 우선순위: 수동 자막 → 자동 생성 자막
- 타임스탬프 매핑: 초 → `[HH:MM:SS]` 형식
- 노이즈 필터링: [음악], [박수] 등 제거

**출력:**
```python
ExtractionResult(
    source_type='youtube',
    segments=[{
        'start': '00:01:23',
        'end': '00:01:30',
        'text': '본문 내용'
    }, ...],
    full_text='[00:01:23] 본문 내용\n[00:01:30] ...'
)
```

#### PDF 추출기 (`extractors/pdf.py`)
**기능:**
- PDF 유형 자동 감지: 텍스트 PDF vs 스캔 PDF
- 텍스트 PDF: pdfplumber로 직접 추출
- 스캔 PDF: OCR (pytesseract) 자동 적용
- 페이지 번호 매핑: `[p.N]`

**출력:**
```python
ExtractionResult(
    source_type='pdf',
    segments=[{
        'page': 1,
        'text': '페이지 내용',
        'tables': 2
    }, ...],
    full_text='[p.1]\n페이지 내용\n\n[p.2]\n...'
)
```

#### 웹 추출기 (`extractors/web.py`)
**기능:**
- trafilatura로 본문 정확 추출 (광고/네비게이션 자동 제거)
- 실패 시 BeautifulSoup 폴백
- 메타데이터 추출: 제목, 작성자, 날짜
- 섹션 자동 분리

**출력:**
```python
ExtractionResult(
    source_type='web',
    sections=[{
        'heading': '섹션 제목',
        'content': '섹션 내용'
    }, ...],
    full_text='## 섹션 제목\n내용\n\n## ...'
)
```

---

## 2단계: 검증 (Validate)

### 담당 로직
각 추출기 내부의 `calculate_quality_score()` 함수

#### 검증 항목
1. **자막/추출 유형**: 수동 vs 자동 vs OCR
2. **완성도**: 빈 세그먼트, 누락 페이지
3. **텍스트 품질**: 평균 길이, 노이즈 비율
4. **구조 품질**: 단락 구분, 섹션 분리

#### 품질 점수 계산
```python
# 기본 점수: 100
score = 100

# 감점 요인
- 자동 생성 자막: -15점
- OCR 사용: -15점
- 빈 세그먼트 10% 이상: -10점
- 평균 텍스트 매우 짧음: -10점
- 누락 페이지 있음: -5점 × 페이지 수
```

#### 경고 생성
```python
warnings = [
    "자동 생성 자막 사용 - 오타/오류 가능성 있음",
    "3개 페이지 텍스트 없음",
    "OCR 추출 - 오류 가능성 있음"
]
```

---

## 3단계: 구조화 (Structure)

### 담당 로직
각 추출기 내부의 세그먼트 구조화

#### YouTube: 타임스탬프 기반 구조화
```python
segments = [
    {
        'start': '00:01:23',
        'start_seconds': 83,
        'end': '00:01:30',
        'end_seconds': 90,
        'text': '...'
    }
]
```

#### PDF: 페이지 기반 구조화
```python
segments = [
    {
        'page': 1,
        'text': '...',
        'tables': 2  # 테이블 개수
    }
]
```

#### Web: 섹션 기반 구조화
```python
sections = [
    {
        'heading': '서론',
        'content': '...'
    },
    {
        'heading': '본론',
        'content': '...'
    }
]
```

---

## 4단계: 노트 생성 (Generate)

### 담당 모듈
**`generators/note_generator.py`** - AI 기반 노트 생성기

#### 핵심 기능

##### 1. 템플릿 로딩 (`load_template()`)
```python
# templates/detailed.md, essence.md, easy.md, mindmap.md 로드
template = load_template('detailed')
```

##### 2. 프롬프트 결합 (`create_prompt()`)
```python
# 템플릿 + 원문 결합
prompt = f"""
{template_instructions}

## 입력 데이터
### 메타 정보
- 출처: {source_url}
- 품질점수: {quality_score}/100

### 원문
{full_text}
"""
```

##### 3. AI 생성 (`generate_with_api()`)
```python
# Anthropic API 호출
client = anthropic.Anthropic(api_key=api_key)
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": prompt}]
)
```

#### 4가지 노트 형식

##### detailed (자세한 노트)
- **목적**: 전체 내용 정리
- **구조**: 계층적 번호 (1. → 1.1 → 1.1.1)
- **특징**: 모든 예시, 세부사항 포함
- **길이**: 원문의 80-100%

##### essence (핵심 노트)
- **목적**: 핵심 개념 추출
- **구조**: 5-10개 포인트
- **특징**: 개념 간 관계도 포함
- **길이**: 원문의 30-40%

##### easy (쉬운 노트)
- **목적**: 입문자용 설명
- **구조**: 3-5개 최핵심
- **특징**: 전문용어 풀이, 비유
- **길이**: 원문의 10-20%

##### mindmap (마인드맵)
- **목적**: 시각적 구조
- **구조**: Mermaid 다이어그램 + 텍스트 트리
- **특징**: 키워드 중심
- **길이**: 구조만

---

## 통합 도구들

### 🚀 `summarize.py` - 올인원 자동화

**역할**: 전체 워크플로우 1-4단계 자동 실행

```bash
python summarize.py "URL 또는 파일" --auto
```

**내부 동작:**
```
1. 소스 타입 자동 감지
   ↓
   YouTube URL? → --youtube
   PDF 파일? → --pdf
   웹 URL? → --web

2. main.py 호출
   ↓
   python main.py --youtube "URL" --generate-notes

3. 결과 출력
   ↓
   - 추출 완료 (품질: 85/100)
   - 4가지 노트 생성 완료
```

### 🎯 `main.py` - 메인 실행기

**역할**: 1-3단계 자동 + 4단계 옵션

```bash
# 추출만
python main.py --youtube "URL" --extract-only

# 추출 + 자동 노트 생성
python main.py --youtube "URL" --generate-notes

# 추출 + 프롬프트 저장
python main.py --youtube "URL" --save-prompts
```

**내부 워크플로우:**
```
[1/3] 콘텐츠 추출 중...
├─ YouTube extractor 실행
├─ 품질 검증
└─ output/youtube_20240101_120000_extracted.json 저장

[2/3] 원문 저장 중...
└─ output/youtube_20240101_120000_raw.md 저장

[3/3] 노트 생성...
├─ --generate-notes 있으면: API로 자동 생성
├─ --save-prompts 있으면: 프롬프트 파일 저장
└─ 없으면: 수동 생성 방법 안내
```

### 💬 `quick_note.py` - 대화형 생성기

**역할**: 4단계 (노트 생성)만 대화형으로

```bash
python quick_note.py
```

**대화형 흐름:**
```
1. 추출된 파일 목록 표시
   ↓
   1. youtube_20240101_120000_raw.md
   2. pdf_20240101_130000_raw.md
   ...

2. 파일 선택
   ↓
   "파일 번호를 선택하세요 (1-10): " → 1

3. 형식 선택
   ↓
   1. detailed
   2. essence
   3. easy
   4. mindmap
   5. all
   "형식 번호를 선택하세요 (1-5): " → 5

4. 생성 방법 선택
   ↓
   1. 자동 생성 (API)
   2. 프롬프트만 생성
   "방법을 선택하세요 (1-2): " → 1

5. 실행
   ↓
   generators/note_generator.py 호출
```

---

## 사용 시나리오별 도구 선택

### 시나리오 1: 가장 빠르게 (완전 자동)
```bash
export ANTHROPIC_API_KEY='sk-ant-...'
python summarize.py "URL" --auto
```
**사용 도구**: `summarize.py` → `main.py` → `extractors/*` → `generators/note_generator.py`
**커버 단계**: 1→2→3→4 (전체)

### 시나리오 2: 추출과 생성 분리
```bash
# 1-3단계: 추출
python main.py --youtube "URL" --extract-only

# 4단계: 대화형 생성
python quick_note.py
```
**사용 도구**: `main.py` → `extractors/*` → `quick_note.py` → `generators/note_generator.py`
**커버 단계**: (1→2→3) then (4)

### 시나리오 3: API 없이 수동
```bash
# 1-3단계: 추출 + 프롬프트 생성
python main.py --youtube "URL" --save-prompts

# 4단계: 수동 (Claude.ai에 복사)
cat output/youtube_*_detailed_prompt.txt
# → Claude.ai에 붙여넣기
```
**사용 도구**: `main.py` → `extractors/*` → `generators/note_generator.py` (프롬프트만)
**커버 단계**: (1→2→3) + 4 준비

### 시나리오 4: 특정 형식만
```bash
# 1-3단계: 추출
python main.py --youtube "URL" --extract-only

# 4단계: essence만
python generators/note_generator.py output/youtube_*_raw.md --format essence --auto
```
**사용 도구**: `main.py` → `generators/note_generator.py`
**커버 단계**: (1→2→3) then (4-essence)

---

## 도구 간 데이터 흐름

```
┌──────────────────┐
│   summarize.py   │ ← 사용자 입력: URL/파일
└────────┬─────────┘
         │ 소스 타입 감지
         ↓
┌──────────────────┐
│     main.py      │ ← 옵션: --generate-notes, --save-prompts
└────────┬─────────┘
         │
    ┌────┴─────┬──────────┐
    ↓          ↓          ↓
┌─────────┐┌─────────┐┌─────────┐
│youtube  ││  pdf    ││  web    │ ← extractors/
│extractor││extractor││extractor│
└────┬────┘└────┬────┘└────┬────┘
     │          │          │
     └──────────┴──────────┘
                │
                ↓
        ┌───────────────┐
        │extracted.json │ ← 메타데이터
        │    raw.md     │ ← 원문 텍스트
        └───────┬───────┘
                │
    ┌───────────┴──────────────┐
    │                          │
    ↓                          ↓
┌─────────────────┐    ┌──────────────┐
│note_generator.py│    │quick_note.py │ ← 대화형 선택
└────────┬────────┘    └──────┬───────┘
         │                    │
         └────────┬───────────┘
                  │
         ┌────────┴────────┐
         │   load_template │ ← templates/*.md
         │   create_prompt │
         └────────┬────────┘
                  │
         ┌────────┴────────┐
         │                 │
         ↓                 ↓
    ┌─────────┐      ┌──────────┐
    │API 호출 │      │프롬프트  │
    │(자동)   │      │저장(수동)│
    └────┬────┘      └────┬─────┘
         │                │
         └────────┬───────┘
                  ↓
        ┌─────────────────┐
        │  detailed.md    │
        │  essence.md     │
        │  easy.md        │
        │  mindmap.md     │
        └─────────────────┘
```

---

## 핵심 원칙 적용

### 1. 정확성 우선 (모든 단계)
- **1단계**: 원본 그대로 추출 (필터링 최소화)
- **2단계**: 품질 문제 경고
- **3단계**: 원본 구조 보존
- **4단계**: 템플릿에 "원문에 있는 내용만" 명시

### 2. 출처 추적 (1→3→4 단계)
- **1단계**: 위치 정보 추출 (시간/페이지/섹션)
- **3단계**: 구조화 시 위치 보존
- **4단계**: 템플릿에 출처 표기 규칙 포함

### 3. 원문 보존 (2→4 단계)
- **2단계**: raw.md로 전체 저장
- **4단계**: 노트에 원문 첨부

---

## 확장 가능성

현재 구현되지 않았지만 같은 패턴으로 추가 가능한 기능:

### 새 추출기 추가
```python
# extractors/podcast.py
def extract_podcast(url: str) -> ExtractionResult:
    # 팟캐스트 오디오 → 텍스트
    # 타임스탬프 매핑
    # 화자 구분
    pass
```

### 새 노트 형식 추가
```markdown
# templates/qa.md (Q&A 형식)
- 원문에서 질문/답변 추출
- FAQ 형식으로 정리
```

### 배치 처리
```python
# batch_summarize.py
def process_multiple(urls: list):
    for url in urls:
        # 병렬 추출
        # 순차 노트 생성
```

모든 확장은 4단계 워크플로우와 핵심 원칙을 따릅니다.
