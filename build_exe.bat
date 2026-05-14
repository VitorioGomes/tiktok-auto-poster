@echo off
echo Instalando PyInstaller...
pip install pyinstaller --quiet

echo.
echo Gerando TikTokAutoPoster.exe ...
pyinstaller --onefile --windowed ^
  --name "TikTokAutoPoster" ^
  --collect-all selenium ^
  --collect-all webdriver_manager ^
  --hidden-import win32com.client ^
  --hidden-import win32api ^
  --hidden-import pywintypes ^
  --hidden-import pyperclip ^
  bot.py

echo.
if exist dist\TikTokAutoPoster.exe (
    echo [OK] Criado: dist\TikTokAutoPoster.exe
    explorer dist
) else (
    echo [ERRO] Build falhou. Veja as mensagens acima.
)
pause
