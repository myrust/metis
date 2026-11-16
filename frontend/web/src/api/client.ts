export interface HealthInfo {
  status: string
  host: string
  port: number
  workspace: string
  pending_approvals: number
  skills_count: number
  cron_enabled: boolean
  telegram_enabled: boolean
}

export interface NodeItem {
  id: string
  kind: 'local' | 'ssh' | string
  host: string
  workspace: string
  allowed_paths: string[]
  user?: string | null
  port?: number | null
  description?: string
}

export interface NodesResponse {
  active_node_id: string
  nodes: NodeItem[]
}

export interface SkillItem {
  name: string
  description: string
  path: string
}

export interface ModelsPayload {
  providers: Array<{
    id: string
    type: string
    base_url?: string | null
    api_key?: string | null
    default_model?: string | null
    enabled: boolean
  }>
  roles: Record<
    string,
    {
      provider_id: string
      model?: string | null
      fallback_providers?: string[]
    }
  >
}

export interface SystemMetrics {
  platform: string
  cpu_percent: number
  cpu_count: number
  memory_percent: number
  memory_used_gb: number
  memory_total_gb: number
  disk_percent: number
  disk_used_gb: number
  disk_total_gb: number
  disk_io: {
    read_mb: number
    write_mb: number
    read_count: number
    write_count: number
  }
  process_count: number
  top_processes: Array<{
    pid: number
    name: string
    cpu_percent: number
    memory_percent: number
  }>
}

export interface UsageSummary {
  days: number
  total_calls: number
  success_rate: number
  total_input_tokens: number
  total_output_tokens: number
  total_cost_usd: number
  forecast_30d_usd: number
  by_model: Record<
    string,
    { calls: number; input_tokens: number; output_tokens: number; cost_usd: number }
  >
  daily: Array<{ day: string; tokens: number; cost_usd: number; calls: number }>
}

export interface TodoItem {
  id: string
  title: string
  done: boolean
  priority: string
  created_at: number
}

export interface IdeaItem {
  id: string
  title: string
  content: string
  tag: string
  created_at: number
}

export interface CustomChartItem {
  id: string
  title: string
  chart_type: string
  labels: string[]
  values: number[]
}

export interface CronDetail {
  name: string
  cron_expr: string
  enabled: boolean
  next_run: string
}

export interface SessionMessage {
  id: string
  kind: 'user' | 'thinking' | 'tool_call' | 'tool_result' | 'approval' | 'assistant'
  text: string
  meta?: Record<string, unknown>
}

export interface SessionItem {
  id: string
  title: string
  project_id?: string | null
  created_at: number
  messages: SessionMessage[]
}

export interface ProjectItem {
  id: string
  name: string
  path: string
  node_id: string
  description: string
  created_at: number
}

export interface PendingApprovalItem {
  approval_id: string
  action_type: string
  summary: string
  details: Record<string, unknown>
}

export interface SseEvent {
  event: 'thinking' | 'tool_call' | 'tool_result' | 'approval_required' | 'done'
  data: Record<string, unknown>
}

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `HTTP ${res.status}`)
  }
  return (await res.json()) as T
}

export const api = {
  health: () => jsonFetch<HealthInfo>('/health'),
  nodes: () => jsonFetch<NodesResponse>('/api/nodes'),
  upsertNode: (node: Partial<NodeItem> & { id: string; host: string; workspace: string }) =>
    jsonFetch<NodeItem>('/api/nodes', { method: 'POST', body: JSON.stringify(node) }),
  activateNode: (id: string) =>
    jsonFetch<{ active_node_id: string }>(`/api/nodes/${encodeURIComponent(id)}/activate`, {
      method: 'POST',
    }),
  deleteNode: (id: string) =>
    jsonFetch<{ deleted: string; active_node_id: string }>(
      `/api/nodes/${encodeURIComponent(id)}`,
      { method: 'DELETE' },
    ),
  approve: (approval_id: string, approved: boolean) =>
    jsonFetch<{ approval_id: string; approved: boolean }>('/api/approval', {
      method: 'POST',
      body: JSON.stringify({ approval_id, approved }),
    }),
  skills: () => jsonFetch<{ skills: SkillItem[] }>('/api/skills'),
  skillDetail: (name: string) =>
    jsonFetch<{ name: string; content: string }>(`/api/skills/${encodeURIComponent(name)}`),
  workspaceFiles: () => jsonFetch<{ workspace: string; files: string[] }>('/api/workspace/files'),
  readWorkspaceFile: (path: string, start_line = 1, end_line = 200) =>
    jsonFetch<{ path: string; content: string }>(
      `/api/workspace/read?path=${encodeURIComponent(path)}&start_line=${start_line}&end_line=${end_line}`,
    ),
  models: () => jsonFetch<ModelsPayload>('/api/models'),
  discoverModels: () =>
    jsonFetch<{ models: Array<{ provider_id: string; model: string }>; error: string | null }>(
      '/api/models/discover',
    ),
  updateModels: (payload: Partial<ModelsPayload>) =>
    jsonFetch<ModelsPayload>('/api/models', { method: 'POST', body: JSON.stringify(payload) }),
  queryMemory: (question: string, mode = 'hybrid') =>
    jsonFetch<{ question: string; mode: string; answer: string }>('/api/memory/query', {
      method: 'POST',
      body: JSON.stringify({ question, mode }),
    }),
  ingestMemory: (text: string) =>
    jsonFetch<{ status: string }>('/api/memory/ingest', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  cron: () => jsonFetch<{ enabled: boolean; jobs: string[]; details: CronDetail[] }>('/api/cron'),
  addCron: (name: string, cron_expr: string, prompt: string) =>
    jsonFetch<{ jobs: string[]; details: CronDetail[] }>('/api/cron', {
      method: 'POST',
      body: JSON.stringify({ name, cron_expr, prompt }),
    }),
  deleteCron: (name: string) =>
    jsonFetch<{ jobs: string[]; details: CronDetail[] }>(`/api/cron/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),
  triggerCron: (name: string) =>
    jsonFetch<{ status: string }>(`/api/cron/${encodeURIComponent(name)}/run`, {
      method: 'POST',
    }),
  runBackup: () =>
    jsonFetch<{ status: string; archive?: string; reason?: string }>('/api/backup/run', {
      method: 'POST',
    }),
  systemMetrics: () => jsonFetch<SystemMetrics>('/api/system/metrics'),
  usageSummary: (days = 7) => jsonFetch<UsageSummary>(`/api/usage/summary?days=${days}`),
  todos: () => jsonFetch<{ todos: TodoItem[] }>('/api/todos'),
  addTodo: (title: string, priority = 'medium') =>
    jsonFetch<TodoItem>('/api/todos', { method: 'POST', body: JSON.stringify({ title, priority }) }),
  toggleTodo: (id: string, done?: boolean) =>
    jsonFetch<TodoItem>(`/api/todos/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ done }),
    }),
  deleteTodo: (id: string) =>
    jsonFetch<{ deleted: string }>(`/api/todos/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  ideas: () => jsonFetch<{ ideas: IdeaItem[] }>('/api/ideas'),
  addIdea: (title: string, content = '', tag = 'general') =>
    jsonFetch<IdeaItem>('/api/ideas', {
      method: 'POST',
      body: JSON.stringify({ title, content, tag }),
    }),
  deleteIdea: (id: string) =>
    jsonFetch<{ deleted: string }>(`/api/ideas/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  charts: () => jsonFetch<{ charts: CustomChartItem[] }>('/api/charts'),
  addChart: (title: string, chart_type: string, labels: string[], values: number[]) =>
    jsonFetch<CustomChartItem>('/api/charts', {
      method: 'POST',
      body: JSON.stringify({ title, chart_type, labels, values }),
    }),
  deleteChart: (id: string) =>
    jsonFetch<{ deleted: string }>(`/api/charts/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  memoryStats: () =>
    jsonFetch<{ graph_dir: string; files_count: number; files: string[] }>('/api/memory/stats'),
  uploadMemoryFile: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch('/api/memory/upload', { method: 'POST', body: form })
    if (!res.ok) throw new Error(await res.text())
    return (await res.json()) as { status: string; filename: string }
  },
  pendingApprovals: () => jsonFetch<{ pending: PendingApprovalItem[] }>('/api/approval'),
  sessions: () => jsonFetch<{ sessions: SessionItem[] }>('/api/sessions'),
  createSession: (title = '新对话', project_id?: string | null) =>
    jsonFetch<SessionItem>('/api/sessions', {
      method: 'POST',
      body: JSON.stringify({ title, project_id: project_id ?? null }),
    }),
  appendSessionMessage: (sessionId: string, entry: SessionMessage) =>
    jsonFetch<SessionItem>(`/api/sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: 'POST',
      body: JSON.stringify(entry),
    }),
  deleteSession: (sessionId: string) =>
    jsonFetch<{ deleted: string }>(`/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
    }),
  projects: () => jsonFetch<{ projects: ProjectItem[] }>('/api/projects'),
  addProject: (name: string, path: string, node_id = 'local', description = '') =>
    jsonFetch<ProjectItem>('/api/projects', {
      method: 'POST',
      body: JSON.stringify({ name, path, node_id, description }),
    }),
  deleteProject: (projectId: string) =>
    jsonFetch<{ deleted: string }>(`/api/projects/${encodeURIComponent(projectId)}`, {
      method: 'DELETE',
    }),
}

export async function streamChat(
  prompt: string,
  onEvent: (ev: SseEvent) => void,
  options?: { model?: string; provider_id?: string; system_prompt?: string },
): Promise<void> {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      model: options?.model || null,
      provider_id: options?.provider_id || null,
      system_prompt: options?.system_prompt || null,
    }),
  })
  if (!res.ok || !res.body) {
    throw new Error(`Stream failed: HTTP ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() ?? ''

    for (const block of blocks) {
      let eventName: SseEvent['event'] = 'thinking'
      let dataLine = '{}'
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith('event:')) {
          eventName = line.slice(6).trim() as SseEvent['event']
        } else if (line.startsWith('data:')) {
          dataLine = line.slice(5).trim()
        }
      }
      try {
        onEvent({ event: eventName, data: JSON.parse(dataLine) })
      } catch {
        onEvent({ event: eventName, data: { raw: dataLine } })
      }
    }
  }
}
