# IntelliDocs AI - Windows 11 PowerShell Setup Guide

This guide provides end-to-end instructions for installing, configuring, and running IntelliDocs AI on Windows 11 with PowerShell.

---

## 1. System Requirements

- **Operating System**: Windows 11 (64-bit)
- **Processor**: Intel Core i5 or AMD equivalent
- **Memory (RAM)**: 16 GB recommended
- **Graphics (Optional)**: NVIDIA RTX 3050 (4 GB VRAM) with CUDA 12.x or CPU execution
- **Storage**: ~5 GB free space for virtual environments, models, and embeddings

---

## 2. Install Required System Software

### A. Python 3.12 (or 3.11)
Ensure Python is installed and added to your `PATH`:
```powershell
python --version
# Output should show: Python 3.12.x or 3.11.x
```

### B. Node.js (20 LTS or 24 Current) & npm
```powershell
node --version
npm --version
```

### C. Tesseract OCR (Windows)
1. Download the official Windows installer from:  
   `https://github.com/UB-Mannheim/tesseract/wiki`
2. Install to default path: `C:\Program Files\Tesseract-OCR`
3. Verify in PowerShell:
```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
```
Set `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` in your `.env`.

### D. PostgreSQL 15 / 16 (or SQLite Fallback)
If using PostgreSQL:
1. Download and install PostgreSQL from `https://www.postgresql.org/download/windows/`.
2. Start the service and create the database:
```powershell
psql -U postgres -c "CREATE DATABASE intellidocs;"
```
*Note: If PostgreSQL is not installed, the platform automatically supports SQLite (`sqlite:///./backend/storage/intellidocs.db`) for immediate local development.*

---

## 3. Clone and Setup Environment

```powershell
# Navigate to project directory
cd D:\nlpProject

# Create Python virtual environment
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip
```

### PyTorch Installation Note (CPU vs. CUDA)
By default, the standard PyTorch wheel in `backend/requirements.txt` runs smoothly on CPU.  
If you wish to enable NVIDIA RTX 3050 hardware acceleration:
```powershell
# For CUDA 12.1 acceleration:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# For standard CPU-only execution (default):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Install backend dependencies:
```powershell
pip install -r backend/requirements.txt
```

Download NLP models and language datasets:
```powershell
python scripts/download_models.py
```

---

## 4. Environment Configuration

```powershell
Copy-Item .env.example .env
```
Open `.env` and verify your settings (`DATABASE_URL`, `SECRET_KEY`, `TESSERACT_CMD`, etc.).

---

## 5. Database Migrations

```powershell
cd backend
alembic upgrade head
cd ..
```

---

## 6. Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```
The frontend will start at `http://localhost:5173`.

---

## 7. Helper Scripts

We provide convenient PowerShell scripts in `scripts/`:
- `.\scripts\setup.ps1`: Automated environment setup
- `.\scripts\run_backend.ps1`: Starts FastAPI on port 8000
- `.\scripts\run_frontend.ps1`: Starts Vite frontend on port 5173
- `.\scripts\seed_demo.py`: Seeds demonstration user and documents

---

## 8. Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| `Activate.ps1 cannot be loaded because running scripts is disabled` | PowerShell ExecutionPolicy | Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `TesseractNotFoundError` | Path to tesseract executable incorrect | Set `TESSERACT_CMD` in `.env` to the full path of `tesseract.exe` |
| CUDA `OutOfMemoryError` | GPU VRAM limit reached (4 GB) | Set `DEVICE=cpu` in `.env` or the platform will automatically fall back to CPU |
| Port 8000/5173 in use | Existing process binding port | Run `Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process` |
