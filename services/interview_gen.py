import re
from typing import List
from models import InterviewGenResponse, InterviewQuestion

async def generate_interview_questions(cover_letter: str) -> InterviewGenResponse:
    questions = []
    cl_lower = cover_letter.lower()
    
    # Predefined question banks based on keywords
    question_bank = [
        {
            "trigger": "jwt",
            "question": "JWT(JSON Web Token)의 구조와 인증 흐름에 대해 설명하고, 왜 세션 대신 JWT를 선택했는지 설명해주세요.",
            "intent": "토큰 기반 인증의 보안 메커니즘과 상태 비저장(Stateless) 아키텍처에 대한 깊은 이해도를 평가하기 위함입니다.",
            "suggested_keywords": ["Header.Payload.Signature", "Access Token & Refresh Token", "Stateless", "XSS/CSRF"],
            "sample_answer_tip": "JWT의 세 부분 구성을 설명하고, 로컬 스토리지와 쿠키의 보안 차이점을 언급하면서 Refresh Token을 사용해 보안을 강화한 흐름을 답변하세요.",
            "sample_answer": "JWT는 Header, Payload, Signature 세 부분으로 구성되며, 각각 Base64URL로 인코딩되어 점(.)으로 연결됩니다. 저는 세션 대신 JWT를 선택한 이유로 서버의 Stateless 유지를 꼽습니다. 세션 방식은 서버 메모리에 상태를 저장해야 하므로 수평 확장 시 세션 공유 문제가 생기지만, JWT는 토큰 자체에 사용자 정보가 담겨 있어 어느 서버에서도 검증이 가능합니다. 프로젝트에서는 Access Token의 만료 시간을 짧게(15분) 설정하고, Refresh Token은 HttpOnly 쿠키에 저장하여 XSS 공격을 방어했습니다. Access Token 탈취 위험을 최소화하면서도 사용자 경험을 해치지 않도록 Refresh Token으로 재발급하는 흐름을 구현했습니다."
        },
        {
            "trigger": "security",
            "question": "Spring Security 필터 체인의 동작 방식을 설명하고, 프로젝트에서 커스텀 필터를 삽입한 목적이 무엇인지 설명해주세요.",
            "intent": "요청의 흐름을 가로채어 인증 및 인가를 수행하는 필터 아키텍처 설계 역량을 확인합니다.",
            "suggested_keywords": ["FilterChainProxy", "SecurityContextHolder", "UsernamePasswordAuthenticationFilter"],
            "sample_answer_tip": "Spring Security가 DispatcherServlet 앞단에서 동작함을 언급하고, JWT 검증을 위해 `OncePerRequestFilter`를 상속받은 필터를 구현한 과정을 설명하세요.",
            "sample_answer": "Spring Security는 DispatcherServlet 앞단에 위치한 FilterChainProxy를 통해 요청을 가로챕니다. 요청이 들어오면 설정된 SecurityFilterChain 중 매칭되는 체인을 선택하고, 등록된 필터들이 순서대로 실행됩니다. 프로젝트에서는 JWT 인증을 위해 OncePerRequestFilter를 상속받은 JwtAuthenticationFilter를 구현하고, UsernamePasswordAuthenticationFilter 앞에 삽입했습니다. 이 필터는 요청 헤더의 Authorization 값에서 JWT를 추출하고, 서명을 검증한 뒤 사용자 정보를 SecurityContextHolder에 저장합니다. 이후 Spring Security의 인가 처리가 SecurityContext의 Authentication 객체를 참조하여 접근 제어를 수행하는 방식으로 동작합니다."
        },
        {
            "trigger": "jpa",
            "question": "JPA N+1 문제가 무엇이며, 프로젝트에서 이를 감지하고 해결하기 위해 어떤 해결책(Fetch Join, Entity Graph 등)을 적용했습니까?",
            "intent": "ORM 사용 시 빈번하게 일어나는 데이터베이스 성능 저하를 방지하고 최적화할 수 있는지 확인합니다.",
            "suggested_keywords": ["Fetch Join", "Entity Graph", "Batch Size", "Lazy Loading"],
            "sample_answer_tip": "N+1 문제는 연관 관계 데이터를 조회할 때 1번의 쿼리로 연관 데이터 개수(N)만큼 추가 쿼리가 발생하는 현상입니다. Fetch Join으로 단일 쿼리 해결한 경험을 제시하세요.",
            "sample_answer": "N+1 문제는 1번의 조회 쿼리로 가져온 엔티티 N개에 대해 연관된 데이터를 조회하기 위해 추가로 N번의 쿼리가 발생하는 현상입니다. 예를 들어 게시글 10개를 조회한 뒤 각 게시글의 작성자를 Lazy Loading으로 접근하면 총 11번의 쿼리가 실행됩니다. 프로젝트에서는 Hibernate의 쿼리 로깅을 활성화하여 N+1을 감지했고, @Query 어노테이션으로 JPQL Fetch Join을 적용해 단일 쿼리로 해결했습니다. 컬렉션 연관관계에서는 Fetch Join이 페이징 처리와 충돌하는 경우가 있어, 해당 상황에서는 @BatchSize를 설정하여 IN 절 기반의 배치 로딩으로 쿼리 수를 N+1에서 2회로 줄였습니다."
        },
        {
            "trigger": "docker",
            "question": "도커(Docker) 컨테이너 레이어 빌드 과정을 최적화하기 위해 멀티 스테이지 빌드나 캐시 레이어 최적화를 수행한 경험이 있습니까?",
            "intent": "컨테이너 빌드 크기와 배포 효율성을 향상시킬 수 있는 DevOps 소양을 검증합니다.",
            "suggested_keywords": ["Multi-stage Build", "Layer Caching", "Base Image Size"],
            "sample_answer_tip": "빌드 단계와 실행 단계를 나누어 실행 이미지 크기를 수백 MB 단위에서 수십 MB 단위로 축소시킨 과정을 구체적 수치와 함께 답변하면 좋습니다.",
            "sample_answer": "네, 프로젝트에서 Spring Boot 애플리케이션을 컨테이너화할 때 멀티 스테이지 빌드를 적용했습니다. 처음에는 JDK 이미지를 그대로 사용해 이미지 크기가 600MB가 넘었는데, 빌드 스테이지에서는 Gradle과 JDK가 포함된 이미지로 빌드를 수행하고, 실행 스테이지에서는 JRE만 포함된 경량 이미지(eclipse-temurin:17-jre)로 jar 파일만 복사하는 방식으로 변경했습니다. 결과적으로 최종 이미지 크기를 약 200MB로 줄였습니다. 또한 Dockerfile에서 의존성 설치 레이어(COPY build.gradle, RUN gradle dependencies)를 소스 코드 COPY 전에 배치하여, 소스만 변경된 경우 의존성 레이어를 캐시에서 재사용하도록 최적화했습니다."
        },
        {
            "trigger": "aws",
            "question": "AWS 인프라를 구축할 때 보안 그룹(Security Group)과 NACL의 차이점을 고려하여 프로젝트 네트워크망을 어떻게 구성했습니까?",
            "intent": "클라우드 가상 네트워크 보안 및 서브넷 격리 아키텍처를 이해하는지 파악합니다.",
            "suggested_keywords": ["VPC", "Public/Private Subnet", "Stateful / Stateless", "Bastion Host"],
            "sample_answer_tip": "보안 그룹은 Stateful하여 응답 포트를 자동 개방하지만 NACL은 Stateless하여 직접 제어함을 밝히고, DB는 Private Subnet에 격리 배치했음을 강조하세요.",
            "sample_answer": "보안 그룹은 인스턴스 레벨에서 동작하는 Stateful 방화벽으로, 인바운드 규칙을 허용하면 응답 트래픽은 자동으로 허용됩니다. 반면 NACL은 서브넷 레벨에서 동작하는 Stateless 방화벽으로, 인바운드와 아웃바운드 규칙을 모두 명시적으로 설정해야 합니다. 프로젝트에서는 VPC를 생성하고 Public Subnet과 Private Subnet을 분리했습니다. EC2 웹 서버는 Public Subnet에 배치하고 80, 443 포트만 외부에 개방했으며, RDS는 Private Subnet에 격리하여 EC2의 보안 그룹에서만 3306 포트로 접근 가능하도록 설정했습니다. 운영 중 서버 접속이 필요할 때는 Public Subnet의 Bastion Host를 통해 SSH 터널링으로 접근하는 구조를 적용했습니다."
        },
        {
            "trigger": "react",
            "question": "리액트(React)에서 컴포넌트 렌더링 횟수를 최적화하기 위해 사용한 기법(useMemo, useCallback, React.memo)과 그 효과를 설명해주세요.",
            "intent": "프론트엔드 렌더링 성능을 프로파일링하고 컴포넌트 단위를 잘 분리하여 최적화하는 역량을 평가합니다.",
            "suggested_keywords": ["Virtual DOM", "Reference Equality", "Re-rendering", "Profiler"],
            "sample_answer_tip": "무조건적인 최적화 적용보다는 렌더링 비용을 측정하고 복잡한 연산에 `useMemo`를, 자식 컴포넌트의 불필요한 리렌더 방지를 위해 `React.memo`를 적용했던 사례를 설명하세요.",
            "sample_answer": "React는 부모 컴포넌트가 리렌더링될 때 자식 컴포넌트도 함께 리렌더링됩니다. 프로젝트에서 목록 컴포넌트가 필터 상태 변경마다 불필요하게 리렌더링되는 문제를 React DevTools Profiler로 발견했습니다. 자식 컴포넌트에 React.memo를 적용하여 props가 변경되지 않으면 리렌더링을 건너뛰도록 했고, 부모에서 콜백 함수를 useCallback으로 메모이제이션하여 참조 동등성을 유지했습니다. 또한 필터링된 목록을 계산하는 복잡한 연산에는 useMemo를 적용해 의존 값이 변경될 때만 재계산하도록 했습니다. 다만 모든 컴포넌트에 무분별하게 적용하면 메모이제이션 비용이 오히려 커질 수 있어, Profiler로 병목을 확인한 뒤 선택적으로 적용했습니다."
        },
        {
            "trigger": "typescript",
            "question": "TypeScript를 도입하여 얻은 이점이 무엇이며, any 타입을 남용하지 않기 위해 어떤 코딩 규칙이나 제네릭(Generic) 패턴을 설계했습니까?",
            "intent": "정적 타입 지원을 통한 코드 안전성과 인터페이스 정의 능력을 확인합니다.",
            "suggested_keywords": ["Static Typing", "Generics", "Type Guard", "Strict Mode"],
            "sample_answer_tip": "런타임 에러를 컴파일 타임에 조기 발견하고 리팩토링 안정성을 얻었음을 말하고, API Response 공통 구조를 제네릭으로 추상화하여 안전성을 극대화한 경험을 답하세요.",
            "sample_answer": "TypeScript 도입으로 런타임에서야 발견되던 타입 오류를 컴파일 타임에 미리 잡아 버그를 크게 줄일 수 있었고, 리팩토링 시 영향 범위를 IDE가 자동으로 추적해줘 안전성이 높아졌습니다. any 타입 남용 방지를 위해 팀에서 ESLint의 @typescript-eslint/no-explicit-any 규칙을 활성화했습니다. API 응답 공통 구조는 `ApiResponse<T>` 제네릭 인터페이스로 추상화하여, 각 엔드포인트마다 응답 타입을 명확히 지정했습니다. 외부 라이브러리나 JSON 파싱처럼 타입을 알 수 없는 경우에는 any 대신 unknown을 사용하고, Type Guard 함수로 런타임 검증 후 타입을 좁히는 패턴을 적용했습니다."
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
                sample_answer_tip=item["sample_answer_tip"],
                sample_answer=item["sample_answer"]
            ))
            q_id += 1
            
    # 4. Fallback default questions if cover letter does not contain specific triggers
    if len(questions) < 3:
        fallbacks = [
            {
                "question": "협업 과정에서 기술적 의견 충돌이나 소통 문제를 겪은 적이 있나요? 그것을 어떻게 조율했는지 구체적인 사례를 들려주세요.",
                "intent": "팀워크 조율 능력 및 협업에 임하는 소프트 스킬을 평가합니다.",
                "suggested_keywords": ["상호 존중", "데이터 기반 의사결정", "테스트 코드 입증"],
                "sample_answer_tip": "갈등 상황에서 감정 대립을 피하고, 각 안의 장단점을 벤치마킹 데이터로 정리하여 팀원들을 설득하고 최선의 결정을 내렸던 경험을 답변하세요.",
                "sample_answer": "팀 프로젝트에서 API 응답 구조를 두고 의견이 갈린 적이 있었습니다. 저는 일관성을 위해 공통 래퍼 구조를 제안했고, 다른 팀원은 불필요한 중첩이라며 반대했습니다. 감정적으로 대립하지 않고 각 방식의 장단점을 문서로 정리한 뒤 팀 회의에서 공유했습니다. 실제로 두 방식을 모두 간단히 구현해서 프론트엔드 팀원이 직접 사용해보고 피드백을 주는 방식으로 결정했고, 결과적으로 공통 래퍼 방식을 채택했습니다. 이 경험을 통해 의견 충돌 시 데이터나 실증으로 소통하면 감정 소모 없이 더 나은 결론에 이를 수 있다는 것을 배웠습니다."
            },
            {
                "question": "본인이 설계하고 구현한 프로젝트 중 가장 자랑스럽거나 해결하기 어려웠던 버그/트러블슈팅 경험은 무엇인가요?",
                "intent": "문제의 정의 능력, 디버깅 방식, 그리고 기술적 집요함을 확인합니다.",
                "suggested_keywords": ["가설 설정", "로그 분석", "근본 원인 해결 (Root Cause)"],
                "sample_answer_tip": "단순 버그 수정을 넘어, 문제가 일어나는 가설을 설정하고 로그를 모니터링하여 병목이나 락 문제를 찾아내 개선한 흐름을 논리적으로 설명하세요.",
                "sample_answer": "프로젝트에서 특정 시간대에 간헐적으로 응답이 느려지는 현상이 발생했습니다. 처음에는 네트워크 문제라고 생각했지만, 로그를 분석하던 중 DB 커넥션 풀이 고갈되는 패턴을 발견했습니다. 가설을 세워 확인해보니, 트랜잭션 안에서 외부 API를 호출하는 코드가 있어 외부 API 응답이 지연될 때 커넥션이 오랫동안 점유되는 것이 원인이었습니다. 외부 API 호출을 트랜잭션 밖으로 분리하고, 타임아웃을 명시적으로 설정하여 문제를 해결했습니다. 단순히 풀 크기를 늘리는 임시방편이 아닌 근본 원인을 찾아 해결한 점이 가장 의미 있었습니다."
            },
            {
                "question": "기술 트렌드 변화에 적응하기 위해 평소 어떤 방식으로 학습하고 지식을 사내/학습 커뮤니티에 공유하시나요?",
                "intent": "개발자로서의 지속 가능한 성장 잠재력과 능동적인 태도를 평가합니다.",
                "suggested_keywords": ["기술 블로그", "스터디 운영", "공식 문서 분석"],
                "sample_answer_tip": "최신 릴리즈 노트를 꾸준히 챙겨보는 습관, 배운 내용을 공유하기 위해 세미나를 열거나 블로그를 정리해 올리는 피드백 활동을 답변에 녹여내세요.",
                "sample_answer": "새로운 기술을 접할 때는 공식 문서를 먼저 읽는 습관을 갖고 있습니다. 블로그 포스팅은 정보가 오래되거나 부정확한 경우가 있어, 공식 문서로 개념을 잡은 뒤 실제로 작은 예제를 만들어 동작을 확인합니다. 학습한 내용은 개인 기술 블로그에 정리하는데, 남에게 설명하듯 글을 쓰는 과정에서 이해가 더 깊어진다고 느낍니다. 또한 스터디 그룹에서 격주로 기술 발표를 진행하며, 최근에는 Spring Boot 3.x의 Virtual Thread 지원에 대해 발표하고 팀원들과 실무 적용 가능성을 토론했습니다. 이런 공유 활동이 개인 학습의 동기 부여도 되고, 팀 전체의 기술 역량을 높이는 데도 기여한다고 생각합니다."
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
                sample_answer_tip=fb["sample_answer_tip"],
                sample_answer=fb["sample_answer"]
            ))
            q_id += 1
            
    return InterviewGenResponse(questions=questions)
