' ---------------------------------------------------------------------
'  Kot Karelaji - penceresiz baslatici
'
'  Bu dosyaya cift tiklayin. Komut penceresi acilmadan harita arayuzu
'  tarayicida acilir.
'
'  Gereksinim: Python 3.8 veya uzeri (pythonw.exe ile birlikte kurulur)
'  Python yoksa baslat.bat dosyasini kullanin; o dosya ne yapmaniz
'  gerektigini yazar.
' ---------------------------------------------------------------------
Option Explicit

Dim fso, kabuk, klasor, komut, python

Set fso = CreateObject("Scripting.FileSystemObject")
Set kabuk = CreateObject("WScript.Shell")

klasor = fso.GetParentFolderName(WScript.ScriptFullName)
kabuk.CurrentDirectory = klasor

If Not fso.FileExists(fso.BuildPath(klasor, "karelaj.py")) Then
    MsgBox "karelaj.py bulunamadi." & vbCrLf & vbCrLf & _
           "Bu dosya kot-karelaj klasorunun icinde olmalidir.", _
           vbCritical, "Kot Karelaji"
    WScript.Quit 1
End If

' pythonw.exe konsol acmadan calisir
python = "pythonw"
On Error Resume Next
kabuk.Run """" & python & """ karelaj.py arayuz", 0, False
If Err.Number <> 0 Then
    Err.Clear
    ' pythonw bulunamadiysa py -w ile dene
    kabuk.Run "py -w karelaj.py arayuz", 0, False
    If Err.Number <> 0 Then
        MsgBox "Python bulunamadi." & vbCrLf & vbCrLf & _
               "python.org adresinden Python 3.8 veya uzerini kurun ve" & vbCrLf & _
               "kurulum sirasinda ""Add Python to PATH"" kutusunu isaretleyin.", _
               vbCritical, "Kot Karelaji"
        WScript.Quit 1
    End If
End If
On Error Goto 0
