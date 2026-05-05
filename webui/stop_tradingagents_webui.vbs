Option Explicit

Dim shell
Set shell = CreateObject("WScript.Shell")

' Best-effort stop: kill python processes serving webui/server.py
shell.Run "powershell -NoProfile -ExecutionPolicy Bypass -Command ""Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*webui\\server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }""", 0, True

MsgBox "TradingAgents Web UI stopped (if it was running).", vbInformation, "TradingAgents Web UI"

