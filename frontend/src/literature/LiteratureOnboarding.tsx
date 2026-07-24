import { useEffect, useState, type CSSProperties } from 'react'

import {
  LITERATURE_ONBOARDING_STORAGE_KEY,
  LITERATURE_TOUR_STEPS,
  completeLiteratureOnboarding,
  literatureOnboardingMode,
  parseLiteratureOnboarding,
  setLiteratureOnboardingStep,
  type LiteratureOnboardingState,
} from './onboarding'

interface LiteratureOnboardingProps {
  modelConfigured: boolean | null
  onConfigureModel: () => void
}

function guideTarget(name: string): HTMLElement | null {
  return document.querySelector<HTMLElement>(`[data-literature-guide="${name}"]`)
}

function cardPosition(target: string, rect: DOMRect | null): CSSProperties {
  if (!rect || window.innerWidth < 920) return {}
  const width = Math.min(370, window.innerWidth - 48)
  if (target === 'composer') {
    return {
      left: Math.max(24, Math.min(rect.left + rect.width / 2 - width / 2, window.innerWidth - width - 24)),
      bottom: Math.max(24, window.innerHeight - rect.top + 20),
      transform: 'none',
      width,
    }
  }
  return {
    left: Math.max(24, Math.min(rect.right + 22, window.innerWidth - width - 24)),
    top: Math.max(24, Math.min(rect.top, window.innerHeight - 230)),
    transform: 'none',
    width,
  }
}

export function LiteratureOnboarding({
  modelConfigured,
  onConfigureModel,
}: LiteratureOnboardingProps) {
  const [state, setState] = useState<LiteratureOnboardingState>(() =>
    parseLiteratureOnboarding(localStorage.getItem(LITERATURE_ONBOARDING_STORAGE_KEY)),
  )
  const [rect, setRect] = useState<DOMRect | null>(null)
  const mode = literatureOnboardingMode(modelConfigured, state)
  const current = LITERATURE_TOUR_STEPS[state.step] ?? LITERATURE_TOUR_STEPS[0]
  const target = mode === 'setup' ? 'settings' : current.target

  useEffect(() => {
    if (mode === 'loading' || mode === 'hidden') return undefined
    const element = guideTarget(target)
    function update() {
      setRect(guideTarget(target)?.getBoundingClientRect() ?? null)
    }
    update()
    const observer = element && 'ResizeObserver' in window ? new ResizeObserver(update) : null
    if (element) observer?.observe(element)
    window.addEventListener('resize', update)
    window.addEventListener('scroll', update, true)
    return () => {
      observer?.disconnect()
      window.removeEventListener('resize', update)
      window.removeEventListener('scroll', update, true)
    }
  }, [mode, target])

  if (mode === 'loading' || mode === 'hidden') return null

  function commit(next: LiteratureOnboardingState) {
    localStorage.setItem(LITERATURE_ONBOARDING_STORAGE_KEY, JSON.stringify(next))
    setState(next)
  }

  function finish() {
    commit(completeLiteratureOnboarding(state))
  }

  const isLast = state.step === LITERATURE_TOUR_STEPS.length - 1

  return (
    <div className="literature-tour" role="presentation">
      {rect && (
        <div
          className="literature-tour-spotlight"
          style={{
            left: Math.max(4, rect.left - 7),
            top: Math.max(4, rect.top - 7),
            width: Math.min(rect.width + 14, window.innerWidth - 8),
            height: Math.min(rect.height + 14, window.innerHeight - 8),
          }}
        />
      )}
      <section
        aria-label={mode === 'setup' ? '配置 DeepSeek API' : `文献界面引导：${current.title}`}
        className="literature-tour-card"
        role="dialog"
        style={cardPosition(target, rect)}
      >
        {mode === 'setup' ? (
          <>
            <span className="literature-tour-count">开始前</span>
            <h2>先配置 DeepSeek API</h2>
            <p>文献助手需要模型 API 才能阅读和回答问题。点击下方按钮，在设置里按新手指引申请 Key、测试连接并保存。</p>
            <div className="literature-tour-actions">
              <button className="primary" type="button" onClick={onConfigureModel}>前往设置</button>
            </div>
          </>
        ) : (
          <>
            <span className="literature-tour-count">{state.step + 1} / {LITERATURE_TOUR_STEPS.length}</span>
            <h2>{current.title}</h2>
            <p>{current.description}</p>
            <div className="literature-tour-actions">
              <button type="button" onClick={finish}>跳过</button>
              {state.step > 0 && (
                <button
                  type="button"
                  onClick={() => commit(setLiteratureOnboardingStep(state, state.step - 1))}
                >
                  上一步
                </button>
              )}
              <button
                className="primary"
                type="button"
                onClick={() => isLast
                  ? finish()
                  : commit(setLiteratureOnboardingStep(state, state.step + 1))}
              >
                {isLast ? '开始使用' : '下一步'}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  )
}
