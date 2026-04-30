# EvoCode Architecture Blueprints

## 1. Solo Architecture Overview
graph TB
    subgraph "Frontend (Next.js)"
        A[User clicks 'Report Bug'] --> B[EvoCode Widget]
        B -->|Captures Text + DOM| C[POST /api/report]
    end
    
    subgraph "Backend (FastAPI)"
        C --> D[FastAPI Router]
        D -->|Save State| E[(SQLite Database)]
        
        D --> F[LangChain Simple Chain]
        F -->|Reads Local File + Bug| G[OpenAI/Bedrock API]
        G -->|Returns Fixed Code| H[Local Subprocess Sandbox]
        
        H -->|Runs 'npm test'| I{Test Passed?}
        I -->|No| F
        I -->|Yes| J[PyGithub API]
    end
    
    subgraph "GitHub"
        J --> K[Create Branch]
        K --> L[Commit File]
        L --> M[Open Pull Request]
    end
    
    style A fill:#ff6b6b
    style B fill:#4ecdc4
    style D fill:#ffe66d
    style F fill:#a8e6cf
    style H fill:#ff8b94
    style M fill:#c7ceea

## 2. Request Flow Sequence   
sequenceDiagram
    participant User
    participant Widget
    participant FastAPI
    participant SQLite
    participant LangChain
    participant Sandbox
    participant GitHub
    
    User->>Widget: Clicks "Report Bug"
    Widget->>Widget: Captures bug text
    Widget->>FastAPI: POST /api/report
    FastAPI->>SQLite: Save issue report
    FastAPI->>LangChain: Process bug report
    
    LangChain->>LangChain: Read target file
    LangChain->>LangChain: Generate prompt
    LangChain->>LangChain: Call LLM
    LangChain->>Sandbox: Test generated fix
    
    Sandbox->>Sandbox: Write code to file
    Sandbox->>Sandbox: Run npm test
    
    alt Tests Pass
        Sandbox->>GitHub: Create branch
        GitHub->>GitHub: Commit changes
        GitHub->>GitHub: Open PR
        GitHub-->>User: PR URL
    else Tests Fail
        Sandbox->>LangChain: Return error logs
        LangChain->>LangChain: Retry (max 3)
    end
## 3. File Structure
graph TB
    A[evocode-v1/] --> B[frontend/]
    A --> C[backend/]
    A --> D[test-target/]
    
    B --> B1[src/]
    B1 --> B2[components/BugReportWidget.tsx]
    B1 --> B3[pages/api/proxy.ts]
    B1 --> B4[app/page.tsx]
    
    C --> C1[main.py]
    C --> C2[models.py]
    C --> C3[utils/]
    C3 --> C4[github_manager.py]
    C3 --> C5[sandbox_runner.py]
    C3 --> C6[langchain_agent.py]
    C --> C7[database.db]
    C --> C8[.env]
    
    D --> D1[src/]
    D1 --> D2[checkout.js - broken]
    D --> D3[tests/]
    D3 --> D4[checkout.test.js]
    D --> D5[package.json]
    
    style A fill:#4ecdc4
    style B fill:#a8e6cf
    style C fill:#ffe66d
    style D fill:#ff8b94

## 4. Database Schema (SQLite)
erDiagram
    ISSUE_REPORTS {
        int id PK
        string bug_text
        string file_path
        string status
        datetime created_at
        datetime updated_at
    }
    
    FIX_ATTEMPTS {
        int id PK
        int issue_id FK
        int attempt_number
        string generated_code
        boolean test_passed
        string error_logs
        datetime created_at
    }
    
    PULL_REQUESTS {
        int id PK
        int issue_id FK
        string pr_url
        string branch_name
        string status
        datetime created_at
    }
    
    ISSUE_REPORTS ||--o{ FIX_ATTEMPTS : has
    ISSUE_REPORTS ||--o| PULL_REQUESTS : creates
## 5: State Machine (Simplified)
stateDiagram-v2
    [*] --> ReceiveReport
    ReceiveReport --> SaveToDB: Store issue
    SaveToDB --> ReadFile: Load target file
    ReadFile --> GenerateFix: Call LLM
    
    GenerateFix --> TestFix: Run sandbox
    
    TestFix --> CheckResult: Evaluate
    CheckResult --> RetryFix: Failed (attempt < 3)
    CheckResult --> CreatePR: Passed
    CheckResult --> Failed: Failed (attempt >= 3)
    
    RetryFix --> GenerateFix
    
    CreatePR --> [*]: Success
    Failed --> [*]: Max retries exceeded