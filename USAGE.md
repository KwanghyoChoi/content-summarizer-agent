# 사용 가이드

Content Summarizer의 사용법을 단계별로 설명합니다.

## 설치

```bash
# 의존성 설치
pip install -r requirements.txt

# API 키 설정 (자동 생성 기능 사용시)
export ANTHROPIC_API_KEY='your-api-key-here'
# Windows의 경우:
# set ANTHROPIC_API_KEY=your-api-key-here
```

---

## 방법 1: 올인원 모드 (가장 간단)

`summarize.py`를 사용하면 한 번에 모든 과정을 수행합니다.

### YouTube 요약
```bash
# 자동 노트 생성 (API 필요)
python summarize.py "https://youtube.com/watch?v=..." --auto

# 프롬프트만 생성 (수동)
python summarize.py "https://youtube.com/watch?v=..."
```

### PDF 요약
```bash
python summarize.py "./document.pdf" --auto
```

### 웹페이지 요약
```bash
python summarize.py "https://example.com/article" --auto
```

### 특정 형식만 생성
```bash
# 핵심 노트와 마인드맵만
python summarize.py "URL" --formats essence,mindmap --auto
```

---

## 방법 2: 단계별 실행

### 1단계: 콘텐츠 추출

```bash
# YouTube
python main.py --youtube "URL"

# PDF
python main.py --pdf "파일경로"

# 웹페이지
python main.py --web "URL"

# 추출만 (노트 생성 안 함)
python main.py --youtube "URL" --extract-only
```

추출 결과:
- `output/[source]_[timestamp]_raw.md` - 원문 텍스트
- `output/[source]_[timestamp]_extracted.json` - 메타데이터

### 2단계: 노트 생성

#### 옵션 A: 자동 생성 (권장)
```bash
# 추출과 동시에 노트 자동 생성
python main.py --youtube "URL" --generate-notes

# 또는 이미 추출된 파일에서
python generators/note_generator.py output/youtube_20240101_120000_raw.md --all --auto
```

#### 옵션 B: 대화형 모드
```bash
# 파일 선택과 형식 선택을 대화형으로
python quick_note.py
```

#### 옵션 C: 프롬프트 생성
```bash
# 프롬프트 파일 생성 (Claude.ai에 복붙용)
python generators/note_generator.py output/youtube_20240101_120000_raw.md --all --save-prompt
```

#### 옵션 D: Claude Code 사용
```
templates 폴더의 모든 템플릿을 참조하여
output/youtube_20240101_120000_raw.md 원문으로 4가지 노트를 모두 생성해줘
```

---

## 방법 3: 특정 형식만 생성

### 자세한 노트만
```bash
python generators/note_generator.py output/youtube_20240101_120000_raw.md --format detailed --auto
```

### 핵심 노트만
```bash
python generators/note_generator.py output/youtube_20240101_120000_raw.md --format essence --auto
```

### 쉬운 노트만
```bash
python generators/note_generator.py output/youtube_20240101_120000_raw.md --format easy --auto
```

### 마인드맵만
```bash
python generators/note_generator.py output/youtube_20240101_120000_raw.md --format mindmap --auto
```

---

## 출력 형식 설명

### 1. 자세한 노트 (detailed)
- **목적**: 전체 내용을 빠짐없이 정리
- **구조**: 계층적 번호 매기기 (1. → 1.1 → 1.1.1)
- **길이**: 가장 긺 (원문의 80-100%)
- **용도**: 학습, 참고자료, 아카이브

### 2. 핵심 노트 (essence)
- **목적**: 핵심 개념만 추출
- **구조**: 5-10개 주요 포인트
- **길이**: 중간 (원문의 30-40%)
- **용도**: 빠른 복습, 개념 파악

### 3. 쉬운 노트 (easy)
- **목적**: 입문자도 이해할 수 있게
- **구조**: 3-5개 최핵심 + 용어 설명
- **길이**: 짧음 (원문의 10-20%)
- **용도**: 처음 접하는 사람, 간단 요약

### 4. 마인드맵 (mindmap)
- **목적**: 시각적 구조 파악
- **구조**: Mermaid 다이어그램 + 텍스트 트리
- **길이**: 키워드 중심
- **용도**: 전체 흐름 파악, 발표 준비

---

## 고급 사용법

### 출력 디렉토리 지정
```bash
python main.py --youtube "URL" --output-dir ./my-notes --generate-notes
```

### 특정 언어 자막 선택
```bash
python main.py --youtube "URL" --lang en --generate-notes
```

### 프롬프트와 노트 모두 저장
```bash
python generators/note_generator.py output/youtube_20240101_120000_raw.md --all --auto --save-prompt
```

---

## 워크플로우 예시

### 시나리오 1: YouTube 강의 정리
```bash
# 1. 추출 및 자동 노트 생성
python summarize.py "https://youtube.com/watch?v=..." --auto

# 2. 결과 확인
ls output/

# 3. 필요시 특정 형식만 재생성
python quick_note.py
# → 파일 선택 → essence 선택 → 자동 생성
```

### 시나리오 2: PDF 논문 요약
```bash
# 1. 먼저 추출만
python main.py --pdf "./paper.pdf" --extract-only

# 2. 원문 확인 후 노트 생성
cat output/pdf_*_raw.md

# 3. 핵심 노트와 마인드맵만 생성
python generators/note_generator.py output/pdf_*_raw.md --format essence --auto
python generators/note_generator.py output/pdf_*_raw.md --format mindmap --auto
```

### 시나리오 3: API 없이 사용
```bash
# 1. 추출
python main.py --youtube "URL" --extract-only

# 2. 프롬프트 생성
python generators/note_generator.py output/youtube_*_raw.md --all --save-prompt

# 3. 생성된 프롬프트를 Claude.ai에 복사
cat output/youtube_*_detailed_prompt.txt
# → Claude.ai에 붙여넣기 → 결과 복사 → output/youtube_*_detailed.md에 저장
```

---

## 문제 해결

### "ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다"
```bash
# API 키 설정
export ANTHROPIC_API_KEY='sk-ant-...'

# 확인
echo $ANTHROPIC_API_KEY
```

### "자막을 가져올 수 없음"
- YouTube 영상이 자막을 지원하지 않을 수 있습니다
- 다른 언어 시도: `--lang en`

### "OCR 라이브러리 미설치"
```bash
# 스캔된 PDF 처리용 (선택적)
pip install pymupdf pytesseract
# Tesseract OCR도 시스템에 설치 필요
```

### "본문을 찾을 수 없음" (웹페이지)
- 일부 사이트는 크롤링 방지 기능이 있을 수 있습니다
- BeautifulSoup 폴백이 자동으로 시도됩니다

---

## 품질 확인

노트 생성 후 반드시 확인:
- [ ] 모든 핵심 내용이 포함되었는가?
- [ ] 원문에 없는 내용이 추가되지 않았는가?
- [ ] 타임스탬프/페이지 번호가 정확한가?
- [ ] 원문 전문이 첨부되었는가?

---

## 추가 도구

### 추출기를 직접 실행
```bash
# YouTube 추출기만
python extractors/youtube.py "URL"

# PDF 추출기만
python extractors/pdf.py "./file.pdf"

# 웹 추출기만
python extractors/web.py "URL"
```

### 템플릿 커스터마이징
```bash
# templates/ 폴더의 프롬프트 수정
# 자신만의 노트 스타일 정의 가능
vim templates/detailed.md
```

---

## 다음 단계

- [CLAUDE.md](./CLAUDE.md) - 개발자용 아키텍처 가이드
- [workflow.md](./workflow.md) - Claude Code 프롬프트 예시
- [templates/](./templates/) - 노트 생성 템플릿
