# AGENTS.md - AI Coding Agent Instructions

## Build/Lint/Test Commands

### Environment Setup
```bash
# Install dependencies
pip install -e ".[dev,test]"

# Run tests
pytest                          # Run all tests
pytest tests/                   # Run tests in directory
pytest tests/test_specific.py    # Run specific test file
pytest tests/test_file.py::test_function  # Run specific test
pytest -m unit                 # Run unit tests only
pytest -m integration           # Run integration tests only
pytest -m "not slow"           # Skip slow tests

# With coverage
pytest --cov=src --cov-report=html
```

### Linting/Formatting
```bash
# Format code
black src/ tests/

# Lint (fast)
ruff check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/

# Type checking
mypy src/
```

## Code Style Guidelines

### Imports
- Standard library imports first, then third-party, then local
- Use `from __future__ import annotations` at top of all files
- Group imports with blank lines between groups
- Avoid wildcard imports (`from x import *`)

### Formatting
- Line length: 100 characters
- Use Black formatter: `black src/`
- Use double quotes for strings
- Use 4 spaces for indentation (not tabs)

### Type Hints
- Use modern type hints: `str | None` (not `Optional[str]`)
- Use `list[str]` (not `List[str]`)
- Always type async functions with `-> Coroutine[...]` or return types
- Use `TypedDict` or `dataclass` for structured data
- Use `pydantic.BaseModel` for API models

### Naming Conventions
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`
- Database tables: `snake_case` (ORM classes: `PascalCase`)

### Error Handling
- Always log exceptions: `logger.exception("message")`
- Use specific exception types: `except ValueError as e`
- Raise HTTPException with proper status codes in FastAPI
- Include context in error messages
- Never expose raw exceptions to API responses

### Async Patterns
- Use `async with` for resources (HTTP clients, DB sessions)
- Use `async for db in get_db_session():` for database context
- Prefer `asyncio.gather()` for parallel independent tasks
- Use `await db.execute()` for SQLAlchemy async queries

### Database/SQL
- Use SQLAlchemy async patterns
- Use parameterized queries (never f-strings in SQL)
- Use `text()` for raw SQL with proper escaping
- Prefer ORM methods (`select().where()`) over raw queries when possible

### Logging
- Import logger: `from src.utils.logger import get_logger`
- Create per-module: `logger = get_logger(__name__)`
- Use levels: `logger.debug()`, `logger.info()`, `logger.error()`, `logger.exception()`
- Include context variables in log messages: `f"Processing {law_id}"`

### Testing
- Test files: `tests/test_*.py` (not in `src/`)
- Test classes: `TestFeatureName`
- Test functions: `test_specific_behavior()`
- Use `pytest-asyncio` for async tests
- Mark slow tests: `@pytest.mark.slow`
- Use fixtures for common setup (DB, clients)

### File Organization
- `src/models/`: SQLAlchemy entities, Pydantic models
- `src/api/` or `src/main.py`: FastAPI routes
- `src/repository/`: Database access layer
- `src/pipeline/`: Data processing/ETL
- `src/core/`: Shared services (cache, vector store, scheduler)
- `src/utils/`: Helper functions (logger, validators)
- `scripts/`: Standalone utility scripts

### API Design
- Use Pydantic models for request/response validation
- Return 400 on validation errors, 404 on missing, 500 on unexpected
- Use descriptive error codes in responses
- Include `X-Request-ID` header for tracing
- Return structured error responses: `{"error": "...", "message": "...", "details": {...}}`

### Documentation
- Korean for business logic explanations
- English for code comments (technical)
- Docstrings follow Google style or simple format
- Include Args/Returns for async functions

### Security
- Never commit secrets (.env, API keys)
- Use environment variables via `pydantic-settings`
- Validate all external input
- Use parameterized SQL to prevent injection
- Set sensible rate limits on API endpoints
