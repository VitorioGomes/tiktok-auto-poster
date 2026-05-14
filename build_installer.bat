@echo off
echo Procurando Inno Setup...

set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"

if not exist %ISCC% (
    echo.
    echo [ERRO] Inno Setup nao encontrado.
    echo Baixe em: https://jrsoftware.org/isdl.php
    echo Instale e rode este arquivo novamente.
    pause
    exit /b 1
)

echo Gerando instalador...
%ISCC% installer.iss

echo.
if exist installer_output\Setup_TikTokAutoPoster.exe (
    echo [OK] Instalador criado em: installer_output\Setup_TikTokAutoPoster.exe
    explorer installer_output
) else (
    echo [ERRO] Falha ao gerar instalador.
)
pause
