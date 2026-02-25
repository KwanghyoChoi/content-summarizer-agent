"""
긴 콘텐츠 청크 분할 및 병합 유틸리티

긴 동영상/PDF 등에서 추출한 텍스트가 API 한 번에 처리하기엔
너무 클 때, 청크로 분할하여 처리하고 결과를 병합합니다.
"""

import re
from typing import Optional


# 청크 처리가 필요한 최소 길이 (문자 수)
CHUNK_THRESHOLD = 20000

# 기본 청크 크기 (phased_pipeline.py와 동기화)
DEFAULT_CHUNK_SIZE = 20000

# 청크 간 겹침 줄 수 (문맥 유지용)
DEFAULT_OVERLAP_LINES = 5


def needs_chunking(text: str, threshold: int = CHUNK_THRESHOLD) -> bool:
    """텍스트가 청크 분할이 필요한지 확인"""
    return len(text) > threshold


def text_stats(text: str) -> dict:
    """텍스트 크기 통계 (사전 검사용)"""
    lines = text.split('\n')
    return {
        'chars': len(text),
        'lines': len(lines),
        'needs_chunking': len(text) > CHUNK_THRESHOLD,
        'estimated_chunks': max(1, (len(text) + DEFAULT_CHUNK_SIZE - 1) // DEFAULT_CHUNK_SIZE),
    }


def _is_paragraph_break(line: str, prev_line: str) -> bool:
    """자연스러운 문단 경계인지 판단"""
    # 빈 줄
    if not line.strip():
        return True
    # 타임스탬프로 시작하는 새 세그먼트 (동영상 자막)
    if re.match(r'^\[?\d{1,2}:\d{2}(:\d{2})?\]?\s', line):
        return True
    # 마크다운 헤더
    if line.startswith('#'):
        return True
    # 페이지 구분 (PDF)
    if re.match(r'^\[p\.\d+\]', line):
        return True
    # 이전 줄이 문장 종결 (. ! ? 로 끝남)
    if prev_line.rstrip().endswith(('.', '!', '?', '。', '다.', '요.', '죠.')):
        return True
    return False


def chunk_text(
    text: str,
    max_size: int = DEFAULT_CHUNK_SIZE,
    overlap_lines: int = DEFAULT_OVERLAP_LINES
) -> list[dict]:
    """
    텍스트를 자연스러운 문단 경계에서 청크로 분할

    max_size에 도달하면 가장 가까운 문단 경계를 찾아 분할합니다.
    적절한 경계가 없으면 줄 단위로 폴백합니다.

    Args:
        text: 전체 텍스트
        max_size: 청크당 최대 문자 수
        overlap_lines: 청크 간 겹침 줄 수 (문맥 연결용)

    Returns:
        list of dicts: [{'index': 0, 'text': '...', 'start_line': 0, 'end_line': 50}]
    """
    lines = text.split('\n')

    # 청크 분할이 필요 없으면 전체를 하나의 청크로
    if len(text) <= max_size:
        return [{
            'index': 0,
            'text': text,
            'start_line': 0,
            'end_line': len(lines) - 1,
        }]

    chunks = []
    current_lines = []
    current_size = 0
    chunk_start = 0
    # 문단 경계 후보 위치 (현재 청크 내에서의 인덱스)
    last_break_idx = -1

    for i, line in enumerate(lines):
        line_size = len(line) + 1  # +1 for newline

        # 문단 경계 확인
        prev_line = current_lines[-1] if current_lines else ''
        if current_lines and _is_paragraph_break(line, prev_line):
            last_break_idx = len(current_lines)  # 현재 줄 직전이 경계

        # 크기 초과 시 분할
        if current_size + line_size > max_size and current_lines:
            # 문단 경계에서 분할 시도 (최소 50% 이상 채웠을 때만)
            min_break = len(current_lines) // 2
            if last_break_idx > min_break:
                split_at = last_break_idx
            else:
                split_at = len(current_lines)

            chunk_lines = current_lines[:split_at]
            remaining_lines = current_lines[split_at:]

            chunks.append({
                'index': len(chunks),
                'text': '\n'.join(chunk_lines),
                'start_line': chunk_start,
                'end_line': chunk_start + len(chunk_lines) - 1,
            })

            # 겹침 + 남은 줄로 새 청크 시작
            overlap = chunk_lines[-overlap_lines:] if overlap_lines > 0 else []
            chunk_start = chunk_start + len(chunk_lines) - len(overlap)
            current_lines = list(overlap) + remaining_lines
            current_size = sum(len(l) + 1 for l in current_lines)
            last_break_idx = -1

        current_lines.append(line)
        current_size += line_size

    # 마지막 청크
    if current_lines:
        chunks.append({
            'index': len(chunks),
            'text': '\n'.join(current_lines),
            'start_line': chunk_start,
            'end_line': chunk_start + len(current_lines) - 1,
        })

    return chunks


def sample_source(text: str, max_length: int = 12000) -> str:
    """
    소스 텍스트에서 시작/중간/끝 부분을 골고루 샘플링

    단순 truncation(앞부분만 자르기) 대신, 텍스트의 여러 구간에서
    추출하여 전체 내용을 더 잘 대표하는 샘플을 생성합니다.

    Args:
        text: 전체 소스 텍스트
        max_length: 최대 출력 길이

    Returns:
        샘플링된 텍스트 (구간 구분자 포함)
    """
    if len(text) <= max_length:
        return text

    lines = text.split('\n')
    total_lines = len(lines)

    if total_lines <= 10:
        return text[:max_length]

    # 구분자 오버헤드 제거
    separator_overhead = 80  # 구분자 2개 ~40자씩
    usable_length = max_length - separator_overhead

    # 3등분: 시작 40%, 중간 30%, 끝 30%
    section_sizes = [
        int(usable_length * 0.40),
        int(usable_length * 0.30),
        int(usable_length * 0.30)
    ]

    # 시작 부분
    start_lines = []
    current_size = 0
    for line in lines:
        if current_size + len(line) + 1 > section_sizes[0]:
            break
        start_lines.append(line)
        current_size += len(line) + 1

    # 중간 부분 (전체의 40% 지점부터)
    mid_start = int(total_lines * 0.4)
    mid_lines = []
    current_size = 0
    for line in lines[mid_start:]:
        if current_size + len(line) + 1 > section_sizes[1]:
            break
        mid_lines.append(line)
        current_size += len(line) + 1

    # 끝 부분 (뒤에서부터 역방향으로 수집하여 실제 끝부분 확보)
    end_lines = []
    current_size = 0
    for line in reversed(lines):
        if current_size + len(line) + 1 > section_sizes[2]:
            break
        end_lines.insert(0, line)
        current_size += len(line) + 1
    end_start = total_lines - len(end_lines)

    # 조합
    parts = ['\n'.join(start_lines)]

    if mid_lines:
        parts.append(f'\n\n... [중간 부분 ~{mid_start}번째 줄부터] ...\n')
        parts.append('\n'.join(mid_lines))

    if end_lines:
        parts.append(f'\n\n... [후반 부분 ~{end_start}번째 줄부터] ...\n')
        parts.append('\n'.join(end_lines))

    return '\n'.join(parts)


def parse_timestamp_seconds(ts_str: str) -> Optional[float]:
    """타임스탬프 문자열을 초 단위로 변환"""
    # HH:MM:SS
    match = re.match(r'\[?(\d{1,2}):(\d{2}):(\d{2})\]?', ts_str)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return h * 3600 + m * 60 + s

    # MM:SS
    match = re.match(r'\[?(\d{1,2}):(\d{2})\]?', ts_str)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        return m * 60 + s

    return None


def merge_analysis_dicts(analyses: list[dict]) -> dict:
    """
    여러 청크의 분석 결과(dict)를 하나로 병합

    Args:
        analyses: 각 청크의 분석 결과 dict 리스트

    Returns:
        병합된 분석 결과 dict
    """
    if not analyses:
        return {}

    if len(analyses) == 1:
        return analyses[0]

    merged = {
        'main_topic': analyses[0].get('main_topic', ''),
        'content_type': _most_common(
            [a.get('content_type', 'lecture') for a in analyses]
        ),
        'structure': [],
        'key_concepts': [],
        'relationships': [],
        'difficulty_level': _most_common(
            [a.get('difficulty_level', 'intermediate') for a in analyses]
        ),
        'recommended_format': analyses[0].get('recommended_format', 'detailed'),
        'summary': ''
    }

    # 구조 병합 (순서 유지)
    for a in analyses:
        merged['structure'].extend(a.get('structure', []))

    # 핵심 개념 병합 (중복 제거, 순서 유지)
    seen_concepts = set()
    for a in analyses:
        for concept in a.get('key_concepts', []):
            if concept not in seen_concepts:
                seen_concepts.add(concept)
                merged['key_concepts'].append(concept)

    # 관계 병합 (중복 제거)
    seen_rels = set()
    for a in analyses:
        for rel in a.get('relationships', []):
            rel_key = (rel.get('from', ''), rel.get('to', ''), rel.get('type', ''))
            if rel_key not in seen_rels:
                seen_rels.add(rel_key)
                merged['relationships'].append(rel)

    # 요약 결합
    summaries = [a.get('summary', '') for a in analyses if a.get('summary')]
    merged['summary'] = ' '.join(summaries)

    return merged


def _most_common(items: list) -> str:
    """리스트에서 가장 많이 나타나는 항목 반환"""
    if not items:
        return ''
    counts = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return max(counts, key=counts.get)
