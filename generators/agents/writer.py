"""
Writer Agent - 노트 작성 전문가
- 분석 결과 기반 노트 작성
- 템플릿 형식 준수
- 인용 자동 삽입
"""

from pathlib import Path
from typing import Optional
from .base import BaseAgent, AgentResult
from .analyst import AnalysisResult


def load_template(template_name: str) -> str:
    """템플릿 파일 로드"""
    template_path = Path(__file__).parent.parent.parent / 'templates' / f'{template_name}.md'

    if not template_path.exists():
        raise FileNotFoundError(f"템플릿을 찾을 수 없음: {template_path}")

    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


WRITER_SYSTEM_PROMPT = """당신은 전문 노트 작성자입니다.
분석 결과와 원문을 기반으로 고품질 노트를 작성합니다.

## 핵심 규칙
1. **원문에 있는 내용만** 포함 - 절대 추가하거나 추론하지 마세요
2. **모든 정보에 인용 표시** - [HH:MM:SS] 또는 [p.N] 형식
3. **분석된 구조를 따름** - 제공된 섹션 구조 활용
4. **템플릿 형식 준수** - 지정된 템플릿 스타일 적용

## 인용 규칙
- 모든 주요 내용에 타임스탬프/페이지 번호 포함
- 여러 위치를 참조할 경우 모두 표시: [00:01:30, 00:05:00]
- 인용은 문장 끝에 배치"""


class WriterAgent(BaseAgent):
    """노트 작성 에이전트"""

    def __init__(self, api_key: str, verbose: bool = True):
        super().__init__(
            api_key=api_key,
            model="claude-sonnet-4-20250514",  # 고품질 작성을 위해 Sonnet 사용
            name="Writer",
            verbose=verbose
        )
        self.system_prompt = WRITER_SYSTEM_PROMPT

    def run(
        self,
        analysis: AnalysisResult,
        source_text: str,
        template_name: str,
        video_id: Optional[str] = None
    ) -> AgentResult:
        """
        노트 작성 실행

        Args:
            analysis: 분석 결과
            source_text: 원문 텍스트
            template_name: 템플릿 이름 (detailed, essence, easy, mindmap)
            video_id: YouTube video ID (임베딩용)

        Returns:
            AgentResult: 작성된 노트
        """
        self._log(f"{template_name} 노트 작성 시작...")

        # 템플릿 로드
        try:
            template = load_template(template_name)
        except FileNotFoundError as e:
            return AgentResult(success=False, output=None, error=str(e))

        # 분석 결과를 문자열로 변환
        analysis_summary = self._format_analysis(analysis)

        # 비디오 임베딩 HTML
        embed_html = ""
        if video_id:
            embed_html = f'<iframe width="1280" height="720" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>'

        # 원문 자르기
        max_source_length = 12000
        if len(source_text) > max_source_length:
            truncated_source = source_text[:max_source_length] + "\n... (이하 생략)"
        else:
            truncated_source = source_text

        prompt = f"""다음 분석 결과와 원문을 바탕으로 {template_name} 형식의 노트를 작성하세요.

## 분석 결과
{analysis_summary}

## 템플릿 형식
{template}

## 원문
---
{truncated_source}
---

## 임베딩 (노트 제목 아래에 포함)
{embed_html if embed_html else "(임베딩 없음)"}

## 지시사항
1. 분석된 구조(섹션)를 따라 노트를 구성하세요
2. 모든 내용에 원문의 타임스탬프/페이지 번호를 인용하세요
3. 원문에 없는 내용은 절대 추가하지 마세요
4. 템플릿의 형식과 스타일을 정확히 따르세요

노트를 작성하세요:"""

        try:
            response, tokens = self._call_api(prompt, max_tokens=6000)

            if self.verbose:
                self._log(f"길이: {len(response)}자")
                # 인용 개수 확인
                import re
                citations = re.findall(r'\[\d{1,2}:\d{2}(:\d{2})?\]', response)
                self._log(f"인용: {len(citations)}개")

            return AgentResult(
                success=True,
                output=response,
                tokens_used=tokens
            )

        except Exception as e:
            return AgentResult(
                success=False,
                output=None,
                error=str(e)
            )

    def revise(
        self,
        current_draft: str,
        critique: dict,
        source_text: str
    ) -> AgentResult:
        """
        비평을 반영하여 노트 수정

        Args:
            current_draft: 현재 초안
            critique: 비평 결과 (issues, suggestions)
            source_text: 원문 텍스트

        Returns:
            AgentResult: 수정된 노트
        """
        self._log("피드백 반영 수정 중...")

        # 원문 자르기
        max_source_length = 8000
        if len(source_text) > max_source_length:
            truncated_source = source_text[:max_source_length] + "\n... (이하 생략)"
        else:
            truncated_source = source_text

        issues_str = "\n".join(f"- {issue}" for issue in critique.get('issues', []))
        suggestions_str = "\n".join(f"- {s}" for s in critique.get('suggestions', []))

        prompt = f"""다음 노트를 비평을 반영하여 수정하세요.

## 현재 노트
---
{current_draft}
---

## 발견된 문제점
{issues_str if issues_str else "없음"}

## 개선 제안
{suggestions_str if suggestions_str else "없음"}

## 원문 (참조용)
---
{truncated_source}
---

## 지시사항
1. 위의 문제점을 모두 해결하세요
2. 개선 제안을 반영하세요
3. 원문에 없는 내용은 절대 추가하지 마세요
4. 기존 형식은 유지하세요

수정된 노트를 작성하세요:"""

        try:
            response, tokens = self._call_api(prompt, max_tokens=6000)

            if self.verbose:
                self._log(f"수정 완료: {len(response)}자")

            return AgentResult(
                success=True,
                output=response,
                tokens_used=tokens
            )

        except Exception as e:
            return AgentResult(
                success=False,
                output=None,
                error=str(e)
            )

    def _format_analysis(self, analysis: AnalysisResult) -> str:
        """분석 결과를 프롬프트용 문자열로 변환"""
        lines = [
            f"- 주제: {analysis.main_topic}",
            f"- 유형: {analysis.content_type}",
            f"- 난이도: {analysis.difficulty_level}",
            f"- 요약: {analysis.summary}",
            "",
            "### 구조"
        ]

        for i, section in enumerate(analysis.structure, 1):
            lines.append(f"{i}. {section.get('section', 'Unknown')}")
            if section.get('timestamps'):
                lines.append(f"   시간: {', '.join(section['timestamps'])}")
            if section.get('key_points'):
                for point in section['key_points'][:3]:  # 최대 3개
                    lines.append(f"   - {point}")

        lines.append("")
        lines.append("### 핵심 개념")
        lines.append(", ".join(analysis.key_concepts[:10]))  # 최대 10개

        if analysis.relationships:
            lines.append("")
            lines.append("### 관계")
            for rel in analysis.relationships[:5]:  # 최대 5개
                lines.append(f"- {rel.get('from')} → {rel.get('to')} ({rel.get('type')})")

        return "\n".join(lines)
