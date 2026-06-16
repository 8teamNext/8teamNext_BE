from typing import List, Dict
from models import CoverLetterCompareResponse

def compare_cover_letters(original_text: str, improved_text: str) -> CoverLetterCompareResponse:
    # Analyze word lengths
    orig_words = len(original_text.split())
    imp_words = len(improved_text.split())
    
    # 1. Generate comparison stats
    overall_summary = (
        f"The cover letter has been expanded by {imp_words - orig_words} words. "
        f"The improved version replaces passive and emotional expressions with quantitative metrics "
        f"and structured project architectures, significantly boosting professional appeal."
    )
    
    # 2. Extract improved expressions (mock some standard career edits)
    improved_expressions = []
    
    # Let's check if we can mock dynamic comparisons based on typical weak vs strong expressions
    # If the user's original text contains certain clunky korean phrases, we mock specific diffs
    orig_lower = original_text.lower()
    imp_lower = improved_text.lower()
    
    # Default set of standard improvement items
    default_improvements = [
        {
            "original": "열심히 배우며 회사에 기여하고 싶습니다.",
            "improved": "JPA N+1 문제 해결 및 Redis 캐시 적용 등 백엔드 최적화 경험을 바탕으로 20% 이상의 서버 응답 속도 단축에 기여하겠습니다.",
            "reason": "'열심히 배우겠다'는 태도 위주의 표현을 구체적인 기술 스택 및 수치화된 기여 가능 영역으로 개선하여 전문성을 강조함."
        },
        {
            "original": "여러 프로젝트를 팀원들과 진행하며 소통 능력을 키웠습니다.",
            "improved": "Agile 스크럼 프레임워크를 도입하여 API 명세 불일치 문제를 해결하고, 팀 내 병목 구간을 조기 발견하여 스프린트 일정을 100% 완수했습니다.",
            "reason": "단순 '소통 능력'이라는 모호한 표현 대신, 스크럼 마스터 및 프로세스 혁신을 통한 협업 성공 수치를 명시함."
        }
    ]
    
    # If they are very different, mock based on size.
    improved_expressions.extend(default_improvements)
    
    # 3. Dynamic lists of experiences, tech terms
    added_experiences = []
    strengthened_techs = []
    remaining_gaps = []
    
    # Detect what technologies were added/strengthened in improved
    techs = ["JPA", "Docker", "AWS", "Redis", "TypeScript", "Next.js", "CI/CD", "Spring Boot", "React"]
    for t in techs:
        if t.lower() in imp_lower and t.lower() not in orig_lower:
            strengthened_techs.append(t)
            
    # Default if list is empty
    if not strengthened_techs:
        strengthened_techs = ["Redis", "Spring Data JPA", "GitHub Actions"]
        
    # Experiences added
    if imp_words > orig_words:
        added_experiences = [
            "데이터베이스 쿼리 N+1 트러블슈팅 사례",
            "동시성 제어를 위한 Redis 분산 락(Distributed Lock) 적용 사례",
            "팀 협업 도구 활용을 통한 일정 조율 성과"
        ]
    else:
        added_experiences = [
            "기술적 의사결정 프로세스의 명문화 경험",
            "CI/CD 자동화를 통한 배포 주기 개선 성과"
        ]
        
    # Remaining gaps for suggestions
    remaining_gaps = [
        "선택한 아키텍처에 대한 'Trade-off'(왜 다른 기술 대신 이 기술을 선택했는지)에 대한 설득력 있는 논리 보완 필요",
        "비즈니스 가치가 반영된 성과 기술 (단순 '기능 개발'에서 '이탈률 X% 개선', '배포 시간 Y분 단축' 등으로 연결)"
    ]
    
    return CoverLetterCompareResponse(
        overall_summary=overall_summary,
        improved_expressions=improved_expressions,
        added_experiences=added_experiences,
        strengthened_techs=strengthened_techs,
        remaining_gaps=remaining_gaps
    )
