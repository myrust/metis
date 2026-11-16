import { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  BarChart3,
  BookOpen,
  Brain,
  Check,
  CheckCircle2,
  Clock,
  DollarSign,
  FileCode2,
  Home,
  Lightbulb,
  ListTodo,
  MessageSquare,
  Moon,
  Play,
  Plus,
  Send,
  ShieldAlert,
  Sparkles,
  Sun,
  Trash2,
  Upload,
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
  type SkillItem,
  type SystemMetrics,
  type TodoItem,
  type UsageSummary,
} from './api/client'
import { NodeSwitcher } from './components/NodeSwitcher'
import { CustomChartSvg, RadialGauge } from './components/RadialGauge'

type NavTab = 'workbench' | 'library' | 'ideas' | 'skills'
type ChatSubTab = 'chat' | 'approvals' | 'cron'
type RightBottomTab = 'todos' | 'workspace'

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
  const [rightBottomTab, setRightBottomTab] = useState<RightBottomTab>('todos')

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
  const [ideaTag, setIdeaTag] = useState('product')
  const [charts, setCharts] = useState<CustomChartItem[]>([])
  const [chartTitle, setChartTitle] = useState('')
  const [chartType, setChartType] = useState<'bar' | 'line' | 'ring'>('bar')
  const [chartLabels, setChartLabels] = useState('Mon,Tue,Wed,Thu')
  const [chartValues, setChartValues] = useState('12,19,8,24')

  const [cronName, setCronName] = useState('')
  const [cronExpr, setCronExpr] = useState('0 * * * *')
  const [cronPrompt, setCronPrompt] = useState('')

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
  const [memStats, setMemStats] = useState<{ graph_dir: string; files_count: number; files: string[] } | null>(null)
  const [uploadStatus, setUploadStatus] = useState('')

  const refreshAll = useCallback(async () => {
    try {
      const [h, n, s, f, c, m, d, sys, u, td, idList, chList, ms] = await Promise.all([
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
    } catch {
      // Backend might not be running during standalone preview.
    }
  }, [])

  useEffect(() => {
    void refreshAll()
    const timer = window.setInterval(() => {
      void api.systemMetrics().then(setMetrics).catch(() => {})
    }, 10000)
    return () => window.clearInterval(timer)
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
              { id: 'library' as const, icon: Brain, label: '资料库 / Mnemosyne' },
              { id: 'ideas' as const, icon: Lightbulb, label: 'Idea & 自定义图表' },
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
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-tight">Metis Workbench</h1>
                <div
                  className={`flex items-center rounded-full p-1 text-xs font-medium ${
                    dark ? 'bg-white/10' : 'bg-white/70 shadow-sm'
                  }`}
                >
                  {[
                    { id: 'workbench' as const, label: 'Workbench' },
                    { id: 'library' as const, label: '资料库' },
                    { id: 'ideas' as const, label: 'Idea & 图表' },
                    { id: 'skills' as const, label: 'Skills & Models' },
                  ].map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setTab(t.id)}
                      className={`rounded-full px-3.5 py-1 transition ${
                        tab === t.id
                          ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-white'
                          : 'opacity-65 hover:opacity-100'
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>
              <p className="mt-1 text-sm opacity-65">
                Active node: <span className="font-medium">{activeNodeId}</span> ·{' '}
                {health?.workspace ?? '~/.metis/workspace'}
              </p>
            </div>

            <div className="flex items-center gap-4">
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

              <div className="hidden items-center gap-5 sm:flex">
                <div>
                  <div className="text-[11px] opacity-60">7d Cost</div>
                  <div className="text-lg font-semibold">
                    ${(usage?.total_cost_usd ?? 0).toFixed(4)}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] opacity-60">Processes</div>
                  <div className="text-lg font-semibold">{metrics?.process_count ?? '-'}</div>
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
              {/* Left Chat + Cron + Approvals Card */}
              <section className={`${cardClass} flex h-[660px] flex-col p-5 lg:col-span-5`}>
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {[
                      { id: 'chat' as const, icon: MessageSquare, label: 'Chat' },
                      { id: 'approvals' as const, icon: ShieldAlert, label: 'Approvals' },
                      { id: 'cron' as const, icon: Clock, label: '定时任务' },
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
                    <div className={`flex-1 space-y-3 overflow-y-auto rounded-3xl border p-4 ${innerSurface}`}>
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
                              <span className="font-semibold uppercase opacity-60">{item.kind}: </span>
                              <span className="break-all">{item.text}</span>
                            </div>
                          )
                        }

                        const isUser = item.kind === 'user'
                        return (
                          <div key={item.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
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
                        className="max-w-[145px] truncate rounded-full bg-zinc-500/10 px-2.5 py-1 text-[11px] font-medium outline-none"
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
                  <div className={`flex flex-1 flex-col gap-3 overflow-y-auto rounded-3xl border p-4 text-xs ${innerSurface}`}>
                    <div className="flex items-center justify-between">
                      <span className="font-semibold">
                        Cron 心跳：{cronInfo.enabled ? '已启用' : '未启用'}
                      </span>
                      <span className="opacity-60">{cronInfo.details.length} 个任务</span>
                    </div>
                    <form
                      onSubmit={async (e) => {
                        e.preventDefault()
                        if (!cronName.trim() || !cronExpr.trim()) return
                        await api.addCron(cronName.trim(), cronExpr.trim(), cronPrompt.trim())
                        setCronName('')
                        setCronPrompt('')
                        await refreshAll()
                      }}
                      className="space-y-2 rounded-2xl bg-zinc-500/8 p-3"
                    >
                      <div className="flex gap-2">
                        <input
                          value={cronName}
                          onChange={(e) => setCronName(e.target.value)}
                          placeholder="任务名"
                          className="w-1/2 rounded-xl border border-zinc-400/30 bg-transparent px-2.5 py-1.5 outline-none"
                        />
                        <input
                          value={cronExpr}
                          onChange={(e) => setCronExpr(e.target.value)}
                          placeholder="0 * * * *"
                          className="w-1/2 rounded-xl border border-zinc-400/30 bg-transparent px-2.5 py-1.5 font-mono outline-none"
                        />
                      </div>
                      <div className="flex gap-2">
                        <input
                          value={cronPrompt}
                          onChange={(e) => setCronPrompt(e.target.value)}
                          placeholder="执行指令 (可选)"
                          className="flex-1 rounded-xl border border-zinc-400/30 bg-transparent px-2.5 py-1.5 outline-none"
                        />
                        <button
                          type="submit"
                          className="rounded-xl bg-zinc-900 px-3 py-1.5 font-medium text-white dark:bg-white dark:text-zinc-900"
                        >
                          添加
                        </button>
                      </div>
                    </form>
                    <div className="space-y-2">
                      {cronInfo.details.map((job) => (
                        <div
                          key={job.name}
                          className="flex items-center justify-between rounded-2xl border border-zinc-400/20 px-3 py-2"
                        >
                          <div>
                            <div className="font-semibold">{job.name}</div>
                            <div className="font-mono text-[10px] opacity-60">{job.cron_expr}</div>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => void api.triggerCron(job.name)}
                              className="rounded-lg bg-emerald-500/15 px-2 py-1 text-[11px] text-emerald-700 dark:text-emerald-300"
                            >
                              执行
                            </button>
                            <button
                              type="button"
                              onClick={async () => {
                                await api.deleteCron(job.name)
                                await refreshAll()
                              }}
                              className="rounded-lg p-1 text-rose-500 hover:bg-rose-500/10"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>

              {/* Right Column: Host Load + Usage + Todos/Workspace */}
              <div className="flex flex-col gap-6 lg:col-span-7">
                {/* Top-Right: Circular Gauges + Disk IO + Processes + Usage Cost */}
                <section className={`${cardClass} p-5`}>
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <h2 className="text-base font-semibold">本机负载与额度预估</h2>
                      <p className="text-xs opacity-60">
                        {metrics?.platform ?? 'Host'} · 进程数 {metrics?.process_count ?? '-'} · 磁盘
                        IO R {metrics?.disk_io.read_mb ?? 0} MB / W {metrics?.disk_io.write_mb ?? 0} MB
                      </p>
                    </div>
                    <Activity className="h-4 w-4 opacity-50" />
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
                    {/* 3 Circular Ring Gauges */}
                    <div
                      className={`flex items-center justify-around rounded-2xl border p-3 md:col-span-6 ${innerSurface}`}
                    >
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

                    {/* Top Processes + Usage Cost */}
                    <div className={`flex flex-col justify-between rounded-2xl border p-3 md:col-span-6 ${innerSurface}`}>
                      <div className="flex items-center justify-between border-b border-zinc-400/20 pb-2">
                        <div className="flex items-center gap-1.5 text-xs font-semibold">
                          <DollarSign className="h-3.5 w-3.5 text-emerald-500" />
                          7日额度预估：${(usage?.total_cost_usd ?? 0).toFixed(4)}
                        </div>
                        <span className="text-[11px] opacity-65">
                          {(usage?.total_input_tokens ?? 0) + (usage?.total_output_tokens ?? 0)} tok ·{' '}
                          {usage?.total_calls ?? 0} 次
                        </span>
                      </div>
                      <div className="mt-2 max-h-24 space-y-1 overflow-y-auto text-[11px]">
                        {(metrics?.top_processes ?? []).map((p) => (
                          <div key={p.pid} className="flex items-center justify-between font-mono">
                            <span className="truncate max-w-[140px]">
                              {p.pid} {p.name}
                            </span>
                            <span className="opacity-75">
                              CPU {p.cpu_percent}% · MEM {p.memory_percent}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </section>

                {/* Bottom-Right: To-do List & Workspace Explorer */}
                <section className={`${cardClass} flex flex-1 flex-col p-5`}>
                  <div className="mb-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setRightBottomTab('todos')}
                        className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                          rightBottomTab === 'todos'
                            ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900'
                            : 'bg-zinc-500/10'
                        }`}
                      >
                        <ListTodo className="h-3.5 w-3.5" /> To-do List ({todos.length})
                      </button>
                      <button
                        type="button"
                        onClick={() => setRightBottomTab('workspace')}
                        className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                          rightBottomTab === 'workspace'
                            ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900'
                            : 'bg-zinc-500/10'
                        }`}
                      >
                        <FileCode2 className="h-3.5 w-3.5" /> Workspace ({files.length})
                      </button>
                    </div>
                  </div>

                  {rightBottomTab === 'todos' ? (
                    <div className="flex flex-1 flex-col gap-3">
                      <form
                        onSubmit={async (e) => {
                          e.preventDefault()
                          if (!newTodo.trim()) return
                          await api.addTodo(newTodo.trim())
                          setNewTodo('')
                          await refreshAll()
                        }}
                        className="flex gap-2"
                      >
                        <input
                          value={newTodo}
                          onChange={(e) => setNewTodo(e.target.value)}
                          placeholder="添加待办事项..."
                          className={`flex-1 rounded-full border px-4 py-2 text-xs outline-none ${innerSurface}`}
                        />
                        <button
                          type="submit"
                          className="flex items-center gap-1 rounded-full bg-zinc-900 px-4 py-2 text-xs font-medium text-white dark:bg-white dark:text-zinc-900"
                        >
                          <Plus className="h-3.5 w-3.5" /> 添加
                        </button>
                      </form>
                      <div className={`max-h-[240px] flex-1 space-y-2 overflow-y-auto rounded-2xl border p-3 ${innerSurface}`}>
                        {todos.length === 0 ? (
                          <div className="text-xs opacity-60">暂无待办事项</div>
                        ) : (
                          todos.map((td) => (
                            <div
                              key={td.id}
                              className="flex items-center justify-between rounded-xl px-2 py-1.5 hover:bg-zinc-500/8"
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
                                <span className={td.done ? 'line-through opacity-50' : ''}>
                                  {td.title}
                                </span>
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
                          ))
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="grid flex-1 grid-cols-1 gap-4 md:grid-cols-5">
                      <div
                        className={`max-h-[260px] overflow-y-auto rounded-2xl border p-2.5 md:col-span-2 ${innerSurface}`}
                      >
                        {files.length === 0 ? (
                          <div className="p-3 text-xs opacity-60">工作区暂无文件</div>
                        ) : (
                          files.map((f) => (
                            <button
                              key={f}
                              type="button"
                              onClick={async () => setSelectedFile(await api.readWorkspaceFile(f, 1, 200))}
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
                        className={`max-h-[260px] overflow-auto rounded-2xl border p-3 font-mono text-xs md:col-span-3 ${innerSurface}`}
                      >
                        {selectedFile ? selectedFile.content : '点击左侧文件查看带行号内容'}
                      </pre>
                    </div>
                  )}
                </section>
              </div>
            </div>
          )}

          {/* View 2: 资料库 / Mnemosyne */}
          {tab === 'library' && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <section className={`${cardClass} p-6`}>
                <h2 className="text-lg font-semibold">Mnemosyne 资料库检索</h2>
                <p className="mt-1 text-xs opacity-60">
                  图谱目录：{memStats?.graph_dir ?? '~/.metis/memory/graph'} · 持久化文件数：
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
                <div>
                  <h2 className="text-lg font-semibold">上传文档 / 写入资料库</h2>
                  <p className="mt-1 text-xs opacity-60">
                    支持 PDF / Markdown / TXT（RAG-Anything + Qwen 云端解析）
                  </p>
                </div>
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
                  placeholder="或直接粘贴文本笔记写入 Mnemosyne 图谱..."
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

          {/* View 3: Idea & 自定义图表 */}
          {tab === 'ideas' && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <section className={`${cardClass} p-6`}>
                <div className="flex items-center gap-2">
                  <Lightbulb className="h-5 w-5 text-amber-500" />
                  <h2 className="text-lg font-semibold">Idea 灵感收集</h2>
                </div>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault()
                    if (!ideaTitle.trim()) return
                    await api.addIdea(ideaTitle, ideaContent, ideaTag)
                    setIdeaTitle('')
                    setIdeaContent('')
                    await refreshAll()
                  }}
                  className="mt-4 space-y-2"
                >
                  <div className="flex gap-2">
                    <input
                      value={ideaTitle}
                      onChange={(e) => setIdeaTitle(e.target.value)}
                      placeholder="灵感标题..."
                      className={`flex-1 rounded-2xl border px-3.5 py-2 text-sm outline-none ${innerSurface}`}
                    />
                    <input
                      value={ideaTag}
                      onChange={(e) => setIdeaTag(e.target.value)}
                      placeholder="标签"
                      className={`w-28 rounded-2xl border px-3 py-2 text-xs outline-none ${innerSurface}`}
                    />
                  </div>
                  <textarea
                    value={ideaContent}
                    onChange={(e) => setIdeaContent(e.target.value)}
                    rows={2}
                    placeholder="补充想法细节..."
                    className={`w-full rounded-2xl border p-3 text-xs outline-none ${innerSurface}`}
                  />
                  <button
                    type="submit"
                    className="rounded-full bg-zinc-900 px-4 py-1.5 text-xs font-medium text-white dark:bg-white dark:text-zinc-900"
                  >
                    记录灵感
                  </button>
                </form>

                <div className="mt-4 space-y-2.5">
                  {ideas.map((idea) => (
                    <div key={idea.id} className={`flex items-start justify-between rounded-2xl border p-3 ${innerSurface}`}>
                      <div>
                        <div className="flex items-center gap-2 text-sm font-semibold">
                          {idea.title}
                          <span className="rounded-full bg-amber-400/20 px-2 py-0.5 text-[10px] text-amber-700 dark:text-amber-300">
                            {idea.tag}
                          </span>
                        </div>
                        {idea.content && <p className="mt-1 text-xs opacity-70">{idea.content}</p>}
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

              <section className={`${cardClass} p-6`}>
                <div className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-emerald-500" />
                  <h2 className="text-lg font-semibold">自定义图表</h2>
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
                      className={`flex-1 rounded-2xl border px-3.5 py-2 text-sm outline-none ${innerSurface}`}
                    />
                    <select
                      value={chartType}
                      onChange={(e) => setChartType(e.target.value as 'bar' | 'line' | 'ring')}
                      className={`rounded-2xl border px-3 py-2 text-xs outline-none ${innerSurface}`}
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
                      placeholder="标签 (逗号分隔)"
                      className={`rounded-2xl border px-3 py-1.5 text-xs outline-none ${innerSurface}`}
                    />
                    <input
                      value={chartValues}
                      onChange={(e) => setChartValues(e.target.value)}
                      placeholder="数值 (逗号分隔)"
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

                <div className="mt-4 grid grid-cols-1 gap-3">
                  {charts.map((ch) => (
                    <div key={ch.id} className={`rounded-2xl border p-3.5 ${innerSurface}`}>
                      <div className="mb-1 flex items-center justify-between">
                        <span className="text-xs font-semibold">{ch.title}</span>
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
          )}

          {/* View 4: Skills & Models */}
          {tab === 'skills' && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <section className={`${cardClass} p-6`}>
                <h2 className="text-lg font-semibold">渐进式 SKILL.md</h2>
                <div className="mt-4 space-y-2">
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
                {selectedSkill && (
                  <pre className={`mt-4 max-h-64 overflow-auto rounded-2xl border p-3 text-xs ${innerSurface}`}>
                    {selectedSkill.content}
                  </pre>
                )}
              </section>

              <section className={`${cardClass} p-6`}>
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">多模型自由切换 (~/.metis/models.json)</h2>
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
                        <div className="flex items-center justify-between">
                          <span className="font-semibold">{roleName}</span>
                          <select
                            value={`${route.provider_id}::${route.model ?? ''}`}
                            onChange={(e) => {
                              const [pid, mod] = e.target.value.split('::')
                              void handleUpdateRoleModel(roleName, pid, mod)
                            }}
                            className="max-w-[200px] rounded-xl border border-zinc-400/30 bg-transparent px-2 py-1 font-mono text-[11px] outline-none"
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
