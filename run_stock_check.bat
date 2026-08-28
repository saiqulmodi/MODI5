@echo off
cd /d C:\Users\saiqu\Projects\MODI5
"C:\Users\saiqu\AppData\Local\Python\pythoncore-3.14-64\python.exe" stock_check.py >> logs\stock_check.log 2>&1

git add watchlist.json
git diff --cached --quiet watchlist.json
if errorlevel 1 (
    git commit -m "Update watchlist.json (automated daily screener run)" >> logs\stock_check.log 2>&1
    git push >> logs\stock_check.log 2>&1
) else (
    echo No watchlist.json changes to commit. >> logs\stock_check.log
)
