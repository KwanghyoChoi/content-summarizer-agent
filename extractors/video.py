"""
로컬 비디오 파일 자막 추출기
- Whisper를 사용한 음성 인식
- 타임스탬프 매핑
- 로컬 파일 메타데이터 추출
"""

import os
import re
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
import json


@dataclass
class ExtractionResult:
    """추출 결과 데이터 클래스"""
    success: bool
    source_type: str  # 'video'
    source_path: str
    title: str
    creation_date: str  # YYYYMMDD
    duration: str
    language: str
    transcript_type: str  # 'whisper'
    segments: list  # [{start, end, text}]
    full_text: str
    quality_score: int  # 0-100
    warnings: list


def format_timestamp(seconds: float) -> str:
    """초를 HH:MM:SS 형식으로 변환"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def extract_metadata_from_filename(filepath: str) -> dict:
    """
    파일명에서 메타데이터 추출
    예: 20240521_204707.mp4 -> 2024-05-21 20:47:07
    """
    filename = os.path.basename(filepath)
    name_without_ext = os.path.splitext(filename)[0]

    metadata = {
        'title': name_without_ext,
        'creation_date': ''
    }

    # YYYYMMDD_HHMMSS 패턴 감지
    date_match = re.match(r'^(\d{8})_(\d{6})', name_without_ext)
    if date_match:
        date_str = date_match.group(1)
        time_str = date_match.group(2)
        metadata['creation_date'] = date_str
        metadata['title'] = f"Video_{date_str}_{time_str}"

    return metadata


def transcribe_with_whisper(video_path: str, language: str = 'ko') -> tuple[list, list]:
    """
    Whisper를 사용하여 비디오 음성을 텍스트로 변환
    """
    try:
        import whisper

        print("   Whisper 모델 로딩 중...")
        # small 모델 사용 (base보다 정확도 향상)
        model = whisper.load_model("small")

        print("   음성 인식 중... (시간이 걸릴 수 있습니다)")
        # 음성 인식 수행
        result = model.transcribe(
            video_path,
            language=language,
            verbose=False,
            word_timestamps=True
        )

        segments = []
        warnings = []

        # 세그먼트 변환
        for seg in result['segments']:
            text = seg['text'].strip()
            if not text:
                continue

            segments.append({
                'start': format_timestamp(seg['start']),
                'start_seconds': seg['start'],
                'end': format_timestamp(seg['end']),
                'end_seconds': seg['end'],
                'text': text
            })

        if not segments:
            warnings.append("음성 인식 결과 없음")

        return segments, warnings

    except ImportError:
        return [], ["Whisper 라이브러리 미설치 (pip install openai-whisper)"]
    except Exception as e:
        return [], [f"Whisper 오류: {str(e)}"]


def get_video_duration(video_path: str) -> float:
    """비디오 재생 시간 가져오기"""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = frame_count / fps if fps > 0 else 0
        cap.release()
        return duration
    except:
        return 0


def calculate_quality_score(segments: list) -> tuple[int, list]:
    """품질 점수 계산"""
    warnings = []
    score = 100

    if not segments:
        return 0, ["자막 추출 실패"]

    # Whisper 사용 (자동 생성)
    score -= 10
    warnings.append("Whisper 자동 인식 - 오류 가능성 있음")

    # 세그먼트 개수 체크
    if len(segments) < 5:
        score -= 10
        warnings.append("세그먼트가 매우 적음")

    # 평균 길이 체크
    avg_length = sum(len(s['text']) for s in segments) / len(segments)
    if avg_length < 10:
        score -= 10
        warnings.append("평균 세그먼트가 매우 짧음")

    return max(0, min(100, score)), warnings


def extract_video(video_path: str, language: str = 'ko') -> ExtractionResult:
    """
    로컬 비디오 파일에서 음성 추출 및 텍스트 변환

    Args:
        video_path: 비디오 파일 경로
        language: 언어 코드 (기본: ko)

    Returns:
        ExtractionResult: 추출 결과
    """
    if not os.path.exists(video_path):
        return ExtractionResult(
            success=False,
            source_type='video',
            source_path=video_path,
            title='',
            creation_date='',
            duration='',
            language='',
            transcript_type='',
            segments=[],
            full_text='',
            quality_score=0,
            warnings=['파일을 찾을 수 없음']
        )

    # 파일명에서 메타데이터 추출
    metadata = extract_metadata_from_filename(video_path)

    # 비디오 재생 시간
    duration_seconds = get_video_duration(video_path)
    duration_str = format_timestamp(duration_seconds) if duration_seconds > 0 else "00:00"

    # Whisper로 음성 인식
    segments, warnings = transcribe_with_whisper(video_path, language)

    if not segments:
        return ExtractionResult(
            success=False,
            source_type='video',
            source_path=video_path,
            title=metadata['title'],
            creation_date=metadata['creation_date'],
            duration=duration_str,
            language=language,
            transcript_type='whisper',
            segments=[],
            full_text='',
            quality_score=0,
            warnings=warnings + ['음성 인식 실패']
        )

    # 전체 텍스트 생성 (타임스탬프 포함)
    full_text_parts = []
    for seg in segments:
        full_text_parts.append(f"[{seg['start']}] {seg['text']}")
    full_text = '\n'.join(full_text_parts)

    # 품질 점수 계산
    quality_score, quality_warnings = calculate_quality_score(segments)
    warnings.extend(quality_warnings)

    # 실제 재생 시간 (세그먼트 기준)
    if segments:
        actual_duration = format_timestamp(segments[-1]['end_seconds'])
    else:
        actual_duration = duration_str

    return ExtractionResult(
        success=True,
        source_type='video',
        source_path=video_path,
        title=metadata['title'],
        creation_date=metadata['creation_date'] or datetime.now().strftime('%Y%m%d'),
        duration=actual_duration,
        language=language,
        transcript_type='whisper',
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
        path = sys.argv[1]
        result = extract_video(path)
        print(to_json(result))
    else:
        print("Usage: python video.py <video_path>")
