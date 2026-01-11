"""
BaseAgent - 모든 에이전트의 기본 클래스
"""

import time
import json
from dataclasses import dataclass, field
from typing import Any, Optional
from abc import ABC, abstractmethod


@dataclass
class AgentResult:
    """에이전트 실행 결과"""
    success: bool
    output: Any
    tokens_used: dict = field(default_factory=lambda: {'input': 0, 'output': 0})
    execution_time: float = 0.0
    error: Optional[str] = None


class BaseAgent(ABC):
    """
    모든 에이전트의 기본 클래스

    Attributes:
        api_key: Anthropic API 키
        model: 사용할 모델 (기본: claude-haiku-4-20250514)
        name: 에이전트 이름 (로깅용)
        system_prompt: 시스템 프롬프트
        verbose: 상세 출력 여부
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-20250514",
        name: str = "Agent",
        verbose: bool = True
    ):
        self.api_key = api_key
        self.model = model
        self.name = name
        self.verbose = verbose
        self.system_prompt = ""
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Anthropic client"""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic 패키지가 설치되지 않았습니다: pip install anthropic")
        return self._client

    def _call_api(
        self,
        user_message: str,
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> tuple[str, dict]:
        """
        API 호출

        Returns:
            tuple: (응답 텍스트, 토큰 사용량)
        """
        messages = [{"role": "user", "content": user_message}]

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages
        }

        if self.system_prompt:
            kwargs["system"] = self.system_prompt

        response = self.client.messages.create(**kwargs)

        tokens = {
            'input': response.usage.input_tokens,
            'output': response.usage.output_tokens
        }

        return response.content[0].text, tokens

    def _parse_json(self, text: str) -> dict:
        """
        텍스트에서 JSON 추출 및 파싱

        Args:
            text: JSON을 포함한 텍스트

        Returns:
            dict: 파싱된 JSON
        """
        # 코드 블록 안에 있을 수 있음
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0]
        elif '```' in text:
            text = text.split('```')[1].split('```')[0]

        # 앞뒤 공백 제거
        text = text.strip()

        return json.loads(text)

    def _log(self, message: str):
        """조건부 로깅"""
        if self.verbose:
            print(f"   [{self.name}] {message}")

    @abstractmethod
    def run(self, *args, **kwargs) -> AgentResult:
        """
        에이전트 실행 (하위 클래스에서 구현)

        Returns:
            AgentResult: 실행 결과
        """
        pass

    def execute(self, *args, **kwargs) -> AgentResult:
        """
        에이전트 실행 (시간 측정 포함)

        Returns:
            AgentResult: 실행 결과
        """
        start_time = time.time()

        try:
            result = self.run(*args, **kwargs)
            result.execution_time = time.time() - start_time

            if self.verbose and result.success:
                self._log(f"완료 ({result.execution_time:.1f}초)")

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            self._log(f"오류: {str(e)[:100]}")

            return AgentResult(
                success=False,
                output=None,
                execution_time=execution_time,
                error=str(e)
            )
