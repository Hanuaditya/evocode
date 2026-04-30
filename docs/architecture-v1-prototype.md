# 🎯 EVOCODE V2: AGENTIC DEVELOPER DASHBOARD
**Complete Hackathon Architecture & Battle Plan**

## 🔥 EXECUTIVE SUMMARY
EvoCode V2 bridges the gap between client feedback and production code by combining an AI Product Manager with an AI Software Engineer. Instead of replacing the developer, EvoCode eliminates the project management bottleneck while keeping the Lead Engineer in total control.

**The Core Innovations:**
1. **Dynamic Guardrails (Assist Mode):** EvoCode evaluates feature requests and assigns a Confidence Score. Low-risk UI tasks are fully automated end-to-end. High-risk architectural changes (like DB migrations) trigger "Assist Mode," halting automated execution and generating an Architectural Strategy Guide for the Lead Developer, ensuring zero-trust enterprise security.
2. **Feedback Aggregation:** Users upvote feature requests (like Reddit/ProductHunt).
3. **Developer Dashboard:** Devs see trending requests and click "Build".
4. **AI Planning Agent:** Generates GitHub issues + implementation plans.
5. **AI Coder Agent with Tools:** Reads codebase files natively to avoid hallucinations.
6. **Autonomous Execution:** Runs sandbox tests and creates Pull Requests automatically.

---

## 📊 CORE ARCHITECTURE DIAGRAMS

### Diagram 1: Database Schema
```mermaid
erDiagram
    FEATURE_REQUESTS {
        int id PK
        string title
        string description
        string category
        string status "pending, planning, building, completed, requires_manual_dev"
        int vote_count
        datetime created_at
    }
    
    BUILD_PLANS {
        int id PK
        int github_issue_id FK
        text plan_markdown
        json files_to_modify
        int confidence_score "0-100"
        boolean is_critical "True if touches DB/Auth"
        string status 
        datetime created_at
    }
    
    FEATURE_REQUESTS ||--o{ COMMENTS : has
    FEATURE_REQUESTS ||--o{ VOTES : receives
    FEATURE_REQUESTS ||--|| GITHUB_ISSUES : creates
    GITHUB_ISSUES ||--o{ BUILD_PLANS : generates
    BUILD_PLANS ||--o{ CODE_EXECUTIONS : executes
    CODE_EXECUTIONS ||--o{ TOOL_CALLS : uses
    CODE_EXECUTIONS ||--|| PULL_REQUESTS : creates
```

### Diagram 2: Developer Dashboard UI & Guardrail Flow
```mermaid
stateDiagram-v2
    [*] --> Dashboard
    
    Dashboard --> SelectRequest: Developer clicks BUILD
    SelectRequest --> PlanGeneration: AI creates plan & scores risk
    
    PlanGeneration --> PlanReview: Show PLAN.md & Confidence Score
    
    PlanReview --> RiskAssessment: Engine evaluates safety
    
    RiskAssessment --> AutoMode: Score >= 80 (Safe)
    RiskAssessment --> AssistMode: Score < 80 or Critical
    
    %% The Happy Path (Automated) %%
    AutoMode --> ApproveOrReject: "APPROVE PLAN" enabled
    ApproveOrReject --> ExecuteCode: Approved
    ExecuteCode --> Testing: Run Sandbox Tests
    Testing --> CreatePR: Tests pass
    CreatePR --> Completed: PR opened
    
    %% The Guardrail Path (Human-in-Loop) %%
    AssistMode --> DevAssistUI: "APPROVE" Disabled + Show Warning
    DevAssistUI --> StrategyGuide: Display Migration/Architecture Steps
    StrategyGuide --> ManualExecution: Developer codes manually in IDE
    ManualExecution --> Completed: Dev commits code
    
    Completed --> [*]
```
### Diagram 3: AI Agent Tool Flow (Solving Hallucinations)
```mermaid
sequenceDiagram
    participant Dev as Developer
    participant UI as Dashboard
    participant Executor as Execution Agent
    participant Tools as LangChain Tools
    participant Files as Local Repo
    
    UI->>Executor: Start execution with approved plan
    Note over Executor: Agent with Tools enabled
    
    Executor->>Executor: Task: Add dark mode
    Executor->>Tools: CALL read_file('src/About.jsx')
    Tools->>Files: Read file
    Files-->>Tools: Return content
    Tools-->>Executor: Here's the current code
    
    Executor->>Executor: I see it imports from './assets'
    Executor->>Tools: CALL read_file('src/assets.js')
    Tools->>Files: Read file
    Files-->>Tools: Return content
    Tools-->>Executor: Available icons list
    
    Executor->>Executor: I found project_icon_dark (not iconDark)
    Executor->>Tools: CALL write_file('src/About.jsx', updated_code)
    Tools->>Files: Write changes
```