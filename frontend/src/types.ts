export type SpaceStatus = 'interviewing' | 'generating' | 'ready'

export interface SpaceSummary {
  id: string
  name: string
  status: SpaceStatus
  created_at: string
  source_count: number
  artifact_count: number
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
}

export type ArtifactKind = 'study_plan' | 'notes' | 'sample_test'

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
