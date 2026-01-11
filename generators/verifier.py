"""
노트 검증기 (Level 1: Self-Critique)
- 생성된 노트의 품질을 검증
- 인용, 구조, 원문 충실도 확인
- 검증 실패 시 피드백 제공
"""

import re
import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VerificationResult:
    """검증 결과 데이터 클래스"""
    passed: bool
    score: int  # 0-100
    issues: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    details: dict = field(default_factory=dict)


# 템플릿별 필수 섹션
REQUIRED_SECTIONS = {
    'detailed': {
        'markers': ['# ', '## '],
        'min_sections': 3,
        'min_subsections': 5
    },
    'essence': {
        'markers': ['# ', '## '],
        'required_keywords': ['핵심', '관계', '요약'],
        'min_points': 5
    },
    'easy': {
        'markers': ['# ', '## '],
        'required_keywords': ['꼭 알아야', '한 줄'],
        'min_points': 3
    },
    'mindmap': {
        'markers': ['# ', '```mermaid', 'mindmap'],
        'required_keywords': ['root'],
        'tree_chars': ['├', '└', '│']
    }
}

# 소스 타입별 인용 패턴
CITATION_PATTERNS = {
    'youtube': r'\[(\d{1,2}:\d{2}(:\d{2})?)\]',
    'video': r'\[(\d{1,2}:\d{2}(:\d{2})?)\]',
    'pdf': r'\[(p\.?\s*\d+)\]',
    'web': r'\[([^\]]+)\]'
}


def verify_citations(note: str, source_type: str = 'youtube') -> tuple[int, list, dict]:
    """
    인용 존재 및 분포 검증

    Returns:
        tuple: (점수 0-100, 이슈 목록, 상세 정보)
    """
    issues = []
    pattern = CITATION_PATTERNS.get(source_type, CITATION_PATTERNS['youtube'])

    citations = re.findall(pattern, note)
    citation_count = len(citations)

    # 노트 길이 대비 인용 밀도 계산
    note_length = len(note)
    lines = note.split('\n')
    content_lines = [l for l in lines if l.strip() and not l.startswith('#')]

    details = {
        'citation_count': citation_count,
        'note_length': note_length,
        'content_lines': len(content_lines)
    }

    # 점수 계산
    if citation_count == 0:
        score = 0
        issues.append("인용이 전혀 없습니다. 모든 주요 내용에 출처를 표시해야 합니다.")
    elif citation_count < 3:
        score = 40
        issues.append(f"인용이 부족합니다 ({citation_count}개). 최소 5개 이상 권장.")
    elif citation_count < 5:
        score = 70
        issues.append(f"인용이 다소 부족합니다 ({citation_count}개).")
    else:
        score = 100

    # 인용 분포 확인 (처음/중간/끝에 골고루 있는지)
    if citation_count > 0:
        first_citation = note.find('[')
        last_citation = note.rfind(']')

        if first_citation > note_length * 0.3:
            issues.append("노트 초반부에 인용이 없습니다.")
            score = max(0, score - 10)

        if last_citation < note_length * 0.7:
            issues.append("노트 후반부에 인용이 없습니다.")
            score = max(0, score - 10)

    return score, issues, details


def verify_structure(note: str, template_name: str) -> tuple[int, list, dict]:
    """
    템플릿 구조 준수 검증

    Returns:
        tuple: (점수 0-100, 이슈 목록, 상세 정보)
    """
    issues = []
    template_rules = REQUIRED_SECTIONS.get(template_name, REQUIRED_SECTIONS['detailed'])

    details = {
        'template': template_name,
        'sections_found': [],
        'keywords_found': []
    }

    score = 100

    # 마커 확인
    for marker in template_rules.get('markers', []):
        if marker not in note:
            issues.append(f"필수 마커 '{marker.strip()}' 가 없습니다.")
            score -= 20
        else:
            details['sections_found'].append(marker.strip())

    # 필수 키워드 확인
    for keyword in template_rules.get('required_keywords', []):
        if keyword.lower() not in note.lower():
            issues.append(f"필수 섹션 '{keyword}'이(가) 없습니다.")
            score -= 15
        else:
            details['keywords_found'].append(keyword)

    # 섹션 수 확인
    h2_count = note.count('\n## ')
    h3_count = note.count('\n### ')

    min_sections = template_rules.get('min_sections', 0)
    if min_sections > 0 and h2_count < min_sections:
        issues.append(f"섹션이 부족합니다 ({h2_count}개, 최소 {min_sections}개 필요)")
        score -= 15

    # 마인드맵 특수 검증
    if template_name == 'mindmap':
        if '```mermaid' not in note:
            issues.append("Mermaid 다이어그램이 없습니다.")
            score -= 30

        has_tree = any(char in note for char in template_rules.get('tree_chars', []))
        if not has_tree:
            issues.append("텍스트 트리 구조가 없습니다.")
            score -= 20

    details['h2_count'] = h2_count
    details['h3_count'] = h3_count

    return max(0, score), issues, details


def verify_faithfulness(
    note: str,
    source_text: str,
    api_key: str,
    model: str = "claude-haiku-4-20250514"
) -> tuple[int, list, dict]:
    """
    원문 충실도 검증 (AI 기반)

    Returns:
        tuple: (점수 0-100, 이슈 목록, 상세 정보)
    """
    try:
        import anthropic
    except ImportError:
        return 80, ["anthropic 패키지 없음 - AI 검증 생략"], {}

    if not api_key:
        return 80, ["API 키 없음 - AI 검증 생략"], {}

    # 원문이 너무 길면 앞부분만 사용
    max_source_length = 10000
    truncated_source = source_text[:max_source_length]
    if len(source_text) > max_source_length:
        truncated_source += "\n... (이하 생략)"

    verification_prompt = f"""당신은 노트 품질 검증 전문가입니다.

## 작업
생성된 노트가 원본 텍스트에 충실한지 검증하세요.

## 검증 기준
1. 노트의 모든 정보가 원본에 존재하는가?
2. 원본에 없는 내용이 추가되었는가? (환각/hallucination)
3. 핵심 내용이 누락되지 않았는가?

## 원본 텍스트
---
{truncated_source}
---

## 생성된 노트
---
{note}
---

## 출력 형식
반드시 다음 JSON 형식으로만 응답하세요:
{{
    "score": <0-100 정수>,
    "hallucinations": ["원본에 없는 내용 목록"],
    "missing_key_points": ["누락된 핵심 내용"],
    "suggestions": ["개선 제안"]
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model=model,
            max_tokens=1000,
            messages=[
                {"role": "user", "content": verification_prompt}
            ]
        )

        response_text = message.content[0].text.strip()

        # JSON 파싱 시도
        # 코드 블록 안에 있을 수 있음
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0]

        result = json.loads(response_text)

        score = result.get('score', 80)
        issues = []

        hallucinations = result.get('hallucinations', [])
        if hallucinations:
            issues.append(f"원본에 없는 내용 발견: {', '.join(hallucinations[:3])}")

        missing = result.get('missing_key_points', [])
        if missing:
            issues.append(f"누락된 핵심: {', '.join(missing[:3])}")

        details = {
            'hallucinations': hallucinations,
            'missing_key_points': missing,
            'suggestions': result.get('suggestions', [])
        }

        return score, issues, details

    except json.JSONDecodeError:
        return 70, ["AI 검증 응답 파싱 실패"], {'raw_response': response_text[:500]}
    except Exception as e:
        return 80, [f"AI 검증 오류: {str(e)[:100]}"], {}


def verify_note(
    note: str,
    source_text: str,
    template_name: str,
    api_key: Optional[str] = None,
    source_type: str = 'youtube'
) -> VerificationResult:
    """
    통합 노트 검증

    Args:
        note: 생성된 노트
        source_text: 원본 텍스트
        template_name: 템플릿 이름 (detailed, essence, easy, mindmap)
        api_key: Anthropic API 키 (None이면 AI 검증 생략)
        source_type: 소스 타입 (youtube, video, pdf, web)

    Returns:
        VerificationResult: 검증 결과
    """
    all_issues = []
    all_suggestions = []
    all_details = {}

    # 1. 인용 검증 (25%)
    citation_score, citation_issues, citation_details = verify_citations(note, source_type)
    all_issues.extend(citation_issues)
    all_details['citations'] = citation_details

    # 2. 구조 검증 (25%)
    structure_score, structure_issues, structure_details = verify_structure(note, template_name)
    all_issues.extend(structure_issues)
    all_details['structure'] = structure_details

    # 3. 원문 충실도 검증 (50%)
    if api_key:
        faithfulness_score, faithfulness_issues, faithfulness_details = verify_faithfulness(
            note, source_text, api_key
        )
        all_issues.extend(faithfulness_issues)
        all_details['faithfulness'] = faithfulness_details
        all_suggestions.extend(faithfulness_details.get('suggestions', []))
    else:
        faithfulness_score = 80  # API 없으면 기본값

    # 가중 평균 점수 계산
    total_score = int(
        citation_score * 0.25 +
        structure_score * 0.25 +
        faithfulness_score * 0.50
    )

    all_details['scores'] = {
        'citation': citation_score,
        'structure': structure_score,
        'faithfulness': faithfulness_score,
        'total': total_score
    }

    return VerificationResult(
        passed=total_score >= 80,
        score=total_score,
        issues=all_issues,
        suggestions=all_suggestions,
        details=all_details
    )


def format_feedback(result: VerificationResult) -> str:
    """
    검증 결과를 재생성용 피드백 문자열로 변환
    """
    feedback_parts = ["\n\n## 이전 생성 피드백\n"]
    feedback_parts.append(f"이전 시도 점수: {result.score}/100\n")

    if result.issues:
        feedback_parts.append("\n### 발견된 문제점:\n")
        for issue in result.issues:
            feedback_parts.append(f"- {issue}\n")

    if result.suggestions:
        feedback_parts.append("\n### 개선 제안:\n")
        for suggestion in result.suggestions:
            feedback_parts.append(f"- {suggestion}\n")

    feedback_parts.append("\n위 문제점을 해결하여 다시 생성해주세요.\n")

    return ''.join(feedback_parts)


if __name__ == '__main__':
    # 테스트
    test_note = """# 테스트 노트

## 핵심 내용
이것은 테스트입니다. [00:01:30]

### 세부 사항
더 자세한 내용 [00:05:00]
"""

    test_source = """[00:01:30] 이것은 테스트입니다.
[00:05:00] 더 자세한 내용이 있습니다."""

    result = verify_note(test_note, test_source, 'detailed', source_type='youtube')
    print(f"통과: {result.passed}")
    print(f"점수: {result.score}")
    print(f"이슈: {result.issues}")
    print(f"상세: {result.details}")
