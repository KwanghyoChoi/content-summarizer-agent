"""
Orchestrator - 워크플로우 조율자
- 에이전트 간 협업 관리
- 분석 → 작성 → 검증 파이프라인 실행
- 피드백 루프 제어
"""

import time
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from .analyst import AnalystAgent, AnalysisResult
from .writer import WriterAgent
from .critic import CriticAgent, CritiqueResult


@dataclass
class GenerationResult:
    """노트 생성 결과"""
    success: bool
    note: str
    analysis: Optional[AnalysisResult] = None
    final_critique: Optional[CritiqueResult] = None
    attempts: int = 0
    total_time: float = 0.0
    total_tokens: dict = field(default_factory=lambda: {'input': 0, 'output': 0})
    error: Optional[str] = None


class Orchestrator:
    """
    에이전트 오케스트레이터

    분석 → 작성 → 검증 파이프라인을 조율하고
    필요시 피드백 루프를 통해 품질을 보장합니다.
    """

    def __init__(
        self,
        api_key: str,
        max_attempts: int = 3,
        min_score: int = 80,
        verbose: bool = True
    ):
        """
        Args:
            api_key: Anthropic API 키
            max_attempts: 최대 시도 횟수
            min_score: 최소 통과 점수
            verbose: 상세 출력 여부
        """
        self.api_key = api_key
        self.max_attempts = max_attempts
        self.min_score = min_score
        self.verbose = verbose

        # 에이전트 초기화
        self.analyst = AnalystAgent(api_key, verbose=verbose)
        self.writer = WriterAgent(api_key, verbose=verbose)
        self.critic = CriticAgent(api_key, verbose=verbose)

    def generate_note(
        self,
        source_text: str,
        template_name: str,
        source_type: str = 'youtube',
        video_id: Optional[str] = None
    ) -> GenerationResult:
        """
        노트 생성 파이프라인 실행

        Args:
            source_text: 원문 텍스트
            template_name: 템플릿 이름
            source_type: 소스 타입
            video_id: YouTube video ID (임베딩용)

        Returns:
            GenerationResult: 생성 결과
        """
        start_time = time.time()
        total_tokens = {'input': 0, 'output': 0}

        if self.verbose:
            print(f"\n   {'='*50}")
            print(f"   에이전트 파이프라인: {template_name}")
            print(f"   {'='*50}")

        # === Phase 1: 분석 ===
        if self.verbose:
            print("\n   [Phase 1] 콘텐츠 분석")

        analyst_result = self.analyst.execute(source_text, source_type)

        if not analyst_result.success:
            return GenerationResult(
                success=False,
                note="",
                error=f"분석 실패: {analyst_result.error}",
                total_time=time.time() - start_time
            )

        analysis = analyst_result.output
        self._add_tokens(total_tokens, analyst_result.tokens_used)

        # === Phase 2: 작성 ===
        if self.verbose:
            print("\n   [Phase 2] 노트 작성")

        writer_result = self.writer.execute(
            analysis, source_text, template_name, video_id
        )

        if not writer_result.success:
            return GenerationResult(
                success=False,
                note="",
                analysis=analysis,
                error=f"작성 실패: {writer_result.error}",
                total_time=time.time() - start_time
            )

        current_draft = writer_result.output
        self._add_tokens(total_tokens, writer_result.tokens_used)

        # === Phase 3: 검증 루프 ===
        if self.verbose:
            print("\n   [Phase 3] 품질 검증")

        best_draft = current_draft
        best_critique = None
        best_score = 0

        for attempt in range(1, self.max_attempts + 1):
            if self.verbose:
                print(f"\n   --- 시도 {attempt}/{self.max_attempts} ---")

            # 검증
            critic_result = self.critic.execute(
                current_draft,
                source_text,
                analysis,
                template_name,
                source_type
            )

            if not critic_result.success:
                if self.verbose:
                    print(f"   [Critic] 검증 오류: {critic_result.error}")
                continue

            critique = critic_result.output
            self._add_tokens(total_tokens, critic_result.tokens_used)

            # 최고 점수 기록
            if critique.score > best_score:
                best_score = critique.score
                best_draft = current_draft
                best_critique = critique

            # 통과 확인
            if critique.passed:
                if self.verbose:
                    print(f"\n   [SUCCESS] 검증 통과! 점수: {critique.score}/100")
                break

            # 마지막 시도가 아니면 수정
            if attempt < self.max_attempts:
                if self.verbose:
                    print(f"   [Writer] 피드백 반영 수정 중...")

                revise_result = self.writer.revise(
                    current_draft,
                    self.critic.get_critique_dict(critique),
                    source_text
                )

                if revise_result.success:
                    current_draft = revise_result.output
                    self._add_tokens(total_tokens, revise_result.tokens_used)

        total_time = time.time() - start_time

        if self.verbose:
            print(f"\n   {'='*50}")
            print(f"   완료: {total_time:.1f}초, 최종 점수: {best_score}/100")
            print(f"   토큰: 입력 {total_tokens['input']}, 출력 {total_tokens['output']}")
            print(f"   {'='*50}\n")

        return GenerationResult(
            success=True,
            note=best_draft,
            analysis=analysis,
            final_critique=best_critique,
            attempts=attempt,
            total_time=total_time,
            total_tokens=total_tokens
        )

    def _add_tokens(self, total: dict, new: dict):
        """토큰 사용량 누적"""
        total['input'] += new.get('input', 0)
        total['output'] += new.get('output', 0)


def generate_with_agents(
    raw_file_path: str,
    template_name: str,
    api_key: str,
    output_path: Optional[str] = None,
    source_type: str = 'youtube',
    max_attempts: int = 3,
    min_score: int = 80,
    verbose: bool = True
) -> dict:
    """
    에이전트 기반 노트 생성 (편의 함수)

    Args:
        raw_file_path: 원문 파일 경로
        template_name: 템플릿 이름
        api_key: Anthropic API 키
        output_path: 출력 파일 경로
        source_type: 소스 타입
        max_attempts: 최대 시도 횟수
        min_score: 최소 통과 점수
        verbose: 상세 출력 여부

    Returns:
        dict: 생성 결과
    """
    # 원문 로드
    from ..note_generator import load_raw_content

    raw_content = load_raw_content(raw_file_path)
    video_id = raw_content['metadata'].get('video_id', '')

    # 오케스트레이터 실행
    orchestrator = Orchestrator(
        api_key=api_key,
        max_attempts=max_attempts,
        min_score=min_score,
        verbose=verbose
    )

    result = orchestrator.generate_note(
        source_text=raw_content['full_text'],
        template_name=template_name,
        source_type=source_type,
        video_id=video_id
    )

    # 출력 경로 자동 생성
    if output_path is None:
        raw_path = Path(raw_file_path)
        base_name = raw_path.stem.replace('_raw', '')
        output_path = raw_path.parent / f'{base_name}_{template_name}.md'

    # 저장
    if result.success:
        import os
        os.makedirs(os.path.dirname(str(output_path)), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result.note)

    return {
        'success': result.success,
        'note_path': str(output_path) if result.success else None,
        'score': result.final_critique.score if result.final_critique else 0,
        'attempts': result.attempts,
        'total_time': result.total_time,
        'tokens': result.total_tokens,
        'video_id': video_id,
        'error': result.error
    }
