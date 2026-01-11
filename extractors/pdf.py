"""
PDF 텍스트 추출기
- 텍스트 PDF: pdfplumber 사용
- 스캔 PDF: OCR 자동 감지 및 처리
- 페이지 번호 매핑
"""

import os
from dataclasses import dataclass, asdict
from typing import Optional
import json


@dataclass
class ExtractionResult:
    """추출 결과 데이터 클래스"""
    success: bool
    source_type: str  # 'pdf'
    source_path: str
    title: str
    author: str
    creation_date: str  # YYYYMMDD or empty
    total_pages: int
    segments: list  # [{page, text}]
    full_text: str
    quality_score: int  # 0-100
    warnings: list
    extraction_method: str  # 'text', 'ocr', 'hybrid'


def extract_pdf_metadata(pdf_path: str) -> dict:
    """
    PDF 메타데이터 추출
    Returns:
        dict: {'title': str, 'author': str, 'creation_date': str}
    """
    import re

    metadata = {
        'title': '',
        'author': '',
        'creation_date': ''
    }

    try:
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            # PDF 메타데이터에서 추출
            pdf_metadata = pdf.metadata or {}

            # 제목 추출
            if pdf_metadata.get('Title'):
                metadata['title'] = pdf_metadata['Title'].strip()

            # 저자 추출
            if pdf_metadata.get('Author'):
                metadata['author'] = pdf_metadata['Author'].strip()

            # 생성일 추출 (D:20250115... 형식을 YYYYMMDD로 변환)
            if pdf_metadata.get('CreationDate'):
                creation_str = pdf_metadata['CreationDate']
                # D:YYYYMMDD 형식에서 날짜 추출
                date_match = re.search(r'D:(\d{8})', creation_str)
                if date_match:
                    metadata['creation_date'] = date_match.group(1)
    except Exception:
        pass

    # 메타데이터가 없으면 파일명에서 추출 시도
    if not metadata['title']:
        filename = os.path.basename(pdf_path)
        # .pdf 확장자 제거
        filename_without_ext = os.path.splitext(filename)[0]

        # 파일명에서 연도 패턴 찾기 (예: "2025. IJOS. ...")
        year_match = re.match(r'^(\d{4})\.\s*([A-Z]+)\.\s*(.+)', filename_without_ext)
        if year_match:
            year = year_match.group(1)
            journal = year_match.group(2)
            title = year_match.group(3).strip()
            metadata['title'] = title
            metadata['author'] = journal
            metadata['creation_date'] = year + '0101'  # 연도만 있으면 0101로
        else:
            metadata['title'] = filename_without_ext

    return metadata


def detect_pdf_type(pdf_path: str) -> str:
    """
    PDF 유형 감지
    - 'text': 텍스트 레이어 있음
    - 'scanned': 스캔본 (이미지만)
    - 'hybrid': 혼합
    """
    try:
        import pdfplumber
        
        with pdfplumber.open(pdf_path) as pdf:
            text_pages = 0
            image_pages = 0
            
            for page in pdf.pages[:min(5, len(pdf.pages))]:  # 처음 5페이지만 체크
                text = page.extract_text() or ''
                has_text = len(text.strip()) > 50
                has_images = len(page.images) > 0
                
                if has_text:
                    text_pages += 1
                if has_images and not has_text:
                    image_pages += 1
            
            if text_pages > 0 and image_pages == 0:
                return 'text'
            elif image_pages > 0 and text_pages == 0:
                return 'scanned'
            else:
                return 'hybrid'
    except Exception:
        return 'unknown'


def extract_text_pdf(pdf_path: str) -> tuple[list, list]:
    """텍스트 PDF에서 추출"""
    import pdfplumber
    
    segments = []
    warnings = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ''
            
            if text.strip():
                segments.append({
                    'page': i,
                    'text': text.strip(),
                    'tables': len(page.extract_tables() or [])
                })
            else:
                warnings.append(f"페이지 {i}: 텍스트 없음")
    
    return segments, warnings


def extract_ocr_pdf(pdf_path: str) -> tuple[list, list]:
    """스캔 PDF에서 OCR 추출"""
    try:
        import fitz  # pymupdf
        import pytesseract
        from PIL import Image
        import io
    except ImportError:
        return [], ["OCR 라이브러리 미설치 (pymupdf, pytesseract 필요)"]
    
    segments = []
    warnings = []
    
    doc = fitz.open(pdf_path)
    
    for i, page in enumerate(doc, 1):
        # 페이지를 이미지로 변환
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x 해상도
        img = Image.open(io.BytesIO(pix.tobytes()))
        
        # OCR 수행
        try:
            text = pytesseract.image_to_string(img, lang='kor+eng')
            if text.strip():
                segments.append({
                    'page': i,
                    'text': text.strip(),
                    'method': 'ocr'
                })
            else:
                warnings.append(f"페이지 {i}: OCR 결과 없음")
        except Exception as e:
            warnings.append(f"페이지 {i}: OCR 실패 - {str(e)}")
    
    doc.close()
    return segments, warnings


def calculate_quality_score(segments: list, extraction_method: str, total_pages: int) -> tuple[int, list]:
    """품질 점수 계산"""
    warnings = []
    score = 100
    
    if not segments:
        return 0, ["텍스트 추출 실패"]
    
    # 추출 방법에 따른 기본 점수
    if extraction_method == 'ocr':
        score -= 15
        warnings.append("OCR 추출 - 오류 가능성 있음")
    elif extraction_method == 'hybrid':
        score -= 10
        warnings.append("혼합 추출 - 일부 페이지 OCR 사용")
    
    # 추출 성공률
    extracted_pages = len(segments)
    if extracted_pages < total_pages:
        missing = total_pages - extracted_pages
        score -= min(30, missing * 5)
        warnings.append(f"{missing}개 페이지 텍스트 없음")
    
    # 평균 텍스트 길이
    avg_length = sum(len(s['text']) for s in segments) / len(segments)
    if avg_length < 100:
        score -= 10
        warnings.append("평균 페이지 텍스트가 매우 짧음")
    
    return max(0, min(100, score)), warnings


def extract_pdf(pdf_path: str) -> ExtractionResult:
    """
    PDF에서 텍스트 추출
    
    Args:
        pdf_path: PDF 파일 경로
    
    Returns:
        ExtractionResult: 추출 결과
    """
    if not os.path.exists(pdf_path):
        return ExtractionResult(
            success=False,
            source_type='pdf',
            source_path=pdf_path,
            title='',
            author='',
            creation_date='',
            total_pages=0,
            segments=[],
            full_text='',
            quality_score=0,
            warnings=['파일을 찾을 수 없음'],
            extraction_method=''
        )

    # PDF 메타데이터 추출
    pdf_metadata = extract_pdf_metadata(pdf_path)
    
    # PDF 유형 감지
    pdf_type = detect_pdf_type(pdf_path)
    
    # 유형에 따른 추출
    if pdf_type == 'text':
        segments, warnings = extract_text_pdf(pdf_path)
        method = 'text'
    elif pdf_type == 'scanned':
        segments, warnings = extract_ocr_pdf(pdf_path)
        method = 'ocr'
    else:
        # 하이브리드: 텍스트 먼저 시도, 실패 시 OCR
        segments, warnings = extract_text_pdf(pdf_path)
        method = 'text'
        
        if not segments:
            segments, ocr_warnings = extract_ocr_pdf(pdf_path)
            warnings.extend(ocr_warnings)
            method = 'ocr'
    
    # 총 페이지 수
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
    except:
        total_pages = len(segments)
    
    # 전체 텍스트 생성 (페이지 번호 포함)
    full_text_parts = []
    for seg in segments:
        full_text_parts.append(f"[p.{seg['page']}]\n{seg['text']}")
    full_text = '\n\n'.join(full_text_parts)
    
    # 품질 점수 계산
    quality_score, quality_warnings = calculate_quality_score(segments, method, total_pages)
    warnings.extend(quality_warnings)
    
    return ExtractionResult(
        success=len(segments) > 0,
        source_type='pdf',
        source_path=pdf_path,
        title=pdf_metadata['title'],
        author=pdf_metadata['author'],
        creation_date=pdf_metadata['creation_date'],
        total_pages=total_pages,
        segments=segments,
        full_text=full_text,
        quality_score=quality_score,
        warnings=warnings,
        extraction_method=method
    )


def to_json(result: ExtractionResult) -> str:
    """결과를 JSON 문자열로 변환"""
    return json.dumps(asdict(result), ensure_ascii=False, indent=2)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        result = extract_pdf(path)
        print(to_json(result))
    else:
        print("Usage: python pdf.py <pdf_path>")
