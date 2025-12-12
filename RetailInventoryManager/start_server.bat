@echo off
echo ====================================================================
echo Starting Retail Inventory Manager Production Server
echo ====================================================================
echo.
echo This will start the server and make it accessible from any device
echo on your network.
echo.
echo To stop the server, press Ctrl+C in this window.
echo ====================================================================
echo.

call venv\Scripts\activate.bat

python prod_server.py

pause
