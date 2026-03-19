## Logging for Error Observability

Use the standard Python `logging` library instead of `print()` to ensure errors are captured with timestamps, severity levels, and stack traces.

### 1. Initialization
Define the logger at the top of your scripts (FastAPI routers, ETL pipelines, or Playwright scrapers):

```python
import logging

# Basic configuration (typically done once in main.py)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)