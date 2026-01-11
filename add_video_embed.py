#!/usr/bin/env python3
"""
생성된 노트에 YouTube iframe 임베딩 추가
"""

import re
import sys
from pathlib import Path


def extract_video_id_from_url(url: str) -> str:
    """YouTube URL에서 video_id 추출"""
    patterns = [
        r'(?:v=|\/videos\/|embed\/|youtu.be\/|\/v\/|\/e\/|watch\?v=|&v=)([^#\&\?\n]+)',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def create_video_embed(video_url: str, width: int = 960) -> str:
    """YouTube iframe 임베딩 HTML 생성"""
    video_id = extract_video_id_from_url(video_url)

    if not video_id:
        return ""

    # 16:9 비율 유지
    height = int(width * 9 / 16)

    embed_html = f"""
## 🎥 영상 보기

<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; margin: 20px 0;">
  <iframe
    style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
    width="{width}"
    height="{height}"
    src="https://www.youtube.com/embed/{video_id}"
    frameborder="0"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
    allowfullscreen>
  </iframe>
</div>

> 💡 영상 제목을 클릭하거나 우측 상단의 "YouTube에서 보기" 버튼을 누르면 브라우저에서 YouTube로 이동합니다.

---
"""

    return embed_html


def add_video_to_note(note_path: str, video_url: str):
    """노트 파일에 비디오 임베딩 추가"""

    # 파일 읽기
    with open(note_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 이미 iframe이 있는지 확인
    if '<iframe' in content or '## 🎥 영상 보기' in content:
        print(f"[SKIP] Already embedded: {note_path}")
        return False

    # iframe HTML 생성
    embed_html = create_video_embed(video_url)

    if not embed_html:
        print(f"[ERROR] Cannot parse URL: {video_url}")
        return False

    # 메타 정보 섹션 뒤에 삽입 (첫 번째 --- 뒤)
    # 패턴: 메타 정보 다음의 --- 를 찾아서 그 뒤에 삽입
    lines = content.split('\n')

    # --- 를 찾아서 그 뒤에 삽입
    dash_count = 0
    insert_position = 0

    for i, line in enumerate(lines):
        if line.strip() == '---':
            dash_count += 1
            if dash_count == 1:  # 첫 번째 --- 뒤
                insert_position = i + 1
                break

    if insert_position > 0:
        # 삽입
        lines.insert(insert_position, embed_html)
        new_content = '\n'.join(lines)

        # 파일 저장
        with open(note_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"[SUCCESS] Video embedded: {note_path}")
        return True
    else:
        print(f"[WARN] Cannot find --- separator: {note_path}")
        return False


def main():
    if len(sys.argv) < 2:
        print("""
YouTube 영상 임베딩 추가 도구

사용법:
  python add_video_embed.py <노트_파일> [YouTube_URL]

예시:
  # URL 자동 추출 (노트 파일의 메타데이터에서)
  python add_video_embed.py output/youtube_20260111_181129_detailed.md

  # URL 직접 지정
  python add_video_embed.py output/youtube_20260111_181129_detailed.md "https://youtu.be/x2ZX2Z5jEtc"

  # 여러 파일에 한 번에 추가
  python add_video_embed.py output/youtube_20260111_181129_*.md
        """)
        sys.exit(1)

    # 첫 번째 인자가 파일 경로
    note_paths = sys.argv[1:-1] if len(sys.argv) > 2 and sys.argv[-1].startswith('http') else sys.argv[1:]
    video_url_arg = sys.argv[-1] if len(sys.argv) > 2 and sys.argv[-1].startswith('http') else None

    success_count = 0

    for note_path in note_paths:
        note_file = Path(note_path)

        if not note_file.exists():
            print(f"[ERROR] File not found: {note_path}")
            continue

        # URL 결정 (직접 지정 또는 파일에서 추출)
        if video_url_arg:
            video_url = video_url_arg
        else:
            # 파일에서 출처 URL 추출
            with open(note_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('- 출처:'):
                        video_url = line.replace('- 출처:', '').strip()
                        break
                else:
                    print(f"[ERROR] Source URL not found in file: {note_path}")
                    continue

        # 영상 추가
        if add_video_to_note(note_path, video_url):
            success_count += 1

    print(f"\n[DONE] Completed: {success_count}/{len(note_paths)} files updated")


if __name__ == '__main__':
    main()
