Option Explicit

Dim fso, shell, repoRoot, pyExe, scriptPath, htmlPath, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

repoRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
pyExe = repoRoot & "\venv\Scripts\python.exe"
scriptPath = repoRoot & "\webui\build_report_ui.py"
htmlPath = repoRoot & "\webui\report_viewer.html"

If Not fso.FileExists(pyExe) Then
  MsgBox "Python not found in venv: " & pyExe, vbCritical, "TradingAgents"
  WScript.Quit 1
End If

If Not fso.FileExists(scriptPath) Then
  MsgBox "build_report_ui.py not found: " & scriptPath, vbCritical, "TradingAgents"
  WScript.Quit 1
End If

cmd = """" & pyExe & """ """ & scriptPath & """"
shell.Run cmd, 0, True

If fso.FileExists(htmlPath) Then
  shell.Run """" & htmlPath & """", 1, False
Else
  MsgBox "report_viewer.html was not generated.", vbExclamation, "TradingAgents"
End If

