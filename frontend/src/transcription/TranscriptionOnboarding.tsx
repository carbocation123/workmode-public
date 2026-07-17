import { useEffect, useRef, useState } from 'react'

import { openExternalUrl } from '../desktop'
import {
  TRANSCRIPTION_ONBOARDING_STEPS,
  TRANSCRIPTION_ONBOARDING_STORAGE_KEY,
  completeTranscriptionOnboarding,
  parseTranscriptionOnboarding,
  setTranscriptionOnboardingStep,
  type TranscriptionOnboardingState,
} from './onboarding'

const DASHSCOPE_CONSOLE_URL = 'https://bailian.console.aliyun.com/?tab=model'
const DASHSCOPE_API_KEY_GUIDE_URL = 'https://help.aliyun.com/zh/model-studio/get-api-key'
const DASHSCOPE_FREE_QUOTA_GUIDE_URL = 'https://help.aliyun.com/zh/model-studio/new-free-quota/'

interface TranscriptionOnboardingProps {
  dashscopeConfigured: boolean
  onConfigure: () => void
  onClose: () => void
}

const CONTENT = [
  {
    eyebrow: 'STEP 1 · CONNECTION',
    title: '先配置 DashScope',
    body: '会议转写固定使用阿里云百炼的 Fun-ASR。没有用过百炼也没关系，请从下面第 1 项开始逐项完成。',
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

const DASHSCOPE_SETUP_STEPS = [
  {
    title: '登录或注册阿里云账号',
    detail: '点击下方“打开百炼控制台”。没有账号就按页面提示注册；如果页面提示尚未实名认证，请先完成实名认证再回来。优先使用主账号，子账号必须具有管理员或 API-Key 页面权限。',
  },
  {
    title: '选择华北2（北京）并开通百炼',
    detail: '在控制台右上角把地域切到“华北2（北京）”。第一次进入时阅读并同意协议，系统会自动开通；如果没有弹出协议，说明该地域已经开通。',
  },
  {
    title: '创建 API Key',
    detail: '进入 API Key 页面，点击“创建 API Key”。归属业务空间选择“默认业务空间”，权限选择“全部”；描述可以填写“Workmode Public 会议转写”。',
  },
  {
    title: '立刻复制并妥善保存',
    detail: '新 Key 通常以 sk-ws 开头，完整明文只在创建成功时显示一次。请立刻复制，不要发给别人；丢失后只能重置或重新创建。',
  },
  {
    title: '确认费用保护',
    detail: 'Fun-ASR 调用属于按量付费。新用户可能有免费额度；符合条件时建议在百炼中开启“免费额度用完即停”，最终价格和余额以控制台显示为准。',
  },
  {
    title: '粘贴到 Workmode Public',
    detail: '点击“打开设置填写 Key”，粘贴百炼 API Key 并保存；不要粘贴阿里云 AccessKey ID 或 AccessKey Secret。“DashScope 已配置”只表示保存成功，再上传一小段测试录音并转写完成，才表示 Key 确实可用。',
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
          {state.step === 0 ? (
            <ol className="transcription-guide-setup-list">
              {DASHSCOPE_SETUP_STEPS.map((item, index) => (
                <li key={item.title}>
                  <span aria-hidden>{index + 1}</span>
                  <div><strong>{item.title}</strong><p>{item.detail}</p></div>
                </li>
              ))}
            </ol>
          ) : (
            <ul>
              {content.points.map((point) => <li key={point}><span aria-hidden>✓</span>{point}</li>)}
            </ul>
          )}
          {state.step === 0 && (
            <div className="transcription-guide-setup-actions">
              <div className="transcription-guide-links">
                <button type="button" onClick={() => void openExternalUrl(DASHSCOPE_CONSOLE_URL)}>打开百炼控制台 ↗</button>
                <button type="button" onClick={() => void openExternalUrl(DASHSCOPE_API_KEY_GUIDE_URL)}>查看阿里云官方步骤 ↗</button>
                <button type="button" onClick={() => void openExternalUrl(DASHSCOPE_FREE_QUOTA_GUIDE_URL)}>查看免费额度与防超额 ↗</button>
              </div>
              <div className="transcription-guide-configure">
                <span className={dashscopeConfigured ? 'configured' : ''}>
                  {dashscopeConfigured ? '完成：DashScope 已配置，可以开始上传' : '尚未完成：Workmode Public 还没有检测到 Key'}
                </span>
                {!dashscopeConfigured && <button type="button" onClick={onConfigure}>打开设置填写 Key</button>}
              </div>
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
