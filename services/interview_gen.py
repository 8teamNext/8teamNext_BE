import re
from typing import List
from models import InterviewGenResponse, InterviewQuestion

def generate_interview_questions(cover_letter: str) -> InterviewGenResponse:
    questions = []
    cl_lower = cover_letter.lower()
    
    # Predefined question banks based on keywords
    question_bank = [
        {
            "trigger": "jwt",
            "question": "JWT(JSON Web Token)의 구조와 인증 흐름에 대해 설명하고, 왜 세션 대신 JWT를 선택했는지 설명해주세요.",
            "intent": "토큰 기반 인증의 보안 메커니즘과 상태 비저장(Stateless) 아키텍처에 대한 깊은 이해도를 평가하기 위함입니다.",
            "suggested_keywords": ["Header.Payload.Signature", "Access Token & Refresh Token", "Stateless", "XSS/CSRF"],
            "sample_answer_tip": "JWT의 세 부분 구성을 설명하고, 로컬 스토리지와 쿠키의 보안 차이점을 언급하면서 Refresh Token을 사용해 보안을 강화한 흐름을 답변하세요."
        },
        {
            "trigger": "security",
            "question": "Spring Security 필터 체인의 동작 방식을 설명하고, 프로젝트에서 커스텀 필터를 삽입한 목적이 무엇인지 설명해주세요.",
            "intent": "요청의 흐름을 가로채어 인증 및 인가를 수행하는 필터 아키텍처 설계 역량을 확인합니다.",
            "suggested_keywords": ["FilterChainProxy", "SecurityContextHolder", "UsernamePasswordAuthenticationFilter"],
            "sample_answer_tip": "Spring Security가 DispatcherServlet 앞단에서 동작함을 언급하고, JWT 검증을 위해 `OncePerRequestFilter`를 상속받은 필터를 구현한 과정을 설명하세요."
        },
        {
            "trigger": "jpa",
            "question": "JPA N+1 문제가 무엇이며, 프로젝트에서 이를 감지하고 해결하기 위해 어떤 해결책(Fetch Join, Entity Graph 등)을 적용했습니까?",
            "intent": "ORM 사용 시 빈번하게 일어나는 데이터베이스 성능 저하를 방지하고 최적화할 수 있는지 확인합니다.",
            "suggested_keywords": ["Fetch Join", "Entity Graph", "Batch Size", "Lazy Loading"],
            "sample_answer_tip": "N+1 문제는 연관 관계 데이터를 조회할 때 1번의 쿼리로 연관 데이터 개수(N)만큼 추가 쿼리가 발생하는 현상입니다. Fetch Join으로 단일 쿼리 해결한 경험을 제시하세요."
        },
        {
            "trigger": "docker",
            "question": "도커(Docker) 컨테이너 레이어 빌드 과정을 최적화하기 위해 멀티 스테이지 빌드나 캐시 레이어 최적화를 수행한 경험이 있습니까?",
            "intent": "컨테이너 빌드 크기와 배포 효율성을 향상시킬 수 있는 DevOps 소양을 검증합니다.",
            "suggested_keywords": ["Multi-stage Build", "Layer Caching", "Base Image Size"],
            "sample_answer_tip": "빌드 단계와 실행 단계를 나누어 실행 이미지 크기를 수백 MB 단위에서 수십 MB 단위로 축소시킨 과정을 구체적 수치와 함께 답변하면 좋습니다."
        },
        {
            "trigger": "aws",
            "question": "AWS 인프라를 구축할 때 보안 그룹(Security Group)과 NACL의 차이점을 고려하여 프로젝트 네트워크망을 어떻게 구성했습니까?",
            "intent": "클라우드 가상 네트워크 보안 및 서브넷 격리 아키텍처를 이해하는지 파악합니다.",
            "suggested_keywords": ["VPC", "Public/Private Subnet", "Stateful / Stateless", "Bastion Host"],
            "sample_answer_tip": "보안 그룹은 Stateful하여 응답 포트를 자동 개방하지만 NACL은 Stateless하여 직접 제어함을 밝히고, DB는 Private Subnet에 격리 배치했음을 강조하세요."
        },
        {
            "trigger": "react",
            "question": "리액트(React)에서 컴포넌트 렌더링 횟수를 최적화하기 위해 사용한 기법(useMemo, useCallback, React.memo)과 그 효과를 설명해주세요.",
            "intent": "프론트엔드 렌더링 성능을 프로파일링하고 컴포넌트 단위를 잘 분리하여 최적화하는 역량을 평가합니다.",
            "suggested_keywords": ["Virtual DOM", "Reference Equality", "Re-rendering", "Profiler"],
            "sample_answer_tip": "무조건적인 최적화 적용보다는 렌더링 비용을 측정하고 복잡한 연산에 `useMemo`를, 자식 컴포넌트의 불필요한 리렌더 방지를 위해 `React.memo`를 적용했던 사례를 설명하세요."
        },
        {
            "trigger": "typescript",
            "question": "TypeScript를 도입하여 얻은 이점이 무엇이며, any 타입을 남용하지 않기 위해 어떤 코딩 규칙이나 제네릭(Generic) 패턴을 설계했습니까?",
            "intent": "정적 타입 지원을 통한 코드 안전성과 인터페이스 정의 능력을 확인합니다.",
            "suggested_keywords": ["Static Typing", "Generics", "Type Guard", "Strict Mode"],
            "sample_answer_tip": "런타임 에러를 컴파일 타임에 조기 발견하고 리팩토링 안정성을 얻었음을 말하고, API Response 공통 구조를 제네릭으로 추상화하여 안전성을 극대화한 경험을 답하세요."
        }
    ]
    
    # 3. Compile matching questions
    q_id = 1
    for item in question_bank:
        if item["trigger"] in cl_lower:
            questions.append(InterviewQuestion(
                id=q_id,
                question=item["question"],
                intent=item["intent"],
                suggested_keywords=item["suggested_keywords"],
                sample_answer_tip=item["sample_answer_tip"]
            ))
            q_id += 1
            
    # 4. Fallback default questions if cover letter does not contain specific triggers
    if len(questions) < 3:
        fallbacks = [
            {
                "question": "협업 과정에서 기술적 의견 충돌이나 소통 문제를 겪은 적이 있나요? 그것을 어떻게 조율했는지 구체적인 사례를 들려주세요.",
                "intent": "팀워크 조율 능력 및 협업에 임하는 소프트 스킬을 평가합니다.",
                "suggested_keywords": ["상호 존중", "데이터 기반 의사결정", "테스트 코드 입증"],
                "sample_answer_tip": "갈등 상황에서 감정 대립을 피하고, 각 안의 장단점을 벤치마킹 데이터로 정리하여 팀원들을 설득하고 최선의 결정을 내렸던 경험을 답변하세요."
            },
            {
                "question": "본인이 설계하고 구현한 프로젝트 중 가장 자랑스럽거나 해결하기 어려웠던 버그/트러블슈팅 경험은 무엇인가요?",
                "intent": "문제의 정의 능력, 디버깅 방식, 그리고 기술적 집요함을 확인합니다.",
                "suggested_keywords": ["가설 설정", "로그 분석", "근본 원인 해결 (Root Cause)"],
                "sample_answer_tip": "단순 버그 수정을 넘어, 문제가 일어나는 가설을 설정하고 로그를 모니터링하여 병목이나 락 문제를 찾아내 개선한 흐름을 논리적으로 설명하세요."
            },
            {
                "question": "기술 트렌드 변화에 적응하기 위해 평소 어떤 방식으로 학습하고 지식을 사내/학습 커뮤니티에 공유하시나요?",
                "intent": "개발자로서의 지속 가능한 성장 잠재력과 능동적인 태도를 평가합니다.",
                "suggested_keywords": ["기술 블로그", "스터디 운영", "공식 문서 분석"],
                "sample_answer_tip": "최신 릴리즈 노트를 꾸준히 챙겨보는 습관, 배운 내용을 공유하기 위해 세미나를 열거나 블로그를 정리해 올리는 피드백 활동을 답변에 녹여내세요."
            }
        ]
        
        for fb in fallbacks:
            if len(questions) >= 5:
                break
            questions.append(InterviewQuestion(
                id=q_id,
                question=fb["question"],
                intent=fb["intent"],
                suggested_keywords=fb["suggested_keywords"],
                sample_answer_tip=fb["sample_answer_tip"]
            ))
            q_id += 1
            
    return InterviewGenResponse(questions=questions)
