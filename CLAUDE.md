# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Content Summarizer is an AI-powered system for extracting and summarizing content from YouTube videos, PDFs, and web pages. The system prioritizes accuracy by only including content from the source material and always preserving citations.

---

## Claude Code 워크플로우 (중요!)

사용자가 소스(YouTube URL, PDF, 동영상, 웹페이지)를 제공하면 다음 워크플로우를 따릅니다:

### 1단계: 노트 형식 선택 (AskUserQuestion 사용)
```
사용자가 소스를 입력하면 즉시 AskUserQuestion 도구를 사용하여 노트 형식을 물어봅니다:

- question: "어떤 노트 형식을 생성할까요?"
- header: "노트 형식"
- multiSelect: true
- options:
  1. Detailed - 상세 노트 (계층적 구조의 포괄적인 노트)
  2. Essence - 핵심 노트 (5~10개 핵심 포인트)
  3. Easy - 쉬운 노트 (초보자용 3~5개 핵심)
  4. Mindmap - 마인드맵 (Mermaid 다이어그램 + 트리 구조)
```

### 2단계: 콘텐츠 추출
```bash
python main.py --youtube "URL" -f [선택한형식] --extract-only
```

### 3단계: 노트 생성
선택한 형식에 따라 노트를 생성합니다.

### 4단계: YouTube/동영상 임베딩
YouTube나 동영상 소스인 경우, 생성된 노트 상단에 반드시 임베딩을 추가합니다:
```markdown
# [제목]

<iframe width="1280" height="720" src="https://www.youtube.com/embed/[VIDEO_ID]" frameborder="0" allowfullscreen></iframe>

## 메타 정보
...
```

### 워크플로우 예시
```
사용자: https://youtu.be/ABC123

Claude Code:
1. AskUserQuestion으로 노트 형식 선택 물어봄
2. 사용자가 "Detailed, Essence" 선택
3. python main.py --youtube "URL" -f detailed,essence --extract-only 실행
4. 추출된 내용으로 Detailed, Essence 노트 생성
5. 각 노트 상단에 YouTube 임베딩 추가 (height=720)
6. 완료 보고
```

---

## Core Development Commands

### Installation
```bash
pip install -r requirements.txt
```

### Run Extractors
```bash
# YouTube extraction
python main.py --youtube "URL"

# PDF extraction
python main.py --pdf "path/to/file.pdf"

# Web page extraction
python main.py --web "URL"

# Extract only (skip note generation)
python main.py --youtube "URL" --extract-only

# Extract and auto-generate notes (requires ANTHROPIC_API_KEY)
python main.py --youtube "URL" --generate-notes

# Specify output formats
python main.py --youtube "URL" --formats detailed,essence
```

### Quick Start (All-in-One)
```bash
# Simplest way - auto-detect source type
python summarize.py "URL or file path" --auto

# Examples
python summarize.py "https://youtube.com/watch?v=..." --auto
python summarize.py "./document.pdf" --auto
python summarize.py "https://example.com/article" --formats essence,mindmap --auto
```

### Generate Notes from Extracted Content
```bash
# Generate all 4 note formats
python generators/note_generator.py output/youtube_*_raw.md --all --auto

# Generate specific format
python generators/note_generator.py output/youtube_*_raw.md --format detailed --auto

# Interactive mode
python quick_note.py

# Generate prompts only (for manual use with Claude.ai)
python generators/note_generator.py output/youtube_*_raw.md --all --save-prompt
```

### Run Individual Extractors
```bash
# Test extractors directly
python extractors/youtube.py "https://youtube.com/watch?v=..."
python extractors/pdf.py "./document.pdf"
python extractors/web.py "https://example.com/article"
```

## Architecture

### Two-Phase Design

The system operates in two distinct phases:

1. **Extraction Phase** (Python scripts)
   - Extracts raw content from sources
   - Validates extraction quality with scoring (0-100)
   - Preserves source location metadata (timestamps/page numbers/sections)
   - Outputs: JSON metadata + raw text file

2. **Note Generation Phase** (AI/manual)
   - Uses template prompts in `templates/` folder
   - Generates 4 note formats from extracted content
   - Must only use content from raw text (no inference)
   - Always includes source citations

### Extractor Pattern

All extractors (`extractors/youtube.py`, `extractors/pdf.py`, `extractors/web.py`) follow a common pattern:

1. Return `ExtractionResult` dataclass with:
   - `success`: bool
   - `source_type`: 'youtube'|'pdf'|'web'
   - `segments`: list with location metadata
   - `full_text`: formatted text with citations
   - `quality_score`: 0-100 with warnings
   - `warnings`: list of issues

2. Include `to_json()` function for serialization

3. Provide location mapping:
   - YouTube: timestamps `[HH:MM:SS]`
   - PDF: page numbers `[p.N]`
   - Web: section headings

### Main.py Workflow

1. Parse arguments (source type, output options)
2. Call appropriate extractor
3. Save JSON metadata: `{source}_{timestamp}_extracted.json`
4. Save raw text: `{source}_{timestamp}_raw.md`
5. Print instructions for manual note generation

Note: `main.py` does NOT generate notes automatically - it provides instructions for using the template prompts with AI tools.

## Note Generation Templates

Four templates in `templates/` directory define note formats:

- `detailed.md`: Comprehensive hierarchical notes (1. → 1.1 → 1.1.1)
- `essence.md`: 5-10 key points with concept relationships
- `easy.md`: 3-5 core points simplified for beginners
- `mindmap.md`: Mermaid diagram + text tree structure

Each template includes:
- Strict rules against inference/addition
- Required citation format
- Output structure specification
- DO/DON'T guidelines

## Critical Principles

When working with this codebase:

1. **Accuracy First**: Never add content not in the source
2. **Source Tracking**: All content must have location references
3. **Quality Validation**: Use quality_score and warnings systems
4. **Raw Preservation**: Always save complete raw text alongside summaries

## Automated Note Generation

The system now includes automated note generation:

- `generators/note_generator.py`: Core note generation module
  - Combines templates with extracted content
  - Supports Anthropic API for auto-generation
  - Falls back to prompt generation for manual use

- `summarize.py`: All-in-one wrapper script
  - Auto-detects source type (YouTube/PDF/Web)
  - Runs extraction + note generation in one command

- `quick_note.py`: Interactive note generator
  - Lists recent extractions
  - Dialog-based format selection
  - Quick regeneration of specific formats

Usage modes:
1. **Fully automated**: `--generate-notes` with ANTHROPIC_API_KEY
2. **Prompt generation**: `--save-prompts` for manual Claude.ai use
3. **Interactive**: `quick_note.py` for guided workflow

## Missing Components

The codebase does not include:
- Test suite (should test extractors, quality scoring, template parsing)
- Batch processing for multiple files
- Web UI or API server

If implementing these, maintain the two-phase separation and accuracy-first principles.
