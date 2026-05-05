Option Explicit

Dim fso, shell, repoRoot, pyExe, scriptPath, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

repoRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
pyExe = repoRoot & "\venv\Scripts\python.exe"
scriptPath = repoRoot & "\webui\build_report_ui.py"

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

MsgBox "Report viewer updated successfully.", vbInformation, "TradingAgents"

