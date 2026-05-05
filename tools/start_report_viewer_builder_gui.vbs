Option Explicit

Dim fso, shell, repoRoot, pyExe, guiScript, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

repoRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
pyExe = repoRoot & "\venv\Scripts\python.exe"
guiScript = repoRoot & "\tools\report_viewer_builder_gui.py"

If Not fso.FileExists(pyExe) Then
  MsgBox "Python not found: " & pyExe, vbCritical, "Report Viewer Builder"
  WScript.Quit 1
End If

If Not fso.FileExists(guiScript) Then
  MsgBox "GUI script not found: " & guiScript, vbCritical, "Report Viewer Builder"
  WScript.Quit 1
End If

cmd = """" & pyExe & """ """ & guiScript & """"
shell.Run cmd, 1, False

