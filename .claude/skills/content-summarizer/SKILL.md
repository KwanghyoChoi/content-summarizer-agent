---
name: content-summarizer
description: |
  콘텐츠 요약 워크플로우 오케스트레이션. YouTube, 로컬 비디오, PDF, 웹페이지에서
  콘텐츠를 추출하고 AI 에이전트 파이프라인으로 고품질 노트를 생성합니다.
  Use when user provides a URL (YouTube, web) or file path (video, PDF) to summarize.
---

# Content Summarizer Skill

콘텐츠 추출 및 노트 생성 워크플로우를 관리합니다.

## Workflow Overview

```
[사용자 입력] → [형식 선택] → [콘텐츠 추출] → [3-Phase 에이전트 파이프라인] → [완성된 노트]
                   ↓              ↓                    ↓
              AskUserQuestion  Python CLI      Analyst→Writer→Critic
```

## Step 1: Format Selection

사용자가 소스를 제공하면 즉시 AskUserQuestion으로 노트 형식을 물어봅니다:

```
Question: "어떤 노트 형식을 생성할까요?"
Header: "노트 형식"
MultiSelect: true
Options:
  1. Detailed - 상세 노트 (계층적 구조의 포괄적인 노트)
  2. Essence - 핵심 노트 (5~10개 핵심 포인트)
  3. Easy - 쉬운 노트 (초보자용 3~5개 핵심)
  4. Mindmap - 마인드맵 (Mermaid 다이어그램 + 트리 구조)
```

## Step 2: Content Extraction

소스 유형에 따라 적절한 추출 명령 실행:

```bash
# YouTube
python main.py --youtube "URL" --extract-only

# 로컬 비디오
python main.py --video "./video.mp4" --extract-only

# PDF
python main.py --pdf "path/to/file.pdf" --extract-only

# 웹페이지
python main.py --web "URL" --extract-only

# Vision 분석 (화면 캡처 포함)
python main.py --youtube "URL" --with-vision --extract-only
```

**출력 파일:**
- `output/{title}_{source}_{date}_extracted.json` - 메타데이터
- `output/{title}_{source}_{date}_raw.md` - 전체 텍스트

## Step 3: Agent Pipeline

### Phase 1: Content Analyst
```
Task 도구로 content-analyst 에이전트 실행
입력: raw.md 파일 경로
출력: 구조화된 JSON 분석 결과
```

### Phase 2: Note Writer
```
Task 도구로 note-writer 에이전트 실행
입력: 분석 JSON + raw.md + 선택된 템플릿
출력: 마크다운 노트 초안
```

### Phase 3: Note Critic
```
Task 도구로 note-critic 에이전트 실행
입력: 생성된 노트 + raw.md
출력: 검증 JSON (점수, 문제점, 개선 제안)
```

### Validation Loop
```
검증 점수 >= 80: 통과 → Step 4로 진행
검증 점수 < 80: 실패 → Writer가 수정 후 재검증
최대 3회 반복 후 강제 완료
```

## Step 4: Finalization

### YouTube/동영상 임베딩 추가
```html
<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; margin: 20px 0;">
  <iframe
    style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
    src="https://www.youtube.com/embed/[VIDEO_ID]"
    frameborder="0"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
    allowfullscreen>
  </iframe>
</div>
```

### 파일 저장
```
output/{title}_{source}_{date}_{format}.md
```

## Quick Reference

### Source Detection
| Pattern | Type | Command |
|---------|------|---------|
| `youtube.com`, `youtu.be` | YouTube | `--youtube` |
| `*.mp4`, `*.mkv`, `*.avi` | Video | `--video` |
| `*.pdf` | PDF | `--pdf` |
| `http*` (other) | Web | `--web` |

### Note Formats
| Format | Purpose | Coverage |
|--------|---------|----------|
| detailed | 완전한 학습 노트 | 80-100% |
| essence | 핵심 개념 정리 | 30-40% |
| easy | 초보자용 요약 | 10-20% |
| mindmap | 시각적 구조화 | 키워드 |

## Error Handling

### 추출 실패
- quality_score < 50: 경고 표시, 사용자에게 확인
- 자막 없음 (YouTube): `--with-vision` 옵션 제안

### 검증 실패 (3회)
- 현재 버전 저장 + 경고 메시지
- 문제점 요약 제공

## See Also

- [note-templates.md](note-templates.md) - 노트 형식 상세 가이드
- `.claude/agents/content-analyst.md` - 분석 에이전트
- `.claude/agents/note-writer.md` - 작성 에이전트
- `.claude/agents/note-critic.md` - 검증 에이전트
