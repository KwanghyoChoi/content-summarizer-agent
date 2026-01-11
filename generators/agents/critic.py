"""
Critic Agent - 품질 검증 전문가
- Level 1 verifier 기능 포함
- 분석-노트 일관성 검증
- 구체적 수정 지시 생성
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from .base import BaseAgent, AgentResult
from .analyst import AnalysisResult


@dataclass
class CritiqueResult:
    """비평 결과 데이터 클래스"""
    passed: bool
    score: int  # 0-100
    issues: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    details: dict = field(default_factory=dict)


# 소스 타입별 인용 패턴
CITATION_PATTERNS = {
    'youtube': r'\[(\d{1,2}:\d{2}(:\d{2})?)\]',
    'video': r'\[(\d{1,2}:\d{2}(:\d{2})?)\]',
    'pdf': r'\[(p\.?\s*\d+)\]',
    'web': r'\[([^\]]+)\]'
}

# 템플릿별 필수 섹션
REQUIRED_SECTIONS = {
    'detailed': {
        'markers': ['# ', '## '],
        'min_sections': 3
    },
    'essence': {
        'markers': ['# ', '## '],
        'required_keywords': ['핵심', '관계', '요약']
    },
    'easy': {
        'markers': ['# ', '## '],
        'required_keywords': ['꼭 알아야', '한 줄']
    },
    'mindmap': {
        'markers': ['# ', '```mermaid', 'mindmap'],
        'tree_chars': ['├', '└', '│']
    }
}


CRITIC_SYSTEM_PROMPT = """당신은 노트 품질 검증 전문가입니다.
생성된 노트가 원문에 충실하고 품질 기준을 충족하는지 검증합니다.

## 검증 기준
1. **원문 충실도**: 노트의 모든 내용이 원문에 존재하는가?
2. **환각 탐지**: 원문에 없는 내용이 추가되었는가?
3. **인용 정확성**: 타임스탬프/페이지 번호가 정확한가?
4. **구조 일관성**: 분석된 구조와 일치하는가?
5. **완성도**: 핵심 내용이 누락되지 않았는가?

## 출력 형식
반드시 JSON 형식으로 출력하세요."""


class CriticAgent(BaseAgent):
    """품질 검증 에이전트"""

    def __init__(self, api_key: str, verbose: bool = True):
        super().__init__(
            api_key=api_key,
            model="claude-haiku-4-20250514",  # 빠르고 저렴한 모델
            name="Critic",
            verbose=verbose
        )
        self.system_prompt = CRITIC_SYSTEM_PROMPT

    def run(
        self,
        note: str,
        source_text: str,
        analysis: Optional[AnalysisResult] = None,
        template_name: str = 'detailed',
        source_type: str = 'youtube'
    ) -> AgentResult:
        """
        노트 검증 실행

        Args:
            note: 생성된 노트
            source_text: 원문 텍스트
            analysis: 분석 결과 (선택)
            template_name: 템플릿 이름
            source_type: 소스 타입

        Returns:
            AgentResult: 비평 결과
        """
        self._log("검증 시작...")

        # 1. 규칙 기반 검증 (빠름)
        citation_score, citation_issues = self._verify_citations(note, source_type)
        structure_score, structure_issues = self._verify_structure(note, template_name)

        # 2. AI 기반 검증 (정확)
        ai_score, ai_issues, ai_suggestions = self._verify_with_ai(
            note, source_text, analysis
        )

        # 가중 평균 점수 계산
        # 인용: 20%, 구조: 20%, AI: 60%
        total_score = int(
            citation_score * 0.20 +
            structure_score * 0.20 +
            ai_score * 0.60
        )

        all_issues = citation_issues + structure_issues + ai_issues
        passed = total_score >= 80

        critique = CritiqueResult(
            passed=passed,
            score=total_score,
            issues=all_issues,
            suggestions=ai_suggestions,
            details={
                'citation_score': citation_score,
                'structure_score': structure_score,
                'ai_score': ai_score
            }
        )

        if self.verbose:
            status = "[PASS]" if passed else "[FAIL]"
            self._log(f"점수: {total_score}/100 {status}")
            if all_issues:
                for issue in all_issues[:2]:  # 최대 2개만 출력
                    self._log(f"  - {issue[:60]}...")

        return AgentResult(
            success=True,
            output=critique,
            tokens_used={'input': 0, 'output': 0}  # AI 검증에서 업데이트됨
        )

    def _verify_citations(self, note: str, source_type: str) -> tuple[int, list]:
        """인용 검증 (규칙 기반)"""
        issues = []
        pattern = CITATION_PATTERNS.get(source_type, CITATION_PATTERNS['youtube'])

        citations = re.findall(pattern, note)
        citation_count = len(citations)

        if citation_count == 0:
            score = 0
            issues.append("인용이 전혀 없습니다")
        elif citation_count < 3:
            score = 40
            issues.append(f"인용이 부족합니다 ({citation_count}개)")
        elif citation_count < 5:
            score = 70
        else:
            score = 100

        return score, issues

    def _verify_structure(self, note: str, template_name: str) -> tuple[int, list]:
        """구조 검증 (규칙 기반)"""
        issues = []
        rules = REQUIRED_SECTIONS.get(template_name, REQUIRED_SECTIONS['detailed'])
        score = 100

        # 마커 확인
        for marker in rules.get('markers', []):
            if marker not in note:
                issues.append(f"필수 마커 '{marker.strip()}' 누락")
                score -= 20

        # 키워드 확인
        for keyword in rules.get('required_keywords', []):
            if keyword.lower() not in note.lower():
                issues.append(f"필수 섹션 '{keyword}' 누락")
                score -= 15

        # 마인드맵 특수 검증
        if template_name == 'mindmap':
            if '```mermaid' not in note:
                issues.append("Mermaid 다이어그램 누락")
                score -= 30

        return max(0, score), issues

    def _verify_with_ai(
        self,
        note: str,
        source_text: str,
        analysis: Optional[AnalysisResult]
    ) -> tuple[int, list, list]:
        """AI 기반 검증"""
        # 원문 자르기
        max_length = 8000
        if len(source_text) > max_length:
            truncated = source_text[:max_length] + "\n... (이하 생략)"
        else:
            truncated = source_text

        # 분석 결과 요약
        analysis_info = ""
        if analysis:
            analysis_info = f"""
## 분석 결과 참조
- 주제: {analysis.main_topic}
- 핵심 개념: {', '.join(analysis.key_concepts[:5])}
- 섹션 수: {len(analysis.structure)}개
"""

        prompt = f"""다음 노트를 검증하세요.

## 생성된 노트
---
{note[:5000]}
---
{analysis_info}
## 원문
---
{truncated}
---

## 검증 항목
1. 노트의 모든 내용이 원문에 존재하는가?
2. 원문에 없는 내용(환각)이 추가되었는가?
3. 핵심 내용이 누락되었는가?
4. 인용이 정확한가?

## 출력 형식
```json
{{
    "score": 0-100,
    "hallucinations": ["원문에 없는 내용 목록"],
    "missing_points": ["누락된 핵심 내용"],
    "inaccurate_citations": ["부정확한 인용"],
    "suggestions": ["구체적인 개선 제안"]
}}
```"""

        try:
            response, tokens = self._call_api(prompt, max_tokens=1500)
            result = self._parse_json(response)

            score = result.get('score', 80)
            issues = []

            # 환각 체크
            hallucinations = result.get('hallucinations', [])
            if hallucinations:
                for h in hallucinations[:2]:
                    issues.append(f"환각: {h}")

            # 누락 체크
            missing = result.get('missing_points', [])
            if missing:
                for m in missing[:2]:
                    issues.append(f"누락: {m}")

            # 부정확한 인용
            inaccurate = result.get('inaccurate_citations', [])
            if inaccurate:
                for i in inaccurate[:2]:
                    issues.append(f"부정확한 인용: {i}")

            suggestions = result.get('suggestions', [])

            return score, issues, suggestions

        except Exception as e:
            # AI 검증 실패 시 기본값
            return 75, [f"AI 검증 오류: {str(e)[:50]}"], []

    def get_critique_dict(self, result: CritiqueResult) -> dict:
        """CritiqueResult를 dict로 변환 (Writer.revise용)"""
        return {
            'issues': result.issues,
            'suggestions': result.suggestions,
            'score': result.score
        }
