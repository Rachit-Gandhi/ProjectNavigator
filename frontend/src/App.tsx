import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { jsPDF } from 'jspdf'
import './App.css'

const COMMANDS = [
  { label: '/clear', description: 'Reset the active chat session' },
  { label: '/help', description: 'Show available commands' },
  { label: '/status', description: 'Summarize current session context' },
]

const SAMPLE_RESPONSES = [
  'I have processed your request based on the available data.',
  'Here is the information you asked for.',
  'The analysis of the uploaded files indicates the following results.',
  'Please let me know if you need further clarification on this topic.',
]

type UploadedFile = {
  path: string
  size: string
}

type UploadedProject = {
  name: string
  updatedAt: string
  files: UploadedFile[]
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'system'
  text: string
  timestamp: string
  isStreaming?: boolean
}

const formatBytes = (bytes: number) => {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 KB'
  const units = ['B', 'KB', 'MB', 'GB']
  const order = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / Math.pow(1024, order)).toFixed(1)} ${units[order]}`
}

const nowStamp = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

const escapeHtml = (value: string) =>
  value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

function App() {
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID())
  const [projects, setProjects] = useState<UploadedProject[]>([])
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([
    {
      id: crypto.randomUUID(),
      role: 'assistant',
      text: 'Hi! Upload a project directory and ask anything.',
      timestamp: nowStamp(),
    },
  ])
  const [message, setMessage] = useState('')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const streamingTimer = useRef<number | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const directoryInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    return () => {
      if (streamingTimer.current) {
        window.clearInterval(streamingTimer.current)
      }
    }
  }, [])

  useEffect(() => {
    if (directoryInputRef.current) {
      directoryInputRef.current.setAttribute('webkitdirectory', 'true')
      directoryInputRef.current.setAttribute('directory', 'true')
    }
  }, [])

  const filteredCommands = useMemo(() => {
    if (!message.startsWith('/')) return []
    return COMMANDS.filter((cmd) => cmd.label.startsWith(message.trim()))
  }, [message])

  const activeFiles = useMemo(() => {
    // Flatten all files from all projects for display, or just show the latest uploaded ones
    const allFiles = projects.flatMap((p) => p.files)
    return allFiles.slice(0, 6)
  }, [projects])

  const highlightedInput = useMemo(() => {
    let markup = escapeHtml(message)
    COMMANDS.forEach((cmd) => {
      const pattern = new RegExp(cmd.label.replace('/', '\\/'), 'gi')
      markup = markup.replace(pattern, (match) => `<span class="command-highlight">${match}</span>`)
    })
    return markup || '&nbsp;'
  }, [message])

  const handleDirectoryUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files) return

    const combined = new Map<string, UploadedProject>(projects.map((project) => [project.name, project]))
    Array.from(files).forEach((file) => {
      const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name
      const [projectName = 'data', ...rest] = relativePath.split('/')
      const normalized = projectName || 'data'
      const existing = combined.get(normalized) || {
        name: normalized,
        updatedAt: new Date().toLocaleString(),
        files: [],
      }
      existing.updatedAt = new Date().toLocaleString()
      existing.files = [
        ...existing.files,
        {
          path: rest.join('/') || file.name,
          size: formatBytes(file.size),
        },
      ]
      combined.set(normalized, existing)
    })

    const aggregated = Array.from(combined.values())
    setProjects(aggregated)
  }

  const pushMessage = (message: ChatMessage) => {
    setChatHistory((prev) => [...prev, message])
  }

  const handleCommand = (command: string) => {
    if (command === '/clear') {
      setSessionId(crypto.randomUUID())
      setChatHistory([])
      setMessage('')
      return
    }

    const responseMap: Record<string, string> = {
      '/help': 'Commands: /clear, /help, /status.',
      '/status': `${projects.length} project(s) loaded.`,
    }

    const text = responseMap[command] || 'Command acknowledged.'
    pushMessage({ id: crypto.randomUUID(), role: 'system', text, timestamp: nowStamp() })
    setMessage('')
  }

  const synthesizeResponse = (prompt: string) => {
    const base = SAMPLE_RESPONSES[Math.floor(Math.random() * SAMPLE_RESPONSES.length)]
    return `${base}\n\nResponse to: ${prompt}`
  }

  const streamAssistantResponse = (draftId: string, fullText: string) => {
    setIsStreaming(true)
    let index = 0
    const characters = fullText.split('')
    streamingTimer.current = window.setInterval(() => {
      index += 3
      const chunk = characters.slice(0, index).join('')
      setChatHistory((prev) =>
        prev.map((msg) => (msg.id === draftId ? { ...msg, text: chunk, isStreaming: index < characters.length } : msg)),
      )
      if (index >= characters.length && streamingTimer.current) {
        window.clearInterval(streamingTimer.current)
        streamingTimer.current = null
        setIsStreaming(false)
      }
    }, 45)
  }

  const handleSend = () => {
    if (!message.trim() || isStreaming) return

    if (message.startsWith('/')) {
      handleCommand(message.trim())
      return
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      text: message,
      timestamp: nowStamp(),
    }
    pushMessage(userMessage)
    setMessage('')

    const assistantId = crypto.randomUUID()
    pushMessage({ id: assistantId, role: 'assistant', text: '', timestamp: nowStamp(), isStreaming: true })
    const response = synthesizeResponse(message)
    streamAssistantResponse(assistantId, response)
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
      return
    }
    if (event.key === 'Tab' && filteredCommands.length) {
      event.preventDefault()
      setMessage(filteredCommands[0].label + ' ')
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }

  const handleDownloadPdf = () => {
    const doc = new jsPDF({ unit: 'pt', format: 'a4' })
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(18)
    doc.text('Controlled RAG Session', 40, 50)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(12)

    let cursorY = 80
    chatHistory.forEach((entry) => {
      const prefix = `[${entry.timestamp}] ${entry.role.toUpperCase()}:`
      doc.setFont('helvetica', 'bold')
      doc.text(prefix, 40, cursorY)
      doc.setFont('helvetica', 'normal')
      const lines = doc.splitTextToSize(entry.text || '...', 520)
      cursorY += 16
      doc.text(lines, 40, cursorY)
      cursorY += lines.length * 14 + 8
      if (cursorY > 760) {
        doc.addPage()
        cursorY = 40
      }
    })

    doc.save('controlled-rag-session.pdf')
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-mark">
          <div className="logo-mark">CR</div>
          <div>
            <p className="title">Controlled RAG Cockpit</p>
            <p className="subtitle">Multi-project assistant workspace</p>
          </div>
        </div>
        <div className="header-actions">
          <label className="upload-control">
            <input ref={directoryInputRef} type="file" multiple onChange={handleDirectoryUpload} />
            <span>Sync data folder</span>
          </label>
          <button className="ghost" onClick={handleDownloadPdf}>
            Download PDF
          </button>
        </div>
      </header>

      <div className="workspace">
        <aside className={sidebarCollapsed ? 'sidebar collapsed' : 'sidebar'}>
          <button
            className="collapse-toggle"
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={() => setSidebarCollapsed((prev) => !prev)}
          >
            <QuillHamburgerIcon collapsed={sidebarCollapsed} />
          </button>
          {!sidebarCollapsed && (
            <>
            <section>
              <div className="section-heading">
                <h3>Project Library</h3>
                <span className="badge">{projects.length}</span>
              </div>
              <div className="project-list">
                {projects.length === 0 && <p className="empty">Upload a directory to populate /data.</p>}
                {projects.map((project) => (
                  <div
                    key={project.name}
                    className={'project-card'}
                  >
                    <div>
                      <p className="project-name">{project.name}</p>
                      <p className="project-meta">{project.files.length} files · Updated {project.updatedAt}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>

              <section>
                <div className="section-heading">
                  <h3>Recent Files</h3>
                </div>
                <div className="file-list">
                  {activeFiles.length === 0 && <p className="empty">No files yet.</p>}
                  {activeFiles.map((file, index) => (
                    <div key={`${file.path}-${index}`} className="file-row">
                      <div>
                        <p className="file-name">{file.path || '(root)'}</p>
                        <p className="file-size">{file.size}</p>
                      </div>
                      <span className="file-pill">@{deriveTag(file.path)}</span>
                    </div>
                  ))}
                </div>
              </section>

            </>
          )}
        </aside>

        <main className="chat-panel">
          <div className="chat-header">
            <div>
              <p className="panel-label">Chatbot</p>
              <h2>AI Assistant</h2>
              <div className="session-id">Session {sessionId.slice(0, 8)}</div>
            </div>
            {isStreaming && <div className="spinner" aria-label="Processing" />}
          </div>

          <div className="chat-stream">
            {chatHistory.map((message) => (
              <div key={message.id} className={`chat-bubble ${message.role}`}>
                <div className="bubble-header">
                  <span className="role-chip">{message.role}</span>
                  <span className="timestamp">{message.timestamp}</span>
                </div>
                <p>{message.text}</p>
                {message.isStreaming && <div className="typing-indicator" />}
              </div>
            ))}
          </div>

          <div className="input-stack">
            {filteredCommands.length > 0 && (
              <div className="command-hints">
                {filteredCommands.map((cmd) => (
                  <button key={cmd.label} onClick={() => setMessage(`${cmd.label} `)}>
                    <span>{cmd.label}</span>
                    <small>{cmd.description}</small>
                  </button>
                ))}
              </div>
            )}
            <div className="input-shell">
              <div className="input-highlight" dangerouslySetInnerHTML={{ __html: highlightedInput }} />
              <textarea
                ref={inputRef}
                value={message}
                placeholder="Type / for commands, @ for tags, Shift+Enter for newline"
                onChange={(event) => setMessage(event.target.value)}
                onKeyDown={handleKeyDown}
                rows={3}
              />
              <button className="primary" onClick={handleSend} disabled={!message.trim() || isStreaming}>
                {isStreaming ? 'Streaming…' : 'Send'}
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

const QuillHamburgerIcon = ({ collapsed }: { collapsed: boolean }) => (
  <svg
    viewBox="0 0 64 64"
    role="img"
    aria-hidden="true"
    focusable="false"
    className={collapsed ? 'icon collapsed' : 'icon'}
  >
    <path
      d="M40 8c-5.5 5-10 13-10 18 0 6 2.8 10.5 8.5 14.5l10.5-12c1.5-1.8 2-3.8 2-5.8C51 17 47 12 40 8z"
      fill="url(#quillGradient)"
      stroke="#0f62fe"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <line x1="12" y1="18" x2="28" y2="18" stroke="#0f62fe" strokeWidth="2.4" strokeLinecap="round" />
    <line x1="12" y1="30" x2="26" y2="30" stroke="#0f62fe" strokeWidth="2.4" strokeLinecap="round" />
    <line x1="12" y1="42" x2="30" y2="42" stroke="#0f62fe" strokeWidth="2.4" strokeLinecap="round" />
    <defs>
      <linearGradient id="quillGradient" x1="32" y1="8" x2="50" y2="32" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#dfe8ff" />
        <stop offset="100%" stopColor="#8fb1ff" />
      </linearGradient>
    </defs>
  </svg>
)

const deriveTag = (path: string) => {
  const extension = path.split('.').pop() || 'file'
  return extension.toLowerCase()
}

export default App
