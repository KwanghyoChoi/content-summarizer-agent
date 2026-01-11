"""
노트 생성기
- 추출된 원문으로부터 4가지 형식의 노트 자동 생성
- Anthropic API 사용 (선택적)
- 프롬프트만 생성하여 수동 실행도 가능
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional


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
    save_prompt: bool = False
) -> dict:
    """
    노트 생성 메인 함수

    Args:
        raw_file_path: 추출된 원문 파일 경로
        template_name: 템플릿 이름 (detailed, essence, easy, mindmap)
        output_path: 출력 파일 경로 (None이면 자동 생성)
        api_key: Anthropic API 키 (None이면 프롬프트만 생성)
        save_prompt: 프롬프트를 파일로 저장할지 여부

    Returns:
        dict: {
            'success': bool,
            'note_path': str (API 사용시),
            'prompt_path': str (프롬프트 저장시),
            'prompt': str (프롬프트만 생성시),
            'video_id': str (임베딩용, YouTube인 경우)
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
        print(f"🤖 API를 사용하여 {template_name} 노트 생성 중...")
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
    formats: list = None
):
    """4가지 형식 노트 모두 생성"""
    if formats is None:
        formats = ['detailed', 'essence', 'easy', 'mindmap']

    print(f"\n{'='*60}")
    print(f"노트 생성: {len(formats)}가지 형식")
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
                save_prompt=(not api_key)  # API 없으면 프롬프트 저장
            )
            results[template_name] = result

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

    args = parser.parse_args()

    # API 키 확인
    api_key = None
    if args.auto:
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("[ERROR] ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
            print("   export ANTHROPIC_API_KEY='your-api-key' 로 설정하세요.\n")
            sys.exit(1)

    # 형식 선택
    if args.all:
        formats = ['detailed', 'essence', 'easy', 'mindmap']
        generate_all_notes(args.raw_file, args.output_dir, api_key, formats)
    elif args.format:
        result = generate_note(
            args.raw_file,
            args.format,
            None,
            api_key,
            args.save_prompt
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
