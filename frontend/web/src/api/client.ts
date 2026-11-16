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
  cron: () => jsonFetch<{ enabled: boolean; jobs: string[] }>('/api/cron'),
  runBackup: () => jsonFetch<{ status: string; archive?: string; reason?: string }>('/api/backup/run', { method: 'POST' }),
}

export async function streamChat(
  prompt: string,
  onEvent: (ev: SseEvent) => void,
): Promise<void> {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
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
