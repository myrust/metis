import { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  BookOpen,
  Brain,
  CheckCircle2,
  Clock,
  Cpu,
  FileCode2,
  HardDrive,
  Home,
  MessageSquare,
  Moon,
  Play,
  Send,
  ShieldAlert,
  Sparkles,
  Sun,
  Wrench,
  XCircle,
} from 'lucide-react'
import {
  api,
  streamChat,
  type HealthInfo,
  type ModelsPayload,
  type NodeItem,
  type SkillItem,
} from './api/client'
import { NodeSwitcher } from './components/NodeSwitcher'

type NavTab = 'workbench' | 'memory' | 'skills'
type ChatSubTab = 'chat' | 'approvals' | 'cron'

interface TimelineEntry {
  id: string
  kind: 'user' | 'thinking' | 'tool_call' | 'tool_result' | 'approval' | 'assistant'
  text: string
  meta?: Record<string, unknown>
  resolved?: boolean
}

export default function App() {
  const [dark, setDark] = useState(false)
  const [tab, setTab] = useState<NavTab>('workbench')
  const [chatTab, setChatTab] = useState<ChatSubTab>('chat')

  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [nodes, setNodes] = useState<NodeItem[]>([])
  const [activeNodeId, setActiveNodeId] = useState('local')
  const [skills, setSkills] = useState<SkillItem[]>([])
  const [selectedSkill, setSelectedSkill] = useState<{ name: string; content: string } | null>(null)
  const [files, setFiles] = useState<string[]>([])
  const [selectedFile, setSelectedFile] = useState<{ path: string; content: string } | null>(null)
  const [cronInfo, setCronInfo] = useState<{ enabled: boolean; jobs: string[] }>({
    enabled: false,
    jobs: [],
  })
  const [models, setModels] = useState<ModelsPayload | null>(null)
  const [discoveredModels, setDiscoveredModels] = useState<
    Array<{ provider_id: string; model: string }>
  >([])
  const [selectedModelKey, setSelectedModelKey] = useState<string>('auto')
  const [backupStatus, setBackupStatus] = useState<string>('')

  const [prompt, setPrompt] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [timeline, setTimeline] = useState<TimelineEntry[]>([
    {
      id: 'welcome',
      kind: 'assistant',
      text: "Hi! I'm Metis. Ask me to inspect files, run tasks on any node, or query Mnemosyne.",
    },
  ])

  const [memQuestion, setMemQuestion] = useState('')
  const [memMode, setMemMode] = useState<'hybrid' | 'local' | 'global'>('hybrid')
  const [memAnswer, setMemAnswer] = useState('')
  const [memIngest, setMemIngest] = useState('')

  const refreshAll = useCallback(async () => {
    try {
      const [h, n, s, f, c, m, d] = await Promise.all([
        api.health(),
        api.nodes(),
        api.skills(),
        api.workspaceFiles(),
        api.cron(),
        api.models(),
        api.discoverModels(),
      ])
      setHealth(h)
      setNodes(n.nodes)
      setActiveNodeId(n.active_node_id)
      setSkills(s.skills)
      setFiles(f.files)
      setCronInfo(c)
      setModels(m)
      setDiscoveredModels(d.models)
    } catch {
      // Backend might not be running yet during standalone preview.
    }
  }, [])

  useEffect(() => {
    void refreshAll()
  }, [refreshAll])

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!prompt.trim() || streaming) return
    const text = prompt.trim()
    setPrompt('')
    setStreaming(true)
    setTimeline((prev) => [...prev, { id: `u-${Date.now()}`, kind: 'user', text }])

    const [pinnedProvider, pinnedModel] =
      selectedModelKey === 'auto' ? [undefined, undefined] : selectedModelKey.split('::')

    let assistantBuffer = ''
    try {
      await streamChat(
        text,
        (ev) => {
        if (ev.event === 'thinking') {
          if (typeof ev.data.delta === 'string') {
            assistantBuffer += ev.data.delta
          } else if (typeof ev.data.content === 'string' && ev.data.content) {
            setTimeline((prev) => [
              ...prev,
              { id: `th-${Date.now()}-${Math.random()}`, kind: 'thinking', text: String(ev.data.content) },
            ])
          }
        } else if (ev.event === 'tool_call') {
          setTimeline((prev) => [
            ...prev,
            {
              id: `tc-${Date.now()}-${Math.random()}`,
              kind: 'tool_call',
              text: `${ev.data.name}(${JSON.stringify(ev.data.args ?? {})})`,
            },
          ])
        } else if (ev.event === 'tool_result') {
          setTimeline((prev) => [
            ...prev,
            {
              id: `tr-${Date.now()}-${Math.random()}`,
              kind: 'tool_result',
              text: String(ev.data.output ?? ''),
              meta: ev.data,
            },
          ])
        } else if (ev.event === 'approval_required') {
          setTimeline((prev) => [
            ...prev,
            {
              id: String(ev.data.approval_id ?? `ap-${Date.now()}`),
              kind: 'approval',
              text: String(ev.data.summary ?? 'Approval required'),
              meta: ev.data,
              resolved: false,
            },
          ])
        } else if (ev.event === 'done') {
          const finalContent =
            typeof ev.data.error === 'string'
              ? `Error: ${ev.data.error}`
              : String(ev.data.content || assistantBuffer || 'Done.')
          setTimeline((prev) => [
            ...prev,
            { id: `a-${Date.now()}`, kind: 'assistant', text: finalContent },
          ])
        }
      },
        { provider_id: pinnedProvider, model: pinnedModel },
      )
    } catch (err) {
      setTimeline((prev) => [
        ...prev,
        { id: `err-${Date.now()}`, kind: 'assistant', text: `Request failed: ${String(err)}` },
      ])
    } finally {
      setStreaming(false)
      void refreshAll()
    }
  }

  const handleApproval = async (entryId: string, approvalId: string, approved: boolean) => {
    await api.approve(approvalId, approved)
    setTimeline((prev) =>
      prev.map((item) => (item.id === entryId ? { ...item, resolved: true } : item)),
    )
    void refreshAll()
  }

  const handleOpenFile = async (path: string) => {
    const res = await api.readWorkspaceFile(path, 1, 200)
    setSelectedFile(res)
  }

  const handleOpenSkill = async (name: string) => {
    const res = await api.skillDetail(name)
    setSelectedSkill(res)
  }

  const handleBackup = async () => {
    const res = await api.runBackup()
    setBackupStatus(res.status === 'completed' ? `已备份: ${res.archive}` : `已跳过: ${res.reason}`)
  }

  const cardClass = dark
    ? 'bento-card rounded-[28px] border border-white/10 bg-zinc-900/65 text-zinc-100 shadow-xl'
    : 'bento-card rounded-[28px] border border-white/75 bg-white/70 text-zinc-800 shadow-[0_14px_40px_rgba(31,41,55,0.06)]'

  const innerSurface = dark ? 'bg-zinc-950/60 border-white/8' : 'bg-white/85 border-zinc-200/60'

  return (
    <div
      className={`min-h-screen w-full transition-colors duration-300 ${
        dark ? 'metis-mesh-dark text-zinc-100' : 'metis-mesh-light text-zinc-800'
      }`}
    >
      <div className="mx-auto flex min-h-screen max-w-[1440px] gap-6 p-5 md:p-8">
        {/* Left Floating Icon Rail */}
        <aside className="flex flex-col items-center justify-between py-2">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-zinc-900 text-white shadow-md dark:bg-white dark:text-zinc-900">
            <Sparkles className="h-5 w-5" />
          </div>

          <nav className="flex flex-col gap-3">
            {[
              { id: 'workbench' as const, icon: Home, label: 'Workbench' },
              { id: 'memory' as const, icon: Brain, label: 'Mnemosyne' },
              { id: 'skills' as const, icon: BookOpen, label: 'Skills & Models' },
            ].map((item) => {
              const Icon = item.icon
              const active = tab === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setTab(item.id)}
                  title={item.label}
                  className={`flex h-11 w-11 items-center justify-center rounded-full transition ${
                    active
                      ? 'bg-zinc-900 text-white shadow-md dark:bg-white dark:text-zinc-900'
                      : dark
                        ? 'bg-white/10 text-zinc-300 hover:bg-white/20'
                        : 'bg-white/80 text-zinc-600 shadow-sm hover:bg-white'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </button>
              )
            })}
          </nav>

          {/* Bottom-left Node Switcher (Image 4 style) */}
          <NodeSwitcher
            nodes={nodes}
            activeNodeId={activeNodeId}
            dark={dark}
            onActivate={async (id) => {
              await api.activateNode(id)
              await refreshAll()
            }}
            onAdd={async (node) => {
              await api.upsertNode(node)
              await refreshAll()
            }}
            onDelete={async (id) => {
              await api.deleteNode(id)
              await refreshAll()
            }}
          />
        </aside>

        {/* Main Workspace Canvas */}
        <main className="flex flex-1 flex-col gap-6">
          {/* Top Bar */}
          <header className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-tight">Metis Workbench</h1>
                <div
                  className={`flex items-center rounded-full p-1 text-xs font-medium ${
                    dark ? 'bg-white/10' : 'bg-white/70 shadow-sm'
                  }`}
                >
                  {(['workbench', 'memory', 'skills'] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setTab(t)}
                      className={`rounded-full px-3.5 py-1 capitalize transition ${
                        tab === t
                          ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-white'
                          : 'opacity-65 hover:opacity-100'
                      }`}
                    >
                      {t === 'skills' ? 'Skills & Models' : t}
                    </button>
                  ))}
                </div>
              </div>
              <p className="mt-1 text-sm opacity-65">
                Active node: <span className="font-medium">{activeNodeId}</span> ·{' '}
                {health?.workspace ?? '~/.metis/workspace'}
              </p>
            </div>

            <div className="flex items-center gap-5">
              {/* Light / Dark Toggle Pill */}
              <button
                type="button"
                onClick={() => setDark((d) => !d)}
                className={`flex items-center gap-1 rounded-full p-1 ${
                  dark ? 'bg-white/10' : 'bg-white/80 shadow-sm'
                }`}
                title="Toggle theme"
              >
                <span
                  className={`rounded-full p-1.5 ${
                    dark ? 'bg-zinc-900 text-white' : 'opacity-45'
                  }`}
                >
                  <Moon className="h-3.5 w-3.5" />
                </span>
                <span
                  className={`rounded-full p-1.5 ${
                    !dark ? 'bg-white text-amber-500 shadow-sm' : 'opacity-45'
                  }`}
                >
                  <Sun className="h-3.5 w-3.5" />
                </span>
              </button>

              <div className="hidden items-center gap-6 sm:flex">
                <div>
                  <div className="text-[11px] opacity-60">Skills</div>
                  <div className="text-xl font-semibold">{health?.skills_count ?? skills.length}</div>
                </div>
                <div>
                  <div className="text-[11px] opacity-60">Approvals</div>
                  <div className="text-xl font-semibold">{health?.pending_approvals ?? 0}</div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => void handleBackup()}
                className="flex items-center gap-2 rounded-full bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white shadow-md transition hover:scale-[1.02] dark:bg-white dark:text-zinc-900"
              >
                <Play className="h-3.5 w-3.5" />
                Run Backup
              </button>
            </div>
          </header>

          {backupStatus && (
            <div className="rounded-2xl bg-white/80 px-4 py-2 text-xs font-medium text-zinc-700 shadow-sm dark:bg-zinc-900/80 dark:text-zinc-200">
              {backupStatus}
            </div>
          )}

          {/* View 1: Workbench Bento */}
          {tab === 'workbench' && (
            <div className="grid flex-1 grid-cols-1 gap-6 lg:grid-cols-12">
              {/* Left Chat Card */}
              <section className={`${cardClass} flex h-[620px] flex-col p-5 lg:col-span-5`}>
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {[
                      { id: 'chat' as const, icon: MessageSquare, label: 'Chat' },
                      { id: 'approvals' as const, icon: ShieldAlert, label: 'Approvals' },
                      { id: 'cron' as const, icon: Clock, label: 'Cron' },
                    ].map((st) => {
                      const Icon = st.icon
                      const active = chatTab === st.id
                      return (
                        <button
                          key={st.id}
                          type="button"
                          onClick={() => setChatTab(st.id)}
                          className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                            active
                              ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900'
                              : 'bg-white/60 text-zinc-600 hover:bg-white dark:bg-white/10 dark:text-zinc-300'
                          }`}
                        >
                          <Icon className="h-3.5 w-3.5" />
                          {st.label}
                        </button>
                      )
                    })}
                  </div>
                  <span className="rounded-full bg-emerald-400/20 px-2.5 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
                    {activeNodeId}
                  </span>
                </div>

                {chatTab === 'chat' && (
                  <>
                    <div
                      className={`flex-1 space-y-3 overflow-y-auto rounded-3xl border p-4 ${innerSurface}`}
                    >
                      {timeline.map((item) => {
                        if (item.kind === 'approval') {
                          const apId = String(item.meta?.approval_id ?? item.id)
                          return (
                            <div
                              key={item.id}
                              className="rounded-2xl border border-amber-400/40 bg-amber-50/90 p-3 text-xs text-amber-950 dark:bg-amber-950/40 dark:text-amber-100"
                            >
                              <div className="font-semibold">人工审批请求: {item.text}</div>
                              <pre className="mt-1 overflow-x-auto text-[11px] opacity-80">
                                {JSON.stringify(item.meta?.details ?? {}, null, 2)}
                              </pre>
                              {!item.resolved ? (
                                <div className="mt-2 flex gap-2">
                                  <button
                                    type="button"
                                    onClick={() => void handleApproval(item.id, apId, true)}
                                    className="flex items-center gap-1 rounded-full bg-emerald-600 px-3 py-1 text-white"
                                  >
                                    <CheckCircle2 className="h-3 w-3" /> 批准
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => void handleApproval(item.id, apId, false)}
                                    className="flex items-center gap-1 rounded-full bg-rose-600 px-3 py-1 text-white"
                                  >
                                    <XCircle className="h-3 w-3" /> 拒绝
                                  </button>
                                </div>
                              ) : (
                                <div className="mt-1 text-[11px] font-medium opacity-70">已处理</div>
                              )}
                            </div>
                          )
                        }

                        if (item.kind === 'tool_call' || item.kind === 'tool_result') {
                          return (
                            <div
                              key={item.id}
                              className="rounded-2xl bg-zinc-500/10 px-3 py-2 font-mono text-[11px]"
                            >
                              <span className="font-semibold uppercase opacity-60">
                                {item.kind}:{' '}
                              </span>
                              <span className="break-all">{item.text}</span>
                            </div>
                          )
                        }

                        const isUser = item.kind === 'user'
                        return (
                          <div
                            key={item.id}
                            className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
                          >
                            <div
                              className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm whitespace-pre-wrap ${
                                isUser
                                  ? 'bg-zinc-900 text-white dark:bg-emerald-400 dark:text-zinc-950'
                                  : dark
                                    ? 'bg-zinc-800 text-zinc-100'
                                    : 'bg-zinc-100 text-zinc-800'
                              }`}
                            >
                              {item.text}
                            </div>
                          </div>
                        )
                      })}
                    </div>

                    <form
                      onSubmit={(e) => void handleSend(e)}
                      className={`mt-3 flex items-center gap-2 rounded-full border px-3 py-1.5 ${innerSurface}`}
                    >
                      <select
                        value={selectedModelKey}
                        onChange={(e) => setSelectedModelKey(e.target.value)}
                        title="切换模型或自动路由"
                        className="max-w-[150px] truncate rounded-full bg-zinc-500/10 px-2.5 py-1 text-[11px] font-medium outline-none"
                      >
                        <option value="auto">Auto (Router)</option>
                        {discoveredModels.map((item) => {
                          const key = `${item.provider_id}::${item.model}`
                          return (
                            <option key={key} value={key}>
                              {item.model} ({item.provider_id})
                            </option>
                          )
                        })}
                      </select>
                      <input
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        placeholder={`向 Metis 发送指令（${activeNodeId}）...`}
                        className="flex-1 bg-transparent text-sm outline-none"
                      />
                      <button
                        type="submit"
                        disabled={streaming}
                        className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900 text-white disabled:opacity-40 dark:bg-white dark:text-zinc-900"
                      >
                        <Send className="h-3.5 w-3.5" />
                      </button>
                    </form>
                  </>
                )}

                {chatTab === 'approvals' && (
                  <div className={`flex-1 rounded-3xl border p-4 text-sm ${innerSurface}`}>
                    当前挂起审批数：{health?.pending_approvals ?? 0}。当 Agent 触发文件写入、敏感
                    Shell 或 `git push` 时，审批卡片会直接出现在 Chat 流中。
                  </div>
                )}

                {chatTab === 'cron' && (
                  <div className={`flex-1 space-y-2 rounded-3xl border p-4 text-sm ${innerSurface}`}>
                    <div>Cron 心跳：{cronInfo.enabled ? '已启用' : '未启用'}</div>
                    <div className="text-xs opacity-70">
                      已注册任务：{cronInfo.jobs.length ? cronInfo.jobs.join(', ') : '暂无'}
                    </div>
                  </div>
                )}
              </section>

              {/* Right Column: Overview + Workspace Explorer */}
              <div className="flex flex-col gap-6 lg:col-span-7">
                {/* Top-Right Status Bento */}
                <section className={`${cardClass} p-5`}>
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <h2 className="text-base font-semibold">Runtime & Nodes Overview</h2>
                      <p className="text-xs opacity-60">Hephaestus · NodeRouter · Mnemosyne</p>
                    </div>
                    <Activity className="h-4 w-4 opacity-50" />
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    <div className={`rounded-2xl border p-3.5 ${innerSurface}`}>
                      <div className="flex items-center gap-2 text-xs opacity-60">
                        <Cpu className="h-3.5 w-3.5" /> Active Node
                      </div>
                      <div className="mt-1.5 text-lg font-semibold">{activeNodeId}</div>
                      <div className="text-[11px] opacity-60">
                        {nodes.find((n) => n.id === activeNodeId)?.kind ?? 'local'}
                      </div>
                    </div>

                    <div className={`rounded-2xl border p-3.5 ${innerSurface}`}>
                      <div className="flex items-center gap-2 text-xs opacity-60">
                        <HardDrive className="h-3.5 w-3.5" /> Workspace Files
                      </div>
                      <div className="mt-1.5 text-lg font-semibold">{files.length}</div>
                      <div className="text-[11px] opacity-60">Sandboxed guard active</div>
                    </div>

                    <div className={`rounded-2xl border p-3.5 ${innerSurface}`}>
                      <div className="flex items-center gap-2 text-xs opacity-60">
                        <Wrench className="h-3.5 w-3.5" /> Telegram / Cron
                      </div>
                      <div className="mt-1.5 text-lg font-semibold">
                        {health?.cron_enabled ? 'ON' : 'OFF'}
                      </div>
                      <div className="text-[11px] opacity-60">
                        Telegram: {health?.telegram_enabled ? 'ON' : 'OFF'}
                      </div>
                    </div>
                  </div>
                </section>

                {/* Bottom-Right Workspace Explorer */}
                <section className={`${cardClass} flex flex-1 flex-col p-5`}>
                  <div className="mb-3 flex items-center justify-between">
                    <h2 className="text-base font-semibold">Workspace Explorer</h2>
                    <FileCode2 className="h-4 w-4 opacity-50" />
                  </div>

                  <div className="grid flex-1 grid-cols-1 gap-4 md:grid-cols-5">
                    <div
                      className={`max-h-[300px] overflow-y-auto rounded-2xl border p-2.5 md:col-span-2 ${innerSurface}`}
                    >
                      {files.length === 0 ? (
                        <div className="p-3 text-xs opacity-60">工作区暂无文件</div>
                      ) : (
                        files.map((f) => (
                          <button
                            key={f}
                            type="button"
                            onClick={() => void handleOpenFile(f)}
                            className={`block w-full truncate rounded-xl px-2.5 py-1.5 text-left text-xs transition ${
                              selectedFile?.path === f
                                ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900'
                                : 'hover:bg-zinc-500/10'
                            }`}
                          >
                            {f}
                          </button>
                        ))
                      )}
                    </div>

                    <pre
                      className={`max-h-[300px] overflow-auto rounded-2xl border p-3 font-mono text-xs md:col-span-3 ${innerSurface}`}
                    >
                      {selectedFile ? selectedFile.content : '点击左侧文件查看带行号内容'}
                    </pre>
                  </div>
                </section>
              </div>
            </div>
          )}

          {/* View 2: Mnemosyne Memory */}
          {tab === 'memory' && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <section className={`${cardClass} p-6`}>
                <h2 className="text-lg font-semibold">Mnemosyne 图谱检索</h2>
                <p className="mt-1 text-xs opacity-60">LightRAG + RAG-Anything（Qwen 云端 API）</p>
                <div className="mt-4 flex gap-2">
                  {(['hybrid', 'local', 'global'] as const).map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setMemMode(m)}
                      className={`rounded-full px-3 py-1 text-xs capitalize ${
                        memMode === m
                          ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900'
                          : 'bg-zinc-500/10'
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
                <div className="mt-3 flex gap-2">
                  <input
                    value={memQuestion}
                    onChange={(e) => setMemQuestion(e.target.value)}
                    placeholder="输入检索问题..."
                    className={`flex-1 rounded-2xl border px-3.5 py-2 text-sm outline-none ${innerSurface}`}
                  />
                  <button
                    type="button"
                    onClick={async () => {
                      const res = await api.queryMemory(memQuestion, memMode)
                      setMemAnswer(res.answer)
                    }}
                    className="rounded-2xl bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-white dark:text-zinc-900"
                  >
                    检索
                  </button>
                </div>
                {memAnswer && (
                  <div className={`mt-4 rounded-2xl border p-4 text-sm whitespace-pre-wrap ${innerSurface}`}>
                    {memAnswer}
                  </div>
                )}
              </section>

              <section className={`${cardClass} p-6`}>
                <h2 className="text-lg font-semibold">写入知识片段</h2>
                <textarea
                  value={memIngest}
                  onChange={(e) => setMemIngest(e.target.value)}
                  rows={6}
                  placeholder="粘贴文本笔记写入 Mnemosyne 图谱..."
                  className={`mt-4 w-full rounded-2xl border p-3.5 text-sm outline-none ${innerSurface}`}
                />
                <button
                  type="button"
                  onClick={async () => {
                    if (!memIngest.trim()) return
                    await api.ingestMemory(memIngest)
                    setMemIngest('')
                  }}
                  className="mt-3 rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white dark:bg-white dark:text-zinc-900"
                >
                  写入图谱
                </button>
              </section>
            </div>
          )}

          {/* View 3: Skills & Models */}
          {tab === 'skills' && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <section className={`${cardClass} p-6`}>
                <h2 className="text-lg font-semibold">渐进式 SKILL.md</h2>
                <div className="mt-4 space-y-2">
                  {skills.map((s) => (
                    <button
                      key={s.name}
                      type="button"
                      onClick={() => void handleOpenSkill(s.name)}
                      className={`block w-full rounded-2xl border p-3 text-left transition hover:scale-[1.01] ${innerSurface}`}
                    >
                      <div className="text-sm font-semibold">{s.name}</div>
                      <div className="mt-0.5 text-xs opacity-65">{s.description}</div>
                    </button>
                  ))}
                </div>
                {selectedSkill && (
                  <pre className={`mt-4 max-h-64 overflow-auto rounded-2xl border p-3 text-xs ${innerSurface}`}>
                    {selectedSkill.content}
                  </pre>
                )}
              </section>

              <section className={`${cardClass} p-6`}>
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">模型注册表 (~/.metis/models.json)</h2>
                  <button
                    type="button"
                    onClick={() => void refreshAll()}
                    className="rounded-full bg-zinc-900 px-3 py-1 text-xs font-medium text-white dark:bg-white dark:text-zinc-900"
                  >
                    拉取可用模型 ({discoveredModels.length})
                  </button>
                </div>
                <div className="mt-4 space-y-3">
                  {models &&
                    Object.entries(models.roles).map(([roleName, route]) => (
                      <div key={roleName} className={`rounded-2xl border p-3 text-xs ${innerSurface}`}>
                        <div className="font-semibold">{roleName}</div>
                        <div className="mt-1 opacity-75">
                          provider: <span className="font-mono">{route.provider_id}</span> · model:{' '}
                          <span className="font-mono">{route.model ?? '(default)'}</span>
                        </div>
                      </div>
                    ))}
                </div>
              </section>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
