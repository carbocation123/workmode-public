import { useState } from 'react'

import { Icon } from './Icon'
import {
  LITERATURE_ONBOARDING_STEPS,
  LITERATURE_ONBOARDING_STORAGE_KEY,
  completeLiteratureOnboarding,
  parseLiteratureOnboarding,
  setLiteratureOnboardingStep,
  type LiteratureOnboardingState,
} from './onboarding'

interface LiteratureOnboardingProps {
  onConfigureMineru: () => void
}

const CONTENT = [
  {
    eyebrow: 'LITERATURE MODE',
    title: '欢迎来到文献智库',
    body: '这里把熟悉的 AI 对话和本地文献库放在同一页。左侧管理论文与标签，中央围绕你选中的论文和笔记持续讨论。',
    points: ['项目文件夹是唯一事实来源', '对话沿用 Workmode 的 session、工具记录与上下文压缩', '文献模式只开放文献领域工具'],
  },
  {
    eyebrow: 'IMPORT',
    title: '拖入 PDF，确认后才会入库',
    body: '把一篇或多篇 PDF 拖进对话区，核对文件名后点击确认入库。系统按内容去重，原文件与后续解析结果都保存在当前文献项目中。',
    points: ['取消确认不会写入项目', '入库事件作为系统上下文记录，不制造模拟对话', 'PDF 有文本层时，AI 无需等待 MinerU 也能直接阅读正文'],
  },
  {
    eyebrow: 'MINERU',
    title: 'MinerU 不是必须的，但推荐配置',
    body: '不配置 MinerU 时，AI 仍能直接读取带文本层的 PDF；配置后会明显提高多栏正文、表格、公式和版面顺序的识别准确性。扫描件或纯图片 PDF 没有文本层，仍需要 MinerU/OCR。',
    points: ['在设置中填写 MinerU Token', '可选择 pipeline 或 vlm 与文献语言', '工具结果会标明正文来自 MinerU 还是 PDF 文本层'],
    configure: true,
  },
  {
    eyebrow: 'COLLABORATION',
    title: '选择材料，然后自然语言协作',
    body: '勾选论文或笔记，相当于把当前文件交给 AI。你可以直接要求比较、提取事实、维护标签和整理笔记；长任务可随时停止，阶段结束后再整理上下文。',
    points: ['选择是当前上下文，不是编辑权限批准', '客观事实与跨文献推理分开维护', '项目记忆保存长期协作纪律，笔记可以被 AI 检索和更新'],
  },
] as const

export function LiteratureOnboarding({ onConfigureMineru }: LiteratureOnboardingProps) {
  const [state, setState] = useState<LiteratureOnboardingState>(() =>
    parseLiteratureOnboarding(localStorage.getItem(LITERATURE_ONBOARDING_STORAGE_KEY)),
  )

  if (state.completed) return null
  const content = CONTENT[state.step] ?? CONTENT[0]
  const isLast = state.step === LITERATURE_ONBOARDING_STEPS.length - 1

  function commit(next: LiteratureOnboardingState) {
    localStorage.setItem(LITERATURE_ONBOARDING_STORAGE_KEY, JSON.stringify(next))
    setState(next)
  }

  function finish() {
    commit(completeLiteratureOnboarding(state))
  }

  return (
    <div className="modal-backdrop centered-dialog-backdrop literature-onboarding-backdrop" role="presentation">
      <section className="literature-onboarding-modal" role="dialog" aria-modal="true" aria-labelledby="literature-onboarding-title">
        <header>
          <div className="literature-onboarding-mark"><Icon name="book" /></div>
          <div>
            <span className="eyebrow">{content.eyebrow}</span>
            <h2 id="literature-onboarding-title">{content.title}</h2>
          </div>
          <button type="button" className="literature-onboarding-skip" onClick={finish}>跳过引导</button>
        </header>
        <div className="literature-onboarding-body">
          <p>{content.body}</p>
          <ul>
            {content.points.map((point) => <li key={point}><Icon name="check" /><span>{point}</span></li>)}
          </ul>
          {'configure' in content && content.configure && (
            <button
              type="button"
              className="literature-onboarding-configure"
              onClick={() => {
                commit(setLiteratureOnboardingStep(state, state.step))
                onConfigureMineru()
              }}
            >
              打开设置配置 MinerU
            </button>
          )}
        </div>
        <footer>
          <div className="literature-onboarding-progress" aria-label={`第 ${state.step + 1} 步，共 ${LITERATURE_ONBOARDING_STEPS.length} 步`}>
            {LITERATURE_ONBOARDING_STEPS.map((step, index) => (
              <span className={index === state.step ? 'active' : index < state.step ? 'done' : ''} key={step} />
            ))}
          </div>
          <div className="literature-onboarding-actions">
            <button
              type="button"
              disabled={state.step === 0}
              onClick={() => commit(setLiteratureOnboardingStep(state, state.step - 1))}
            >
              上一步
            </button>
            <button
              type="button"
              onClick={() => isLast ? finish() : commit(setLiteratureOnboardingStep(state, state.step + 1))}
            >
              {isLast ? '开始使用' : '下一步'}
            </button>
          </div>
        </footer>
      </section>
    </div>
  )
}
