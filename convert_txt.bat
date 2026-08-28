@echo off
setlocal enabledelayedexpansion

if "%~1"=="" (
    echo 사용법: convert_txt.bat ext1 [ext2 ...]
    echo 예시  : convert_txt.bat py
    echo 예시  : convert_txt.bat c h
    exit /b 1
)

for %%e in (%*) do call :process "%%~e"

echo.
echo 완료되었습니다.
pause
exit /b 0

:process
set "EXT=%~1"

echo [1/3] .%EXT% -^> .%EXT%.txt 내용 복제 (type 사용)
for %%f in (*.%EXT%) do (
    echo   Reading & Writing: %%f -> %%f.txt
    type "%%f" > "%%f.txt"
)

echo.
echo [2/3] 원본 .%EXT% 파일 삭제
for %%f in (*.%EXT%) do (
    echo   Deleting original: %%f
    del "%%f"
)

echo.
echo [3/3] VBScript(탐색기 엔진)로 .%EXT%.txt -^> .%EXT% 이름 변경

set "VBS_FILE=%temp%\rename_via_explorer.vbs"
if exist "%VBS_FILE%" del "%VBS_FILE%"

call :strlen SUFFIX_LEN ".%EXT%.txt"

>> "%VBS_FILE%" echo Set objShell = CreateObject("Shell.Application"^)
>> "%VBS_FILE%" echo Set fso = CreateObject("Scripting.FileSystemObject"^)
>> "%VBS_FILE%" echo strPath = fso.GetAbsolutePathName("."^)
>> "%VBS_FILE%" echo Set objFolder = objShell.NameSpace(strPath^)
>> "%VBS_FILE%" echo For Each objFile In objFolder.Items
>> "%VBS_FILE%" echo     If Right(objFile.Name, %SUFFIX_LEN%^) = ".%EXT%.txt" Then
>> "%VBS_FILE%" echo         objFile.Name = Left(objFile.Name, Len(objFile.Name^) - 4^)
>> "%VBS_FILE%" echo     End If
>> "%VBS_FILE%" echo Next

cscript //nologo "%VBS_FILE%"
del "%VBS_FILE%"

goto :eof

:strlen
setlocal enabledelayedexpansion
set "s=%~2"
set "len=0"
:strlen_loop
if defined s (
    set "s=%s:~1%"
    set /a len+=1
    goto :strlen_loop
)
endlocal & set "%~1=%len%"
goto :eof