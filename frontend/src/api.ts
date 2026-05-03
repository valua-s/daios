import { API_URL } from './config'

export async function apiFetch<T>(path: string, options?: RequestInit, token?: string): Promise<T> {
  let res: Response
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
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
  scheduled_date: string
  scheduled_time: string | null
  source: string | null
  notes: string | null
}

export const getTodayTasks = (token?: string) =>
  apiFetch<TaskDTO[]>('/api/tasks/today', undefined, token)

export const toggleTask = (id: number, token?: string) =>
  apiFetch<TaskDTO>(`/api/tasks/${id}/toggle`, { method: 'PATCH' }, token)

export const moveTaskToBacklog = (id: number, token?: string) =>
  apiFetch<{ ok: boolean }>(`/api/tasks/${id}/backlog`, { method: 'POST' }, token)

export const deleteTask = (id: number, token?: string) =>
  apiFetch<void>(`/api/tasks/${id}`, { method: 'DELETE' }, token)

export const getTasksByRange = (from: string, to: string, token?: string) =>
  apiFetch<TaskDTO[]>(`/api/tasks/range?from=${from}&to=${to}`, undefined, token)

export const updateTask = (id: number, data: {
  title?: string
  scheduled_date?: string
  scheduled_time?: string | null
  notes?: string | null
  clear_time?: boolean
  clear_notes?: boolean
}, token?: string) =>
  apiFetch<TaskDTO>(`/api/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }, token)

// ── Backlog ────────────────────────────────────────────────────────────────

export interface BacklogItemDTO {
  id: number
  title: string
  reason: string | null
  notes: string | null
}

export const getBacklog = (token?: string) =>
  apiFetch<BacklogItemDTO[]>('/api/backlog/', undefined, token)

export const moveBacklogToToday = (id: number, token?: string) =>
  apiFetch<TaskDTO>(`/api/backlog/${id}/today`, { method: 'POST' }, token)

export const deleteBacklogItem = (id: number, token?: string) =>
  apiFetch<void>(`/api/backlog/${id}`, { method: 'DELETE' }, token)

// ── Focus ──────────────────────────────────────────────────────────────────

export interface FocusDTO {
  id: number
  period: string
  period_key: string
  description: string
  is_active: boolean
}

export const getFocus = (token?: string) =>
  apiFetch<{ week: FocusDTO | null; month: FocusDTO | null }>('/api/focus/', undefined, token)

export const setWeekFocus = (description: string, token?: string) =>
  apiFetch<FocusDTO>('/api/focus/week', {
    method: 'PUT',
    body: JSON.stringify({ description }),
  }, token)

export const setMonthFocus = (description: string, token?: string) =>
  apiFetch<FocusDTO>('/api/focus/month', {
    method: 'PUT',
    body: JSON.stringify({ description }),
  }, token)

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

export const getWeekWorkouts = (token?: string) =>
  apiFetch<WorkoutDTO[]>('/api/workouts/week', undefined, token)

// ── Settings ───────────────────────────────────────────────────────────────

export interface ScheduleDTO {
  event_name: string
  cron_expr: string
  enabled: boolean
  description: string
  time: string
  cron_expr_weekend: string | null
  time_weekend: string | null
  supports_weekend: boolean
}

export const getInterests = (token?: string) =>
  apiFetch<Record<string, boolean>>('/api/settings/interests', undefined, token)

export const setInterests = (interests: Record<string, boolean>, token?: string) =>
  apiFetch<Record<string, boolean>>('/api/settings/interests', {
    method: 'POST',
    body: JSON.stringify(interests),
  }, token)

export const getSchedules = (token?: string) =>
  apiFetch<ScheduleDTO[]>('/api/settings/schedules', undefined, token)

export const updateSchedule = (
  event_name: string,
  time: string,
  enabled: boolean,
  token?: string,
  time_weekend?: string | null,
) =>
  apiFetch<ScheduleDTO>(`/api/settings/schedules/${event_name}`, {
    method: 'PATCH',
    body: JSON.stringify({ time, enabled, time_weekend: time_weekend ?? null }),
  }, token)

export const addInterest = (key: string, token?: string) =>
  apiFetch<Record<string, boolean>>(`/api/settings/interests/${key}`, { method: 'POST' }, token)

export const deleteInterest = (key: string, token?: string) =>
  apiFetch<void>(`/api/settings/interests/${key}`, { method: 'DELETE' }, token)

// ── Notes ──────────────────────────────────────────────────────────────────

export interface NoteItemDTO {
  id: number
  note_id: number
  text: string
  checked: boolean
  sort_order: number
}

export interface NoteDTO {
  id: number
  title: string
  body: string | null
  items: NoteItemDTO[]
}

export const getNotes = (token?: string) =>
  apiFetch<NoteDTO[]>('/api/notes/', undefined, token)

export const getNote = (id: number, token?: string) =>
  apiFetch<NoteDTO>(`/api/notes/${id}`, undefined, token)

export const createNote = (title: string, body: string | null, token?: string) =>
  apiFetch<NoteDTO>('/api/notes/', {
    method: 'POST',
    body: JSON.stringify({ title, body }),
  }, token)

export const updateNote = (id: number, data: {
  title?: string
  body?: string | null
  clear_body?: boolean
}, token?: string) =>
  apiFetch<NoteDTO>(`/api/notes/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }, token)

export const deleteNote = (id: number, token?: string) =>
  apiFetch<void>(`/api/notes/${id}`, { method: 'DELETE' }, token)

export const addNoteItem = (noteId: number, text: string, token?: string) =>
  apiFetch<NoteItemDTO>(`/api/notes/${noteId}/items`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  }, token)

export const updateNoteItem = (id: number, data: { text?: string; checked?: boolean }, token?: string) =>
  apiFetch<NoteItemDTO>(`/api/notes/items/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }, token)

export const toggleNoteItem = (id: number, token?: string) =>
  apiFetch<NoteItemDTO>(`/api/notes/items/${id}/toggle`, { method: 'POST' }, token)

export const deleteNoteItem = (id: number, token?: string) =>
  apiFetch<void>(`/api/notes/items/${id}`, { method: 'DELETE' }, token)
