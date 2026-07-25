!macro NSIS_HOOK_POSTINSTALL
  ExecWait '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\word-addin-native\install-native-word-addin.ps1" -AssemblyPath "$INSTDIR\word-addin-native\Workmode.WordAddin.dll"' $0
  ${If} $0 != 0
    MessageBox MB_ICONEXCLAMATION|MB_OK "Workmode 已安装，但 Word 插件注册失败。请重新运行安装程序，或在 Workmode 中查看帮助。"
  ${EndIf}
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  ExecWait '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\word-addin-native\uninstall-native-word-addin.ps1"' $0
!macroend
