# Testing Guide

This guide describes the steps to set up the environment and run tests for the Sentio Engine project.

## 1. Environment Setup

### 1.1. Install Poetry

Poetry is used to manage project dependencies.

**Windows (PowerShell):**
```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

**macOS / Linux:**
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

You may need to restart your terminal after installation.

### 1.2. Install Project Dependencies

1.  Navigate to the `sentio_engine` directory.
2.  Run the command:
    ```bash
    poetry install
    ```

## 2. Unit Tests

Unit tests check individual application components in isolation. They do not require Docker or Redis to be running.

To run them, execute the following from the `sentio_engine` directory:
```bash
poetry run pytest
```

## 3. Integration Test

This test verifies the full application flow, including database interaction.

### 3.1. Start Services

Ensure that:
1.  **MongoDB** is running locally (default: `localhost:27017`).
2.  **Sentio Engine** is running:
    ```bash
    poetry run uvicorn sentio_engine.api.main:app --host 0.0.0.0 --port 8000
    ```

### 3.2. Run the Test Script

Execute the following from the `sentio_engine` directory:
```bash
poetry run python tests/integration_test.py
```

---

**Previous:** [Caching Strategy](./06_caching_strategy.md)
