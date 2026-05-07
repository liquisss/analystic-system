import { useState, useMemo, useRef } from 'react'
import type { BertopicResult, TopicResult } from '../App'
import type { ProcessedDocument, NerEntity } from './TopicDetailModal'
import type { DocTopic } from '../App'

const TOPIC_COLORS = [
  '#e8413b', '#177dbe', '#0ea54b', '#fc8c00',
  '#8e409a', '#cc0e74', '#b8b008', '#00aba5',
  '#6d3f1f', '#5b5b5b',
]

const NER_CONFIG: Record<string, { label: string; color: string }> = {
  ORG: { label: 'ORG', color: '#00aba5' },
  PER: { label: 'PER', color: '#a78bfa' },
  LOC: { label: 'LOC', color: '#0ea54b' },
}

interface DocDetailPanelProps {
  docName:     string
  docTopic:    DocTopic | null
  topic:       TopicResult | null
  topicIdx:    number
  natasha:     ProcessedDocument | undefined
  onClose:     () => void
}

const DocDetailPanel = ({ docName, docTopic, topic, topicIdx, natasha, onClose }: DocDetailPanelProps) => {
  const color   = topic ? TOPIC_COLORS[topicIdx % TOPIC_COLORS.length] : '#5b5b5b'
  const isNoise = docTopic?.topic === -1

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

  return (
    <div style={{
      width: 280, flexShrink: 0,
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      padding: '16px 14px',
      display: 'flex', flexDirection: 'column', gap: 12,
      maxHeight: 500, overflowY: 'auto',
    }}>
      {/* Шапка */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          {natasha?.reg_number && (
            <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--text-lo)', marginBottom: 3 }}>
              {natasha.reg_number}
            </div>
          )}
          <div style={{ fontSize: 12, fontWeight: 700, wordBreak: 'break-word', marginBottom: 4 }}>
            {natasha?.title ?? docName.replace(/\.[^.]+$/, '')}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-lo)', fontFamily: 'var(--mono)' }}>
            {natasha?.tokens_count ?? '—'} токенов
          </div>
        </div>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--text-lo)', fontSize: 16, lineHeight: 1, flexShrink: 0, padding: '0 0 0 8px',
        }}>×</button>
      </div>

      {/* Тема */}
      <div style={{
        padding: '8px 10px',
        background: 'var(--bg-deep)',
        border: `1px solid ${color}44`,
        borderRadius: 7,
      }}>
        <div style={{ fontSize: 10, color: 'var(--text-lo)', marginBottom: 4 }}>Принадлежность к теме</div>
        {isNoise ? (
          <div style={{ fontSize: 11, color: 'var(--amber)', fontWeight: 600 }}>⚠ Шум (не распознан)</div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
            <span style={{ fontSize: 11, fontWeight: 600 }}>{topic?.label ?? `Тема ${docTopic?.topic}`}</span>
          </div>
        )}
      </div>

      {/* Сущности */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-lo)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 8 }}>
          Именованные сущности
        </div>
        {Object.keys(grouped).length === 0 ? (
          <div style={{ fontSize: 11, color: 'var(--text-lo)', fontStyle: 'italic' }}>Не обнаружены</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(['PER', 'ORG', 'LOC'] as const).map(type => {
              const items = grouped[type]
              if (!items?.length) return null
              const cfg = NER_CONFIG[type]
              return (
                <div key={type}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: cfg.color, fontFamily: 'var(--mono)', marginBottom: 4 }}>{type}</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {items.slice(0, 12).map((e, i) => (
                      <span key={i} style={{
                        fontSize: 10, fontFamily: 'var(--mono)',
                        padding: '1px 6px', borderRadius: 4,
                        background: `${cfg.color}22`, color: cfg.color,
                      }}>{e.text}</span>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

interface PageDocMapProps {
  btResult:    BertopicResult | null
  natashaDocs: ProcessedDocument[]
}

const PageDocMap = ({ btResult, natashaDocs }: PageDocMapProps) => {
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null)
  const [tooltip, setTooltip]         = useState<{ x: number; y: number; name: string } | null>(null)
  const [filterTopic, setFilterTopic] = useState<number | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const topics    = btResult?.topics      ?? []
  const docTopics = btResult?.doc_topics  ?? []
  const positions = btResult?.doc_positions ?? []

  const natashaIndex = useMemo(() => {
    const idx: Record<string, ProcessedDocument> = {}
    for (const d of natashaDocs) idx[d.name] = d
    return idx
  }, [natashaDocs])

  const topicIndex = useMemo(() => {
    const idx: Record<number, { topic: TopicResult; idx: number }> = {}
    topics.forEach((t, i) => { idx[t.id] = { topic: t, idx: i } })
    return idx
  }, [topics])

  // Нормализуем координаты в SVG viewport
  const SVG_W = 640
  const SVG_H = 460
  const PAD   = 40

  const points = useMemo(() => {
    if (!positions.length || positions.length !== docTopics.length) return []

    const xs = positions.map(p => p.x)
    const ys = positions.map(p => p.y)
    const minX = Math.min(...xs), maxX = Math.max(...xs)
    const minY = Math.min(...ys), maxY = Math.max(...ys)
    const rangeX = maxX - minX || 1
    const rangeY = maxY - minY || 1

    return positions.map((pos, i) => {
      const dt      = docTopics[i]
      const ti      = dt ? topicIndex[dt.topic] : null
      const color   = ti ? TOPIC_COLORS[ti.idx % TOPIC_COLORS.length] : '#5b5b5b'
      const natasha = natashaIndex[dt?.name ?? '']
      const size    = natasha
        ? 4 + Math.min(10, (natasha.tokens_count / 500) * 6)
        : 5

      return {
        svgX:  PAD + ((pos.x - minX) / rangeX) * (SVG_W - PAD * 2),
        svgY:  PAD + ((pos.y - minY) / rangeY) * (SVG_H - PAD * 2),
        name:  dt?.name ?? `doc_${i}`,
        topic: dt?.topic ?? -1,
        color,
        size,
        topicIdx: ti?.idx ?? -1,
      }
    })
  }, [positions, docTopics, topicIndex, natashaIndex])

  const selectedDocData = useMemo(() => {
    if (!selectedDoc) return null
    const dt = docTopics.find(d => d.name === selectedDoc) ?? null
    const ti = dt && dt.topic >= 0 ? topicIndex[dt.topic] : null
    return {
      docTopic: dt,
      topic:    ti?.topic ?? null,
      topicIdx: ti?.idx   ?? -1,
      natasha:  natashaIndex[selectedDoc],
    }
  }, [selectedDoc, docTopics, topicIndex, natashaIndex])

  if (!btResult || !positions.length) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-mid)' }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>🗺</div>
        <p style={{ fontSize: 13 }}>Карта документов недоступна — запустите BERTopic анализ</p>
      </div>
    )
  }

  return (
    <div className="animate-fadeIn">
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginBottom: 16 }}>
        <div style={{ flex: 1 }}>
          <p className="field-label" style={{ marginBottom: 4 }}>Семантическая карта документов</p>
          <p style={{ fontSize: 10, color: 'var(--text-lo)', fontFamily: 'var(--mono)' }}>
            // позиции вычислены UMAP · цвет = тема · размер = объём документа · нажмите на точку
          </p>
        </div>

        {/* Фильтр по теме */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end', maxWidth: 320 }}>
          <button
            onClick={() => setFilterTopic(null)}
            style={{
              padding: '4px 10px', borderRadius: 6, fontSize: 10, cursor: 'pointer',
              border: `1px solid ${filterTopic === null ? 'var(--border-hi)' : 'var(--border)'}`,
              background: filterTopic === null ? 'var(--bg-card)' : 'transparent',
              color: 'var(--text-mid)', fontFamily: 'var(--mono)',
            }}>
            Все
          </button>
          {topics.map((t, i) => (
            <button key={t.id} onClick={() => setFilterTopic(filterTopic === t.id ? null : t.id)}
              style={{
                padding: '4px 10px', borderRadius: 6, fontSize: 10, cursor: 'pointer',
                border: `1px solid ${filterTopic === t.id ? TOPIC_COLORS[i % TOPIC_COLORS.length] : 'var(--border)'}`,
                background: filterTopic === t.id ? `${TOPIC_COLORS[i % TOPIC_COLORS.length]}22` : 'transparent',
                color: TOPIC_COLORS[i % TOPIC_COLORS.length], fontFamily: 'var(--mono)',
              }}>
              {t.label.length > 14 ? t.label.slice(0, 14) + '…' : t.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        {/* SVG карта */}
        <div style={{
          flex: 1, border: '1px solid var(--border)', borderRadius: 10,
          background: 'var(--bg-deep)', position: 'relative', overflow: 'hidden',
        }}>
          <svg
            ref={svgRef}
            viewBox={`0 0 ${SVG_W} ${SVG_H}`}
            style={{ width: '100%', height: 460, display: 'block' }}
            onMouseLeave={() => setTooltip(null)}
          >
            {/* Точки */}
            {points.map((p, i) => {
              const isFiltered  = filterTopic !== null && p.topic !== filterTopic
              const isSelected  = p.name === selectedDoc
              const isNoise     = p.topic === -1
              const opacity     = isFiltered ? 0.1 : isNoise ? 0.3 : 0.8

              return (
                <circle
                  key={i}
                  cx={p.svgX} cy={p.svgY} r={isSelected ? p.size + 3 : p.size}
                  fill={p.color}
                  opacity={opacity}
                  stroke={isSelected ? '#fff' : 'none'}
                  strokeWidth={isSelected ? 2 : 0}
                  style={{ cursor: 'pointer', transition: 'r .15s, opacity .2s' }}
                  onMouseEnter={e => {
                    const rect = svgRef.current?.getBoundingClientRect()
                    if (!rect) return
                    setTooltip({
                      x: e.clientX - rect.left,
                      y: e.clientY - rect.top,
                      name: p.name,
                    })
                  }}
                  onMouseLeave={() => setTooltip(null)}
                  onClick={() => setSelectedDoc(p.name === selectedDoc ? null : p.name)}
                />
              )
            })}
          </svg>

          {/* Тултип */}
          {tooltip && (
              <div style={{
                position: 'absolute',
                left: tooltip.x + 12, top: tooltip.y - 10,
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: 6, padding: '6px 10px',
                fontSize: 11, fontFamily: 'var(--mono)',
                pointerEvents: 'none', zIndex: 10,
                maxWidth: 240, wordBreak: 'break-word',
                boxShadow: '0 4px 12px rgba(0,0,0,.3)',
              }}>
                {(() => {
                  const nd = natashaIndex[tooltip.name]
                  return (
                    <>
                      {nd?.reg_number && (
                        <div style={{ fontSize: 9, color: 'var(--text-lo)', marginBottom: 2 }}>
                          {nd.reg_number}
                        </div>
                      )}
                      <div>{nd?.title ?? tooltip.name.replace(/\.[^.]+$/, '')}</div>
                    </>
                  )
                })()}
              </div>
          )}
        </div>

        {/* Панель документа */}
        {selectedDoc && selectedDocData && (
          <DocDetailPanel
            docName={selectedDoc}
            docTopic={selectedDocData.docTopic}
            topic={selectedDocData.topic}
            topicIdx={selectedDocData.topicIdx}
            natasha={selectedDocData.natasha}
            onClose={() => setSelectedDoc(null)}
          />
        )}

        {/* Легенда если ничего не выбрано */}
        {!selectedDoc && (
          <div style={{
            width: 200, flexShrink: 0,
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 10, padding: '14px 12px',
          }}>
            <p className="field-label" style={{ marginBottom: 10 }}>Легенда</p>
            {topics.map((t, i) => (
              <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 7 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: TOPIC_COLORS[i % TOPIC_COLORS.length], flexShrink: 0 }} />
                <span style={{ fontSize: 11, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.label}>{t.label}</span>
                <span style={{ fontSize: 10, color: 'var(--text-lo)', fontFamily: 'var(--mono)' }}>×{t.count}</span>
              </div>
            ))}
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#5b5b5b', opacity: 0.4 }} />
              <span style={{ fontSize: 10, color: 'var(--text-lo)' }}>Шум</span>
            </div>
            <p style={{ fontSize: 10, color: 'var(--text-lo)', marginTop: 12, lineHeight: 1.5, fontFamily: 'var(--mono)' }}>
              // нажмите на точку чтобы увидеть детали документа
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default PageDocMap
