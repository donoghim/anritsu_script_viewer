# Anritsu STD Scenario Viewer

PyQt6 기반 Anritsu `.test` 시나리오 뷰어입니다. 메인 및 하위 scope의 action 흐름을 그래프로 표시하고, 선택한 action의 파라미터를 확인할 수 있습니다.

## Requirements

- Windows
- Python 3.8 이상
- PyQt6

## Virtual Environment Setup

프로젝트 루트에서 `.venv` 가상환경을 생성하고 활성화합니다.

```cmd
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install PyQt6
```

PowerShell에서는 활성화 명령이 다음과 같습니다.

```powershell
.\.venv\Scripts\Activate.ps1
```

PowerShell 실행 정책 오류가 발생하면 현재 터미널에만 적용되는 다음 명령을 먼저 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Run

현재 작업공간의 `.venv`를 직접 지정해 실행할 수 있습니다.

```cmd
.venv\Scripts\python.exe app.py
```

시나리오 파일을 함께 열려면 `.test` 파일 경로를 인자로 전달합니다.

```cmd
.venv\Scripts\python.exe app.py NBIoT_06.14_ODB_disconnection.test
```

또는 가상환경을 활성화한 뒤 실행합니다.

```cmd
python app.py NBIoT_06.14_ODB_disconnection.test
```

## Project Files

- `app.py`: application entry point
- `main_window.py`: main window and scope navigation
- `flowchart_viewer.py`: graph layout and connector routing
- `anritsu_parser.py`: Anritsu `.test` XML parser
- `parameter_tree.py`: selected action parameter inspector
- `REQUIREMENTS_SPEC.md`: graph layout and rendering requirements

## Notes

- `.venv`, `venv`, and Python cache files are local artifacts and are excluded from Git.
- The supplied `.test` files are sample scenarios for checking graph rendering.