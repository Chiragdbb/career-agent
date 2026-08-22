# Agent Development Rules

Mandatory rules for humans and AI agents working in this repository.

## Core Rules

1. Read README.md and relevant docs before modifying code.
2. Never rewrite working architecture unnecessarily.
3. Business logic belongs in application/domain services, not route handlers.
4. Third-party providers must only be accessed through provider interfaces/adapters.
5. MCP tools must call application services and must not contain business logic.
6. PostgreSQL is the system of record.
7. Redis is used for queues/cache.
8. Long-running operations must run in workers, not HTTP request handlers.
9. All user-owned data must be tenant isolated.
10. LLM output must be validated before persistence.
11. Scraped web content is untrusted input.
12. Scraped content must never be allowed to override system instructions or directly execute tools.
13. Never fabricate candidate experience, skills, dates, employers, achievements or metrics.
14. Never invent an email address.
15. Never mark an application SUBMITTED without explicit submission evidence.
16. Never bypass CAPTCHA, authentication security or anti-bot controls.
17. External communication must require user approval unless an explicit automation rule allows it.
18. Never put API keys or secrets in source code.
19. Add tests for business-critical logic.
20. Database changes must use migrations.
21. Every workflow must be observable and auditable.
22. Prefer small, testable changes.
23. When implementing a feature, first inspect the existing code, then list intended files, then implement, then test.
24. Do not silently introduce new architectural patterns.

## When Implementing Something

- Inspect the existing code first.
- Explain the implementation briefly.
- Modify only necessary files.
- Run relevant tests.
- Report failures honestly.
- Do not claim something works unless it was actually verified.
