---
inclusion: fileMatch
fileMatchPattern: "*.test.*,*.spec.*,__tests__/**"
---

# Testing Standards

- Write descriptive test names that explain the expected behavior
- Follow the Arrange-Act-Assert pattern
- Test one behavior per test case
- Use meaningful assertions with clear error messages
- Mock external dependencies; never call real APIs in unit tests
- Aim for edge cases: null values, empty arrays, boundary conditions
- Keep test files co-located with the source files they test
