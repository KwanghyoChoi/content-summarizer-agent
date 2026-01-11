"""
웹페이지 본문 추출기
- trafilatura 기반 정확한 본문 추출
- 메타데이터 추출 (제목, 작성자, 날짜)
- 광고/네비게이션 자동 필터링
"""

import json
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import urlparse


@dataclass
class ExtractionResult:
    """추출 결과 데이터 클래스"""
    success: bool
    source_type: str  # 'web'
    source_url: str
    title: str
    author: str
    date: str
    domain: str
    sections: list  # [{heading, content}]
    full_text: str
    quality_score: int  # 0-100
    warnings: list


def extract_with_trafilatura(url: str) -> tuple[dict, list]:
    """trafilatura로 본문 추출"""
    try:
        import trafilatura
        
        # 페이지 다운로드
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None, ["페이지를 가져올 수 없음"]
        
        # 메타데이터 포함 추출
        result = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            include_images=False,
            include_links=False,
            output_format='json',
            with_metadata=True
        )
        
        if result:
            return json.loads(result), []
        else:
            return None, ["본문 추출 실패"]
            
    except ImportError:
        return None, ["trafilatura 라이브러리 미설치"]
    except Exception as e:
        return None, [f"추출 오류: {str(e)}"]


def extract_with_beautifulsoup(url: str) -> tuple[dict, list]:
    """BeautifulSoup 폴백 추출"""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 불필요한 요소 제거
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe']):
            tag.decompose()
        
        # 제목 추출
        title = ''
        if soup.title:
            title = soup.title.string or ''
        elif soup.find('h1'):
            title = soup.find('h1').get_text(strip=True)
        
        # 본문 추출 (article 또는 main 태그 우선)
        content_tag = soup.find('article') or soup.find('main') or soup.find('body')
        
        if content_tag:
            # 단락 추출
            paragraphs = content_tag.find_all(['p', 'h2', 'h3', 'h4', 'li'])
            text_parts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 20:  # 너무 짧은 텍스트 제외
                    text_parts.append(text)
            
            return {
                'title': title,
                'text': '\n\n'.join(text_parts),
                'author': '',
                'date': ''
            }, ["BeautifulSoup 폴백 사용 - 정확도 낮을 수 있음"]
        
        return None, ["본문을 찾을 수 없음"]
        
    except Exception as e:
        return None, [f"폴백 추출 오류: {str(e)}"]


def parse_sections(text: str) -> list:
    """텍스트를 섹션으로 분리"""
    if not text:
        return []
    
    sections = []
    current_section = {'heading': '본문', 'content': []}
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 헤딩 감지 (짧고 마침표 없는 줄)
        if len(line) < 100 and not line.endswith(('.', '?', '!')):
            if current_section['content']:
                sections.append({
                    'heading': current_section['heading'],
                    'content': '\n'.join(current_section['content'])
                })
            current_section = {'heading': line, 'content': []}
        else:
            current_section['content'].append(line)
    
    # 마지막 섹션 추가
    if current_section['content']:
        sections.append({
            'heading': current_section['heading'],
            'content': '\n'.join(current_section['content'])
        })
    
    return sections


def calculate_quality_score(text: str, method: str) -> tuple[int, list]:
    """품질 점수 계산"""
    warnings = []
    score = 100
    
    if not text:
        return 0, ["텍스트 없음"]
    
    # 추출 방법
    if method == 'beautifulsoup':
        score -= 15
        warnings.append("폴백 방법 사용 - 광고/네비게이션 포함 가능성")
    
    # 텍스트 길이
    if len(text) < 500:
        score -= 20
        warnings.append("본문이 매우 짧음")
    elif len(text) < 1000:
        score -= 10
        warnings.append("본문이 짧음")
    
    # 텍스트 품질 체크
    if text.count('\n') < 3:
        score -= 10
        warnings.append("단락 구분이 부족함")
    
    return max(0, min(100, score)), warnings


def extract_web(url: str) -> ExtractionResult:
    """
    웹페이지에서 본문 추출
    
    Args:
        url: 웹페이지 URL
    
    Returns:
        ExtractionResult: 추출 결과
    """
    # URL 검증
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL")
        domain = parsed.netloc
    except:
        return ExtractionResult(
            success=False,
            source_type='web',
            source_url=url,
            title='',
            author='',
            date='',
            domain='',
            sections=[],
            full_text='',
            quality_score=0,
            warnings=['유효하지 않은 URL']
        )
    
    # trafilatura 우선 시도
    data, warnings = extract_with_trafilatura(url)
    method = 'trafilatura'
    
    # 실패 시 BeautifulSoup 폴백
    if not data:
        data, bs_warnings = extract_with_beautifulsoup(url)
        warnings.extend(bs_warnings)
        method = 'beautifulsoup'
    
    if not data:
        return ExtractionResult(
            success=False,
            source_type='web',
            source_url=url,
            title='',
            author='',
            date='',
            domain=domain,
            sections=[],
            full_text='',
            quality_score=0,
            warnings=warnings
        )
    
    # 데이터 파싱
    text = data.get('text', '')
    title = data.get('title', '')
    author = data.get('author', '')
    date = data.get('date', '')
    
    # 섹션 분리
    sections = parse_sections(text)
    
    # 전체 텍스트 (섹션 표시 포함)
    full_text_parts = []
    for sec in sections:
        full_text_parts.append(f"## {sec['heading']}\n{sec['content']}")
    full_text = '\n\n'.join(full_text_parts) if full_text_parts else text
    
    # 품질 점수
    quality_score, quality_warnings = calculate_quality_score(text, method)
    warnings.extend(quality_warnings)
    
    return ExtractionResult(
        success=True,
        source_type='web',
        source_url=url,
        title=title,
        author=author,
        date=date,
        domain=domain,
        sections=sections,
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
        result = extract_web(url)
        print(to_json(result))
    else:
        print("Usage: python web.py <url>")
