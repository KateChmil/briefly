export type SpaceStatus = 'interviewing' | 'generating' | 'ready'

export interface SpaceSummary {
  id: string
  name: string
  status: SpaceStatus
  created_at: string
  source_count: number
  artifact_count: number
  exam_date: string | null
  sessions_total: number
  sessions_done: number
}

export interface Source {
  id: string
  origin: 'upload' | 'teams'
  filename: string
  mime_type: string
  teams_ref: { file_id?: string } | null
  created_at: string
}

export interface SpaceDetail {
  id: string
  name: string
  status: SpaceStatus
  profile: Record<string, unknown> | null
  exam_date: string | null
  created_at: string
  sources: Source[]
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ChatResponse {
  message: ChatMessage
  space_status: SpaceStatus
  profile_completed: boolean
  plan_updating: boolean
}

export type ArtifactKind = 'study_plan' | 'notes' | 'sample_test' | 'flashcards'

export interface Artifact {
  id: number
  kind: ArtifactKind
  format: 'markdown' | 'json'
  content: string
  version: number
  created_at: string
}

export interface TeamsItem {
  id: string
  name: string
}

export interface ImportResult {
  imported: Source[]
  skipped: { file_id: string; reason: string }[]
}

export interface QuizQuestion {
  type: 'mcq' | 'short'
  question: string
  choices?: string[]
  answer: string
  explanation: string
}

export interface Quiz {
  title: string
  questions: QuizQuestion[]
}

export interface Flashcard {
  front: string
  back: string
}

export type SessionKind = 'study' | 'review' | 'practice' | 'mock_exam'

export interface StudySession {
  id: number
  space_id: string
  date: string
  title: string
  topic: string
  minutes: number
  kind: SessionKind
  done: boolean
}

export interface PlanContent {
  overview: string
  sessions: { date: string; title: string; topic?: string; minutes: number; kind: SessionKind }[]
}

export type EventKind = 'class' | 'exam' | 'other'

export interface CalendarItem {
  id: string
  type: 'event' | 'session' | 'exam'
  date: string
  start_time: string | null
  end_time: string | null
  title: string
  kind: string
  space_id: string | null
  space_name: string | null
  done: boolean | null
  minutes: number | null
  topic: string | null
  deletable: boolean
}

export interface NewEvent {
  title: string
  date: string
  start_time?: string | null
  end_time?: string | null
  kind: EventKind
  space_id?: string | null
  description?: string
}

export interface CalendarImportResult {
  imported: number
  skipped: number
}

export interface UserNote {
  id: number
  space_id: string
  title: string
  content: string
  created_at: string
  updated_at: string
}

export type NoteAction =
  | 'summarize'
  | 'key_terms'
  | 'simplify'
  | 'improve'
  | 'quiz_me'
  | 'flashcards'

export interface NoteEnhanceResult {
  result: string
  cards?: Flashcard[] | null
}
