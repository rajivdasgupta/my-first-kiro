# Project Standards

## General Principles
- Write clean, readable, and maintainable code
- Follow the DRY (Don't Repeat Yourself) principle
- Prefer composition over inheritance
- Keep functions small and focused on a single responsibility
- Use meaningful and descriptive variable/function names

## Code Style
- Use consistent indentation (2 spaces)
- Always use strict equality (=== over ==)
- Prefer const over let; avoid var
- Use template literals over string concatenation
- Add trailing commas in multi-line objects and arrays
- Use semicolons consistently

## Error Handling
- Always handle errors explicitly; never swallow exceptions silently
- Use try/catch for async operations
- Provide meaningful error messages
- Log errors with sufficient context for debugging

## Security
- Never hardcode secrets, API keys, or credentials
- Use environment variables for sensitive configuration
- Validate and sanitize all user inputs
- Follow the principle of least privilege

## Documentation
- Add JSDoc or inline comments for complex logic
- Keep a README.md updated with setup and usage instructions
- Document public APIs and exported functions

## Git Practices
- Write clear, concise commit messages in imperative mood (e.g., "Add login feature")
- Keep commits small and focused
- Use feature branches for new work
