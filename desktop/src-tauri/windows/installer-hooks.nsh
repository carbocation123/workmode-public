!define WORKMODE_WORD_ADDIN_ID "0f621bd7-1e31-47e8-8a9f-7d61fdac8805"

!macro NSIS_HOOK_POSTINSTALL
  WriteRegStr HKCU "Software\Microsoft\Office\16.0\WEF\Developer" "${WORKMODE_WORD_ADDIN_ID}" "$INSTDIR\word-addin\manifest.xml"
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  DeleteRegValue HKCU "Software\Microsoft\Office\16.0\WEF\Developer" "${WORKMODE_WORD_ADDIN_ID}"
  DeleteRegKey HKCU "Software\Microsoft\Office\16.0\WEF\Developer\${WORKMODE_WORD_ADDIN_ID}"
!macroend
