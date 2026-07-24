export interface ButtonTooltipSource {
  explicit?: string | null
  ariaLabel?: string | null
  text?: string | null
}

function normalizeTooltipText(value: string | null | undefined): string {
  return (value || '').replace(/\s+/g, ' ').trim()
}

export function resolveButtonTooltip(source: ButtonTooltipSource): string {
  return normalizeTooltipText(source.explicit)
    || normalizeTooltipText(source.ariaLabel)
    || normalizeTooltipText(source.text)
}

function syncButtonTooltip(button: HTMLButtonElement): void {
  const autoManaged = button.dataset.autoTooltip === 'true'
  if (button.title && !autoManaged) return

  const emphasizedLabel = button.querySelector<HTMLElement>(':scope > strong, :scope > span > strong')?.textContent
  const tooltip = resolveButtonTooltip({
    explicit: button.dataset.tooltip,
    ariaLabel: button.getAttribute('aria-label'),
    text: emphasizedLabel || button.textContent,
  })
  if (!tooltip) return

  button.title = tooltip
  button.dataset.autoTooltip = 'true'
}

function syncAllButtonTooltips(root: HTMLElement): void {
  root.querySelectorAll<HTMLButtonElement>('button').forEach(syncButtonTooltip)
}

function syncButtonsInNode(node: Node): void {
  const element = node instanceof Element ? node : node.parentElement
  if (!element) return
  if (element instanceof HTMLButtonElement) syncButtonTooltip(element)
  element.querySelectorAll<HTMLButtonElement>('button').forEach(syncButtonTooltip)
  const containingButton = element.closest<HTMLButtonElement>('button')
  if (containingButton) syncButtonTooltip(containingButton)
}

export function installButtonTooltips(root: HTMLElement): () => void {
  syncAllButtonTooltips(root)
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'attributes' || mutation.type === 'characterData') {
        syncButtonsInNode(mutation.target)
        continue
      }
      mutation.addedNodes.forEach(syncButtonsInNode)
      syncButtonsInNode(mutation.target)
    }
  })
  observer.observe(root, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: ['aria-label', 'data-tooltip'],
  })
  return () => observer.disconnect()
}
