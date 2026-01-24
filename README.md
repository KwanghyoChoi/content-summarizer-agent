# Content Summarizer

AI 기반 콘텐츠 요약 시스템 - YouTube 영상, PDF 문서, 웹페이지에서 정확한 원문 추출 후 신뢰할 수 있는 요약 노트 생성

## 특징

- **4가지 노트 형식**: 자세한 노트, 핵심 노트, 쉬운 노트, 마인드맵
- **정확성 우선**: 원문에 있는 내용만 포함, 추론/추가 금지
- **출처 추적**: 모든 내용에 타임스탬프/페이지 번호 표기
- **3단계 에이전트 파이프라인**: Analyst → Writer → Critic (80점 이상 통과)
- **Obsidian 호환**: `[[링크]]`, `#태그` 자동 생성

## 빠른 시작

### 설치
```bash
pip install -r requirements.txt

# 로컬 비디오 트랜스크립션용 (선택)
pip install openai-whisper opencv-python
```

### Claude Code에서 사용
```
# URL을 입력하면 자동으로 워크플로우 실행
https://youtube.com/watch?v=...
```

Claude Code가 자동으로:
1. 노트 형식 선택 (AskUserQuestion)
2. 콘텐츠 추출 (Python CLI)
3. 에이전트 파이프라인 실행 (Analyst → Writer → Critic)
4. 검증 통과 후 저장

### CLI 직접 사용
```bash
# YouTube
python main.py --youtube "URL" --extract-only

# 로컬 비디오
python main.py --video "./video.mp4" --extract-only

# PDF
python main.py --pdf "path/to/file.pdf" --extract-only

# 웹페이지
python main.py --web "URL" --extract-only
```

## 노트 형식

| 형식 | 목적 | 커버리지 |
|------|------|----------|
| **Detailed** | 완전한 계층적 노트 | 80-100% |
| **Essence** | 5-10개 핵심 포인트 | 30-40% |
| **Easy** | 초보자용 3-5개 핵심 | 10-20% |
| **Mindmap** | Mermaid 시각화 | 키워드 |

## 프로젝트 구조

```
content-summarizer/
├── CLAUDE.md                    # Claude Code 마스터 프롬프트
├── .claude/
│   ├── agents/                  # Claude Code 서브에이전트
│   │   ├── content-analyst.md   # Phase 1: 분석
│   │   ├── note-writer.md       # Phase 2: 작성
│   │   └── note-critic.md       # Phase 3: 검증
│   └── skills/
│       └── content-summarizer/  # 워크플로우 스킬
│           ├── SKILL.md
│           └── note-templates.md
│
├── extractors/                  # Python 추출기
│   ├── youtube.py
│   ├── video.py
│   ├── pdf.py
│   └── web.py
│
├── generators/                  # Python 생성기 (대체 옵션)
│   ├── note_generator.py
│   └── agents/                  # Python 기반 에이전트
│
├── templates/                   # 노트 템플릿
│   ├── detailed.md
│   ├── essence.md
│   ├── easy.md
│   └── mindmap.md
│
├── main.py                      # 메인 CLI
└── output/                      # 생성된 노트
```

## 핵심 원칙

1. **정확성 우선**: 원문에 있는 내용만 요약에 포함
2. **출처 추적 필수**: `[HH:MM:SS]` 또는 `[p.N]` 형식
3. **품질 검증**: Critic 에이전트가 80점 이상 통과 필요
4. **원문 보존**: 모든 노트에 원문 첨부

## 출력 파일

```
output/
├── {title}_{source}_{date}_extracted.json  # 메타데이터
├── {title}_{source}_{date}_raw.md          # 전체 텍스트
└── {title}_{source}_{date}_{format}.md     # 생성된 노트
```

## 문서

- [CLAUDE.md](./CLAUDE.md) - Claude Code 가이드

## 라이선스

MIT License
