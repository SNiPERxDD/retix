# RETIX

RETIX - The Optic Nerve for Autonomous Agents.

RETIX is a local-first vision CLI for coding agents. It analyzes screenshots, extracts visible text, and verifies visual claims with deterministic defaults suitable for engineering workflows.

## Installation

### From PyPI (Recommended)

```bash
# Fast install (recommended - uses Rust-based resolver)
uv pip install retix

# Or with standard pip
pip install retix
```

**Why `uv`?** The Rust-based resolver is 10-100x faster than pip, especially with complex dependencies like torch. Installation time: ~50 seconds vs indefinite pip hangs.

### From Source (Development)

```bash
git clone https://github.com/SNiPERxDD/retix.git
cd retix
python3 -m pip install -e .
```

## Quick Start

```bash
retix setup                    # Bootstrap your environment
retix describe screenshot.png  # Analyze a screenshot
retix ocr document.png         # Extract text from image
retix check image.png "button is visible"  # Verify visual claims
```

## Core Commands

### Describe

```bash
retix describe <image>
retix describe <image> --prompt "focus on form validation"
retix describe <image> --json
```

### OCR

```bash
retix ocr <image>
retix ocr <image> --json
```

### Check

```bash
retix check <image> "submit button is visible"
retix check <image> "error banner is red" --json
```

### Setup and Configuration

After installing via `pip install retix`, run the setup command:

```bash
retix setup
retix setup --non-interactive
retix config
```

`retix setup` performs:
- environment validation (macOS tooling checks)
- virtual environment creation in `~/.cache/retix/venv` (if needed)
- hardware-aware model tier selection (2B, 8B, MoE profile)
- optional custom Hugging Face model repo selection with format and reachability checks

`retix config` initializes project context in `.retix/` and updates `.gitignore` with RETIX-specific ignore entries.

### Model Management

```bash
retix model list
retix model info
retix model switch 2b
retix model switch 8b
retix model switch moe
```

### Benchmarking

```bash
retix bench
```

### Daemon Mode

```bash
retix daemon start
retix daemon status
retix daemon stop
```

`retix daemon stop` performs deterministic shutdown:
- sends `SIGTERM`
- waits for graceful exit
- escalates to `SIGKILL` on timeout
- removes stale PID/socket files

## Project Context

RETIX project context is stored in:

```text
.retix/
  SKILL.md
  config.yaml
```

The generated skill file uses a strict metadata header:
- `ID`
- `Name`
- `Version`

## Security and Hygiene

- Unix daemon socket permissions are set to `600`.
- Stale sockets are cleaned up when daemon responsiveness checks fail.
- Local project context and archive artifacts are ignored through `.gitignore`.

## Testing

### Unit and Integration Tests

```bash
pytest tests
```

### Real-World Screenshot Suite

```bash
RETIX_RUN_REAL_WORLD=1 pytest tests/real_world -m real_world
```

The real-world suite covers:
- login screenshots
- dashboard screenshots
- code editor screenshots

If fixtures are missing, tests are skipped with explicit reasons.

## Troubleshooting

### Installation Hangs on Torch

If `pip install retix` hangs indefinitely during torch installation, use `uv` instead:

```bash
uv pip install retix
```

**Why?** The standard pip resolver gets stuck backtracking through version combinations for complex ML dependencies (torch, transformers, datasets). The Rust-based `uv` resolver handles this in ~50 seconds.

If you don't have `uv` installed:

```bash
# Install uv 
brew install uv  # macOS
# or
pip install uv
```

### Installation Failed Despite uv

If installation still fails, try installing torch first in isolation:

```bash
uv pip install torch torchvision
uv pip install retix
```

## License

MIT License.
