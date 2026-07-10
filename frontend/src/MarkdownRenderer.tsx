import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'


const components: Components = {
  table: ({ node: _node, ...props }) => (
    <div className="markdown-table-scroll">
      <table {...props} />
    </div>
  )
}


export function MarkdownRenderer({ children }: { children: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {children}
    </ReactMarkdown>
  )
}
