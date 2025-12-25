# Development Setup

## Quick Start

### Option 1: Docker (Recommended)

```bash
docker compose up -d
```

This starts all services in the background. Check logs with:

```bash
docker compose logs -f
```

### Option 2: Local Setup

1. Install `mise`:
   ```bash
   curl https://mise.jdx.dev/install.sh | sh
   ```
2. Setup tools:
   ```bash
   mise install
   ```
3. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
4. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   ```

---

## Running the Project

### With Docker

```bash
docker compose up -d          # Start all services
docker compose down           # Stop all services
docker compose logs -f        # View logs
```

### Locally

**Terminal 1 - Backend:**

```bash
cd backend
python main.py
```

**Terminal 2 - Frontend:**

```bash
cd frontend
npm run dev
```

---

## Tools & Versions

Tool versions are pinned in `.mise.toml` (local) or `.devcontainer/Dockerfile` (Docker). All team members use the same versions automatically.

Check installed versions:

```bash
mise ls
```

---

## Troubleshooting

**Docker won't start?**

- Ensure Docker daemon is running
- Check port conflicts: `docker ps`
- Rebuild: `docker compose build --no-cache`

**Python/Node commands not found locally?**

- Run `mise install` in project root
- Verify: `mise ls`

**Port already in use?**

- Check what's using the port: `lsof -i :PORT_NUMBER`
- Or edit `docker-compose.yaml` to use different port mapping
