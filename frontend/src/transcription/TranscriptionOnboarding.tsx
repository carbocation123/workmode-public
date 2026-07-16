import { useEffect, useRef, useState } from 'react'

import {
  TRANSCRIPTION_ONBOARDING_STEPS,
  TRANSCRIPTION_ONBOARDING_STORAGE_KEY,
  completeTranscriptionOnboarding,
  parseTranscriptionOnboarding,
  setTranscriptionOnboardingStep,
  type TranscriptionOnboardingState,
} from './onboarding'

interface TranscriptionOnboardingProps {
  dashscopeConfigured: boolean
  onConfigure: () => void
  onClose: () => void
}

const CONTENT = [
  {
    eyebrow: 'STEP 1 · CONNECTION',
    title: '先配置 DashScope',
    body: '会议转写固定使用阿里云 Fun-ASR。第一次使用前，在共享设置页填写 DashScope API Key；密钥只保存在 Workmode Public 的本机配置中，不会写入录音或转写目录。',
    points: ['转写模型固定为 Fun-ASR', '默认启用说话人区分', '未配置 Key 时不会接收或复制录音文件'],
  },
  {
    eyebrow: 'STEP 2 · INPUT',
    title: '批量上传录音',
    body: '点击“上传录音”，或者把一个或多个文件拖到左侧导入区。原始文件会保存在固定 input 目录，并进入单任务队列依次处理。',
    points: ['支持 M4A、MP3、WAV、OGG、FLAC、AAC、WebM 和 MP4', '可以一次选择多个文件', '关闭再打开应用，排队或处理中任务仍可恢复'],
  },
  {
    eyebrow: 'STEP 3 · OUTPUT',
    title: '查看、整理与导出',
    body: '转写完成后，可以按说话人阅读，也可以切换纯文本或 Markdown。标题可随时修改，结果可下载为 TXT、Markdown 或 JSON。',
    points: ['失败任务保留原始录音，可直接重试', '删除会把录音和结果一起移入回收站', '根目录里的其它文件和 Workmode session 不参与转写扫描'],
  },
] as const

export function TranscriptionOnboarding({
  dashscopeConfigured,
  onConfigure,
  onClose,
}: TranscriptionOnboardingProps) {
  const [state, setState] = useState<TranscriptionOnboardingState>(() =>
    parseTranscriptionOnboarding(localStorage.getItem(TRANSCRIPTION_ONBOARDING_STORAGE_KEY)),
  )
  const dialogRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    dialogRef.current?.focus()
  }, [])

  const content = CONTENT[state.step] ?? CONTENT[0]
  const isLast = state.step === TRANSCRIPTION_ONBOARDING_STEPS.length - 1

  function commit(next: TranscriptionOnboardingState) {
    localStorage.setItem(TRANSCRIPTION_ONBOARDING_STORAGE_KEY, JSON.stringify(next))
    setState(next)
  }

  function finish() {
    commit(completeTranscriptionOnboarding(state))
    onClose()
  }

  return (
    <div className="transcription-guide-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="transcription-guide-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="transcription-guide-title"
        tabIndex={-1}
        onKeyDown={(event) => {
          if (event.key === 'Escape') finish()
        }}
      >
        <header>
          <div className="transcription-guide-mark" aria-hidden>声</div>
          <div>
            <span>{content.eyebrow}</span>
            <h2 id="transcription-guide-title">{content.title}</h2>
          </div>
          <button type="button" onClick={finish}>跳过指引</button>
        </header>
        <div className="transcription-guide-body">
          <p>{content.body}</p>
          <ul>
            {content.points.map((point) => <li key={point}><span aria-hidden>✓</span>{point}</li>)}
          </ul>
          {state.step === 0 && (
            <div className="transcription-guide-configure">
              <span className={dashscopeConfigured ? 'configured' : ''}>
                {dashscopeConfigured ? 'DashScope 已配置，可以开始上传' : 'DashScope 尚未配置'}
              </span>
              {!dashscopeConfigured && <button type="button" onClick={onConfigure}>打开设置填写 Key</button>}
            </div>
          )}
        </div>
        <footer>
          <div className="transcription-guide-progress" aria-label={`第 ${state.step + 1} 步，共 ${TRANSCRIPTION_ONBOARDING_STEPS.length} 步`}>
            {TRANSCRIPTION_ONBOARDING_STEPS.map((step, index) => (
              <span className={index === state.step ? 'active' : index < state.step ? 'done' : ''} key={step} />
            ))}
          </div>
          <div className="transcription-guide-actions">
            <button
              type="button"
              disabled={state.step === 0}
              onClick={() => commit(setTranscriptionOnboardingStep(state, state.step - 1))}
            >
              上一步
            </button>
            <button
              type="button"
              onClick={() => isLast ? finish() : commit(setTranscriptionOnboardingStep(state, state.step + 1))}
            >
              {isLast ? '开始使用' : '下一步'}
            </button>
          </div>
        </footer>
      </section>
    </div>
  )
}
