"""
노트 생성기 모듈
- Level 1: 검증 루프 (Self-Critique) 지원
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

__all__ = [
    # Note Generator
    'generate_note',
    'generate_all_notes',
    'generate_with_verification',
    'create_prompt',
    'load_template',
    'load_raw_content',
    # Verifier
    'verify_note',
    'verify_citations',
    'verify_structure',
    'verify_faithfulness',
    'format_feedback',
    'VerificationResult'
]
