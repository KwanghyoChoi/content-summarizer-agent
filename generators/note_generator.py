"""
노트 생성기
- 추출된 원문으로부터 4가지 형식의 노트 자동 생성
- Anthropic API 사용 (선택적)
- 프롬프트만 생성하여 수동 실행도 가능
- Level 1: 검증 루프 (Self-Critique) 지원
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from .verifier import verify_note, format_feedback, VerificationResult


def load_template(template_name: str) -> str:
    """템플릿 파일 로드"""
    template_path = Path(__file__).parent.parent / 'templates' / f'{template_name}.md'

    if not template_path.exists():
        raise FileNotFoundError(f"템플릿을 찾을 수 없음: {template_path}")

    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_raw_content(raw_file_path: str) -> dict:
    """추출된 원문 파일 로드"""
    with open(raw_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 메타데이터와 본문 분리
    lines = content.split('\n')
    metadata = {}
    text_start = 0

    for i, line in enumerate(lines):
        if line.startswith('- 출처:'):
            metadata['source'] = line.replace('- 출처:', '').strip()
        elif line.startswith('- video_id:'):
            metadata['video_id'] = line.replace('- video_id:', '').strip()
        elif line.startswith('- 추출일:'):
            metadata['date'] = line.replace('- 추출일:', '').strip()
        elif line.startswith('- 품질점수:'):
            metadata['quality'] = line.replace('- 품질점수:', '').strip()
        elif line.strip() == '---' and i > 0:
            text_start = i + 1
            break

    # 본문 추출
    full_text = '\n'.join(lines[text_start:]).strip()

    return {
        'metadata': metadata,
        'full_text': full_text
    }


def get_video_embed_html(video_id: str, width: int = 1280, height: int = 720) -> str:
    """YouTube 임베딩 HTML 생성"""
    if not video_id:
        return ''
    return f'<iframe width="{width}" height="{height}" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>'


def create_prompt(template_name: str, raw_content: dict) -> str:
    """템플릿과 원문을 결합하여 완전한 프롬프트 생성"""
    template = load_template(template_name)

    # 템플릿의 입력 데이터 섹션 찾기
    if '## 입력 데이터' in template:
        # 입력 데이터 섹션 이전까지가 지시사항
        instruction_part = template.split('## 입력 데이터')[0]
    else:
        instruction_part = template

    # video_id가 있으면 임베딩 정보 추가
    video_id = raw_content['metadata'].get('video_id', '')
    embed_instruction = ''
    if video_id:
        embed_html = get_video_embed_html(video_id)
        embed_instruction = f"""
### 동영상 임베딩 (필수)
노트 제목 바로 아래에 다음 임베딩 코드를 반드시 포함하세요:
```html
{embed_html}
```
"""

    # 완전한 프롬프트 생성
    prompt = f"""{instruction_part}
## 입력 데이터

### 메타 정보
- 출처: {raw_content['metadata'].get('source', 'Unknown')}
- 추출일: {raw_content['metadata'].get('date', 'Unknown')}
- 품질점수: {raw_content['metadata'].get('quality', 'Unknown')}
{embed_instruction}
### 원문
---
{raw_content['full_text']}
---

위 원문을 기반으로 노트를 생성해주세요.
"""

    return prompt


def generate_with_api(prompt: str, api_key: str) -> str:
    """Anthropic API를 사용하여 노트 생성"""
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic 패키지가 설치되지 않았습니다: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return message.content[0].text


def generate_with_verification(
    prompt: str,
    source_text: str,
    template_name: str,
    api_key: str,
    source_type: str = 'youtube',
    max_attempts: int = 3,
    min_score: int = 80,
    verbose: bool = True
) -> tuple[str, VerificationResult]:
    """
    검증 루프가 포함된 노트 생성

    Args:
        prompt: 생성 프롬프트
        source_text: 원본 텍스트
        template_name: 템플릿 이름
        api_key: Anthropic API 키
        source_type: 소스 타입 (youtube, video, pdf, web)
        max_attempts: 최대 시도 횟수
        min_score: 최소 통과 점수 (0-100)
        verbose: 상세 출력 여부

    Returns:
        tuple: (생성된 노트, 검증 결과)
    """
    current_prompt = prompt
    best_note = None
    best_result = None

    for attempt in range(1, max_attempts + 1):
        if verbose:
            print(f"      [생성] {attempt}차 시도...")

        # 1. 노트 생성
        note = generate_with_api(current_prompt, api_key)

        # 2. 검증
        result = verify_note(
            note=note,
            source_text=source_text,
            template_name=template_name,
            api_key=api_key,
            source_type=source_type
        )

        if verbose:
            print(f"      [검증] 점수: {result.score}/100", end='')

        # 최고 점수 기록
        if best_result is None or result.score > best_result.score:
            best_note = note
            best_result = result

        # 3. 통과 확인
        if result.passed:
            if verbose:
                print(" [PASS]")
            return note, result

        # 4. 실패 시 피드백 출력 및 프롬프트 수정
        if verbose:
            print()
            for issue in result.issues[:3]:  # 최대 3개만 출력
                print(f"         - {issue}")

        if attempt < max_attempts:
            if verbose:
                print(f"      [재생성] 피드백 반영 중...")
            # 피드백을 프롬프트에 추가
            feedback = format_feedback(result)
            current_prompt = prompt + feedback

    # 최대 시도 후 최선의 결과 반환
    if verbose:
        print(f"      [완료] 최대 시도 도달. 최고 점수: {best_result.score}/100")

    return best_note, best_result


def save_note(content: str, output_path: str):
    """생성된 노트 저장"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)


def generate_note(
    raw_file_path: str,
    template_name: str,
    output_path: Optional[str] = None,
    api_key: Optional[str] = None,
    save_prompt: bool = False,
    use_verification: bool = True,
    source_type: str = 'youtube'
) -> dict:
    """
    노트 생성 메인 함수

    Args:
        raw_file_path: 추출된 원문 파일 경로
        template_name: 템플릿 이름 (detailed, essence, easy, mindmap)
        output_path: 출력 파일 경로 (None이면 자동 생성)
        api_key: Anthropic API 키 (None이면 프롬프트만 생성)
        save_prompt: 프롬프트를 파일로 저장할지 여부
        use_verification: 검증 루프 사용 여부 (기본: True)
        source_type: 소스 타입 (youtube, video, pdf, web)

    Returns:
        dict: {
            'success': bool,
            'note_path': str (API 사용시),
            'prompt_path': str (프롬프트 저장시),
            'prompt': str (프롬프트만 생성시),
            'video_id': str (임베딩용, YouTube인 경우),
            'verification': VerificationResult (검증 사용시)
        }
    """
    # 원문 로드
    raw_content = load_raw_content(raw_file_path)

    # 프롬프트 생성
    prompt = create_prompt(template_name, raw_content)

    # 출력 경로 자동 생성
    if output_path is None:
        raw_path = Path(raw_file_path)
        base_name = raw_path.stem.replace('_raw', '')
        output_dir = raw_path.parent
        output_path = output_dir / f'{base_name}_{template_name}.md'

    result = {
        'success': True,
        'video_id': raw_content['metadata'].get('video_id', '')
    }

    # API 키가 있으면 자동 생성
    if api_key:
        print(f"   [{template_name}] 노트 생성 중...")

        if use_verification:
            # 검증 루프 사용
            note_content, verification_result = generate_with_verification(
                prompt=prompt,
                source_text=raw_content['full_text'],
                template_name=template_name,
                api_key=api_key,
                source_type=source_type,
                max_attempts=3,
                min_score=80,
                verbose=True
            )
            result['verification'] = verification_result
            result['verification_score'] = verification_result.score
        else:
            # 검증 없이 생성
            note_content = generate_with_api(prompt, api_key)

        save_note(note_content, str(output_path))
        result['note_path'] = str(output_path)
        print(f"   [OK] 저장됨: {output_path}")

    # 프롬프트 저장 옵션
    if save_prompt:
        prompt_path = str(output_path).replace('.md', '_prompt.txt')
        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        result['prompt_path'] = prompt_path
        print(f"   [OK] 프롬프트 저장됨: {prompt_path}")

    # API 키 없으면 프롬프트 반환
    if not api_key:
        result['prompt'] = prompt

    return result


def generate_all_notes(
    raw_file_path: str,
    output_dir: Optional[str] = None,
    api_key: Optional[str] = None,
    formats: list = None,
    use_verification: bool = True,
    source_type: str = 'youtube'
):
    """4가지 형식 노트 모두 생성"""
    if formats is None:
        formats = ['detailed', 'essence', 'easy', 'mindmap']

    print(f"\n{'='*60}")
    print(f"노트 생성: {len(formats)}가지 형식")
    if use_verification:
        print(f"검증 모드: ON (Self-Critique)")
    print(f"{'='*60}\n")

    results = {}

    for template_name in formats:
        output_path = None
        if output_dir:
            raw_path = Path(raw_file_path)
            base_name = raw_path.stem.replace('_raw', '')
            output_path = Path(output_dir) / f'{base_name}_{template_name}.md'

        try:
            result = generate_note(
                raw_file_path,
                template_name,
                str(output_path) if output_path else None,
                api_key,
                save_prompt=(not api_key),  # API 없으면 프롬프트 저장
                use_verification=use_verification,
                source_type=source_type
            )
            results[template_name] = result

            # 검증 결과 요약 출력
            if api_key and use_verification and 'verification_score' in result:
                score = result['verification_score']
                status = "[PASS]" if score >= 80 else "[LOW]"
                print(f"      최종 점수: {score}/100 {status}\n")

            # API 없으면 프롬프트 출력
            if not api_key:
                print(f"\n{'='*60}")
                print(f"📋 {template_name.upper()} 노트 생성 프롬프트")
                print(f"{'='*60}\n")
                print("아래 프롬프트를 Claude.ai 또는 다른 AI에 입력하세요:\n")
                print(result['prompt'][:500] + "...\n")
                print(f"(전체 프롬프트 길이: {len(result['prompt'])} 문자)")
                if 'prompt_path' in result:
                    print(f"전체 프롬프트: {result['prompt_path']}\n")

        except Exception as e:
            print(f"[ERROR] {template_name} 생성 실패: {str(e)}")
            results[template_name] = {'success': False, 'error': str(e)}

    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='노트 생성기 - 추출된 원문으로부터 노트 생성',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 프롬프트만 생성 (수동 실행용)
  python generators/note_generator.py output/youtube_20240101_120000_raw.md --format detailed

  # API로 자동 생성 (ANTHROPIC_API_KEY 환경변수 필요)
  python generators/note_generator.py output/youtube_20240101_120000_raw.md --format detailed --auto

  # 전체 형식 생성
  python generators/note_generator.py output/youtube_20240101_120000_raw.md --all
        """
    )

    parser.add_argument('raw_file', help='추출된 원문 파일 (_raw.md)')
    parser.add_argument('--format', '-f', choices=['detailed', 'essence', 'easy', 'mindmap'],
                       help='생성할 노트 형식')
    parser.add_argument('--all', '-a', action='store_true', help='모든 형식 생성')
    parser.add_argument('--auto', action='store_true',
                       help='API로 자동 생성 (ANTHROPIC_API_KEY 환경변수 필요)')
    parser.add_argument('--output-dir', '-o', help='출력 디렉토리')
    parser.add_argument('--save-prompt', action='store_true', help='프롬프트를 파일로 저장')
    parser.add_argument('--no-verify', action='store_true',
                       help='검증 루프 비활성화 (빠르지만 품질 보장 없음)')
    parser.add_argument('--source-type', choices=['youtube', 'video', 'pdf', 'web'],
                       default='youtube', help='소스 타입 (기본: youtube)')
    parser.add_argument('--use-agents', action='store_true',
                       help='Level 2 에이전트 파이프라인 사용 (분석→작성→검증)')

    args = parser.parse_args()

    # API 키 확인
    api_key = None
    if args.auto:
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("[ERROR] ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
            print("   export ANTHROPIC_API_KEY='your-api-key' 로 설정하세요.\n")
            sys.exit(1)

    # 검증 옵션
    use_verification = not args.no_verify

    # 에이전트 모드 처리
    if args.use_agents:
        if not api_key:
            print("[ERROR] --use-agents는 API 키가 필요합니다.")
            print("   --auto 옵션과 함께 사용하거나 ANTHROPIC_API_KEY를 설정하세요.")
            sys.exit(1)

        from .agents.orchestrator import generate_with_agents

        formats = []
        if args.all:
            formats = ['detailed', 'essence', 'easy', 'mindmap']
        elif args.format:
            formats = [args.format]
        else:
            print("[ERROR] --format 또는 --all 옵션 중 하나를 선택하세요.")
            sys.exit(1)

        print(f"\n{'='*60}")
        print(f"Level 2: 에이전트 파이프라인 모드")
        print(f"형식: {', '.join(formats)}")
        print(f"{'='*60}")

        for template_name in formats:
            output_path = None
            if args.output_dir:
                raw_path = Path(args.raw_file)
                base_name = raw_path.stem.replace('_raw', '')
                output_path = str(Path(args.output_dir) / f'{base_name}_{template_name}.md')

            result = generate_with_agents(
                args.raw_file,
                template_name,
                api_key,
                output_path,
                args.source_type,
                max_attempts=3,
                min_score=80,
                verbose=True
            )

            if result['success']:
                print(f"   [OK] {template_name}: {result['note_path']}")
                print(f"        점수: {result['score']}/100, 시간: {result['total_time']:.1f}초")
            else:
                print(f"   [ERROR] {template_name}: {result.get('error', 'Unknown error')}")

    # 기존 모드 (Level 1)
    elif args.all:
        formats = ['detailed', 'essence', 'easy', 'mindmap']
        generate_all_notes(
            args.raw_file,
            args.output_dir,
            api_key,
            formats,
            use_verification=use_verification,
            source_type=args.source_type
        )
    elif args.format:
        result = generate_note(
            args.raw_file,
            args.format,
            None,
            api_key,
            args.save_prompt,
            use_verification=use_verification,
            source_type=args.source_type
        )

        if not api_key and 'prompt' in result:
            print(f"\n{'='*60}")
            print(f"📋 {args.format.upper()} 노트 생성 프롬프트")
            print(f"{'='*60}\n")
            print(result['prompt'])
    else:
        print("[ERROR] --format 또는 --all 옵션 중 하나를 선택하세요.")
        parser.print_help()
        sys.exit(1)
