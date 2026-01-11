"""
노트 생성기 모듈

## 아키텍처 레벨

### Level 1: 검증 루프 (Self-Critique)
- 생성 → 검증 → 재생성 파이프라인
- verifier.py: 규칙 기반 + AI 기반 검증
- Python + Anthropic API 사용

### Level 2: 전문화된 에이전트 (Claude Code 권장)
- Analyst → Writer → Critic 파이프라인
- Claude Code 내에서 Task 도구로 서브에이전트 실행
- 외부 API 불필요 (Claude Code 환경에서)
- 프롬프트 템플릿: templates/agents/

## 사용법

### Python API (Level 1)
```python
from generators import generate_with_verification
result = generate_with_verification(raw_path, template, api_key)
```

### Claude Code (Level 2 - 권장)
CLAUDE.md의 워크플로우 참조
- Task 도구로 Analyst/Writer/Critic 에이전트 순차 실행
- 외부 API 키 불필요
"""

from .note_generator import (
    generate_note,
    generate_all_notes,
    generate_with_verification,
    create_prompt,
    load_template,
    load_raw_content
)

from .verifier import (
    verify_note,
    verify_citations,
    verify_structure,
    verify_faithfulness,
    format_feedback,
    VerificationResult
)

# Level 2 에이전트 (Python API용 - Anthropic API 필요)
# Claude Code 환경에서는 Task 도구 사용 권장
from .agents import (
    Orchestrator,
    AnalystAgent,
    WriterAgent,
    CriticAgent,
    generate_with_agents
)

__all__ = [
    # Note Generator
    'generate_note',
    'generate_all_notes',
    'generate_with_verification',
    'create_prompt',
    'load_template',
    'load_raw_content',
    # Verifier (Level 1)
    'verify_note',
    'verify_citations',
    'verify_structure',
    'verify_faithfulness',
    'format_feedback',
    'VerificationResult',
    # Agents (Level 2)
    'Orchestrator',
    'AnalystAgent',
    'WriterAgent',
    'CriticAgent',
    'generate_with_agents'
]
