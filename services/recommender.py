from typing import List
from models import RecommendedProject

async def recommend_projects(missing_skills: List[str]) -> List[RecommendedProject]:
    recommendations = []
    
    missing_lower = [s.lower() for s in missing_skills]
    
    # 1. Check Cloud / DevOps gaps
    if any(k in missing_lower for k in ["docker", "aws", "kubernetes", "devops", "cloud"]):
        recommendations.append(RecommendedProject(
            title="Docker 컨테이너 기반 Spring Boot & AWS CI/CD 파이프라인 구축",
            description="상용 수준의 백엔드 서비스를 구축하고, Docker를 사용하여 컨테이너화한 뒤, AWS ECS로 배포하는 완전 자동화된 CI/CD 파이프라인을 구성합니다.",
            technologies=["Spring Boot", "Docker", "AWS ECS", "GitHub Actions", "Terraform", "Nginx"],
            missing_skills_covered=[s for s in missing_skills if s.lower() in ["docker", "aws", "devops", "kubernetes"]],
            difficulty="상 (Hard)",
            impact="상 (개발/운영 분리, 배포 자동화 인프라 설계 능력을 강하게 증명)",
            architecture="REST API를 Docker로 컨테이너화하고 AWS ECS Fargate를 통해 오케스트레이션합니다. AWS RDS의 PostgreSQL 인스턴스와 연동되며, ALB(Application Load Balancer) 뒤에 격리 배치합니다."
        ))
        
    # 2. Check Database / Cache / Performance gaps
    if any(k in missing_lower for k in ["redis", "jpa", "mysql", "postgresql", "database", "query"]):
        recommendations.append(RecommendedProject(
            title="Redis 캐시 및 JPA 성능 최적화를 적용한 대용량 트래픽 대비 이커머스 백엔드",
            description="확장 가능한 상품 카탈로그 및 주문 처리 API를 구현합니다. Hibernate/JPA 쿼리를 최적화하여 N+1 문제를 해결하고, 빈번히 조회되는 핫 키에 대해 Redis 캐시를 도입합니다.",
            technologies=["Java", "Spring Boot", "Spring Data JPA", "MySQL", "Redis", "JMeter"],
            missing_skills_covered=[s for s in missing_skills if s.lower() in ["redis", "jpa", "mysql", "postgresql", "database"]],
            difficulty="중 (Medium)",
            impact="상 (실제 트래픽 폭주 상황에서의 대용량 동시성 제어 및 성능 병목 해결 능력을 입증)",
            architecture="데이터베이스 쿼리 결과 캐싱을 위해 Redis를 사용하는 Spring Boot 서비스. JPA 인덱스 최적화, HikariCP를 활용한 커넥션 풀링, JMeter를 사용한 부하 테스트 설정을 포함합니다."
        ))
        
    # 3. Check Frontend frameworks / TypeScript gaps
    if any(k in missing_lower for k in ["react.js", "react", "typescript", "next.js", "next", "redux"]):
        recommendations.append(RecommendedProject(
            title="TypeScript + Next.js를 활용한 상태 최적화 협업 대시보드",
            description="Next.js App Router와 TypeScript를 사용해 실시간 반응형 분석 대시보드를 제작하고, 효율적인 전역 상태 관리와 경량 렌더링을 구현합니다.",
            technologies=["TypeScript", "React.js", "Next.js", "TailwindCSS", "Zustand", "Recharts"],
            missing_skills_covered=[s for s in missing_skills if s.lower() in ["react.js", "typescript", "next.js", "redux"]],
            difficulty="중 (Medium)",
            impact="중상 (프론트엔드 아키텍처 설계, 반응형 레이아웃 제어 및 타입 안전성 구현 능력을 입증)",
            architecture="Next.js SSR 기반 정적 사이트 생성, Zustand를 활용한 클라이언트 상태 동기화, Recharts를 이용한 동적 차트 렌더링, 모든 백엔드 API 요청/응답 페이로드에 대한 엄격한 타입 인터페이스 선언을 수행합니다."
        ))
        
    # 4. Check Mobile App gaps
    if any(k in missing_lower for k in ["kotlin", "android", "swift", "ios", "flutter", "dart"]):
        recommendations.append(RecommendedProject(
            title="Clean Architecture 패턴의 모바일 할 일 관리 앱",
            description="현대적인 클린 아키텍처 패턴을 따르는 고성능 오프라인 우선 할 일 및 리마인더 앱을 구축합니다. Android(Kotlin/Jetpack Compose) 또는 iOS(Swift/SwiftUI)를 적용합니다.",
            technologies=["Kotlin" if "kotlin" in missing_lower else "Swift", "Jetpack Compose" if "kotlin" in missing_lower else "SwiftUI", "Room DB" if "kotlin" in missing_lower else "CoreData", "Coroutines", "Dagger Hilt"],
            missing_skills_covered=[s for s in missing_skills if s.lower() in ["kotlin", "android", "swift", "ios", "flutter", "dart"]],
            difficulty="중 (Medium)",
            impact="상 (모바일 생명주기 관리, 로컬 DB 동기화 및 최신 선언형 UI 프레임워크 제어 역량을 증명)",
            architecture="MVVM (Model-View-ViewModel) 설계로 Presentation, Domain, Data 레이어를 분리합니다. 모의 REST API의 데이터를 캐싱하는 로컬 리포지토리 패턴을 사용합니다."
        ))
        
    # Default fallbacks if no specific skills are matched
    if not recommendations:
        recommendations.append(RecommendedProject(
            title="JWT 인증 및 Docker 배포를 포함한 풀스택 커리어 대시보드",
            description="회원 가입, JWT 세션 토큰 인증, 대시보드 통계 및 Docker 배포 설정을 포함한 완성형 풀스택 웹 애플리케이션을 구축합니다.",
            technologies=["TypeScript", "React.js", "Node.js", "Express", "MongoDB", "Docker"],
            missing_skills_covered=missing_skills[:3],
            difficulty="중 (Medium)",
            impact="중 (프론트엔드, 백엔드 및 배포 기초를 모두 다루는 종합 프로젝트)",
            architecture="Express.js REST API와 MongoDB 데이터베이스 레이어로 구성되며, React SPA 클라이언트 빌드와 함께 Docker Compose를 사용하여 컨테이너화됩니다."
        ))
        
    return recommendations
