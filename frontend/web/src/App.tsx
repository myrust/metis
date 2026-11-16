import { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  BarChart3,
  BookOpen,
  Brain,
  Check,
  CheckCircle2,
  Clock,
  FileCode2,
  FolderGit2,
  Home,
  Lightbulb,
  MessageSquare,
  Moon,
  Play,
  Plus,
  Send,
  Settings,
  ShieldAlert,
  Sparkles,
  Sun,
  Terminal,
  Trash2,
  Upload,
  X,
  XCircle,
} from 'lucide-react'
import {
  api,
  streamChat,
  type CronDetail,
  type CustomChartItem,
  type HealthInfo,
  type IdeaItem,
  type ModelsPayload,
  type NodeItem,
  type PendingApprovalItem,
  type ProjectItem,
  type SessionItem,
  type SkillItem,
  type SystemMetrics,
  type TodoItem,
  type UsageSummary,
} from './api/client'
import { NodeSwitcher } from './components/NodeSwitcher'
import { CustomChartSvg, FluxTokenPanel, RadialGauge } from './components/RadialGauge'

type NavTab = 'workspace' | 'projects' | 'library' | 'automations' | 'monitor' | 'skills'
type RightSandboxTab = 'editor' | 'terminal'
type SettingsTab = 'llm' | 'security'

interface TimelineEntry {
  id: string
  kind: 'user' | 'thinking' | 'tool_call' | 'tool_result' | 'approval' | 'assistant'
  text: string
  meta?: Record<string, unknown>
  resolved?: boolean
}

const SLASH_COMMANDS = [
  { cmd: '/system-health', desc: '运行本机健康检查 (psutil)' },
  { cmd: '/workspace-backup', desc: '执行工作区与图谱增量备份' },
  { cmd: '/deepcode-plan-verify', desc: '按 DeepCode 规范规划与验证' },
  { cmd: 'git status -s', desc: '查看当前项目 Git 状态' },
]

export default function App() {
  const [dark, setDark] = useState(false)
  const [tab, setTab] = useState<NavTab>('workspace')
  const [sandboxTab, setSandboxTab] = useState<RightSandboxTab>('editor')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsTab, setSettingsTab] = useState<SettingsTab>('llm')

  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [nodes, setNodes] = useState<NodeItem[]>([])
  const [activeNodeId, setActiveNodeId] = useState('local')
  const [skills, setSkills] = useState<SkillItem[]>([])
  const [selectedSkill, setSelectedSkill] = useState<{ name: string; content: string } | null>(null)
  const [files, setFiles] = useState<string[]>([])
  const [selectedFile, setSelectedFile] = useState<{ path: string; content: string } | null>(null)
  const [cronInfo, setCronInfo] = useState<{
    enabled: boolean
    jobs: string[]
    details: CronDetail[]
  }>({ enabled: false, jobs: [], details: [] })
  const [models, setModels] = useState<ModelsPayload | null>(null)
  const [discoveredModels, setDiscoveredModels] = useState<
    Array<{ provider_id: string; model: string }>
  >([])
  const [selectedModelKey, setSelectedModelKey] = useState<string>('auto')
  const [backupStatus, setBackupStatus] = useState<string>('')

  const [metrics, setMetrics] = useState<SystemMetrics | null>(null)
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [todos, setTodos] = useState<TodoItem[]>([])
  const [newTodo, setNewTodo] = useState('')
  const [ideas, setIdeas] = useState<IdeaItem[]>([])
  const [ideaTitle, setIdeaTitle] = useState('')
  const [ideaContent, setIdeaContent] = useState('')
  const [charts, setCharts] = useState<CustomChartItem[]>([])
  const [chartTitle, setChartTitle] = useState('')
  const [chartType, setChartType] = useState<'bar' | 'line' | 'ring'>('bar')
  const [chartLabels, setChartLabels] = useState('Mon,Tue,Wed,Thu')
  const [chartValues, setChartValues] = useState('12,19,8,24')

  const [cronName, setCronName] = useState('')
  const [cronExpr, setCronExpr] = useState('0 * * * *')
  const [cronPrompt, setCronPrompt] = useState('')

  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [projects, setProjects] = useState<ProjectItem[]>([])
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const [projName, setProjName] = useState('')
  const [projPath, setProjPath] = useState('')
  const [projNodeId, setProjNodeId] = useState('local')
  const [pendingApprovals, setPendingApprovals] = useState<PendingApprovalItem[]>([])

  const [prompt, setPrompt] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [timeline, setTimeline] = useState<TimelineEntry[]>([
    {
      id: 'welcome',
      kind: 'assistant',
      text: '你好，我是 Metis。输入 `/` 唤起快捷指令，或直接下达任务。',
    },
  ])

  const [memQuestion, setMemQuestion] = useState('')
  const [memMode, setMemMode] = useState<'hybrid' | 'local' | 'global'>('hybrid')
  const [memAnswer, setMemAnswer] = useState('')
  const [memIngest, setMemIngest] = useState('')
  const [memStats, setMemStats] = useState<{
    graph_dir: string
    files_count: number
    files: string[]
  } | null>(null)
  const [uploadStatus, setUploadStatus] = useState('')

  const refreshAll = useCallback(async () => {
    try {
      const [h, n, s, f, c, m, d, sys, u, td, idList, chList, ms, sessRes, projRes, apRes] =
        await Promise.all([
          api.health(),
          api.nodes(),
          api.skills(),
          api.workspaceFiles(),
          api.cron(),
          api.models(),
          api.discoverModels(),
          api.systemMetrics(),
          api.usageSummary(7),
          api.todos(),
          api.ideas(),
          api.charts(),
          api.memoryStats(),
          api.sessions(),
          api.projects(),
          api.pendingApprovals(),
        ])
      setHealth(h)
      setNodes(n.nodes)
      setActiveNodeId(n.active_node_id)
      setSkills(s.skills)
      setFiles(f.files)
      setCronInfo(c)
      setModels(m)
      setDiscoveredModels(d.models)
      setMetrics(sys)
      setUsage(u)
      setTodos(td.todos)
      setIdeas(idList.ideas)
      setCharts(chList.charts)
      setMemStats(ms)
      setSessions(sessRes.sessions)
      setProjects(projRes.projects)
      setPendingApprovals(apRes.pending)
    } catch {
      // Backend might not be running during standalone preview.
    }
  }, [])

  useEffect(() => {
    void refreshAll()
    const timer = window.setInterval(() => {
      void api.systemMetrics().then(setMetrics).catch(() => {})
    }, 12000)
    return () => window.clearInterval(timer)
  }, [refreshAll])

  const handleNewChat = async () => {
    const created = await api.createSession('新对话', activeProjectId)
    setActiveSessionId(created.id)
    setTimeline([
      {
        id: 'welcome',
        kind: 'assistant',
        text: '新会话已就绪，输入 `/` 可唤起快捷技能或指令。',
      },
    ])
    await refreshAll()
  }

  const handleSelectSession = (sessionId: string) => {
    setActiveSessionId(sessionId)
    const found = sessions.find((s) => s.id === sessionId)
    if (found && found.messages.length > 0) {
      setTimeline(found.messages)
    } else {
      setTimeline([{ id: 'welcome', kind: 'assistant', text: '会话已加载。' }])
    }
  }

  const sendPrompt = async (rawText: string) => {
    const text = rawText.trim()
    if (!text || streaming) return
    setPrompt('')
    setStreaming(true)

    let sid = activeSessionId
    if (!sid) {
      try {
        const created = await api.createSession(text.slice(0, 28), activeProjectId)
        sid = created.id
        setActiveSessionId(sid)
      } catch {
        sid = null
      }
    }

    const userEntry: TimelineEntry = { id: `u-${Date.now()}`, kind: 'user', text }
    setTimeline((prev) => [...prev, userEntry])
    if (sid) void api.appendSessionMessage(sid, userEntry).catch(() => {})

    const [pinnedProvider, pinnedModel] =
      selectedModelKey === 'auto' ? [undefined, undefined] : selectedModelKey.split('::')

    const activeProj = projects.find((p) => p.id === activeProjectId)
    const projectSystemPrompt = activeProj
      ? `Active Project: ${activeProj.name} (node_id=${activeProj.node_id}, path=${activeProj.path}). Prefer operating inside this project.`
      : undefined

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
                {
                  id: `th-${Date.now()}-${Math.random()}`,
                  kind: 'thinking',
                  text: String(ev.data.content),
                },
              ])
            }
          } else if (ev.event === 'tool_call') {
            const entry: TimelineEntry = {
              id: `tc-${Date.now()}-${Math.random()}`,
              kind: 'tool_call',
              text: `${ev.data.name}(${JSON.stringify(ev.data.args ?? {})})`,
              meta: ev.data,
            }
            setTimeline((prev) => [...prev, entry])
            if (sid) void api.appendSessionMessage(sid, entry).catch(() => {})
          } else if (ev.event === 'tool_result') {
            const entry: TimelineEntry = {
              id: `tr-${Date.now()}-${Math.random()}`,
              kind: 'tool_result',
              text: String(ev.data.output ?? ''),
              meta: ev.data,
            }
            setTimeline((prev) => [...prev, entry])
            if (sid) void api.appendSessionMessage(sid, entry).catch(() => {})
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
            const entry: TimelineEntry = {
              id: `a-${Date.now()}`,
              kind: 'assistant',
              text: finalContent,
            }
            setTimeline((prev) => [...prev, entry])
            if (sid) void api.appendSessionMessage(sid, entry).catch(() => {})
          }
        },
        { provider_id: pinnedProvider, model: pinnedModel, system_prompt: projectSystemPrompt },
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

  const handleBackup = async () => {
    const res = await api.runBackup()
    setBackupStatus(res.status === 'completed' ? `已备份: ${res.archive}` : `已跳过: ${res.reason}`)
  }

  const handleUpdateRoleModel = async (roleName: string, providerId: string, model: string) => {
    if (!models) return
    const updatedRoles = {
      ...models.roles,
      [roleName]: { ...models.roles[roleName], provider_id: providerId, model },
    }
    const res = await api.updateModels({ roles: updatedRoles })
    setModels(res)
  }

  const cardClass = dark
    ? 'bento-card rounded-[28px] border border-white/10 bg-zinc-900/65 text-zinc-100 shadow-xl'
    : 'bento-card rounded-[28px] border border-white/75 bg-white/72 text-zinc-800 shadow-[0_14px_40px_rgba(31,41,55,0.06)]'

  const innerSurface = dark ? 'bg-zinc-950/60 border-white/8' : 'bg-white/85 border-zinc-200/60'

  const terminalEntries = timeline.filter(
    (t) => t.kind === 'tool_call' || t.kind === 'tool_result',
  )
  const showSlashMenu = prompt.startsWith('/')

  return (
    <div
      className={`min-h-screen w-full transition-colors duration-300 ${
        dark ? 'metis-mesh-dark text-zinc-100' : 'metis-mesh-light text-zinc-800'
      }`}
    >
      <div className="mx-auto flex min-h-screen max-w-[1480px] gap-6 p-5 md:p-7">
        {/* Left Minimal Icon Rail */}
        <aside className="flex flex-col items-center justify-between py-2">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-zinc-900 text-white shadow-md dark:bg-white dark:text-zinc-900">
            <Sparkles className="h-5 w-5" />
          </div>

          <nav className="flex flex-col gap-3">
            {[
              { id: 'workspace' as const, icon: Home, label: '工作台 (对话与代码)' },
              { id: 'projects' as const, icon: FolderGit2, label: '项目、待办与灵感' },
              { id: 'library' as const, icon: Brain, label: '资料库 (Mnemosyne)' },
              { id: 'automations' as const, icon: Clock, label: '定时任务 (Cron)' },
              { id: 'monitor' as const, icon: Activity, label: '负载与 Token 监控' },
              { id: 'skills' as const, icon: BookOpen, label: '技能 (SKILL.md)' },
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

          <div className="flex flex-col items-center gap-3">
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
            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              title="全局设置"
              className={`flex h-11 w-11 items-center justify-center rounded-full transition ${
                dark
                  ? 'bg-white/10 text-zinc-200 hover:bg-white/20'
                  : 'bg-white/85 text-zinc-700 shadow-sm hover:bg-white'
              }`}
            >
              <Settings className="h-4 w-4" />
            </button>
          </div>
        </aside>

        {/* Main Canvas */}
        <main className="flex flex-1 flex-col gap-5">
          {/* Clean Top Bar */}
          <header className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">Metis</h1>
              <span className="rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                {activeNodeId}
              </span>
              {activeProjectId && (
                <span className="rounded-full bg-indigo-500/15 px-3 py-1 text-xs font-medium text-indigo-700 dark:text-indigo-300">
                  {projects.find((p) => p.id === activeProjectId)?.name}
                </span>
              )}
              {pendingApprovals.length > 0 && (
                <span className="flex items-center gap-1 rounded-full bg-amber-500/20 px-3 py-1 text-xs font-medium text-amber-700 dark:text-amber-300">
                  <ShieldAlert className="h-3.5 w-3.5" /> {pendingApprovals.length} 待审批
                </span>
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setDark((d) => !d)}
                className={`flex items-center gap-1 rounded-full p-1 ${
                  dark ? 'bg-white/10' : 'bg-white/80 shadow-sm'
                }`}
                title="Toggle theme"
              >
                <span className={`rounded-full p-1.5 ${dark ? 'bg-zinc-900 text-white' : 'opacity-45'}`}>
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
            </div>
          </header>

          {backupStatus && (
            <div className="rounded-2xl bg-white/80 px-4 py-2 text-xs font-medium text-zinc-700 shadow-sm dark:bg-zinc-900/80 dark:text-zinc-200">
              {backupStatus}
            </div>
          )}

          {/* 1. Focused Workspace (Clean 2-Column: Chat + Code/Terminal) */}
          {tab === 'workspace' && (
            <div className="grid flex-1 grid-cols-1 gap-6 lg:grid-cols-12">
              {/* Left: Focused Chat */}
              <section className={`${cardClass} flex h-[720px] flex-col p-5 lg:col-span-6`}>
                <div className="mb-3 flex items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => void handleNewChat()}
                    className="flex shrink-0 items-center gap-1.5 rounded-full bg-zinc-900 px-3.5 py-1.5 text-xs font-medium text-white dark:bg-white dark:text-zinc-900"
                  >
                    <Plus className="h-3.5 w-3.5" /> 新对话
                  </button>
                  <select
                    value={activeSessionId ?? ''}
                    onChange={(e) => handleSelectSession(e.target.value)}
                    className="min-w-0 flex-1 truncate rounded-full bg-zinc-500/10 px-3 py-1.5 text-xs outline-none"
                  >
                    <option value="">临时会话</option>
                    {sessions.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.title}
                      </option>
                    ))}
                  </select>
                </div>

                <div className={`flex-1 space-y-3 overflow-y-auto rounded-3xl border p-4 ${innerSurface}`}>
                  {timeline.map((item) => {
                    if (item.kind === 'approval') {
                      const apId = String(item.meta?.approval_id ?? item.id)
                      return (
                        <div
                          key={item.id}
                          className="rounded-2xl border border-amber-400/40 bg-amber-50/90 p-3.5 text-xs text-amber-950 dark:bg-amber-950/40 dark:text-amber-100"
                        >
                          <div className="font-semibold">安全审批: {item.text}</div>
                          <pre className="mt-1.5 overflow-x-auto text-[11px] opacity-80">
                            {JSON.stringify(item.meta?.details ?? {}, null, 2)}
                          </pre>
                          {!item.resolved ? (
                            <div className="mt-2.5 flex gap-2">
                              <button
                                type="button"
                                onClick={() => void handleApproval(item.id, apId, true)}
                                className="flex items-center gap-1 rounded-full bg-zinc-900 px-3.5 py-1 text-white dark:bg-emerald-500"
                              >
                                <CheckCircle2 className="h-3 w-3" /> 批准执行
                              </button>
                              <button
                                type="button"
                                onClick={() => void handleApproval(item.id, apId, false)}
                                className="flex items-center gap-1 rounded-full border border-zinc-400/40 px-3.5 py-1"
                              >
                                <XCircle className="h-3 w-3" /> 拒绝
                              </button>
                            </div>
                          ) : (
                            <div className="mt-1.5 text-[11px] opacity-70">已处理</div>
                          )}
                        </div>
                      )
                    }

                    if (item.kind === 'tool_call' || item.kind === 'tool_result') {
                      const ok = item.meta?.ok !== false
                      return (
                        <div
                          key={item.id}
                          className={`rounded-2xl border px-3.5 py-2 font-mono text-[11px] ${
                            item.kind === 'tool_call'
                              ? 'border-sky-400/30 bg-sky-500/8'
                              : ok
                                ? 'border-emerald-400/30 bg-emerald-500/8'
                                : 'border-rose-400/30 bg-rose-500/8'
                          }`}
                        >
                          <span className="font-semibold uppercase opacity-65">{item.kind}: </span>
                          <span className="break-all">{item.text}</span>
                        </div>
                      )
                    }

                    const isUser = item.kind === 'user'
                    return (
                      <div key={item.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                        <div
                          className={`max-w-[84%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
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

                {/* Input + Slash Menu */}
                <div className="relative mt-3">
                  {showSlashMenu && (
                    <div
                      className={`bento-card absolute bottom-14 left-0 z-30 w-full rounded-2xl border p-2 shadow-xl ${
                        dark ? 'border-white/10 bg-zinc-900/95' : 'border-white bg-white/95'
                      }`}
                    >
                      {SLASH_COMMANDS.map((item) => (
                        <button
                          key={item.cmd}
                          type="button"
                          onClick={() => setPrompt(item.cmd + ' ')}
                          className="flex w-full items-center justify-between rounded-xl px-3 py-1.5 text-left text-xs hover:bg-zinc-500/10"
                        >
                          <span className="font-mono font-semibold">{item.cmd}</span>
                          <span className="opacity-65">{item.desc}</span>
                        </button>
                      ))}
                    </div>
                  )}

                  <form
                    onSubmit={(e) => {
                      e.preventDefault()
                      void sendPrompt(prompt)
                    }}
                    className={`flex items-center gap-2 rounded-full border px-3 py-1.5 ${innerSurface}`}
                  >
                    <select
                      value={selectedModelKey}
                      onChange={(e) => setSelectedModelKey(e.target.value)}
                      className="max-w-[140px] truncate rounded-full bg-zinc-500/10 px-2.5 py-1 text-[11px] font-medium outline-none"
                    >
                      <option value="auto">Auto (Router)</option>
                      {discoveredModels.map((item) => {
                        const key = `${item.provider_id}::${item.model}`
                        return (
                          <option key={key} value={key}>
                            {item.model}
                          </option>
                        )
                      })}
                    </select>
                    <input
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="输入消息或 / 唤起技能..."
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
                </div>
              </section>

              {/* Right: Focused Sandbox Workspace (Only Code & Terminal) */}
              <section className={`${cardClass} flex h-[720px] flex-col p-5 lg:col-span-6`}>
                <div className="mb-3 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setSandboxTab('editor')}
                    className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium transition ${
                      sandboxTab === 'editor'
                        ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900'
                        : 'bg-zinc-500/10 hover:bg-zinc-500/20'
                    }`}
                  >
                    <FileCode2 className="h-3.5 w-3.5" /> 工作区文件 ({files.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setSandboxTab('terminal')}
                    className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium transition ${
                      sandboxTab === 'terminal'
                        ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900'
                        : 'bg-zinc-500/10 hover:bg-zinc-500/20'
                    }`}
                  >
                    <Terminal className="h-3.5 w-3.5" /> 执行输出 ({terminalEntries.length})
                  </button>
                </div>

                {sandboxTab === 'editor' ? (
                  <div className="grid flex-1 grid-cols-1 gap-4 overflow-hidden md:grid-cols-5">
                    <div className={`overflow-y-auto rounded-3xl border p-3 md:col-span-2 ${innerSurface}`}>
                      {files.length === 0 ? (
                        <div className="p-2 text-xs opacity-60">工作区暂无文件</div>
                      ) : (
                        files.map((f) => (
                          <button
                            key={f}
                            type="button"
                            onClick={async () =>
                              setSelectedFile(await api.readWorkspaceFile(f, 1, 200))
                            }
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
                      className={`overflow-auto rounded-3xl border p-4 font-mono text-xs md:col-span-3 ${innerSurface}`}
                    >
                      {selectedFile ? selectedFile.content : '选择左侧文件查看内容'}
                    </pre>
                  </div>
                ) : (
                  <div className={`flex-1 space-y-2.5 overflow-y-auto rounded-3xl border p-4 font-mono text-xs ${innerSurface}`}>
                    {terminalEntries.length === 0 ? (
                      <div className="opacity-60">Agent 执行的工具调用与输出会显示在这里。</div>
                    ) : (
                      terminalEntries.map((item) => (
                        <div key={item.id} className="rounded-2xl bg-zinc-500/10 p-3">
                          <div className="text-[10px] font-semibold uppercase opacity-60">
                            {item.kind}
                          </div>
                          <div className="mt-1 whitespace-pre-wrap break-all">{item.text}</div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </section>
            </div>
          )}

          {/* 2. Projects, Todos & Ideas (Dedicated Spacious Page) */}
          {tab === 'projects' && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              {/* Projects */}
              <section className={`${cardClass} p-6`}>
                <h2 className="text-base font-semibold">项目管理</h2>
                <p className="mt-1 text-xs opacity-60">自动同步到节点 allowed_paths</p>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault()
                    if (!projName.trim() || !projPath.trim()) return
                    await api.addProject(projName.trim(), projPath.trim(), projNodeId)
                    setProjName('')
                    setProjPath('')
                    await refreshAll()
                  }}
                  className="mt-4 space-y-2"
                >
                  <div className="flex gap-2">
                    <input
                      value={projName}
                      onChange={(e) => setProjName(e.target.value)}
                      placeholder="项目名"
                      className={`w-1/2 rounded-2xl border px-3 py-2 text-xs outline-none ${innerSurface}`}
                    />
                    <select
                      value={projNodeId}
                      onChange={(e) => setProjNodeId(e.target.value)}
                      className={`w-1/2 rounded-2xl border px-3 py-2 text-xs outline-none ${innerSurface}`}
                    >
                      {nodes.map((n) => (
                        <option key={n.id} value={n.id}>
                          {n.id}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex gap-2">
                    <input
                      value={projPath}
                      onChange={(e) => setProjPath(e.target.value)}
                      placeholder="项目路径..."
                      className={`flex-1 rounded-2xl border px-3 py-2 text-xs outline-none ${innerSurface}`}
                    />
                    <button
                      type="submit"
                      className="rounded-2xl bg-zinc-900 px-4 py-2 text-xs font-medium text-white dark:bg-white dark:text-zinc-900"
                    >
                      添加
                    </button>
                  </div>
                </form>
                <div className="mt-4 space-y-2">
                  {projects.map((proj) => {
                    const bound = activeProjectId === proj.id
                    return (
                      <div
                        key={proj.id}
                        className={`flex items-center justify-between rounded-2xl border p-3 text-xs ${innerSurface}`}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="font-semibold">
                            {proj.name}{' '}
                            <span className="font-mono text-[10px] opacity-60">({proj.node_id})</span>
                          </div>
                          <div className="truncate font-mono text-[10px] opacity-65">{proj.path}</div>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => setActiveProjectId(bound ? null : proj.id)}
                            className={`rounded-full px-2.5 py-1 text-[11px] ${
                              bound ? 'bg-emerald-500 text-white' : 'bg-zinc-500/15'
                            }`}
                          >
                            {bound ? '已绑定' : '绑定'}
                          </button>
                          <button
                            type="button"
                            onClick={async () => {
                              await api.deleteProject(proj.id)
                              if (bound) setActiveProjectId(null)
                              await refreshAll()
                            }}
                            className="text-rose-500 opacity-60 hover:opacity-100"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </section>

              {/* Todos */}
              <section className={`${cardClass} p-6`}>
                <h2 className="text-base font-semibold">To-do List</h2>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault()
                    if (!newTodo.trim()) return
                    await api.addTodo(newTodo.trim())
                    setNewTodo('')
                    await refreshAll()
                  }}
                  className="mt-4 flex gap-2"
                >
                  <input
                    value={newTodo}
                    onChange={(e) => setNewTodo(e.target.value)}
                    placeholder="添加待办..."
                    className={`flex-1 rounded-2xl border px-3.5 py-2 text-xs outline-none ${innerSurface}`}
                  />
                  <button
                    type="submit"
                    className="rounded-2xl bg-zinc-900 px-4 py-2 text-xs font-medium text-white dark:bg-white dark:text-zinc-900"
                  >
                    添加
                  </button>
                </form>
                <div className="mt-4 space-y-2">
                  {todos.map((td) => (
                    <div
                      key={td.id}
                      className={`flex items-center justify-between rounded-2xl border p-3 ${innerSurface}`}
                    >
                      <button
                        type="button"
                        onClick={async () => {
                          await api.toggleTodo(td.id)
                          await refreshAll()
                        }}
                        className="flex items-center gap-2.5 text-left text-xs"
                      >
                        <span
                          className={`flex h-4 w-4 items-center justify-center rounded-full border ${
                            td.done
                              ? 'border-emerald-500 bg-emerald-500 text-white'
                              : 'border-zinc-400'
                          }`}
                        >
                          {td.done && <Check className="h-2.5 w-2.5" />}
                        </span>
                        <span className={td.done ? 'line-through opacity-50' : ''}>{td.title}</span>
                      </button>
                      <button
                        type="button"
                        onClick={async () => {
                          await api.deleteTodo(td.id)
                          await refreshAll()
                        }}
                        className="text-rose-500 opacity-60 hover:opacity-100"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </section>

              {/* Ideas */}
              <section className={`${cardClass} p-6`}>
                <div className="flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-amber-500" />
                  <h2 className="text-base font-semibold">Idea 灵感</h2>
                </div>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault()
                    if (!ideaTitle.trim()) return
                    await api.addIdea(ideaTitle, ideaContent, 'idea')
                    setIdeaTitle('')
                    setIdeaContent('')
                    await refreshAll()
                  }}
                  className="mt-4 space-y-2"
                >
                  <input
                    value={ideaTitle}
                    onChange={(e) => setIdeaTitle(e.target.value)}
                    placeholder="灵感标题..."
                    className={`w-full rounded-2xl border px-3.5 py-2 text-xs outline-none ${innerSurface}`}
                  />
                  <textarea
                    value={ideaContent}
                    onChange={(e) => setIdeaContent(e.target.value)}
                    rows={2}
                    placeholder="补充细节..."
                    className={`w-full rounded-2xl border p-3 text-xs outline-none ${innerSurface}`}
                  />
                  <button
                    type="submit"
                    className="rounded-full bg-zinc-900 px-4 py-1.5 text-xs font-medium text-white dark:bg-white dark:text-zinc-900"
                  >
                    记录灵感
                  </button>
                </form>
                <div className="mt-4 space-y-2">
                  {ideas.map((idea) => (
                    <div
                      key={idea.id}
                      className={`flex items-start justify-between rounded-2xl border p-3 ${innerSurface}`}
                    >
                      <div>
                        <div className="text-xs font-semibold">{idea.title}</div>
                        {idea.content && <p className="mt-1 text-[11px] opacity-70">{idea.content}</p>}
                      </div>
                      <button
                        type="button"
                        onClick={async () => {
                          await api.deleteIdea(idea.id)
                          await refreshAll()
                        }}
                        className="text-rose-500 opacity-60 hover:opacity-100"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}

          {/* 3. Library (Mnemosyne) */}
          {tab === 'library' && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <section className={`${cardClass} p-6`}>
                <h2 className="text-lg font-semibold">Mnemosyne 资料库检索</h2>
                <p className="mt-1 text-xs opacity-60">
                  {memStats?.graph_dir ?? '~/.metis/memory/graph'} · 文件数：
                  {memStats?.files_count ?? 0}
                </p>
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

              <section className={`${cardClass} space-y-4 p-6`}>
                <h2 className="text-lg font-semibold">上传文档 / 写入资料库</h2>
                <label
                  className={`flex cursor-pointer items-center justify-center gap-2 rounded-2xl border border-dashed p-4 text-xs font-medium transition hover:bg-zinc-500/5 ${innerSurface}`}
                >
                  <Upload className="h-4 w-4" />
                  <span>选择文件上传并入库</span>
                  <input
                    type="file"
                    className="hidden"
                    onChange={async (e) => {
                      const f = e.target.files?.[0]
                      if (!f) return
                      const res = await api.uploadMemoryFile(f)
                      setUploadStatus(`已入库: ${res.filename}`)
                      await refreshAll()
                    }}
                  />
                </label>
                {uploadStatus && <div className="text-xs text-emerald-600">{uploadStatus}</div>}

                <textarea
                  value={memIngest}
                  onChange={(e) => setMemIngest(e.target.value)}
                  rows={4}
                  placeholder="或粘贴文本笔记写入 Mnemosyne 图谱..."
                  className={`w-full rounded-2xl border p-3.5 text-sm outline-none ${innerSurface}`}
                />
                <button
                  type="button"
                  onClick={async () => {
                    if (!memIngest.trim()) return
                    await api.ingestMemory(memIngest)
                    setMemIngest('')
                    await refreshAll()
                  }}
                  className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white dark:bg-white dark:text-zinc-900"
                >
                  写入图谱
                </button>
              </section>
            </div>
          )}

          {/* 4. Automations (Cron) */}
          {tab === 'automations' && (
            <section className={`${cardClass} p-6`}>
              <h2 className="text-lg font-semibold">定时任务 (Cron)</h2>
              <p className="mt-1 text-xs opacity-60">
                Cron 心跳：{cronInfo.enabled ? '已启用' : '未启用'}
              </p>
              <form
                onSubmit={async (e) => {
                  e.preventDefault()
                  if (!cronName.trim() || !cronExpr.trim()) return
                  await api.addCron(cronName.trim(), cronExpr.trim(), cronPrompt.trim())
                  setCronName('')
                  setCronPrompt('')
                  await refreshAll()
                }}
                className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-4"
              >
                <input
                  value={cronName}
                  onChange={(e) => setCronName(e.target.value)}
                  placeholder="任务名"
                  className={`rounded-2xl border px-3.5 py-2 text-xs outline-none ${innerSurface}`}
                />
                <input
                  value={cronExpr}
                  onChange={(e) => setCronExpr(e.target.value)}
                  placeholder="0 * * * *"
                  className={`rounded-2xl border px-3.5 py-2 font-mono text-xs outline-none ${innerSurface}`}
                />
                <input
                  value={cronPrompt}
                  onChange={(e) => setCronPrompt(e.target.value)}
                  placeholder="执行指令 (可选)"
                  className={`rounded-2xl border px-3.5 py-2 text-xs outline-none ${innerSurface}`}
                />
                <button
                  type="submit"
                  className="rounded-2xl bg-zinc-900 px-4 py-2 text-xs font-medium text-white dark:bg-white dark:text-zinc-900"
                >
                  添加任务
                </button>
              </form>
              <div className="mt-4 space-y-2">
                {cronInfo.details.map((job) => (
                  <div
                    key={job.name}
                    className={`flex items-center justify-between rounded-2xl border px-4 py-3 text-xs ${innerSurface}`}
                  >
                    <div>
                      <div className="font-semibold">{job.name}</div>
                      <div className="font-mono text-[11px] opacity-65">{job.cron_expr}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => void api.triggerCron(job.name)}
                        className="rounded-full bg-emerald-500/15 px-3 py-1 text-emerald-700 dark:text-emerald-300"
                      >
                        立即执行
                      </button>
                      <button
                        type="button"
                        onClick={async () => {
                          await api.deleteCron(job.name)
                          await refreshAll()
                        }}
                        className="text-rose-500 opacity-60 hover:opacity-100"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* 5. Monitor & Token (Flux Token + Radial Host Load + Custom Charts) */}
          {tab === 'monitor' && (
            <div className="space-y-6">
              <section className={`${cardClass} p-6`}>
                <h2 className="mb-4 text-lg font-semibold">Token 额度与费用预测</h2>
                <FluxTokenPanel
                  totalTokens={
                    (usage?.total_input_tokens ?? 0) + (usage?.total_output_tokens ?? 0)
                  }
                  totalCostUsd={usage?.total_cost_usd ?? 0}
                  forecast30dUsd={usage?.forecast_30d_usd ?? 0}
                  successRate={usage?.success_rate ?? 100}
                  daily={usage?.daily ?? []}
                  innerSurface={innerSurface}
                />
              </section>

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <section className={`${cardClass} p-6`}>
                  <h2 className="mb-4 text-base font-semibold">本机负载与进程</h2>
                  <div className={`flex items-center justify-around rounded-2xl border p-4 ${innerSurface}`}>
                    <RadialGauge
                      label="CPU"
                      value={metrics?.cpu_percent ?? 0}
                      subtitle={`${metrics?.cpu_count ?? 1} cores`}
                      color="#10b981"
                    />
                    <RadialGauge
                      label="Memory"
                      value={metrics?.memory_percent ?? 0}
                      subtitle={`${metrics?.memory_used_gb ?? 0}/${metrics?.memory_total_gb ?? 0}G`}
                      color="#6366f1"
                    />
                    <RadialGauge
                      label="Disk"
                      value={metrics?.disk_percent ?? 0}
                      subtitle={`${metrics?.disk_used_gb ?? 0}/${metrics?.disk_total_gb ?? 0}G`}
                      color="#0ea5e9"
                    />
                  </div>
                  <div className={`mt-4 rounded-2xl border p-4 ${innerSurface}`}>
                    <div className="mb-2 flex items-center justify-between text-xs font-semibold">
                      <span>进程数：{metrics?.process_count ?? '-'}</span>
                      <span className="font-mono text-[11px] opacity-65">
                        IO R {metrics?.disk_io.read_mb ?? 0}M / W {metrics?.disk_io.write_mb ?? 0}M
                      </span>
                    </div>
                    <div className="max-h-36 space-y-1 overflow-y-auto font-mono text-[11px]">
                      {(metrics?.top_processes ?? []).map((p) => (
                        <div key={p.pid} className="flex items-center justify-between">
                          <span className="max-w-[180px] truncate">
                            {p.pid} {p.name}
                          </span>
                          <span className="opacity-75">
                            CPU {p.cpu_percent}% · MEM {p.memory_percent}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>

                <section className={`${cardClass} p-6`}>
                  <div className="flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-emerald-500" />
                    <h2 className="text-base font-semibold">自定义图表</h2>
                  </div>
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault()
                      if (!chartTitle.trim()) return
                      const labels = chartLabels.split(',').map((s) => s.trim()).filter(Boolean)
                      const values = chartValues.split(',').map((s) => Number(s.trim()) || 0)
                      await api.addChart(chartTitle, chartType, labels, values)
                      setChartTitle('')
                      await refreshAll()
                    }}
                    className="mt-4 space-y-2"
                  >
                    <div className="flex gap-2">
                      <input
                        value={chartTitle}
                        onChange={(e) => setChartTitle(e.target.value)}
                        placeholder="图表标题..."
                        className={`flex-1 rounded-2xl border px-3 py-1.5 text-xs outline-none ${innerSurface}`}
                      />
                      <select
                        value={chartType}
                        onChange={(e) => setChartType(e.target.value as 'bar' | 'line' | 'ring')}
                        className={`rounded-2xl border px-3 py-1.5 text-xs outline-none ${innerSurface}`}
                      >
                        <option value="bar">柱状图</option>
                        <option value="line">折线图</option>
                        <option value="ring">环形图</option>
                      </select>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        value={chartLabels}
                        onChange={(e) => setChartLabels(e.target.value)}
                        className={`rounded-2xl border px-3 py-1.5 text-xs outline-none ${innerSurface}`}
                      />
                      <input
                        value={chartValues}
                        onChange={(e) => setChartValues(e.target.value)}
                        className={`rounded-2xl border px-3 py-1.5 text-xs outline-none ${innerSurface}`}
                      />
                    </div>
                    <button
                      type="submit"
                      className="rounded-full bg-zinc-900 px-4 py-1.5 text-xs font-medium text-white dark:bg-white dark:text-zinc-900"
                    >
                      生成图表
                    </button>
                  </form>
                  <div className="mt-4 space-y-3">
                    {charts.map((ch) => (
                      <div key={ch.id} className={`rounded-2xl border p-3 ${innerSurface}`}>
                        <div className="mb-1 flex items-center justify-between text-xs font-semibold">
                          <span>{ch.title}</span>
                          <button
                            type="button"
                            onClick={async () => {
                              await api.deleteChart(ch.id)
                              await refreshAll()
                            }}
                            className="text-rose-500 opacity-60 hover:opacity-100"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        <CustomChartSvg chartType={ch.chart_type} labels={ch.labels} values={ch.values} />
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            </div>
          )}

          {/* 6. Skills */}
          {tab === 'skills' && (
            <section className={`${cardClass} p-6`}>
              <h2 className="text-lg font-semibold">渐进式技能 (SKILL.md)</h2>
              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  {skills.map((s) => (
                    <button
                      key={s.name}
                      type="button"
                      onClick={async () => setSelectedSkill(await api.skillDetail(s.name))}
                      className={`block w-full rounded-2xl border p-3 text-left transition hover:scale-[1.01] ${innerSurface}`}
                    >
                      <div className="text-sm font-semibold">{s.name}</div>
                      <div className="mt-0.5 text-xs opacity-65">{s.description}</div>
                    </button>
                  ))}
                </div>
                <pre className={`max-h-96 overflow-auto rounded-2xl border p-4 text-xs ${innerSurface}`}>
                  {selectedSkill ? selectedSkill.content : '点击左侧技能查看完整内容'}
                </pre>
              </div>
            </section>
          )}
        </main>
      </div>

      {/* Settings Modal */}
      {settingsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4 backdrop-blur-sm">
          <div className={`${cardClass} w-full max-w-xl p-6`}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">全局设置</h2>
              <button
                type="button"
                onClick={() => setSettingsOpen(false)}
                className="rounded-full p-1.5 hover:bg-zinc-500/15"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 flex gap-2">
              {[
                { id: 'llm' as const, label: '模型路由' },
                { id: 'security' as const, label: '安全与备份' },
              ].map((st) => (
                <button
                  key={st.id}
                  type="button"
                  onClick={() => setSettingsTab(st.id)}
                  className={`rounded-full px-3.5 py-1 text-xs font-medium ${
                    settingsTab === st.id
                      ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900'
                      : 'bg-zinc-500/10'
                  }`}
                >
                  {st.label}
                </button>
              ))}
            </div>

            {settingsTab === 'llm' && (
              <div className="mt-4 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="opacity-70">~/.metis/models.json</span>
                  <button
                    type="button"
                    onClick={() => void refreshAll()}
                    className="rounded-full bg-zinc-900 px-3 py-1 text-white dark:bg-white dark:text-zinc-900"
                  >
                    拉取可用模型 ({discoveredModels.length})
                  </button>
                </div>
                {models &&
                  Object.entries(models.roles).map(([roleName, route]) => (
                    <div
                      key={roleName}
                      className={`flex items-center justify-between rounded-2xl border p-3 text-xs ${innerSurface}`}
                    >
                      <span className="font-semibold">{roleName}</span>
                      <select
                        value={`${route.provider_id}::${route.model ?? ''}`}
                        onChange={(e) => {
                          const [pid, mod] = e.target.value.split('::')
                          void handleUpdateRoleModel(roleName, pid, mod)
                        }}
                        className="max-w-[220px] rounded-xl border border-zinc-400/30 bg-transparent px-2 py-1 font-mono text-[11px] outline-none"
                      >
                        <option value={`${route.provider_id}::${route.model ?? ''}`}>
                          {route.provider_id} / {route.model ?? '(default)'}
                        </option>
                        {discoveredModels.map((opt) => (
                          <option
                            key={`${opt.provider_id}::${opt.model}`}
                            value={`${opt.provider_id}::${opt.model}`}
                          >
                            {opt.provider_id} / {opt.model}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
              </div>
            )}

            {settingsTab === 'security' && (
              <div className="mt-4 space-y-3 text-xs">
                <div className={`rounded-2xl border p-3.5 ${innerSurface}`}>
                  <div className="font-semibold">安全审批与熔断</div>
                  <p className="mt-1 opacity-75">
                    文件写入、敏感 Shell（含 `git push` / `rm -rf`）与连续 3 次重复错误自动挂起等待人工审批。
                  </p>
                </div>
                <div className={`flex items-center justify-between rounded-2xl border p-3.5 ${innerSurface}`}>
                  <div>
                    <div className="font-semibold">挂载目录备份</div>
                    <div className="opacity-70">目标路径通过 METIS_BACKUP_TARGET_DIR 配置</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleBackup()}
                    className="flex items-center gap-1.5 rounded-full bg-zinc-900 px-3.5 py-1.5 font-medium text-white dark:bg-white dark:text-zinc-900"
                  >
                    <Play className="h-3 w-3" /> 立即备份
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
