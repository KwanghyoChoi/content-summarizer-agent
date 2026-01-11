"""
YouTube 자막 추출기
- 공식 자막 우선 (수동 > 자동)
- 타임스탬프 매핑
- 품질 검증
"""

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import re
import json
import subprocess
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class ExtractionResult:
    """추출 결과 데이터 클래스"""
    success: bool
    source_type: str  # 'youtube'
    source_url: str
    video_id: str  # YouTube video ID (임베딩용)
    title: str
    channel: str  # 채널명
    upload_date: str  # 공개일 (YYYYMMDD)
    duration: str
    language: str
    transcript_type: str  # 'manual', 'auto', 'whisper'
    segments: list  # [{start, end, text}]
    full_text: str
    quality_score: int  # 0-100
    warnings: list


def extract_video_id(url: str) -> Optional[str]:
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


def get_video_metadata(video_id: str) -> dict:
    """
    yt-dlp로 YouTube 영상 메타데이터 가져오기

    Returns:
        dict: {'title': str, 'channel': str, 'upload_date': str}
    """
    try:
        # yt-dlp로 메타데이터만 가져오기 (영상 다운로드 안 함)
        result = subprocess.run(
            [
                'yt-dlp',
                '--dump-json',
                '--no-download',
                '--no-warnings',
                f'https://www.youtube.com/watch?v={video_id}'
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=30
        )

        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            return {
                'title': data.get('title', f'YouTube Video ({video_id})'),
                'channel': data.get('channel', data.get('uploader', 'Unknown')),
                'upload_date': data.get('upload_date', '')  # YYYYMMDD 형식
            }
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    # 실패 시 기본값 반환
    return {
        'title': f'YouTube Video ({video_id})',
        'channel': 'Unknown',
        'upload_date': ''
    }


def format_timestamp(seconds: float) -> str:
    """초를 HH:MM:SS 형식으로 변환"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def get_transcript_with_priority(video_id: str, preferred_lang: str = 'ko') -> tuple:
    """
    우선순위에 따라 자막 가져오기
    1. 수동 자막 (선호 언어)
    2. 수동 자막 (영어)
    3. 자동 생성 자막 (선호 언어)
    4. 자동 생성 자막 (영어)
    """
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        
        # 1. 수동 자막 시도
        try:
            transcript = transcript_list.find_manually_created_transcript([preferred_lang, 'en'])
            return transcript.fetch(), 'manual', transcript.language_code
        except NoTranscriptFound:
            pass
        
        # 2. 자동 생성 자막 시도
        try:
            transcript = transcript_list.find_generated_transcript([preferred_lang, 'en'])
            return transcript.fetch(), 'auto', transcript.language_code
        except NoTranscriptFound:
            pass
        
        # 3. 아무 자막이나 가져오기
        for transcript in transcript_list:
            return transcript.fetch(), transcript.is_generated and 'auto' or 'manual', transcript.language_code
            
    except TranscriptsDisabled:
        return None, 'disabled', None
    except Exception as e:
        return None, 'error', str(e)
    
    return None, 'not_found', None


def calculate_quality_score(segments: list, transcript_type: str) -> tuple[int, list]:
    """
    품질 점수 계산 (0-100)
    """
    warnings = []
    score = 100
    
    # 자막 유형에 따른 기본 점수
    if transcript_type == 'auto':
        score -= 15
        warnings.append("자동 생성 자막 사용 - 오타/오류 가능성 있음")
    
    if not segments:
        return 0, ["자막 없음"]
    
    # 빈 세그먼트 체크
    empty_count = sum(1 for s in segments if not s.get('text', '').strip())
    if empty_count > len(segments) * 0.1:
        score -= 10
        warnings.append(f"빈 세그먼트 {empty_count}개 발견")
    
    # 너무 짧은 세그먼트 체크 (노이즈 가능성)
    noise_patterns = ['[음악]', '[박수]', '[웃음]', '[Music]', '[Applause]']
    noise_count = sum(1 for s in segments if any(p in s.get('text', '') for p in noise_patterns))
    if noise_count > 5:
        warnings.append(f"노이즈 마커 {noise_count}개 (자동 필터링됨)")
    
    # 평균 세그먼트 길이 체크
    avg_length = sum(len(s.get('text', '')) for s in segments) / len(segments)
    if avg_length < 10:
        score -= 10
        warnings.append("평균 세그먼트가 매우 짧음 - 분절 품질 낮음")
    
    return max(0, min(100, score)), warnings


def extract_youtube(url: str, preferred_lang: str = 'ko') -> ExtractionResult:
    """
    YouTube 영상에서 자막 추출

    Args:
        url: YouTube URL
        preferred_lang: 선호 언어 코드 (기본: ko)

    Returns:
        ExtractionResult: 추출 결과
    """
    video_id = extract_video_id(url)

    if not video_id:
        return ExtractionResult(
            success=False,
            source_type='youtube',
            source_url=url,
            video_id='',
            title='',
            channel='',
            upload_date='',
            duration='',
            language='',
            transcript_type='',
            segments=[],
            full_text='',
            quality_score=0,
            warnings=['유효하지 않은 YouTube URL']
        )

    # 영상 메타데이터 가져오기
    metadata = get_video_metadata(video_id)
    
    # 자막 가져오기
    raw_transcript, transcript_type, language = get_transcript_with_priority(video_id, preferred_lang)

    if raw_transcript is None:
        return ExtractionResult(
            success=False,
            source_type='youtube',
            source_url=url,
            video_id=video_id,
            title=metadata['title'],
            channel=metadata['channel'],
            upload_date=metadata['upload_date'],
            duration='',
            language='',
            transcript_type=transcript_type,
            segments=[],
            full_text='',
            quality_score=0,
            warnings=[f'자막을 가져올 수 없음: {transcript_type}']
        )
    
    # 세그먼트 변환 및 노이즈 필터링
    noise_patterns = ['[음악]', '[박수]', '[웃음]', '[Music]', '[Applause]', '[음악재생]']
    segments = []

    for item in raw_transcript:
        # Handle both dict and object formats
        if hasattr(item, 'text'):
            text = item.text.strip()
            start = item.start
            duration = item.duration
        else:
            text = item['text'].strip()
            start = item['start']
            duration = item.get('duration', 0)

        # 노이즈 제거
        if any(p in text for p in noise_patterns):
            continue
        if not text:
            continue

        segments.append({
            'start': format_timestamp(start),
            'start_seconds': start,
            'end': format_timestamp(start + duration),
            'end_seconds': start + duration,
            'text': text
        })
    
    # 전체 텍스트 생성 (타임스탬프 포함)
    full_text_parts = []
    for seg in segments:
        full_text_parts.append(f"[{seg['start']}] {seg['text']}")
    full_text = '\n'.join(full_text_parts)
    
    # 품질 점수 계산
    quality_score, warnings = calculate_quality_score(segments, transcript_type)
    
    # 총 길이 계산
    if segments:
        duration = format_timestamp(segments[-1]['end_seconds'])
    else:
        duration = '00:00'

    return ExtractionResult(
        success=True,
        source_type='youtube',
        source_url=url,
        video_id=video_id,
        title=metadata['title'],
        channel=metadata['channel'],
        upload_date=metadata['upload_date'],
        duration=duration,
        language=language or '',
        transcript_type=transcript_type,
        segments=segments,
        full_text=full_text,
        quality_score=quality_score,
        warnings=warnings
    )


def to_json(result: ExtractionResult) -> str:
    """결과를 JSON 문자열로 변환"""
    return json.dumps(asdict(result), ensure_ascii=False, indent=2)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
        result = extract_youtube(url)
        print(to_json(result))
    else:
        print("Usage: python youtube.py <youtube_url>")
