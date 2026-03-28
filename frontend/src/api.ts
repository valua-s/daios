const API_URL = process.env.API_URL ?? 'http://daios-api:8000'

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch (e) {
    throw new Error(`Бэкенд недоступен (${API_URL})`)
  }
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ── Tasks ──────────────────────────────────────────────────────────────────

export interface TaskDTO {
  id: number
  title: string
  status: 'pending' | 'done' | 'cancelled'
  priority: 'low' | 'medium' | 'high'
  date: string
  scheduled_time: string | null
  source: string | null
  notes: string | null
}

export const getTodayTasks = () =>
  apiFetch<TaskDTO[]>('/api/tasks/today')

export const toggleTask = (id: number) =>
  apiFetch<TaskDTO>(`/api/tasks/${id}/toggle`, { method: 'PATCH' })

export const moveTaskToBacklog = (id: number) =>
  apiFetch<{ ok: boolean }>(`/api/tasks/${id}/backlog`, { method: 'POST' })

export const deleteTask = (id: number) =>
  apiFetch<void>(`/api/tasks/${id}`, { method: 'DELETE' })

export const getTasksByRange = (from: string, to: string) =>
  apiFetch<TaskDTO[]>(`/api/tasks/range?from=${from}&to=${to}`)

export const updateTask = (id: number, data: {
  title?: string
  date?: string
  scheduled_time?: string | null
  notes?: string | null
  clear_time?: boolean
  clear_notes?: boolean
}) =>
  apiFetch<TaskDTO>(`/api/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })

// ── Backlog ────────────────────────────────────────────────────────────────

export interface BacklogItemDTO {
  id: number
  title: string
  reason: string | null
  notes: string | null
}

export const getBacklog = () =>
  apiFetch<BacklogItemDTO[]>('/api/backlog/')

export const moveBacklogToToday = (id: number) =>
  apiFetch<TaskDTO>(`/api/backlog/${id}/today`, { method: 'POST' })

export const deleteBacklogItem = (id: number) =>
  apiFetch<void>(`/api/backlog/${id}`, { method: 'DELETE' })

// ── Focus ──────────────────────────────────────────────────────────────────

export interface FocusDTO {
  id: number
  period: string
  period_key: string
  description: string
  is_active: boolean
}

export const getFocus = () =>
  apiFetch<{ week: FocusDTO | null; month: FocusDTO | null }>('/api/focus/')

export const setWeekFocus = (description: string) =>
  apiFetch<FocusDTO>('/api/focus/week', {
    method: 'PUT',
    body: JSON.stringify({ description }),
  })

export const setMonthFocus = (description: string) =>
  apiFetch<FocusDTO>('/api/focus/month', {
    method: 'PUT',
    body: JSON.stringify({ description }),
  })

// ── Workouts ───────────────────────────────────────────────────────────────

export interface WorkoutDTO {
  day: string
  date: string
  type: 'running' | 'strength' | 'combined' | 'rest'
  description: string
  duration_minutes: number
  is_today: boolean
  details: Record<string, unknown>
}

export const getWeekWorkouts = () =>
  apiFetch<WorkoutDTO[]>('/api/workouts/week')

// ── Settings ───────────────────────────────────────────────────────────────

export interface ScheduleDTO {
  event_name: string
  cron_expr: string
  enabled: boolean
  description: string
  time: string
}

export const getInterests = () =>
  apiFetch<Record<string, boolean>>('/api/settings/interests')

export const setInterests = (interests: Record<string, boolean>) =>
  apiFetch<Record<string, boolean>>('/api/settings/interests', {
    method: 'POST',
    body: JSON.stringify(interests),
  })

export const getSchedules = () =>
  apiFetch<ScheduleDTO[]>('/api/settings/schedules')

export const updateSchedule = (event_name: string, time: string, enabled: boolean) =>
  apiFetch<ScheduleDTO>(`/api/settings/schedules/${event_name}`, {
    method: 'PATCH',
    body: JSON.stringify({ time, enabled }),
  })

export const addInterest = (key: string) =>
  apiFetch<Record<string, boolean>>(`/api/settings/interests/${key}`, { method: 'POST' })

export const deleteInterest = (key: string) =>
  apiFetch<void>(`/api/settings/interests/${key}`, { method: 'DELETE' })
