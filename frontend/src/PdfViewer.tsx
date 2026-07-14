import { useEffect, useState } from 'react'

interface PdfViewerProps {
  src: string
  title: string
  className?: string
}

export function PdfViewer({ src, title, className = '' }: PdfViewerProps) {
  const classes = `media pdf${className ? ` ${className}` : ''}`
  const [blobUrl, setBlobUrl] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    let objectUrl = ''
    setBlobUrl('')
    setError('')

    void fetch(src, { signal: controller.signal, cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.blob()
      })
      .then((blob) => {
        if (controller.signal.aborted) return
        const pdfBlob = blob.type === 'application/pdf'
          ? blob
          : new Blob([blob], { type: 'application/pdf' })
        objectUrl = URL.createObjectURL(pdfBlob)
        setBlobUrl(objectUrl)
      })
      .catch((reason) => {
        if (controller.signal.aborted) return
        setError(reason instanceof Error ? reason.message : String(reason))
      })

    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [src])

  if (error) {
    return <div className={`${classes} pdf-viewer-state error`} role="alert">PDF 加载失败：{error}</div>
  }
  if (!blobUrl) {
    return <div className={`${classes} pdf-viewer-state`} aria-live="polite">正在加载 PDF…</div>
  }
  return <iframe className={classes} src={blobUrl} title={title} />
}
