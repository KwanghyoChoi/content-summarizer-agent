# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Content Summarizer is an AI-powered system for extracting and summarizing content from YouTube videos, local videos, PDFs, and web pages. The system prioritizes accuracy by only including content from the source material and always preserving citations.

---

## Quick Start Workflow

사용자가 소스(YouTube URL, 로컬 비디오, PDF, 웹페이지)를 제공하면:

1. **AskUserQuestion**으로 노트 형식 선택
2. **Python CLI**로 콘텐츠 추출
3. **에이전트 파이프라인**으로 노트 생성 (Analyst → Writer → Critic)
4. **검증 통과** (80점 이상) 후 저장

상세 워크플로우: `.claude/skills/content-summarizer/SKILL.md` 참조

---

## Agents & Skills

### Subagents (`.claude/agents/`)

| Agent | Role | Phase |
|-------|------|-------|
| `content-analyst` | 콘텐츠 구조 분석, JSON 출력 | Phase 1 |
| `note-writer` | 템플릿 기반 노트 작성 | Phase 2 |
| `note-critic` | 품질 검증, 점수화 (80점 통과) | Phase 3 |

### Skills (`.claude/skills/`)

| Skill | Purpose |
|-------|---------|
| `content-summarizer` | 전체 워크플로우 오케스트레이션 |

---

## Core Commands

### Content Extraction
```bash
# YouTube
python main.py --youtube "URL" --extract-only

# Local video (Whisper transcription)
python main.py --video "./video.mp4" --extract-only

# PDF
python main.py --pdf "path/to/file.pdf" --extract-only

# Web page
python main.py --web "URL" --extract-only

# With vision analysis (screen capture)
python main.py --youtube "URL" --with-vision --extract-only
```

### Output Files
```
output/
├── {title}_{source}_{date}_extracted.json  # Metadata
├── {title}_{source}_{date}_raw.md          # Full text
└── {title}_{source}_{date}_{format}.md     # Generated note
```

---

## Note Formats

| Format | Purpose | Coverage |
|--------|---------|----------|
| `detailed` | 완전한 계층적 노트 | 80-100% |
| `essence` | 5-10개 핵심 포인트 | 30-40% |
| `easy` | 초보자용 3-5개 핵심 | 10-20% |
| `mindmap` | Mermaid 시각화 | 키워드 |

상세 템플릿: `.claude/skills/content-summarizer/note-templates.md` 참조

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Phase 1: Extraction (Python)                                │
│  extractors/*.py → ExtractionResult → JSON + raw.md          │
└──────────────────────────────┬───────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────┐
│  Phase 2: Note Generation (Claude Agents)                    │
│  content-analyst → note-writer → note-critic → final.md     │
└──────────────────────────────────────────────────────────────┘
```

### Extractor Pattern

All extractors return `ExtractionResult`:
```python
@dataclass
class ExtractionResult:
    success: bool
    source_type: str      # 'youtube'|'video'|'pdf'|'web'
    segments: list        # [{start, end, text}] or [{page, text}]
    full_text: str        # Formatted with citations
    quality_score: int    # 0-100
    warnings: list        # Quality issues
```

---

## Critical Principles

1. **Accuracy First**: Never add content not in the source
2. **Mandatory Citations**: All content must have `[HH:MM:SS]` or `[p.N]`
3. **Quality Gate**: 80+ score required from critic agent
4. **Obsidian Integration**: Use `[[links]]` and `#tags`

---

## YouTube Embedding

For video sources, always include responsive embed:
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

---

## Installation

```bash
pip install -r requirements.txt

# For local video transcription
pip install openai-whisper opencv-python
```

---

## Entry Points

| Script | Purpose |
|--------|---------|
| `main.py` | Primary CLI with extraction |
| `summarize.py` | Auto-detect source type |
| `quick_note.py` | Interactive regeneration |
