Option Explicit

Dim fso, shell, repoRoot, pyExe, launcher, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

repoRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
pyExe = repoRoot & "\venv\Scripts\python.exe"
launcher = repoRoot & "\tools\terminal_launcher.py"

If Not fso.FileExists(pyExe) Then
  MsgBox "Python not found: " & pyExe, vbCritical, "TradingAgents Launcher"
  WScript.Quit 1
End If

If Not fso.FileExists(launcher) Then
  MsgBox "Launcher script not found: " & launcher, vbCritical, "TradingAgents Launcher"
  WScript.Quit 1
End If

cmd = """" & pyExe & """ """ & launcher & """"
shell.Run cmd, 1, False

