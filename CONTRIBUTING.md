# Contributing to Algo Trading Bot

Thank you for your interest in contributing! This document outlines the process for contributing to the project.

---

## Getting Started

### 1. Fork & Clone
```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/yourusername/algo-trading-bot.git
cd algo-trading-bot

# Add upstream remote
git remote add upstream https://github.com/originalusername/algo-trading-bot.git
```

### 2. Create a Branch
```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Or bugfix branch
git checkout -b fix/your-bug-fix
```

### 3. Set Up Development Environment
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
python -m pytest tests/
```

---

## Making Changes

### Code Standards
- **Python**: Follow [PEP 8](https://pep8.org/)
- **Type Hints**: Use type hints where possible
- **Docstrings**: Document functions and classes
- **Tests**: Write tests for new features

### Commit Messages
```bash
# Good commit message format
git commit -m "feat: add market regime detection"
git commit -m "fix: resolve concurrent execution timeout"
git commit -m "docs: update configuration guide"
git commit -m "test: add unit tests for orchestrator"

# Format: type: description
# Types: feat, fix, docs, test, refactor, style, chore
```

### Documentation
- Update README if behavior changes
- Update Wiki for feature documentation
- Add code comments for complex logic
- Include examples for new features

---

## Testing

### Run Tests
```bash
# All tests
python -m pytest tests/

# Specific test file
python -m pytest tests/test_concurrent_execution.py -v

# With coverage
python -m pytest --cov=src tests/

# Specific test
python -m pytest tests/test_concurrent_execution.py::test_concurrent_executor -v
```

### Test Requirements
- All tests must pass
- Maintain >80% code coverage
- Test both happy path and edge cases
- Include performance benchmarks if relevant

---

## Pull Request Process

### Before Submitting
1. **Update your branch**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run tests**
   ```bash
   python -m pytest tests/
   ```

3. **Verify code quality**
   ```bash
   # Format code
   black src/ tests/
   
   # Lint
   flake8 src/ tests/
   
   # Type check
   mypy src/
   ```

### Submitting a PR
1. Push your branch to your fork
2. Go to GitHub and create a Pull Request
3. Fill in the PR template:
   - **Title**: Clear, descriptive title
   - **Description**: What and why
   - **Type**: Feature/Bug fix/Documentation
   - **Testing**: How you tested it
   - **Breaking Changes**: Any breaking changes?

### PR Guidelines
- One feature/fix per PR
- Keep PRs focused and manageable
- Link to related issues
- Update documentation
- Add tests for new features
- Ensure CI passes

---

## Areas for Contribution

### High Priority
- [ ] Additional trading algorithms
- [ ] Performance optimizations
- [ ] Risk management improvements
- [ ] Integration tests

### Medium Priority
- [ ] Documentation improvements
- [ ] Example strategies
- [ ] Dashboard enhancements
- [ ] Configuration profiles

### Low Priority
- [ ] Code style improvements
- [ ] Comment/docstring updates
- [ ] Test improvements
- [ ] CI/CD enhancements

---

## Feature Requests

### Suggesting a Feature
1. Check existing issues/discussions
2. Describe the use case
3. Propose a solution (optional)
4. Discuss impact on performance
5. Wait for feedback before coding

### Feature Template
```markdown
## Feature Request: [Title]

**Description**: What do you want?
**Use Case**: Why do you need it?
**Solution**: How should it work?
**Alternatives**: Any alternatives?
**Impact**: Performance/breaking changes?
```

---

## Bug Reports

### Reporting a Bug
1. Search existing issues
2. Include reproduction steps
3. Provide expected vs actual behavior
4. Share environment details
5. Include logs/error messages

### Bug Report Template
```markdown
## Bug: [Title]

**Environment**:
- Python version: 
- Docker version: 
- OS: 

**Steps to Reproduce**:
1. 
2. 
3. 

**Expected Behavior**: 

**Actual Behavior**: 

**Logs**: 
(Paste relevant logs)
```

---

## Code Review

### What to Expect
- Constructive feedback
- Questions about design decisions
- Requests for changes
- No rejections without explanation

### Addressing Reviews
1. Read feedback carefully
2. Ask for clarification if needed
3. Make requested changes
4. Push updates to the same branch
5. Respond to all comments

---

## Development Tips

### Useful Commands
```bash
# Run bot in paper trading
python -m trading_bot paper --symbols AAPL

# Run dashboard
python -m trading_bot web

# Docker development
docker-compose up --build

# View logs
docker-compose logs -f trading_bot
```

### File Structure
```
src/trading_bot/
├── learn/              # Orchestrator, executor, strategies
├── broker/             # Paper & live trading
├── data/               # Data providers
├── strategy/           # Trading strategies
├── indicators.py       # Technical indicators
├── risk.py            # Risk management
└── config.py          # Configuration

tests/
├── test_concurrent_execution.py
├── test_paper_broker.py
└── ...
```

### Git Workflow
```bash
# Fetch latest
git fetch upstream

# Rebase on main
git rebase upstream/main

# Push to your fork
git push origin feature/your-feature

# Create PR on GitHub
```

---

## Documentation

### Wiki Updates
- Update Wiki pages for user-facing changes
- Location: `.github/wiki/`
- Include examples and use cases
- Link to related pages

### Code Documentation
```python
def your_function(param1: str, param2: int) -> bool:
    """
    Brief description.
    
    Longer description if needed.
    
    Args:
        param1: Description
        param2: Description
    
    Returns:
        Description
    
    Raises:
        ValueError: When something is wrong
    
    Example:
        >>> result = your_function("test", 42)
        >>> result
        True
    """
    pass
```

---

## Performance Considerations

### Benchmarking
```bash
# Run performance tests
python -m pytest tests/test_concurrent_execution.py::test_performance -v

# Profile code
python -m cProfile -s cumtime src/trading_bot/__main__.py
```

### What to Avoid
- ❌ Blocking operations in concurrent code
- ❌ Large data copies
- ❌ Inefficient loops
- ❌ Unnecessary I/O operations

### What to Optimize
- ✅ Cache expensive calculations
- ✅ Use vectorized operations
- ✅ Parallel processing
- ✅ Lazy loading

---

## Questions?

- **GitHub Issues**: [Ask a question](https://github.com/yourusername/algo-trading-bot/issues)
- **Discussions**: [Discuss](https://github.com/yourusername/algo-trading-bot/discussions)
- **Wiki**: [Read the docs](.github/wiki/Home.md)

---

## Code of Conduct

Be respectful, inclusive, and professional. Harassment or discrimination will not be tolerated.

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).

---

**Thank you for contributing! Happy coding! 🚀**
