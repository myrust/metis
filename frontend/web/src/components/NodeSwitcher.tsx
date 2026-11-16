import { useState } from 'react'
import { Check, ChevronRight, Plus, Server, Trash2 } from 'lucide-react'
import type { NodeItem } from '../api/client'

interface NodeSwitcherProps {
  nodes: NodeItem[]
  activeNodeId: string
  dark: boolean
  onActivate: (id: string) => Promise<void>
  onAdd: (node: {
    id: string
    kind: string
    host: string
    workspace: string
    allowed_paths: string[]
  }) => Promise<void>
  onDelete: (id: string) => Promise<void>
}

const NODE_COLORS = [
  'bg-amber-400',
  'bg-emerald-400',
  'bg-sky-400',
  'bg-violet-400',
]

export function NodeSwitcher({
  nodes,
  activeNodeId,
  dark,
  onActivate,
  onAdd,
  onDelete,
}: NodeSwitcherProps) {
  const [open, setOpen] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [id, setId] = useState('')
  const [host, setHost] = useState('')
  const [workspace, setWorkspace] = useState('~/workspace')
  const [allowed, setAllowed] = useState('')

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id.trim() || !host.trim()) return
    const allowed_paths = allowed
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    await onAdd({
      id: id.trim(),
      kind: 'ssh',
      host: host.trim(),
      workspace: workspace.trim() || '~/workspace',
      allowed_paths,
    })
    setId('')
    setHost('')
    setAllowed('')
    setShowAdd(false)
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title={`Execution Node: ${activeNodeId}`}
        className={`relative flex h-11 w-11 items-center justify-center rounded-full ring-2 ring-emerald-400 transition hover:scale-105 ${
          dark ? 'bg-zinc-800 text-zinc-100' : 'bg-white text-zinc-800 shadow-sm'
        }`}
      >
        <Server className="h-4 w-4" />
        <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-400" />
      </button>

      {open && (
        <div
          className={`bento-card absolute bottom-0 left-14 z-50 w-72 rounded-3xl border p-3 shadow-2xl ${
            dark
              ? 'border-white/10 bg-zinc-900/90 text-zinc-100'
              : 'border-white/70 bg-white/88 text-zinc-800'
          }`}
        >
          <div className="mb-2 px-2 text-xs font-medium opacity-60">执行节点 (NodeRouter)</div>
          <div className="space-y-1">
            {nodes.map((node, idx) => {
              const active = node.id === activeNodeId
              return (
                <div
                  key={node.id}
                  className={`group flex items-center justify-between rounded-2xl px-2.5 py-2 transition ${
                    active
                      ? dark
                        ? 'bg-white/10'
                        : 'bg-zinc-900/6'
                      : dark
                        ? 'hover:bg-white/5'
                        : 'hover:bg-zinc-900/4'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => void onActivate(node.id)}
                    className="flex flex-1 items-center gap-2.5 text-left"
                  >
                    <span
                      className={`flex h-5 w-5 items-center justify-center rounded-full border ${
                        active
                          ? 'border-zinc-900 bg-zinc-900 text-white dark:border-emerald-400 dark:bg-emerald-400 dark:text-zinc-950'
                          : 'border-zinc-300 dark:border-zinc-600'
                      }`}
                    >
                      {active && <Check className="h-3 w-3" />}
                    </span>
                    <span
                      className={`h-6 w-6 rounded-lg ${NODE_COLORS[idx % NODE_COLORS.length]} opacity-85`}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{node.id}</div>
                      <div className="truncate text-[11px] opacity-60">
                        {node.kind} · {node.host}
                      </div>
                    </div>
                  </button>

                  {node.id !== 'local' ? (
                    <button
                      type="button"
                      onClick={() => void onDelete(node.id)}
                      className="rounded-lg p-1 text-rose-500 opacity-60 hover:bg-rose-500/10 hover:opacity-100"
                      title="移除节点"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  ) : (
                    <ChevronRight className="h-4 w-4 opacity-30" />
                  )}
                </div>
              )
            })}
          </div>

          <div className="my-2 h-px bg-zinc-400/20" />

          {!showAdd ? (
            <button
              type="button"
              onClick={() => setShowAdd(true)}
              className="flex w-full items-center gap-2.5 rounded-2xl px-2.5 py-2 text-sm font-medium opacity-80 transition hover:bg-zinc-500/10 hover:opacity-100"
            >
              <span className="flex h-6 w-6 items-center justify-center rounded-full border border-dashed border-zinc-400">
                <Plus className="h-3.5 w-3.5" />
              </span>
              添加 SSH 节点
            </button>
          ) : (
            <form onSubmit={(e) => void handleCreate(e)} className="space-y-2 p-1">
              <input
                value={id}
                onChange={(e) => setId(e.target.value)}
                placeholder="节点 ID (如 gpu-box)"
                className="w-full rounded-xl border border-zinc-300/60 bg-transparent px-2.5 py-1.5 text-xs outline-none focus:border-zinc-500"
              />
              <input
                value={host}
                onChange={(e) => setHost(e.target.value)}
                placeholder="SSH Host / ~/.ssh/config 别名"
                className="w-full rounded-xl border border-zinc-300/60 bg-transparent px-2.5 py-1.5 text-xs outline-none focus:border-zinc-500"
              />
              <input
                value={workspace}
                onChange={(e) => setWorkspace(e.target.value)}
                placeholder="远端 Workspace 路径"
                className="w-full rounded-xl border border-zinc-300/60 bg-transparent px-2.5 py-1.5 text-xs outline-none focus:border-zinc-500"
              />
              <input
                value={allowed}
                onChange={(e) => setAllowed(e.target.value)}
                placeholder="allowed_paths (逗号分隔，可选)"
                className="w-full rounded-xl border border-zinc-300/60 bg-transparent px-2.5 py-1.5 text-xs outline-none focus:border-zinc-500"
              />
              <div className="flex justify-end gap-1.5">
                <button
                  type="button"
                  onClick={() => setShowAdd(false)}
                  className="rounded-xl px-2.5 py-1 text-xs opacity-70 hover:opacity-100"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="rounded-xl bg-zinc-900 px-3 py-1 text-xs font-medium text-white dark:bg-emerald-400 dark:text-zinc-950"
                >
                  保存
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  )
}
