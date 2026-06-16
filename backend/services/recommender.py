from typing import List
from models import RecommendedProject

def recommend_projects(missing_skills: List[str]) -> List[RecommendedProject]:
    recommendations = []
    
    missing_lower = [s.lower() for s in missing_skills]
    
    # 1. Check Cloud / DevOps gaps
    if any(k in missing_lower for k in ["docker", "aws", "kubernetes", "devops", "cloud"]):
        recommendations.append(RecommendedProject(
            title="Dockerized Spring Boot & AWS CI/CD Pipeline",
            description="Build a production-grade backend service, containerize it using Docker, and configure a fully automated CI/CD pipeline deploying to AWS ECS.",
            technologies=["Spring Boot", "Docker", "AWS ECS", "GitHub Actions", "Terraform", "Nginx"],
            missing_skills_covered=[s for s in missing_skills if s.lower() in ["docker", "aws", "devops", "kubernetes"]],
            difficulty="Hard",
            impact="High (Demonstrates production engineering capabilities required by high-growth startups and enterprises)",
            architecture="A REST API layer containerized inside Docker, orchestrated via AWS ECS Fargate, with PostgreSQL database hosted in AWS RDS, all secured behind an AWS Application Load Balancer."
        ))
        
    # 2. Check Database / Cache / Performance gaps
    if any(k in missing_lower for k in ["redis", "jpa", "mysql", "postgresql", "database", "query"]):
        recommendations.append(RecommendedProject(
            title="High-Concurrency E-Commerce Backend with Redis Cache & JPA Optimization",
            description="Implement a scaleable product catalog and order processing API. Optimize Hibernate/JPA queries to resolve N+1 problems, and introduce Redis caching for hot product keys.",
            technologies=["Java", "Spring Boot", "Spring Data JPA", "MySQL", "Redis", "JMeter"],
            missing_skills_covered=[s for s in missing_skills if s.lower() in ["redis", "jpa", "mysql", "postgresql", "database"]],
            difficulty="Medium",
            impact="High (Directly proves ability to resolve real-world performance bottlenecks under heavy concurrent traffic)",
            architecture="Spring Boot service using Redis for caching database query results. Features JPA index optimization, connection pooling with HikariCP, and JMeter performance benchmark configurations."
        ))
        
    # 3. Check Frontend frameworks / TypeScript gaps
    if any(k in missing_lower for k in ["react.js", "react", "typescript", "next.js", "next", "redux"]):
        recommendations.append(RecommendedProject(
            title="TypeScript + Next.js Collaborative Dashboard with State Optimization",
            description="Create a real-time responsive analytics dashboard using Next.js App Router and TypeScript, implementing proper state management and lightweight rendering.",
            technologies=["TypeScript", "React.js", "Next.js", "TailwindCSS", "Zustand", "Recharts"],
            missing_skills_covered=[s for s in missing_skills if s.lower() in ["react.js", "typescript", "next.js", "redux"]],
            difficulty="Medium",
            impact="Medium-High (Demonstrates frontend architecture skills, responsive layout control, and type-safety implementation)",
            architecture="Next.js SSR-based static-site generation, client-side state syncing using Zustand, dynamic chart rendering with Recharts, and strict type interfaces for all backend API payloads."
        ))
        
    # 4. Check Mobile App gaps
    if any(k in missing_lower for k in ["kotlin", "android", "swift", "ios", "flutter", "dart"]):
        recommendations.append(RecommendedProject(
            title="Clean Architecture Mobile Productivity App",
            description="Build a high-performance offline-first task and reminder app incorporating Kotlin/Jetpack Compose (Android) or Swift/SwiftUI (iOS) matching modern clean architecture patterns.",
            technologies=["Kotlin" if "kotlin" in missing_lower else "Swift", "Jetpack Compose" if "kotlin" in missing_lower else "SwiftUI", "Room DB" if "kotlin" in missing_lower else "CoreData", "Coroutines", "Dagger Hilt"],
            missing_skills_covered=[s for s in missing_skills if s.lower() in ["kotlin", "android", "swift", "ios", "flutter", "dart"]],
            difficulty="Medium",
            impact="High (Shows command of mobile lifecycles, database sync, and modern declarative UI toolkits)",
            architecture="MVVM (Model-View-ViewModel) design separating presentation, domain, and data layers. Employs local repository pattern caching data from a mock REST API."
        ))
        
    # Default fallbacks if no specific skills are matched
    if not recommendations:
        recommendations.append(RecommendedProject(
            title="Full-Stack Career Dashboard with JWT Auth & Docker",
            description="Build a complete full-stack web application featuring user registration, JWT session tokens, dashboard stats, and Docker deployment settings.",
            technologies=["TypeScript", "React.js", "Node.js", "Express", "MongoDB", "Docker"],
            missing_skills_covered=missing_skills[:3],
            difficulty="Medium",
            impact="Medium (Comprehensive project covering both frontend, backend, and deployment basics)",
            architecture="Express.js REST API with MongoDB database layer, containerized and served using Docker Compose alongside a React SPA client build."
        ))
        
    return recommendations
