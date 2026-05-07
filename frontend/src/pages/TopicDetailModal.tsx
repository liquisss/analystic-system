import { useState, useMemo } from 'react'
import Icon from '../components/Icon'
import type { TopicResult, DocTopic } from '../App'

// ── Типы ──────────────────────────────────────────────────────────────────

export interface NerEntity {
  text: string
  type: 'ORG' | 'PER' | 'LOC' | string
}

export interface ProcessedDocument {
  name:           string
  title?:         string    // ← добавить
  reg_number?:    string    // ← добавить
  tokens:         string[]
  lemmas:         string[]
  entities:       NerEntity[]
  dates:          any[]
  text_clean:     string
  chunks_count:   number
  tokens_count:   number
}

interface TopicDetailModalProps {
  topic:       TopicResult
  docTopics:   DocTopic[]             // из btResult.doc_topics
  natashaDocs: ProcessedDocument[]    // из processed.json / natasha_data.documents
  onClose:     () => void
}

// ── Цвета и лейблы для типов NER ──────────────────────────────────────────

const NER_CONFIG: Record<string, { label: string; bg: string; text: string }> = {
  ORG: { label: 'ORG',  bg: 'rgba(0,212,255,.15)',   text: 'var(--cyan)'  },
  PER: { label: 'PER',  bg: 'rgba(167,139,250,.18)',  text: '#a78bfa'      },
  LOC: { label: 'LOC',  bg: 'rgba(52,211,153,.15)',   text: 'var(--green)' },
}

const nerStyle = (type: string) =>
  NER_CONFIG[type] ?? { label: type, bg: 'rgba(156,163,175,.15)', text: 'var(--text-mid)' }

// ── Вспомогательный компонент: бейдж NER ──────────────────────────────────

const NerBadge = ({ entity }: { entity: NerEntity }) => {
  const cfg = nerStyle(entity.type)
  return (
    <span style={{
      display:       'inline-flex',
      alignItems:    'center',
      gap:           4,
      padding:       '2px 7px',
      borderRadius:  4,
      background:    cfg.bg,
      fontSize:      11,
      color:         cfg.text,
      fontFamily:    'var(--mono)',
      whiteSpace:    'nowrap',
    }}>
      <span style={{ opacity: .6, fontSize: 9, fontWeight: 700 }}>{cfg.label}</span>
      {entity.text}
    </span>
  )
}

// ── Вспомогательный компонент: строка документа ───────────────────────────

const DocRow = ({ doc, natasha, defaultOpen }: {
  doc:         DocTopic
  natasha:     ProcessedDocument | undefined
  defaultOpen: boolean
}) => {
  const [open, setOpen] = useState(defaultOpen)

  // Группируем entities по типу, дедуплицируем по text
  const grouped = useMemo(() => {
    if (!natasha?.entities?.length) return {}
    const seen = new Set<string>()
    const out: Record<string, NerEntity[]> = {}
    for (const e of natasha.entities) {
      const key = `${e.type}::${e.text.toLowerCase()}`
      if (seen.has(key)) continue
      seen.add(key)
      if (!out[e.type]) out[e.type] = []
      out[e.type].push(e)
    }
    return out
  }, [natasha])

  const hasEntities = Object.keys(grouped).length > 0
  const fileName    = doc.name.replace(/\.[^.]+$/, '') // убираем расширение для отображения

  return (
    <div style={{
      border:       '1px solid var(--border)',
      borderRadius: 8,
      overflow:     'hidden',
      transition:   'border-color .15s',
    }}>
      {/* Заголовок строки — кликабельный */}
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          display:    'flex',
          alignItems: 'center',
          gap:        10,
          padding:    '10px 14px',
          cursor:     'pointer',
          background: open ? 'var(--bg-card)' : 'transparent',
          userSelect: 'none',
        }}
      >
        {/* Иконка разворачивания */}
        <span style={{
          fontSize:   12,
          color:      'var(--text-lo)',
          transition: 'transform .2s',
          transform:  open ? 'rotate(90deg)' : 'rotate(0deg)',
          flexShrink: 0,
        }}>▶</span>

        {/* Имя файла */}
        <span style={{
          flex: 1, fontSize: 12, fontWeight: 600,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }} title={natasha?.title ?? doc.name}>
          {natasha?.reg_number && (
            <span style={{ fontSize: 9, color: 'var(--text-lo)', fontFamily: 'var(--mono)', marginRight: 6 }}>
              {natasha.reg_number}
            </span>
          )}
          {natasha?.title ?? doc.name.replace(/\.[^.]+$/, '')}
        </span>

        {/* Метрики справа */}
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          {natasha && (
            <span style={{ fontSize: 10, color: 'var(--text-lo)', fontFamily: 'var(--mono)' }}>
              {natasha.tokens_count} токенов
            </span>
          )}
          {hasEntities && (
            <span style={{
              fontSize:   10,
              color:      'var(--cyan)',
              fontFamily: 'var(--mono)',
              background: 'rgba(0,212,255,.1)',
              padding:    '1px 6px',
              borderRadius: 4,
            }}>
              {natasha!.entities.length} NER
            </span>
          )}
          {doc.date && (
            <span style={{
              fontSize:   10,
              color:      'var(--amber)',
              fontFamily: 'var(--mono)',
              background: 'rgba(245,158,11,.1)',
              padding:    '1px 6px',
              borderRadius: 4,
            }}>
              {doc.date}
            </span>
          )}
        </div>
      </div>

      {/* Раскрытая панель с NER */}
      {open && (
        <div style={{
          padding:    '10px 14px 14px',
          borderTop:  '1px solid var(--border)',
          background: 'var(--bg-deep)',
        }}>
          {!natasha ? (
            <p style={{ fontSize: 11, color: 'var(--text-lo)', fontStyle: 'italic' }}>
              Данные Natasha для этого документа не найдены
            </p>
          ) : !hasEntities ? (
            <p style={{ fontSize: 11, color: 'var(--text-lo)', fontStyle: 'italic' }}>
              Именованные сущности не обнаружены
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {/* Каждый тип NER — отдельная строка */}
              {(['PER', 'ORG', 'LOC'] as const).map(type => {
                const items = grouped[type]
                if (!items?.length) return null
                return (
                  <div key={type} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                    {/* Лейбл типа */}
                    <span style={{
                      fontSize:     10,
                      fontWeight:   700,
                      fontFamily:   'var(--mono)',
                      color:        nerStyle(type).text,
                      minWidth:     28,
                      paddingTop:   3,
                      flexShrink:   0,
                    }}>
                      {type}
                    </span>
                    {/* Бейджи */}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                      {items.map((e, i) => <NerBadge key={i} entity={e} />)}
                    </div>
                  </div>
                )
              })}
              {/* Остальные типы если есть */}
              {Object.entries(grouped)
                .filter(([t]) => !['PER', 'ORG', 'LOC'].includes(t))
                .map(([type, items]) => (
                  <div key={type} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700, fontFamily: 'var(--mono)',
                      color: nerStyle(type).text, minWidth: 28, paddingTop: 3, flexShrink: 0,
                    }}>{type}</span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                      {items.map((e, i) => <NerBadge key={i} entity={e} />)}
                    </div>
                  </div>
                ))
              }
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Главный компонент модального окна ─────────────────────────────────────

const TOPIC_COLORS = [
  '#00d4ff', '#f59e0b', '#10b981', '#a78bfa',
  '#f87171', '#34d399', '#60a5fa', '#f472b6',
  '#fb923c', '#a3e635',
]

export const TopicDetailModal = ({
  topic, docTopics, natashaDocs, onClose,
}: TopicDetailModalProps) => {

  const [nerFilter, setNerFilter] = useState<'ALL' | 'ORG' | 'PER' | 'LOC'>('ALL')
  const [searchQuery, setSearchQuery] = useState('')

  // Документы, принадлежащие этой теме
  const topicDocs = useMemo(
    () => docTopics.filter(d => d.topic === topic.id),
    [docTopics, topic.id]
  )

  // Индекс Natasha по имени файла для быстрого поиска
  const natashaIndex = useMemo(() => {
    const idx: Record<string, ProcessedDocument> = {}
    for (const d of natashaDocs) idx[d.name] = d
    return idx
  }, [natashaDocs])

  // Фильтрация документов по поиску и NER-типу
  const filteredDocs = useMemo(() => {
    return topicDocs.filter(doc => {
      // Поиск по имени
      if (searchQuery && !doc.name.toLowerCase().includes(searchQuery.toLowerCase())) {
        const nd = natashaIndex[doc.name]
        if (!nd) return false
        // Ищем ещё по тексту NER entities
        const nerText = nd.entities.map(e => e.text).join(' ').toLowerCase()
        if (!nerText.includes(searchQuery.toLowerCase())) return false
      }
      // Фильтр по NER-типу
      if (nerFilter !== 'ALL') {
        const nd = natashaIndex[doc.name]
        if (!nd?.entities?.some(e => e.type === nerFilter)) return false
      }
      return true
    })
  }, [topicDocs, searchQuery, nerFilter, natashaIndex])

  // Топ NER по всем документам темы (для сводки)
  const topicNerSummary = useMemo(() => {
    const freq: Record<string, { entity: NerEntity; count: number }> = {}
    for (const doc of topicDocs) {
      const nd = natashaIndex[doc.name]
      if (!nd) continue
      const seen = new Set<string>()
      for (const e of nd.entities) {
        const key = `${e.type}::${e.text}`
        if (seen.has(key)) continue
        seen.add(key)
        if (!freq[key]) freq[key] = { entity: e, count: 0 }
        freq[key].count++
      }
    }
    return Object.values(freq)
      .sort((a, b) => b.count - a.count)
      .slice(0, 12)
  }, [topicDocs, natashaIndex])

  // Индекс цвета темы (по id)
  const colorIdx  = topic.id % TOPIC_COLORS.length
  const topicColor = TOPIC_COLORS[colorIdx]

  // Количество документов с каждым NER-типом
  const nerCounts = useMemo(() => {
    const counts: Record<string, number> = { ORG: 0, PER: 0, LOC: 0 }
    for (const doc of topicDocs) {
      const nd = natashaIndex[doc.name]
      if (!nd) continue
      const types = new Set(nd.entities.map(e => e.type))
      for (const t of types) if (t in counts) counts[t]++
    }
    return counts
  }, [topicDocs, natashaIndex])

  return (
    <div
      className="modal-overlay"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="modal" style={{ maxWidth: 740, width: '100%', maxHeight: '88vh', display: 'flex', flexDirection: 'column' }}>

        {/* ── Шапка ── */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 12, height: 12, borderRadius: '50%',
              background: topicColor, flexShrink: 0, marginTop: 2,
            }} />
            <div>
              <h3 style={{ fontSize: 17, fontWeight: 800, marginBottom: 2 }}>
                {topic.label}
              </h3>
              <div style={{ fontSize: 11, color: 'var(--text-lo)', fontFamily: 'var(--mono)' }}>
                Тема #{topic.id} · {topic.count} документов
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-mid)', padding: 4, flexShrink: 0 }}
          >
            <Icon name="close" size={18} />
          </button>
        </div>

        {/* ── Скроллируемое тело ── */}
        <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Ключевые слова с scores */}
          <div style={{
            background:   'var(--bg-deep)',
            border:       '1px solid var(--border)',
            borderRadius: 8,
            padding:      '12px 14px',
          }}>
            <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-lo)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 10 }}>
              Ключевые слова · BERTopic
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {topic.words.map((word, i) => {
                const score   = topic.scores[i] ?? 0
                const maxScore = topic.scores[0] ?? 1
                const pct     = maxScore > 0 ? (score / maxScore) * 100 : 0
                return (
                  <div key={word} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    {/* Ранг */}
                    <span style={{ fontSize: 10, color: 'var(--text-lo)', fontFamily: 'var(--mono)', minWidth: 18, textAlign: 'right' }}>
                      #{i + 1}
                    </span>
                    {/* Слово */}
                    <span style={{ fontSize: 12, fontWeight: 600, minWidth: 130 }}>{word}</span>
                    {/* Прогресс-бар */}
                    <div style={{ flex: 1, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{
                        height:     '100%',
                        width:      `${pct}%`,
                        background: `linear-gradient(90deg, ${topicColor}, ${topicColor}88)`,
                        borderRadius: 2,
                        transition: 'width .3s ease',
                      }} />
                    </div>
                    {/* Score */}
                    <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text-mid)', minWidth: 48, textAlign: 'right' }}>
                      {score.toFixed(4)}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Сводка NER по теме */}
          {topicNerSummary.length > 0 && (
            <div style={{
              background:   'var(--bg-deep)',
              border:       '1px solid var(--border)',
              borderRadius: 8,
              padding:      '12px 14px',
            }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-lo)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 10 }}>
                Частые сущности по теме
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {topicNerSummary.map(({ entity, count }) => (
                  <span key={`${entity.type}::${entity.text}`} style={{
                    display:      'inline-flex',
                    alignItems:   'center',
                    gap:          5,
                    padding:      '3px 8px',
                    borderRadius: 5,
                    background:   nerStyle(entity.type).bg,
                    fontSize:     11,
                    color:        nerStyle(entity.type).text,
                    fontFamily:   'var(--mono)',
                  }}>
                    <span style={{ opacity: .55, fontSize: 9, fontWeight: 700 }}>{entity.type}</span>
                    {entity.text}
                    {count > 1 && (
                      <span style={{ opacity: .7, fontSize: 9 }}>×{count}</span>
                    )}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Панель фильтров документов */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
            {/* Поиск */}
            <div style={{ flex: 1, position: 'relative' }}>
              <input
                className="field-input"
                placeholder="Поиск по имени файла или NER..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{ width: '100%', paddingLeft: 30, fontSize: 12, boxSizing: 'border-box' }}
              />
              <span style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', opacity: .4, fontSize: 13 }}>🔍</span>
            </div>

            {/* NER-фильтры */}
            {(['ALL', 'ORG', 'PER', 'LOC'] as const).map(type => (
              <button
                key={type}
                onClick={() => setNerFilter(type)}
                style={{
                  padding:      '5px 10px',
                  borderRadius: 6,
                  border:       `1px solid ${nerFilter === type ? (type === 'ALL' ? 'var(--border-hi)' : nerStyle(type).text) : 'var(--border)'}`,
                  background:   nerFilter === type ? (type === 'ALL' ? 'var(--bg-card)' : nerStyle(type).bg) : 'transparent',
                  color:        type === 'ALL' ? 'var(--text-mid)' : nerStyle(type).text,
                  fontSize:     11,
                  fontFamily:   'var(--mono)',
                  fontWeight:   600,
                  cursor:       'pointer',
                  transition:   'all .15s',
                  whiteSpace:   'nowrap',
                }}
              >
                {type === 'ALL'
                  ? `Все (${topicDocs.length})`
                  : `${type} (${nerCounts[type] ?? 0})`
                }
              </button>
            ))}
          </div>

          {/* Список документов */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-lo)', textTransform: 'uppercase', letterSpacing: '.06em' }}>
              Документы темы · {filteredDocs.length} из {topicDocs.length}
            </p>

            {filteredDocs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-lo)', fontSize: 12 }}>
                Нет документов по выбранному фильтру
              </div>
            ) : (
              filteredDocs.map((doc, i) => (
                <DocRow
                  key={doc.name}
                  doc={doc}
                  natasha={natashaIndex[doc.name]}
                  defaultOpen={filteredDocs.length <= 3 && i === 0}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default TopicDetailModal
