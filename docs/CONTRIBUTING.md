# Contributing to Next_Prism

Thank you for considering contributing to Next_Prism! This document provides guidelines for contributing to the project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)

## 🤝 Code of Conduct

Be respectful, inclusive, and constructive. We're building this together!

## 🚀 Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a new branch for your feature or bugfix
4. Make your changes
5. Test thoroughly
6. Submit a pull request

## 💻 Development Setup

### Prerequisites
- Python 3.11+
- Docker 20.10+
- Git

### Setup Steps

```bash
# Clone your fork
git clone git@github.com:YOUR_USERNAME/Next_Prism.git
cd Next_Prism

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

## 🔧 Making Changes

### Branch Naming
- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

### Commit Messages
Follow the conventional commits format:
```
type(scope): brief description

Detailed explanation if needed

Fixes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## 📝 Coding Standards

### Python Style
- Follow PEP 8
- Use Black for formatting: `black src/`
- Use type hints wherever possible
- Maximum line length: 100 characters

### Documentation
- Add docstrings to all functions, classes, and modules
- Use Google-style docstrings
- Update README.md and docs/ as needed
- Comment complex logic

### Example Docstring
```python
def move_file(source: str, destination: str) -> bool:
    """
    Move a file from source to destination with deduplication check.
    
    Args:
        source: Absolute path to source file
        destination: Absolute path to destination directory
        
    Returns:
        True if file was moved successfully, False otherwise
        
    Raises:
        FileNotFoundError: If source file doesn't exist
        PermissionError: If insufficient permissions
    """
    pass
```

## 🧪 Testing

### Run Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_sync_engine.py
```

### Writing Tests
- Place tests in `tests/` directory
- Mirror source structure in test directory
- Use descriptive test names: `test_move_file_with_duplicate_detection`
- Mock external dependencies (Docker, file system)
- Aim for >80% code coverage

## 📤 Submitting Changes

### Pull Request Process

1. **Update your fork**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run quality checks**
   ```bash
   black src/
   flake8 src/
   pylint src/
   pytest
   ```

3. **Push to your fork**
   ```bash
   git push origin feature/your-feature
   ```

4. **Create Pull Request on GitHub**
   - Use a clear, descriptive title
   - Reference any related issues
   - Describe what changed and why
   - Include screenshots for UI changes
   - List any breaking changes

### PR Checklist
- [ ] Code follows project style guidelines
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] No merge conflicts
- [ ] Commit messages are clear
- [ ] PR description is complete

## 🐛 Reporting Bugs

Use GitHub Issues with:
- Clear, descriptive title
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Docker version, etc.)
- Logs and screenshots if applicable

## 💡 Suggesting Enhancements

Use GitHub Discussions or Issues:
- Describe the enhancement clearly
- Explain the use case
- Consider backward compatibility
- Provide examples if possible

## 📚 Additional Resources

- [Project Documentation](docs/)
- [AI Agent Notes](_AI_Notes/)
- [Implementation Plan](_AI_Notes_/PROJECT_IMPLEMENTATION_PLAN.md)

## ❓ Questions?

Feel free to open a discussion or issue. We're here to help!

---

Thank you for contributing to Next_Prism! 🎉
