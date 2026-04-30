# Development Guidelines

## Working with Background Tasks

### Rule 1: Don't modify backend files during execution
When a feature is processing, avoid saving changes to:
- orchestrator.py
- sandbox_runner.py
- main.py

Uvicorn reload will kill the process.

### Rule 2: Use recovery tools
If process gets stuck:
```bash
python scripts/recover_database.py --reset-all
```

### Rule 3: Monitor heartbeats
Watch the frontend heartbeat indicator. Green = healthy.

### Rule 4: Check logs
If execution fails, check:
- FastAPI console logs
- Database current_step field
- execution_logs table

## For Production

Migrate to Celery for production deployments:
- Tasks survive server restarts
- Better retry logic
- Horizontal scaling
