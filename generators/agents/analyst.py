"""
Analyst Agent - 콘텐츠 분석 전문가
- 주제 파악
- 구조 분석
- 핵심 개념 추출
- 관계 매핑
"""

from dataclasses import dataclass, field
from typing import Optional
from .base import BaseAgent, AgentResult


@dataclass
class AnalysisResult:
    """분석 결과 데이터 클래스"""
    main_topic: str
    content_type: str  # tutorial, lecture, interview, discussion, presentation
    structure: list  # [{section, timestamps, key_points}]
    key_concepts: list
    relationships: list  # [{from, to, type}]
    difficulty_level: str  # beginner, intermediate, advanced
    recommended_format: str  # detailed, essence, easy, mindmap
    summary: str
    metadata: dict = field(default_factory=dict)


ANALYST_SYSTEM_PROMPT = """당신은 콘텐츠 분석 전문가입니다.
주어진 텍스트를 분석하여 구조화된 정보를 추출합니다.

## 분석 항목
1. **주제 (main_topic)**: 콘텐츠의 핵심 주제를 한 문장으로
2. **유형 (content_type)**: tutorial, lecture, interview, discussion, presentation 중 선택
3. **구조 (structure)**: 주요 섹션별로 분할
   - section: 섹션 이름
   - timestamps: 해당 타임스탬프 범위 (예: ["00:00-02:30"])
   - key_points: 핵심 포인트 목록
4. **핵심 개념 (key_concepts)**: 중요한 용어/개념 목록
5. **관계 (relationships)**: 개념 간 관계
   - from: 시작 개념
   - to: 도착 개념
   - type: causes, enables, contradicts, supports, examples
6. **난이도 (difficulty_level)**: beginner, intermediate, advanced
7. **추천 형식 (recommended_format)**: 콘텐츠 특성에 맞는 노트 형식
8. **요약 (summary)**: 2-3문장 요약

## 출력 형식
반드시 JSON 형식으로 출력하세요."""


class AnalystAgent(BaseAgent):
    """콘텐츠 분석 에이전트"""

    def __init__(self, api_key: str, verbose: bool = True):
        super().__init__(
            api_key=api_key,
            model="claude-haiku-4-20250514",  # 빠르고 저렴한 모델
            name="Analyst",
            verbose=verbose
        )
        self.system_prompt = ANALYST_SYSTEM_PROMPT

    def run(self, source_text: str, source_type: str = 'youtube') -> AgentResult:
        """
        콘텐츠 분석 실행

        Args:
            source_text: 원문 텍스트
            source_type: 소스 타입 (youtube, video, pdf, web)

        Returns:
            AgentResult: 분석 결과
        """
        self._log("분석 시작...")

        # 원문이 너무 길면 요약
        max_length = 15000
        if len(source_text) > max_length:
            truncated = source_text[:max_length] + "\n... (이하 생략)"
        else:
            truncated = source_text

        prompt = f"""다음 콘텐츠를 분석하세요.

## 소스 타입
{source_type}

## 원문
---
{truncated}
---

## 출력 형식
```json
{{
    "main_topic": "주제",
    "content_type": "tutorial|lecture|interview|discussion|presentation",
    "structure": [
        {{
            "section": "섹션명",
            "timestamps": ["HH:MM:SS-HH:MM:SS"],
            "key_points": ["포인트1", "포인트2"]
        }}
    ],
    "key_concepts": ["개념1", "개념2"],
    "relationships": [
        {{"from": "A", "to": "B", "type": "causes|enables|supports|contradicts|examples"}}
    ],
    "difficulty_level": "beginner|intermediate|advanced",
    "recommended_format": "detailed|essence|easy|mindmap",
    "summary": "2-3문장 요약"
}}
```"""

        try:
            response, tokens = self._call_api(prompt, max_tokens=2000)
            analysis_dict = self._parse_json(response)

            # AnalysisResult로 변환
            analysis = AnalysisResult(
                main_topic=analysis_dict.get('main_topic', ''),
                content_type=analysis_dict.get('content_type', 'lecture'),
                structure=analysis_dict.get('structure', []),
                key_concepts=analysis_dict.get('key_concepts', []),
                relationships=analysis_dict.get('relationships', []),
                difficulty_level=analysis_dict.get('difficulty_level', 'intermediate'),
                recommended_format=analysis_dict.get('recommended_format', 'detailed'),
                summary=analysis_dict.get('summary', ''),
                metadata={'source_type': source_type}
            )

            if self.verbose:
                self._log(f"주제: {analysis.main_topic[:50]}...")
                self._log(f"유형: {analysis.content_type}")
                self._log(f"섹션: {len(analysis.structure)}개")
                self._log(f"핵심 개념: {len(analysis.key_concepts)}개")

            return AgentResult(
                success=True,
                output=analysis,
                tokens_used=tokens
            )

        except Exception as e:
            return AgentResult(
                success=False,
                output=None,
                error=str(e)
            )
