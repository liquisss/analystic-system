/* ── ThesaurusModal.tsx ── */
import { useState, useRef } from 'react'

export interface ThesaurusData {
  [canon: string]: string[]
}

interface ThesaurusModalProps {
  open: boolean
  initial: ThesaurusData | null
  onApply: (data: ThesaurusData | null) => void
  onClose: () => void
}

// ─────────────────────────────────────────────────────────────────────────────
// ВАЛИДАЦИЯ
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Допустимые символы: кириллица, латиница, цифры, пробел внутри фразы, дефис
 * Многословные фразы ("европейский союз") — разрешены
 */
const VALID_TERM_RE = /^[a-zA-Zа-яёА-ЯЁ0-9][a-zA-Zа-яёА-ЯЁ0-9\s\-]*$/

function validateTerm(raw: string): string | null {
  const t = raw.trim()
  if (!t)            return 'пустое значение'
  if (t.length < 2)  return `слишком короткое: "${t}"`
  if (!VALID_TERM_RE.test(t)) return `недопустимые символы: "${t}"`
  return null
}

export interface LineError {
  line: number   // 0 = глобальная ошибка JSON
  text: string
  reason: string
}

interface ParseResult {
  data: ThesaurusData
  errors: LineError[]
}

/**
 * Парсит TXT / ручной ввод.
 * Формат строки: канон: вариант1, вариант2
 * # — комментарий, пустые строки — игнорируются.
 * Поддерживает многословные каноны: "европейский союз: ес, eu"
 * Если канон встречается дважды — варианты объединяются.
 */
export function parseTxt(raw: string): ParseResult {
  const data: ThesaurusData = {}
  const errors: LineError[] = []

  raw.split('\n').forEach((line, idx) => {
    const lineNum = idx + 1
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) return

    const colonIdx = trimmed.indexOf(':')
    if (colonIdx === -1) {
      errors.push({ line: lineNum, text: trimmed, reason: 'нет разделителя ":" между каноном и вариантами' })
      return
    }

    const canonRaw   = trimmed.slice(0, colonIdx).trim().toLowerCase()
    const variantStr = trimmed.slice(colonIdx + 1)

    // Проверяем канон
    const canonErr = validateTerm(canonRaw)
    if (canonErr) { errors.push({ line: lineNum, text: trimmed, reason: `канон — ${canonErr}` }); return }

    // Проверяем что что-то есть после ":"
    if (!variantStr.trim()) {
      errors.push({ line: lineNum, text: trimmed, reason: 'нет вариантов после ":"' }); return
    }

    // Парсим варианты
    const validVariants: string[] = []
    for (const rv of variantStr.split(',')) {
      const v = rv.trim().toLowerCase()
      if (!v) continue  // лишняя запятая
      const varErr = validateTerm(v)
      if (varErr) {
        errors.push({ line: lineNum, text: trimmed, reason: `вариант "${rv.trim()}" — ${varErr}` })
        return
      }
      if (v === canonRaw) {
        errors.push({ line: lineNum, text: trimmed, reason: `вариант "${v}" совпадает с каноном — удалите его` })
        return
      }
      if (!validVariants.includes(v)) validVariants.push(v)
    }

    if (validVariants.length === 0) {
      errors.push({ line: lineNum, text: trimmed, reason: 'нет допустимых вариантов' }); return
    }

    // Дубль канона — мёрджим
    if (data[canonRaw]) {
      data[canonRaw] = Array.from(new Set([...data[canonRaw], ...validVariants]))
    } else {
      data[canonRaw] = validVariants
    }
  })

  return { data, errors }
}

/**
 * Парсит JSON формат: { "канон": ["вариант1", "вариант2"] }
 * Многословные каноны — ключи с пробелами — разрешены.
 */
export function parseJson(raw: string): ParseResult {
  let parsed: unknown
  try { parsed = JSON.parse(raw) }
  catch (e) {
    return { data: {}, errors: [{ line: 0, text: '', reason: `Ошибка разбора JSON: ${(e as Error).message}` }] }
  }

  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return { data: {}, errors: [{ line: 0, text: '', reason: 'JSON должен быть объектом: { "канон": ["вариант1", ...] }' }] }
  }

  const data: ThesaurusData = {}
  const errors: LineError[] = []
  let idx = 1

  for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
    const canonRaw = k.toLowerCase().trim()
    const canonErr = validateTerm(canonRaw)
    if (canonErr) { errors.push({ line: idx, text: k, reason: `ключ — ${canonErr}` }); idx++; continue }

    if (!Array.isArray(v)) {
      errors.push({ line: idx, text: k, reason: `значение должно быть массивом строк, например ["вариант1", "вариант2"]` }); idx++; continue
    }

    const validVariants: string[] = []
    let hasErr = false
    for (const item of v) {
      if (typeof item !== 'string') {
        errors.push({ line: idx, text: k, reason: `элемент массива ${JSON.stringify(item)} должен быть строкой` }); hasErr = true; break
      }
      const vv = item.toLowerCase().trim()
      const varErr = validateTerm(vv)
      if (varErr) { errors.push({ line: idx, text: k, reason: `вариант "${item}" — ${varErr}` }); hasErr = true; break }
      if (vv === canonRaw) { errors.push({ line: idx, text: k, reason: `вариант "${vv}" совпадает с каноном` }); hasErr = true; break }
      if (!validVariants.includes(vv)) validVariants.push(vv)
    }

    if (!hasErr) {
      if (validVariants.length === 0) errors.push({ line: idx, text: k, reason: 'нет допустимых вариантов' })
      else data[canonRaw] = validVariants
    }
    idx++
  }

  return { data, errors }
}

// ─────────────────────────────────────────────────────────────────────────────
// SVG ИКОНКИ (независимые от Icon.tsx)
// ─────────────────────────────────────────────────────────────────────────────

const BookIcon = ({ size = 16, color = 'currentColor' }: { size?: number; color?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
  </svg>
)

const InfoIcon = ({ size = 14, color = 'currentColor' }: { size?: number; color?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="8" x2="12" y2="8" strokeWidth="3" strokeLinecap="round" />
    <line x1="12" y1="12" x2="12" y2="16" />
  </svg>
)

const XIcon = ({ size = 16, color = 'currentColor' }: { size?: number; color?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
  </svg>
)

const UploadIcon = ({ size = 24, color = 'currentColor' }: { size?: number; color?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="16 16 12 12 8 16" />
    <line x1="12" y1="12" x2="12" y2="21" />
    <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
  </svg>
)

// ─────────────────────────────────────────────────────────────────────────────

const MANUAL_PLACEHOLDER =
`# Однословный канон
евросоюз: ес, eu, европейский союз

# Многословный канон — тоже работает
искусственный интеллект: ии, ai, нейросеть

# Комментарии начинаются с #
санкции: embargo, ограничения, рестрикции`

// ─────────────────────────────────────────────────────────────────────────────
// КОМПОНЕНТ
// ─────────────────────────────────────────────────────────────────────────────

const ThesaurusModal = ({ open, initial, onApply, onClose }: ThesaurusModalProps) => {
  const [tab, setTab] = useState<'manual' | 'file'>('manual')

  // Ручной ввод
  const [manualText, setManualText] = useState<string>(() =>
    initial ? Object.entries(initial).map(([k, v]) => `${k}: ${v.join(', ')}`).join('\n') : ''
  )
  const [manualErrors, setManualErrors] = useState<LineError[]>([])

  // Файл
  const [fileData, setFileData]     = useState<ThesaurusData | null>(null)
  const [fileName, setFileName]     = useState('')
  const [fileErrors, setFileErrors] = useState<LineError[]>([])
  const [dragOver, setDragOver]     = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [hintOpen, setHintOpen] = useState(false)

  if (!open) return null

  // ── Live-превью для ручного ввода ──
  const liveResult = tab === 'manual' && manualText.trim() ? parseTxt(manualText) : null

  const previewData: ThesaurusData | null =
    tab === 'file' ? fileData :
    liveResult && liveResult.errors.length === 0 ? liveResult.data : null

  const totalEntries  = previewData ? Object.keys(previewData).length : 0
  const totalVariants = previewData ? Object.values(previewData).reduce((s, v) => s + v.length, 0) : 0

  // Ошибки для текущей вкладки
  const currentErrors = tab === 'manual'
    ? (manualErrors.length > 0 ? manualErrors : (liveResult?.errors ?? []))
    : fileErrors
  const hasErrors = currentErrors.length > 0

  // ── Загрузка файла ──
  const handleFile = (file: File) => {
    if (!file.name.endsWith('.json') && !file.name.endsWith('.txt')) {
      setFileErrors([{ line: 0, text: '', reason: 'Поддерживаются только .json и .txt' }])
      return
    }
    setFileName(file.name)
    setFileData(null)
    setFileErrors([])
    const reader = new FileReader()
    reader.onload = e => {
      const raw = e.target?.result as string
      const result = file.name.endsWith('.json') ? parseJson(raw) : parseTxt(raw)
      setFileErrors(result.errors)
      setFileData(result.errors.length === 0 && Object.keys(result.data).length > 0 ? result.data : null)
    }
    reader.readAsText(file, 'utf-8')
  }

  // ── Применить ──
  const handleApply = () => {
    if (tab === 'manual') {
      if (!manualText.trim()) { onApply(null); onClose(); return }
      const { data, errors } = parseTxt(manualText)
      if (errors.length > 0) { setManualErrors(errors); return }
      setManualErrors([])
      onApply(Object.keys(data).length > 0 ? data : null)
    } else {
      if (fileErrors.length > 0) return
      onApply(fileData)
    }
    onClose()
  }

  const handleClear = () => {
    setManualText(''); setManualErrors([])
    setFileData(null); setFileName(''); setFileErrors([])
    onApply(null); onClose()
  }

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        animation: 'fadeIn .15s ease'
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="card" style={{
        width: 600, maxHeight: '90vh', display: 'flex', flexDirection: 'column',
        padding: 0, overflow: 'hidden',
        border: '1px solid var(--border-hi)',
        boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
        animation: 'slideUp .2s ease'
      }}>

        {/* ── HEADER ── */}
        <div style={{
          padding: '20px 24px 16px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'flex-start', gap: 12
        }}>
          <div style={{
            width: 38, height: 38, borderRadius: 10, flexShrink: 0,
            background: 'var(--cyan-dim)', border: '1px solid var(--border-hi)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <BookIcon size={18} color="var(--cyan)" />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-hi)', margin: 0 }}>
                Тезаурус синонимов
              </h2>
              <button
                onClick={() => setHintOpen(h => !h)}
                style={{
                  background: 'var(--bg-deep)', border: '1px solid var(--border)',
                  borderRadius: 20, padding: '2px 9px', cursor: 'pointer', fontSize: 11,
                  color: 'var(--text-mid)', display: 'flex', alignItems: 'center', gap: 4,
                  transition: 'border-color .15s'
                }}
                onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--cyan)')}
                onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
              >
                <InfoIcon size={11} color="var(--text-mid)" />
                Что это?
              </button>
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-mid)', marginTop: 3, marginBottom: 0 }}>
              Необязательно · объединяет синонимы перед анализом в Natasha
            </p>
          </div>
          <button onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-lo)', padding: 4 }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-hi)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-lo)')}>
            <XIcon size={18} />
          </button>
        </div>

        {/* ── HINT ── */}
        {hintOpen && (
          <div style={{
            margin: '12px 24px 0', padding: '12px 14px',
            background: 'rgba(0,188,212,.06)', border: '1px solid rgba(0,188,212,.25)',
            borderRadius: 8, fontSize: 13, color: 'var(--text-mid)', lineHeight: 1.65
          }}>
            <strong style={{ color: 'var(--cyan)', display: 'block', marginBottom: 6 }}>
              Зачем нужен тезаурус?
            </strong>
            Без него <code style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-hi)' }}>«ЕС»</code>,{' '}
            <code style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-hi)' }}>«Евросоюз»</code> и{' '}
            <code style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-hi)' }}>«Европейский союз»</code>{' '}
            попадут в <em>разные</em> темы — система не знает, что это одно понятие.
            Тезаурус задаёт <strong style={{ color: 'var(--text-hi)' }}>каноническую форму</strong> и список синонимов:
            при обработке все варианты заменятся на канон <em>до</em> передачи в BERTopic.
            <br />
            <br />
            Поддерживаются <strong style={{ color: 'var(--text-hi)' }}>многословные каноны</strong>:{' '}
            <code style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--cyan)' }}>искусственный интеллект: ии, ai</code>
            {' '}— фраза целиком станет одним токеном.
          </div>
        )}

        {/* ── TABS ── */}
        <div style={{ padding: '14px 24px 0', display: 'flex', gap: 4 }}>
          {(['manual', 'file'] as const).map(t => (
            <button key={t} onClick={() => { setTab(t); setManualErrors([]) }}
              style={{
                padding: '7px 16px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                cursor: 'pointer', transition: 'all .15s',
                border: tab === t ? '1px solid var(--cyan)' : '1px solid var(--border)',
                background: tab === t ? 'var(--cyan-dim)' : 'transparent',
                color: tab === t ? 'var(--cyan)' : 'var(--text-mid)'
              }}>
              {t === 'manual' ? '✏️  Ввести вручную' : '📂  Загрузить файл'}
            </button>
          ))}
        </div>

        {/* ── BODY ── */}
        <div style={{ padding: '16px 24px', overflowY: 'auto', flex: 1 }}>

          {/* ─── TAB: MANUAL ─── */}
          {tab === 'manual' && (
            <>
              {/* Подсказка по формату */}
              <div style={{
                marginBottom: 8, padding: '8px 12px',
                background: 'var(--bg-deep)', borderRadius: 7,
                border: '1px solid var(--border)',
                display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', fontSize: 11
              }}>
                <span style={{ color: 'var(--text-lo)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', flexShrink: 0 }}>
                  Формат:
                </span>
                <code style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)', fontSize: 12 }}>канон: вариант1, вариант2</code>
                <span style={{ color: 'var(--border)', flexShrink: 0 }}>│</span>
                <code style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)', fontSize: 12 }}>европейский союз: ес, eu</code>
                <span style={{ color: 'var(--text-lo)', marginLeft: 'auto', flexShrink: 0 }}>строки с # — комментарии</span>
              </div>

              <textarea
                value={manualText}
                onChange={e => { setManualText(e.target.value); setManualErrors([]) }}
                placeholder={MANUAL_PLACEHOLDER}
                spellCheck={false}
                style={{
                  width: '100%', height: 200, resize: 'vertical', boxSizing: 'border-box',
                  background: 'var(--bg-deep)',
                  border: `1px solid ${currentErrors.length > 0 ? 'var(--red)' : 'var(--border)'}`,
                  borderRadius: 8, padding: '12px 14px',
                  fontFamily: 'var(--mono)', fontSize: 12.5,
                  color: 'var(--text-hi)', lineHeight: 1.75,
                  outline: 'none', transition: 'border-color .15s'
                }}
                onFocus={e => (e.target.style.borderColor = 'var(--cyan)')}
                onBlur={e => (e.target.style.borderColor = currentErrors.length > 0 ? 'var(--red)' : 'var(--border)')}
              />
            </>
          )}

          {/* ─── TAB: FILE ─── */}
          {tab === 'file' && (
            <>
              <input ref={fileInputRef} type="file" accept=".json,.txt" style={{ display: 'none' }}
                onChange={e => { if (e.target.files?.[0]) handleFile(e.target.files[0]) }} />

              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={e => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]) }}
                style={{
                  border: `2px dashed ${dragOver ? 'var(--cyan)' : 'var(--border)'}`,
                  borderRadius: 10, padding: '24px 20px', textAlign: 'center',
                  cursor: 'pointer', transition: 'all .2s',
                  background: dragOver ? 'var(--cyan-dim)' : 'var(--bg-deep)'
                }}>
                <UploadIcon size={22} color={dragOver ? 'var(--cyan)' : 'var(--text-lo)'} />
                <p style={{ marginTop: 8, fontSize: 13, color: 'var(--text-mid)', fontWeight: 600 }}>
                  Перетащите файл или нажмите
                </p>
                <p style={{ fontSize: 11, color: 'var(--text-lo)', marginTop: 4 }}>
                  <code style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)' }}>.json</code>
                  {'  ·  '}
                  <code style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)' }}>.txt</code>
                </p>
              </div>

              {/* Примеры форматов */}
              <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {[
                  {
                    label: 'JSON формат', color: 'var(--amber)',
                    code: `{\n  "евросоюз": ["ес","eu"],\n  "искусственный интеллект":\n    ["ии","ai","нейросеть"]\n}`
                  },
                  {
                    label: 'TXT формат', color: 'var(--green)',
                    code: `# комментарий\nевросоюз: ес, eu\nискусственный интеллект:\n  ии, ai, нейросеть`
                  }
                ].map(ex => (
                  <div key={ex.label} style={{
                    background: 'var(--bg-deep)', borderRadius: 7,
                    border: '1px solid var(--border)', padding: '10px 12px'
                  }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: ex.color, marginBottom: 6 }}>{ex.label}</div>
                    <pre style={{
                      margin: 0, fontSize: 10.5, fontFamily: 'var(--mono)',
                      color: 'var(--text-mid)', whiteSpace: 'pre-wrap', lineHeight: 1.6
                    }}>{ex.code}</pre>
                  </div>
                ))}
              </div>

              {fileName && (
                <div style={{
                  marginTop: 12, display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 12px', background: 'var(--bg-deep)', borderRadius: 7,
                  border: `1px solid ${fileErrors.length > 0 ? 'var(--red)' : 'var(--cyan)'}`
                }}>
                  <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--text-hi)', flex: 1 }}>
                    {fileErrors.length > 0 ? '⚠' : '✓'} {fileName}
                  </span>
                  <button onClick={() => { setFileData(null); setFileName(''); setFileErrors([]) }}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-lo)', padding: 2 }}>
                    <XIcon size={12} />
                  </button>
                </div>
              )}
            </>
          )}

          {/* ── БЛОК ОШИБОК ── */}
          {hasErrors && (
            <div style={{
              marginTop: 12, padding: '10px 14px',
              background: 'rgba(239,68,68,.07)', borderRadius: 7,
              border: '1px solid rgba(239,68,68,.3)',
              maxHeight: 150, overflowY: 'auto'
            }}>
              <div style={{
                fontSize: 11, fontWeight: 700, color: 'var(--red)',
                marginBottom: 6, textTransform: 'uppercase', letterSpacing: '.05em'
              }}>
                Ошибки формата · {currentErrors.length}
              </div>
              {currentErrors.map((err, i) => (
                <div key={i} style={{
                  fontSize: 11.5, fontFamily: 'var(--mono)', color: 'var(--text-mid)',
                  padding: '3px 0',
                  borderBottom: i < currentErrors.length - 1 ? '1px solid rgba(239,68,68,.1)' : 'none',
                  display: 'flex', gap: 8, alignItems: 'baseline'
                }}>
                  {err.line > 0 && (
                    <span style={{ color: 'var(--red)', minWidth: 60, flexShrink: 0, fontSize: 11 }}>
                      строка {err.line}
                    </span>
                  )}
                  <span style={{ color: '#f87171' }}>{err.reason}</span>
                </div>
              ))}
            </div>
          )}

          {/* ── PREVIEW ── */}
          {previewData && totalEntries > 0 && (
            <div style={{ marginTop: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <span style={{
                  fontSize: 11, fontWeight: 700, color: 'var(--text-mid)',
                  textTransform: 'uppercase', letterSpacing: '.06em'
                }}>Предпросмотр</span>
                <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--cyan)' }}>
                  {totalEntries} {totalEntries === 1 ? 'запись' : totalEntries < 5 ? 'записи' : 'записей'} · {totalVariants} вариантов
                </span>
              </div>
              <div style={{
                maxHeight: 170, overflowY: 'auto',
                background: 'var(--bg-deep)', borderRadius: 8, border: '1px solid var(--border)'
              }}>
                {Object.entries(previewData).map(([canon, variants], i, arr) => (
                  <div key={canon} style={{
                    display: 'grid', gridTemplateColumns: '190px auto',
                    gap: 8, padding: '6px 14px', alignItems: 'center',
                    borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none'
                  }}>
                    <span style={{
                      fontFamily: 'var(--mono)', color: 'var(--cyan)', fontWeight: 700, fontSize: 12,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                    }} title={canon}>{canon}</span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {variants.map(v => (
                        <span key={v} style={{
                          fontSize: 10.5, fontFamily: 'var(--mono)', color: 'var(--text-mid)',
                          background: 'var(--bg-card)', borderRadius: 4, padding: '1px 6px',
                          border: '1px solid var(--border)'
                        }}>{v}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── FOOTER ── */}
        <div style={{
          padding: '14px 24px', borderTop: '1px solid var(--border)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center'
        }}>
          <button onClick={handleClear} className="btn btn-ghost"
            style={{ fontSize: 12, padding: '7px 14px', color: 'var(--red)' }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--red)')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}>
            Сбросить
          </button>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={onClose} className="btn btn-ghost" style={{ fontSize: 12, padding: '7px 16px' }}>
              Отмена
            </button>
            <button
              onClick={handleApply}
              className="btn btn-primary"
              style={{ fontSize: 12, padding: '7px 22px', opacity: hasErrors ? 0.5 : 1, cursor: hasErrors ? 'not-allowed' : 'pointer' }}
              disabled={hasErrors}>
              Применить
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ThesaurusModal
