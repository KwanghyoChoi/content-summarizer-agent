#!/usr/bin/env python3
"""
Phased Pipeline - 단계별 콘텐츠 처리

긴 동영상/PDF 등을 안전하게 처리하기 위한 3단계 파이프라인.
각 단계를 독립적으로 실행할 수 있어 중간 실패 시 복구가 쉽습니다.

CRITICAL RULE: 원본 transcript를 한 번에 컨텍스트에 로드하지 않음.
항상 청크 파일을 통해 작업합니다.

Phase 1: 콘텐츠 추출 → transcript.txt (사전 크기 검사 포함)
Phase 2: transcript.txt → 문단 경계 기준 청크 → 구조화된 notes_partN.md
Phase 3: 파트 노트만 읽어 통합 (executive summary + 주제별 정리 + takeaways + timeline)

사용 예:
  # Phase 1: 추출
  python phased_pipeline.py --phase 1 --video "./long_video.mp4"
  python phased_pipeline.py --phase 1 --youtube "URL"

  # Phase 2: 청크별 노트 생성
  python phased_pipeline.py --phase 2 --work-dir ./output/my_video

  # Phase 3: 병합
  python phased_pipeline.py --phase 3 --work-dir ./output/my_video

  # 전체 실행 (1→2→3 자동)
  python phased_pipeline.py --video "./long_video.mp4"
"""

import argparse
import os
import sys
import re
import glob
from datetime import datetime
from pathlib import Path


def sanitize_dirname(text: str, max_length: int = 60) -> str:
    """디렉토리명에 안전한 문자열로 변환"""
    text = re.sub(r'[^\w\s\-가-힣]', '', text)
    text = re.sub(r'\s+', '_', text.strip())
    text = re.sub(r'_{2,}', '_', text)
    if len(text) > max_length:
        text = text[:max_length].rstrip('_')
    return text


def phase1_extract(args) -> str:
    """
    Phase 1: 콘텐츠 추출 → transcript.txt

    사전 크기 검사 포함. 청크 필요 여부를 미리 판단합니다.

    Returns:
        work_dir: 작업 디렉토리 경로
    """
    print("\n" + "=" * 60)
    print("Phase 1: 콘텐츠 추출")
    print("=" * 60)

    # 소스에 따른 추출
    if args.youtube:
        from extractors.youtube import extract_youtube
        print(f"\n[YouTube] {args.youtube}")
        result = extract_youtube(
            args.youtube, args.lang,
            with_vision=args.with_vision,
            vision_method=getattr(args, 'vision_method', 'scene'),
            max_frames=getattr(args, 'max_frames', 100)
        )
        source_name = 'youtube'
    elif args.video:
        from extractors.video import extract_video
        print(f"\n[Video] {args.video}")
        result = extract_video(
            args.video, args.lang,
            getattr(args, 'model', 'medium'),
            with_vision=args.with_vision,
            vision_method=getattr(args, 'vision_method', 'scene'),
            max_frames=getattr(args, 'max_frames', 100)
        )
        source_name = 'video'
    elif args.pdf:
        from extractors.pdf import extract_pdf
        print(f"\n[PDF] {args.pdf}")
        result = extract_pdf(args.pdf)
        source_name = 'pdf'
    elif args.web:
        from extractors.web import extract_web
        print(f"\n[Web] {args.web}")
        result = extract_web(args.web)
        source_name = 'web'
    else:
        print("[ERROR] 소스를 지정해주세요 (--youtube, --video, --pdf, --web)")
        sys.exit(1)

    if not result.success:
        print(f"\n[ERROR] 추출 실패: {result.warnings}")
        sys.exit(1)

    print(f"\n[OK] 추출 완료 (품질: {result.quality_score}/100)")

    # 작업 디렉토리 생성
    title = sanitize_dirname(getattr(result, 'title', source_name))
    date_str = datetime.now().strftime('%Y%m%d')
    work_dir_name = f"{title}_{source_name}_{date_str}"
    work_dir = os.path.join(args.output_dir, work_dir_name)
    os.makedirs(work_dir, exist_ok=True)

    # transcript.txt 저장
    transcript_path = os.path.join(work_dir, 'transcript.txt')
    with open(transcript_path, 'w', encoding='utf-8') as f:
        f.write(result.full_text)

    # === 사전 크기 검사 (wc -c / wc -l 대체) ===
    from generators.chunker import text_stats
    stats = text_stats(result.full_text)

    print(f"\n[SIZE CHECK]")
    print(f"   문자 수: {stats['chars']:,}")
    print(f"   줄 수:   {stats['lines']:,}")
    print(f"   청크 필요: {'예' if stats['needs_chunking'] else '아니오'}")
    if stats['needs_chunking']:
        chunk_size = getattr(args, 'chunk_size', 20000)
        estimated = max(1, (stats['chars'] + chunk_size - 1) // chunk_size)
        print(f"   예상 청크: {estimated}개 ({chunk_size:,}자 기준)")
    else:
        print(f"   → 단일 청크로 처리 가능")

    # 메타데이터 저장
    meta_path = os.path.join(work_dir, 'metadata.txt')
    with open(meta_path, 'w', encoding='utf-8') as f:
        f.write(f"source_type: {source_name}\n")
        f.write(f"source: {getattr(result, 'source_url', '') or getattr(result, 'source_path', '')}\n")
        f.write(f"title: {getattr(result, 'title', '')}\n")
        f.write(f"duration: {getattr(result, 'duration', '')}\n")
        f.write(f"language: {getattr(result, 'language', args.lang)}\n")
        f.write(f"quality_score: {result.quality_score}\n")
        f.write(f"extraction_date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"transcript_chars: {stats['chars']}\n")
        f.write(f"transcript_lines: {stats['lines']}\n")
        f.write(f"needs_chunking: {stats['needs_chunking']}\n")
        if hasattr(result, 'video_id') and result.video_id:
            f.write(f"video_id: {result.video_id}\n")
        if hasattr(result, 'model_used') and result.model_used:
            f.write(f"model_used: {result.model_used}\n")

    print(f"\n{'=' * 60}")
    print(f"Phase 1 완료!")
    print(f"작업 디렉토리: {work_dir}")
    print(f"{'=' * 60}")
    print(f"\n다음 단계:")
    print(f"  python phased_pipeline.py --phase 2 --work-dir \"{work_dir}\"")

    return work_dir


def phase2_chunk_notes(args) -> str:
    """
    Phase 2: transcript.txt → 문단 경계 기준 청크 → 구조화된 notes_partN.md

    각 파트 노트에 포함되는 구조:
    - 핵심 주제 (Key Topics)
    - 중요 인용 (Important Quotes)
    - 액션 아이템 (Action Items)
    - 타임스탬프 매핑 (Timestamps)

    Returns:
        work_dir: 작업 디렉토리 경로
    """
    work_dir = args.work_dir

    print("\n" + "=" * 60)
    print("Phase 2: 청크별 구조화 노트 생성")
    print("=" * 60)

    # transcript.txt 확인
    transcript_path = os.path.join(work_dir, 'transcript.txt')
    if not os.path.exists(transcript_path):
        print(f"[ERROR] transcript.txt를 찾을 수 없음: {transcript_path}")
        print("        Phase 1을 먼저 실행해주세요.")
        sys.exit(1)

    with open(transcript_path, 'r', encoding='utf-8') as f:
        transcript = f.read()

    # 메타데이터 로드
    meta = load_metadata(work_dir)

    # 사전 크기 검사
    from generators.chunker import text_stats, chunk_text
    stats = text_stats(transcript)

    print(f"\n[SIZE CHECK] {stats['chars']:,}자, {stats['lines']:,}줄")

    # 청크 분할 (문단 경계 인식)
    chunk_size = getattr(args, 'chunk_size', 20000)
    chunks = chunk_text(transcript, max_size=chunk_size, overlap_lines=5)

    print(f"[CHUNKS] {len(chunks)}개 청크 (문단 경계 기준, {chunk_size:,}자)")
    for i, c in enumerate(chunks):
        print(f"   chunk {i+1}: {len(c['text']):,}자 (줄 {c['start_line']+1}~{c['end_line']+1})")

    # 원본 transcript는 이제 메모리에서 불필요 - 청크만 사용
    del transcript

    # chunks/ 서브폴더에 원본 청크 저장 (디버깅/재사용용)
    chunks_dir = os.path.join(work_dir, 'chunks')
    os.makedirs(chunks_dir, exist_ok=True)
    for i, chunk in enumerate(chunks):
        chunk_path = os.path.join(chunks_dir, f'chunk_{i+1:03d}.txt')
        with open(chunk_path, 'w', encoding='utf-8') as f:
            f.write(chunk['text'])

    print(f"[OK] 청크 파일 저장: {chunks_dir}/")

    # API 키 확인
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("\n[WARN] ANTHROPIC_API_KEY 미설정 - 프롬프트만 저장합니다.")

    # 노트 형식
    note_format = getattr(args, 'note_format', 'detailed')

    # 청크별 구조화 노트 생성
    for i, chunk in enumerate(chunks):
        part_num = i + 1
        part_filename = f"notes_part{part_num}.md"
        part_path = os.path.join(work_dir, part_filename)

        # 이미 생성된 파트 스킵
        if os.path.exists(part_path) and not getattr(args, 'force', False):
            print(f"\n[SKIP] Part {part_num}/{len(chunks)} - 이미 존재 ({part_filename})")
            continue

        print(f"\n[{part_num}/{len(chunks)}] Part {part_num} 생성 중... ({len(chunk['text']):,}자)")

        if api_key:
            note_content = generate_structured_chunk_note(
                chunk['text'], note_format, meta, api_key,
                part_num, len(chunks)
            )
        else:
            note_content = create_structured_chunk_prompt(
                chunk['text'], note_format, meta,
                part_num, len(chunks)
            )

        with open(part_path, 'w', encoding='utf-8') as f:
            f.write(note_content)

        print(f"   [OK] 저장: {part_filename}")

    print(f"\n{'=' * 60}")
    print(f"Phase 2 완료! ({len(chunks)}개 파트)")
    print(f"작업 디렉토리: {work_dir}")
    print(f"{'=' * 60}")
    print(f"\n다음 단계:")
    print(f"  python phased_pipeline.py --phase 3 --work-dir \"{work_dir}\"")

    return work_dir


def phase3_combine(args) -> str:
    """
    Phase 3: notes_partN.md → final_notes.md

    CRITICAL: 원본 transcript를 읽지 않음. 오직 파트 노트만 읽어서 통합.

    최종 구조:
    1. Executive Summary (500단어)
    2. 주제별 상세 노트 (시간순 아닌 주제별 재구성)
    3. Key Takeaways
    4. Timeline (주요 포인트 시간순)
    5. 한국어 요약 (executive summary + takeaways 번역)

    Returns:
        final_path: 최종 노트 파일 경로
    """
    work_dir = args.work_dir

    print("\n" + "=" * 60)
    print("Phase 3: 통합 노트 생성")
    print("=" * 60)

    # 파트 파일 수집
    part_files = sorted(glob.glob(os.path.join(work_dir, 'notes_part*.md')))

    if not part_files:
        print(f"[ERROR] notes_partN.md 파일을 찾을 수 없음: {work_dir}")
        print("        Phase 2를 먼저 실행해주세요.")
        sys.exit(1)

    print(f"\n[INFO] {len(part_files)}개 파트 파일 발견")
    print(f"[RULE] 원본 transcript 미사용 - 파트 노트만으로 통합")

    # 메타데이터 로드
    meta = load_metadata(work_dir)

    # 파트 내용 읽기 (원본 transcript 아님!)
    parts = []
    total_chars = 0
    for pf in part_files:
        with open(pf, 'r', encoding='utf-8') as f:
            content = f.read()
        parts.append(content)
        total_chars += len(content)
        print(f"   - {os.path.basename(pf)} ({len(content):,}자)")

    print(f"   총 {total_chars:,}자")

    # API 키로 통합 생성 또는 단순 병합
    api_key = os.getenv('ANTHROPIC_API_KEY')

    if api_key and not getattr(args, 'no_merge_ai', False):
        print(f"\n[AI] 파트들을 주제별로 통합 정리 중...")
        if total_chars > 100000:
            print(f"   [INFO] 파트가 많아 계층적 병합 수행...")
            final_content = merge_hierarchical(parts, meta, api_key)
        else:
            final_content = merge_thematic(parts, meta, api_key)
    else:
        print(f"\n[MERGE] 파트들을 순서대로 병합 중...")
        final_content = merge_simple(parts, meta)

    # 최종 파일 저장
    final_path = os.path.join(work_dir, 'final_notes.md')
    with open(final_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f"\n[OK] 최종 노트 저장: {final_path} ({len(final_content):,}자)")

    # output 폴더에도 복사
    note_format = getattr(args, 'note_format', 'detailed')
    dir_name = os.path.basename(work_dir)
    output_copy = os.path.join(args.output_dir, f"{dir_name}_{note_format}.md")
    with open(output_copy, 'w', encoding='utf-8') as f:
        f.write(final_content)
    print(f"[OK] 복사본 저장: {output_copy}")

    print(f"\n{'=' * 60}")
    print("Phase 3 완료! 파이프라인 전체 종료.")
    print(f"{'=' * 60}")

    return final_path


# ============================================================
# Helper Functions
# ============================================================

def load_metadata(work_dir: str) -> dict:
    """메타데이터 파일 로드"""
    meta_path = os.path.join(work_dir, 'metadata.txt')
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    key, _, value = line.partition(':')
                    meta[key.strip()] = value.strip()
    return meta


# ============================================================
# Phase 2: 구조화된 청크별 노트 생성
# ============================================================

STRUCTURED_NOTE_PROMPT = """다음은 전체 콘텐츠의 Part {part_num}/{total_parts} 부분입니다.

## 메타 정보
- 제목: {title}
- 유형: {source_type}

## 지시사항
이 파트의 내용을 아래 구조로 정리해주세요.
반드시 원문에 있는 내용만 포함하고, 없는 내용은 추가하지 마세요.

### 출력 구조 (반드시 이 형식을 따르세요):

```
## Part {part_num}/{total_parts} 노트

### 핵심 주제 (Key Topics)
이 파트에서 다루는 주요 주제들을 계층적으로 정리

### 상세 내용 (Detailed Notes)
각 주제별 상세 설명, 정의, 예시 포함
- 모든 내용에 타임스탬프 [HH:MM:SS] 또는 페이지 [p.N] 인용 필수

### 중요 인용 (Key Quotes)
원문에서 특히 중요한 발언이나 문장을 그대로 인용
- "인용문" [타임스탬프]

### 액션 아이템 / 실천 포인트 (Action Items)
이 파트에서 언급된 실천 가능한 조언이나 방법론
(없으면 이 섹션 생략)

### 타임라인 (Timeline)
이 파트의 시간순 주요 포인트
- [HH:MM:SS] 내용 요약
```

## 원문 (Part {part_num}/{total_parts})
---
{chunk_text}
---
"""


def generate_structured_chunk_note(
    chunk_text: str,
    note_format: str,
    meta: dict,
    api_key: str,
    part_num: int,
    total_parts: int
) -> str:
    """API를 사용하여 구조화된 청크 노트 생성"""
    try:
        import anthropic
    except ImportError:
        print("   [WARN] anthropic 미설치, 프롬프트로 대체")
        return create_structured_chunk_prompt(chunk_text, note_format, meta, part_num, total_parts)

    client = anthropic.Anthropic(api_key=api_key)

    prompt = STRUCTURED_NOTE_PROMPT.format(
        part_num=part_num,
        total_parts=total_parts,
        title=meta.get('title', 'Unknown'),
        source_type=meta.get('source_type', 'Unknown'),
        chunk_text=chunk_text,
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


def create_structured_chunk_prompt(
    chunk_text: str,
    note_format: str,
    meta: dict,
    part_num: int,
    total_parts: int
) -> str:
    """API 없이 프롬프트를 파일로 저장"""
    return STRUCTURED_NOTE_PROMPT.format(
        part_num=part_num,
        total_parts=total_parts,
        title=meta.get('title', 'Unknown'),
        source_type=meta.get('source_type', 'Unknown'),
        chunk_text=chunk_text,
    )


# ============================================================
# Phase 3: 통합 (원본 transcript 사용하지 않음!)
# ============================================================

THEMATIC_MERGE_PROMPT = """다음은 하나의 콘텐츠를 청크별로 분석한 구조화된 노트들입니다.
이것들을 읽고 하나의 완성된 통합 노트로 재구성해주세요.

CRITICAL: 아래 파트 노트만 사용하세요. 원본 transcript는 참조하지 않습니다.

## 메타 정보
- 제목: {title}
- 유형: {source_type}
- 출처: {source}

## 출력 구조 (반드시 이 형식을 따르세요):

### 1. Executive Summary
전체 콘텐츠의 핵심을 500단어 내외로 요약.
무엇을, 왜, 어떻게 다루는지 명확히.

### 2. 주제별 상세 노트 (Thematic Notes)
시간순이 아닌 주제별로 재구성하여 정리.
- 각 주제에 관련 타임스탬프 [HH:MM:SS] 또는 [p.N] 인용 유지
- 중복 내용 제거
- 논리적 흐름으로 재배치

### 3. Key Takeaways
핵심 교훈 5-10개를 bullet point로 정리.

### 4. Timeline
전체 콘텐츠의 주요 포인트를 시간순으로 정리.
- [HH:MM:SS] 내용 요약

### 5. 한국어 요약 (Korean Summary)
Executive Summary와 Key Takeaways만 한국어로 번역.

## 추가 규칙
- Obsidian 호환 마크다운 형식 ([[links]], #tags)
- 소스에 없는 내용 추가 금지
- 모든 인용에 타임스탬프 유지

{video_embed}

## 파트별 노트
{combined_parts}

위 파트 노트들을 통합하여 완성된 노트를 생성해주세요.
"""


def merge_thematic(parts: list, meta: dict, api_key: str) -> str:
    """AI를 사용하여 주제별로 통합 (원본 transcript 사용 안 함)"""
    try:
        import anthropic
    except ImportError:
        return merge_simple(parts, meta)

    client = anthropic.Anthropic(api_key=api_key)

    combined = "\n\n---\n\n".join(parts)

    # 비디오 임베딩
    video_embed = ''
    video_id = meta.get('video_id', '')
    if video_id:
        video_embed = f"""## YouTube 임베딩
노트 제목 아래에 다음 코드를 포함하세요:
```html
<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; margin: 20px 0;">
  <iframe style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
    src="https://www.youtube.com/embed/{video_id}" frameborder="0"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
    allowfullscreen></iframe>
</div>
```"""

    prompt = THEMATIC_MERGE_PROMPT.format(
        title=meta.get('title', 'Unknown'),
        source_type=meta.get('source_type', 'Unknown'),
        source=meta.get('source', ''),
        video_embed=video_embed,
        combined_parts=combined,
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


def merge_hierarchical(parts: list, meta: dict, api_key: str) -> str:
    """
    파트가 많을 때 계층적 병합 (원본 transcript 사용 안 함)

    1단계: 인접 3개씩 묶어 중간 통합
    2단계: 중간 통합들을 최종 주제별 통합
    """
    try:
        import anthropic
    except ImportError:
        return merge_simple(parts, meta)

    client = anthropic.Anthropic(api_key=api_key)

    # 1단계: 3개씩 묶어 중간 요약
    group_size = 3
    mid_summaries = []

    for i in range(0, len(parts), group_size):
        group = parts[i:i + group_size]
        group_text = "\n\n---\n\n".join(group)
        group_range = f"Part {i+1}-{min(i+group_size, len(parts))}"

        print(f"   [1단계] {group_range} 통합 중...")

        prompt = f"""다음 파트 노트들을 하나로 통합하세요 ({group_range}/{len(parts)}개).

규칙:
- 중복 제거, 타임스탬프 유지
- 핵심 주제, 인용, 액션 아이템 구조 유지
- 소스에 없는 내용 추가 금지

{group_text}
"""
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        mid_summaries.append(response.content[0].text)

    # 2단계: 중간 요약들을 주제별 최종 통합
    print(f"   [2단계] 최종 주제별 통합 중...")
    combined_mid = "\n\n---\n\n".join(mid_summaries)

    video_embed = ''
    video_id = meta.get('video_id', '')
    if video_id:
        video_embed = f"""## YouTube 임베딩
노트 제목 아래에 다음 코드를 포함하세요:
```html
<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; margin: 20px 0;">
  <iframe style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
    src="https://www.youtube.com/embed/{video_id}" frameborder="0"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
    allowfullscreen></iframe>
</div>
```"""

    prompt = THEMATIC_MERGE_PROMPT.format(
        title=meta.get('title', 'Unknown'),
        source_type=meta.get('source_type', 'Unknown'),
        source=meta.get('source', ''),
        video_embed=video_embed,
        combined_parts=combined_mid,
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


def merge_simple(parts: list, meta: dict) -> str:
    """단순 순서대로 병합 (AI 없이)"""
    title = meta.get('title', 'Untitled')
    source = meta.get('source', '')
    video_id = meta.get('video_id', '')

    header = f"# {title}\n\n"
    header += f"- 출처: {source}\n"
    header += f"- 생성일: {datetime.now().strftime('%Y-%m-%d')}\n"
    header += f"- 파트 수: {len(parts)}\n\n"

    # YouTube 임베딩
    if video_id:
        header += (
            '<div style="position: relative; padding-bottom: 56.25%; '
            'height: 0; overflow: hidden; max-width: 100%; margin: 20px 0;">\n'
            '  <iframe\n'
            '    style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"\n'
            f'    src="https://www.youtube.com/embed/{video_id}"\n'
            '    frameborder="0"\n'
            '    allow="accelerometer; autoplay; clipboard-write; '
            'encrypted-media; gyroscope; picture-in-picture"\n'
            '    allowfullscreen>\n'
            '  </iframe>\n'
            '</div>\n\n'
        )

    header += "---\n\n"

    combined = header
    for i, part in enumerate(parts):
        if i > 0:
            combined += "\n\n---\n\n"
        combined += part

    return combined


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Phased Pipeline - 단계별 콘텐츠 처리',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 전체 실행 (Phase 1→2→3)
  python phased_pipeline.py --video "./long_video.mp4"
  python phased_pipeline.py --youtube "URL"

  # 단계별 실행
  python phased_pipeline.py --phase 1 --video "./video.mp4"
  python phased_pipeline.py --phase 2 --work-dir ./output/my_video
  python phased_pipeline.py --phase 3 --work-dir ./output/my_video

  # 옵션
  python phased_pipeline.py --phase 2 --work-dir ./output/my_video --chunk-size 30000
  python phased_pipeline.py --phase 2 --work-dir ./output/my_video --force  # 재생성
  python phased_pipeline.py --phase 3 --work-dir ./output/my_video --no-merge-ai
        """
    )

    # Phase 선택
    parser.add_argument('--phase', type=int, choices=[1, 2, 3],
                        help='실행할 단계 (미지정 시 전체 실행)')

    # 소스 (Phase 1용)
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument('--youtube', '-y', metavar='URL', help='YouTube URL')
    source_group.add_argument('--video', '-v', metavar='PATH', help='로컬 비디오 파일')
    source_group.add_argument('--pdf', '-p', metavar='PATH', help='PDF 파일')
    source_group.add_argument('--web', '-w', metavar='URL', help='웹페이지 URL')

    # 공통 옵션
    parser.add_argument('--output-dir', '-o', default='./output', help='출력 디렉토리 (기본: ./output)')
    parser.add_argument('--work-dir', help='작업 디렉토리 (Phase 2, 3에서 필수)')
    parser.add_argument('--lang', '-l', default='ko', help='언어 (기본: ko)')

    # Phase 1 옵션
    parser.add_argument('--model', '-m', default='medium',
                        choices=['tiny', 'base', 'small', 'medium', 'large-v3'],
                        help='Whisper 모델 (기본: medium)')
    parser.add_argument('--with-vision', action='store_true', help='프레임 추출')
    parser.add_argument('--vision-method', choices=['scene', 'interval'], default='scene')
    parser.add_argument('--max-frames', type=int, default=100)

    # Phase 2 옵션
    parser.add_argument('--chunk-size', type=int, default=20000,
                        help='청크 크기 (기본: 20000자)')
    parser.add_argument('--note-format', default='detailed',
                        choices=['detailed', 'essence', 'easy', 'mindmap'],
                        help='노트 형식 (기본: detailed)')
    parser.add_argument('--force', action='store_true',
                        help='기존 파트 파일 덮어쓰기')

    # Phase 3 옵션
    parser.add_argument('--no-merge-ai', action='store_true',
                        help='AI 병합 대신 단순 병합 사용')

    args = parser.parse_args()

    if args.phase == 1:
        if not (args.youtube or args.video or args.pdf or args.web):
            print("[ERROR] Phase 1에는 소스가 필요합니다 (--youtube, --video, --pdf, --web)")
            sys.exit(1)
        phase1_extract(args)

    elif args.phase == 2:
        if not args.work_dir:
            print("[ERROR] Phase 2에는 --work-dir이 필요합니다.")
            sys.exit(1)
        phase2_chunk_notes(args)

    elif args.phase == 3:
        if not args.work_dir:
            print("[ERROR] Phase 3에는 --work-dir이 필요합니다.")
            sys.exit(1)
        phase3_combine(args)

    else:
        # 전체 실행 (1→2→3)
        if not (args.youtube or args.video or args.pdf or args.web):
            parser.print_help()
            sys.exit(1)

        work_dir = phase1_extract(args)

        input(f"\nPhase 1 완료. Phase 2를 진행하려면 Enter를 누르세요...")

        args.work_dir = work_dir
        phase2_chunk_notes(args)

        input(f"\nPhase 2 완료. Phase 3를 진행하려면 Enter를 누르세요...")

        phase3_combine(args)


if __name__ == '__main__':
    main()
