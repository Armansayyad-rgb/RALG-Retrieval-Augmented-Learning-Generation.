@echo off
setlocal enabledelayedexpansion

REM RALG Engine - comprehensive Windows test runner
REM Run from the project root:
REM   scripts\test_all.bat
REM
REM Optional:
REM   scripts\test_all.bat api
REM This also runs src\test_api_demo.py, assuming the API server is already running.

cd /d "%~dp0\.."

echo.
echo ============================================================
echo RALG Engine - comprehensive local test runner
echo ============================================================
echo Project: %CD%
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Could not find .venv\Scripts\python.exe
    echo Create/activate the venv first, or run:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    exit /b 1
)

set "PY=.venv\Scripts\python.exe"

echo [1/10] Python version
"%PY%" --version
if errorlevel 1 exit /b 1

echo.
echo [2/10] Compile important files
"%PY%" -m py_compile src\retrieval_proof_v1.py src\api_server.py src\webui\chat_handler.py src\webui\document_processor.py scripts\run_commercial_validation.py
if errorlevel 1 (
    echo [FAIL] Compile check failed.
    exit /b 1
)
if exist "src\test_api_demo.py" (
    "%PY%" -m py_compile src\test_api_demo.py
    if errorlevel 1 exit /b 1
)

echo.
echo [3/10] Run simple 50-case benchmark
"%PY%" src\retrieval_proof_v1.py --dataset data\technical_doc_benchmark_v1.jsonl --knowledge-file data\technical_docs_sample.txt
if errorlevel 1 (
    echo [FAIL] Simple benchmark failed.
    exit /b 1
)

echo.
echo [4/10] Run hard benchmark
"%PY%" src\retrieval_proof_v1.py --dataset data\technical_doc_benchmark_hard_v1.jsonl --knowledge-file data\technical_docs_hard_sample.txt
if errorlevel 1 (
    echo [FAIL] Hard benchmark failed.
    exit /b 1
)

echo.
echo [5/10] Run 23-case regression suite
"%PY%" src\regression_tests_v2.py
if errorlevel 1 (
    echo [FAIL] Regression suite failed.
    exit /b 1
)

echo.
echo [6/10] Run API input-hardening tests
"%PY%" src\test_api_input_hardening.py
if errorlevel 1 (
    echo [FAIL] API input-hardening tests failed.
    exit /b 1
)

echo.
echo [7/10] Run evidence traceability and conflict tests
"%PY%" src\test_traceability.py
if errorlevel 1 (
    echo [FAIL] Traceability tests failed.
    exit /b 1
)
"%PY%" src\test_conflict_detection.py
if errorlevel 1 (
    echo [FAIL] Conflict-detection tests failed.
    exit /b 1
)

echo.
echo [8/10] Run upload/provenance tests
"%PY%" src\test_upload_provenance.py
if errorlevel 1 (
    echo [FAIL] Upload/provenance tests failed.
    exit /b 1
)

echo.
echo [9/10] Run held-out commercial validation quality gate
"%PY%" scripts\run_commercial_validation.py
if errorlevel 1 (
    echo [FAIL] Commercial validation quality gate failed.
    exit /b 1
)

echo.
echo [10/10] Optional live API demo test
if /I "%~1"=="api" (
    if exist "src\test_api_demo.py" (
        echo Running API demo test. Make sure server is already running:
        echo   uvicorn src.api_server:app --host 127.0.0.1 --port 8000
        "%PY%" src\test_api_demo.py
        if errorlevel 1 (
            echo [FAIL] API demo test failed.
            exit /b 1
        )
    ) else (
        echo [ERROR] src\test_api_demo.py not found.
        exit /b 1
    )
) else (
    echo Skipping live API demo test.
    echo To run it after starting the server:
    echo   scripts\test_all.bat api
)

echo.
echo ============================================================
echo ALL SELECTED TESTS PASSED
echo ============================================================
echo Retrieval benchmark JSON output:
echo   logs\retrieval_proof_v1_results.json
echo Commercial validation JSON output:
echo   logs\heldout_commercial_v1_results.json
echo.
exit /b 0
