Option Explicit

Dim fso, shell, repoRoot, htmlPath
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

repoRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
htmlPath = repoRoot & "\webui\report_viewer.html"

If fso.FileExists(htmlPath) Then
  shell.Run """" & htmlPath & """", 1, False
Else
  MsgBox "report_viewer.html not found. Please run update_report_viewer_hidden.vbs first.", vbExclamation, "TradingAgents"
End If

