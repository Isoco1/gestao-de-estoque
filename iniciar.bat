@echo off
REM ============================================================
REM  Gestao de Estoque - Inicializador (desenvolvimento)
REM  Sobe: PostgreSQL (Docker) + API FastAPI + Painel Next.js
REM ============================================================
setlocal enabledelayedexpansion
title Gestao de Estoque - Inicializador
cd /d "%~dp0"

echo ============================================
echo   Gestao de Estoque - Inicializador
echo ============================================
echo.

REM ---- 1. Banco de dados (PostgreSQL via Docker) ----
echo [1/5] Subindo o PostgreSQL (Docker)...
docker compose up -d >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERRO] Docker nao esta rodando.
    echo        Abra o Docker Desktop, aguarde ele iniciar e rode este script novamente.
    echo.
    pause
    exit /b 1
)

echo        Aguardando o banco ficar pronto...
:wait_db
docker compose exec -T db pg_isready -U estoque -d estoque_saas >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto wait_db
)

REM ---- 2. Backend: venv + dependencias + .env ----
echo [2/5] Preparando o backend...
cd backend
if not exist .venv (
    echo        Criando ambiente virtual e instalando dependencias...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -q -r requirements.txt
)
if not exist .env copy .env.example .env >nul

REM ---- 3. Migracoes + dados de demonstracao (idempotente) ----
echo [3/5] Aplicando migracoes e dados de demonstracao...
.venv\Scripts\python.exe -m alembic upgrade head >nul 2>&1
set "TENANT_RAW="
for /f "tokens=2 delims=:" %%i in ('.venv\Scripts\python.exe seed_dev.py ^| findstr /C:"Tenant ID"') do set "TENANT_RAW=%%i"
if not defined TENANT_RAW (
    echo.
    echo [ERRO] Falha ao popular o banco. Verifique a conexao com o PostgreSQL.
    pause
    exit /b 1
)
for /f %%a in ("%TENANT_RAW%") do set "TENANT_ID=%%a"
echo        Tenant ID: %TENANT_ID%

REM ---- 4. API FastAPI em janela propria ----
echo [4/5] Iniciando a API (porta 8000)...
REM Encerra instancias antigas do uvicorn para nao acumular processos na porta
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | Where-Object { $_.CommandLine -match 'uvicorn' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
start "Gestao de Estoque - Backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
cd ..

REM ---- 5. Painel Next.js em janela propria ----
echo [5/5] Iniciando o painel (porta 3000)...
REM Encerra o dev server antigo do Next.js, se houver
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1
cd frontend
if not exist node_modules (
    echo        Instalando dependencias do frontend...
    call npm install --no-audit --no-fund
)
if not exist .env.local (
    echo NEXT_PUBLIC_API_URL=http://localhost:8000> .env.local
    echo NEXT_PUBLIC_TENANT_ID=%TENANT_ID%>> .env.local
)
start "Gestao de Estoque - Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ============================================
echo   Tudo pronto!
echo   Painel:    http://localhost:3000
echo   API/Docs:  http://localhost:8000/docs
echo ============================================
echo.
start "" http://localhost:3000
pause

