@echo off
echo Instalando PyInstaller...
pip install pyinstaller --quiet

echo.
echo Gerando TikTokAutoPoster.exe ...
pyinstaller --onefile --windowed ^
  --name "TikTokAutoPoster" ^
  --collect-all selenium ^
  --collect-all webdriver_manager ^
  --collect-all pystray ^
  --hidden-import win32com.client ^
  --hidden-import win32api ^
  --hidden-import pywintypes ^
  --hidden-import pyperclip ^
  --hidden-import PIL ^
  --hidden-import PIL.Image ^
  --hidden-import PIL.ImageDraw ^
  bot.py

echo.
if exist dist\TikTokAutoPoster.exe (
    echo [OK] Criado: dist\TikTokAutoPoster.exe
    explorer dist
) else (
    echo [ERRO] Build falhou. Veja as mensagens acima.
)
pause
