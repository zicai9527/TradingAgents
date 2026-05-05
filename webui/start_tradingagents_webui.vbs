Option Explicit

Dim fso, shell, repoRoot, pyExe, appPath, url, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

repoRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
pyExe = repoRoot & "\venv\Scripts\python.exe"
appPath = repoRoot & "\webui\server.py"
url = "http://127.0.0.1:8765"

If Not fso.FileExists(pyExe) Then
  MsgBox "Python not found in venv: " & pyExe, vbCritical, "TradingAgents Web UI"
  WScript.Quit 1
End If

If Not fso.FileExists(appPath) Then
  MsgBox "server.py not found: " & appPath, vbCritical, "TradingAgents Web UI"
  WScript.Quit 1
End If

' Start server hidden
cmd = """" & pyExe & """ """ & appPath & """"
shell.Run cmd, 0, False

' Wait briefly then open browser
WScript.Sleep 1400
shell.Run url, 1, False

