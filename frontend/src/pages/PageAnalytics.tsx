import { useState, useEffect, useRef } from 'react'
import { VOSviewerOnline } from 'vosviewer-online'
import Icon from '../components/Icon'
import type { BertopicResult, TopicResult, DocTopic } from '../App'
import { generatePdfReport, saveFileDialog, onResult, readJsonFile } from '../bridge'
import { TopicDetailModal } from './TopicDetailModal'
import type { ProcessedDocument } from './TopicDetailModal'

const TOPIC_COLORS = [
  '#00d4ff', '#f59e0b', '#10b981', '#a78bfa',
  '#f87171', '#34d399', '#60a5fa', '#f472b6',
  '#fb923c', '#a3e635',
]

interface BarItem { l: string; v: number }
const MiniBarChart = ({ data, color }: { data: BarItem[]; color?: string }) => {
  const max = Math.max(...data.map(d => d.v))
  if (max === 0) return null
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 60 }}>
      {data.map((d, i) => (
        <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
          <div style={{ width: '100%', borderRadius: '3px 3px 0 0', background: color ?? 'var(--cyan)', opacity: .7 + (d.v / max) * .3, height: `${(d.v / max) * 52}px` }} />
          <span style={{ fontSize: 9, color: 'var(--text-lo)', fontFamily: 'var(--mono)' }}>{d.l}</span>
        </div>
      ))}
    </div>
  )
}

type SectionKey = 'summary' | 'topics' | 'vos' | 'stats' | 'dynamics' | 'anomalies' | 'clusters'
interface Sections extends Record<SectionKey, boolean> {}

const SECTION_CONFIG: [SectionKey, string, boolean, string][] = [
  ['summary',   'Краткое резюме',      true,  'Обязательный раздел'],
  ['topics',    'Тематический анализ', true,  'Обязательный раздел'],
  ['vos',       'Карта VOSviewer',      true,  'Семантическая сеть'],
  ['stats',     'Общая статистика',    true,  'Метрики корпуса'],
  ['dynamics',  'Динамика тем',        false, 'Требуются даты'],
  ['anomalies', 'Аномалии и шум',      false, 'Дополнительный анализ'],
  ['clusters',  'Межкластерные связи', false, 'Граф кластеров'],
]

const ReportModal = ({ onClose, btResult }: { onClose: () => void; btResult: BertopicResult | null }) => {
  const [preview, setPreview]       = useState(false)
  const [generating, setGenerating] = useState(false)
  const [reportPath, setReportPath] = useState<string | null>(null)
  const [error, setError]           = useState<string | null>(null)
  const [sections, setSections]     = useState<Sections>({
    summary: true, topics: true, vos: true, stats: true,
    dynamics: false, anomalies: false, clusters: true,
  })
  const toggle = (k: SectionKey) => setSections(s => ({ ...s, [k]: !s[k] }))

  useEffect(() => {
    onResult((data) => {
      if (data.action === 'report_done') {
        setGenerating(false)
        if (data.error) setError(`Ошибка: ${data.error}`)
        else setReportPath(data.path)
      }
      if (data.action === 'file_saved') setError(null)
    })
  }, [])

  const handleDownload = () => { setGenerating(true); setError(null); setReportPath(null); generatePdfReport(sections) }
  const handleSave     = () => { if (reportPath) saveFileDialog(reportPath) }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Icon name="pdf" size={20} color="var(--red)" />
            <h3 style={{ fontSize: 18, fontWeight: 800 }}>Формирование PDF отчёта</h3>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-mid)', padding: 4 }}>
            <Icon name="close" size={18} />
          </button>
        </div>
        {!preview ? (
          <>
            <p style={{ fontSize: 13, color: 'var(--text-mid)', marginBottom: 20 }}>Выберите разделы которые войдут в итоговый отчёт:</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 24 }}>
              {SECTION_CONFIG.map(([k, label, req, hint]) => (
                <div key={k}
                  style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: sections[k] ? 'var(--cyan-dim)' : 'var(--bg-deep)', border: `1px solid ${sections[k] ? 'var(--border-hi)' : 'var(--border)'}`, borderRadius: 8, cursor: req ? 'default' : 'pointer', transition: 'all .18s' }}
                  onClick={() => !req && toggle(k)}>
                  <input type="checkbox" checked={sections[k]} onChange={() => !req && toggle(k)} disabled={req} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{label}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-lo)' }}>{hint}</div>
                  </div>
                </div>
              ))}
            </div>
            {error && <div style={{ padding: '10px 14px', background: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.3)', borderRadius: 8, marginBottom: 16 }}><span style={{ fontSize: 12, color: 'var(--red)' }}>{error}</span></div>}
            {reportPath && (
              <div style={{ padding: '10px 14px', background: 'rgba(16,185,129,.1)', border: '1px solid rgba(16,185,129,.3)', borderRadius: 8, marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 12, color: 'var(--green)' }}>✓ PDF сформирован — выберите место сохранения</span>
                <button className="btn btn-primary" onClick={handleSave} style={{ padding: '6px 14px', fontSize: 12 }}><Icon name="download" size={13} /> Сохранить</button>
              </div>
            )}
            <div style={{ display: 'flex', gap: 12 }}>
              <button className="btn btn-secondary" onClick={() => setPreview(true)} style={{ flex: 1, justifyContent: 'center' }}><Icon name="eye" size={14} /> Предпросмотр</button>
              <button className="btn btn-amber" onClick={handleDownload} disabled={generating} style={{ flex: 1, justifyContent: 'center' }}>
                {generating ? <><span style={{ animation: 'spin-slow 1s linear infinite', display: 'inline-block' }}>⟳</span> Генерация...</> : <><Icon name="download" size={14} /> Сформировать PDF</>}
              </button>
            </div>
          </>
        ) : (
          <>
            <div style={{ background: 'var(--bg-deep)', border: '1px solid var(--border)', borderRadius: 8, padding: 24, marginBottom: 20, minHeight: 360, maxHeight: '60vh', overflowY: 'auto' }}>
              <div style={{ maxWidth: 520, margin: '0 auto' }}>
                <div style={{ textAlign: 'center', marginBottom: 20, paddingBottom: 20, borderBottom: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-.01em', marginBottom: 4 }}>Аналитический отчёт</div>
                  <div style={{ fontSize: 11, color: 'var(--text-mid)', fontFamily: 'var(--mono)' }}>SemanticAnalyzer v1.0 · {new Date().toLocaleDateString('ru-RU')}</div>
                </div>
                {sections.summary && btResult && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--cyan)', marginBottom: 6, borderLeft: '3px solid var(--cyan)', paddingLeft: 8 }}>1. Краткое резюме</div>
                    <div style={{ fontSize: 11, color: 'var(--text-mid)', lineHeight: 1.8 }}>Проанализировано <b style={{ color: 'var(--text-hi)' }}>{btResult.total_docs} документов</b>, выявлено <b style={{ color: 'var(--text-hi)' }}>{btResult.topics.length} тематических кластеров</b>. Когерентность: {btResult.coherence}%. Шум: {btResult.noise_pct}%.</div>
                  </div>
                )}
                {sections.topics && btResult && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--green)', marginBottom: 6, borderLeft: '3px solid var(--green)', paddingLeft: 8 }}>2. Тематический анализ</div>
                    {btResult.topics.map((t, i) => (
                      <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: TOPIC_COLORS[i % TOPIC_COLORS.length], flexShrink: 0 }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 11, fontWeight: 600 }}>{t.label}</div>
                          <div style={{ fontSize: 10, color: 'var(--text-lo)', fontFamily: 'var(--mono)' }}>{t.words.slice(0, 5).join(' · ')}</div>
                        </div>
                        <span style={{ fontSize: 10, color: 'var(--text-mid)', fontFamily: 'var(--mono)' }}>{t.count} doc</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <button className="btn btn-ghost" onClick={() => setPreview(false)} style={{ flex: 1, justifyContent: 'center' }}>← Назад к настройкам</button>
              <button className="btn btn-amber" onClick={() => { setPreview(false); handleDownload() }} disabled={generating} style={{ flex: 1, justifyContent: 'center' }}>
                {generating ? <><span style={{ animation: 'spin-slow 1s linear infinite', display: 'inline-block' }}>⟳</span> Генерация...</> : <><Icon name="download" size={14} /> Сформировать PDF</>}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

interface PageAnalyticsProps {
  btResult:    BertopicResult | null
  natashaDocs: ProcessedDocument[]
}

const PageAnalytics = ({ btResult, natashaDocs }: PageAnalyticsProps) => {
  const [tab, setTab]                     = useState<'analytics' | 'vos'>('analytics')
  const [selectedTopic, setSelectedTopic] = useState<number | null>(null)
  const [showReport, setShowReport]       = useState(false)
  const [detailTopic, setDetailTopic]     = useState<TopicResult | null>(null)
  const [vosView, setVosView]             = useState<'clusters' | 'keywords'>('clusters')

  // ── Загрузка keywords_vos_data через Qt-мост ─────────────────────────────
  // fetch('file://...') не работает из http://localhost (Vite) — CORS блокирует.
  // Вызываем Python-слот read_json_file(path) через Qt-мост.
  const [keywordsVosData, setKeywordsVosData] = useState<any>(null)
  const [kwLoading, setKwLoading]             = useState(false)
  const [kwError, setKwError]                 = useState<string | null>(null)
  const loadedPathRef = useRef<string | null>(null)

  // Слушатель file_read_done — регистрируем ОДИН РАЗ при монтировании
  useEffect(() => {
    console.log('[KeywordsVOS] регистрируем слушатель file_read_done')
    onResult((data) => {
      if (data.action !== 'file_read_done') return
      console.log('[KeywordsVOS] file_read_done получен, key=', data.key,
        'loadedPathRef=', loadedPathRef.current,
        'match=', data.key === loadedPathRef.current)
      if (data.key !== loadedPathRef.current) return

      if (data.error) {
        console.error('[KeywordsVOS] ошибка:', data.error)
        setKwError(`Ошибка загрузки: ${data.error}`)
        setKwLoading(false)
        return
      }

      console.log('[KeywordsVOS] данные получены, узлов:',
        data.data?.network?.items?.length ?? 0)
      setKeywordsVosData(data.data)
      setKwLoading(false)
    })
  }, [])

  // Запрашиваем файл СРАЗУ как появился путь
  useEffect(() => {
    console.log('[KeywordsVOS] useEffect path сработал, path=',
      btResult?.keywords_vos_path, 'loadedRef=', loadedPathRef.current)
    const path = btResult?.keywords_vos_path
    if (!path) {
      console.log('[KeywordsVOS] path пустой, выходим')
      return
    }
    if (path === loadedPathRef.current) {
      console.log('[KeywordsVOS] уже загружали этот путь, выходим')
      return
    }

    loadedPathRef.current = path
    setKwLoading(true)
    setKwError(null)
    setKeywordsVosData(null)

    console.log('[KeywordsVOS] вызываем readJsonFile:', path)
    readJsonFile(path)
  }, [btResult?.keywords_vos_path])

  const topics     = btResult?.topics      ?? []
  const totalDocs  = btResult?.total_docs  ?? 0
  const coherence  = btResult?.coherence   ?? 0
  const noisePct   = btResult?.noise_pct   ?? 0
  const noiseCount = btResult?.noise_count ?? 0
  const vosData    = btResult?.vos_data    ?? null

  const docTopics: DocTopic[] = btResult?.doc_topics ?? []
  const barData: BarItem[]    = topics.slice(0, 8).map(t => ({ l: `T${t.id}`, v: t.count }))

  const clusterLinks = (() => {
    const links = vosData?.network?.links
    if (!links || links.length === 0) return []
    return [...links]
      .sort((a: any, b: any) => b.strength - a.strength)
      .slice(0, 6)
      .map((lnk: any) => {
        const topicA = topics.find(t => t.id + 1 === lnk.source_id)
        const topicB = topics.find(t => t.id + 1 === lnk.target_id)
        const idxA   = topicA ? topics.indexOf(topicA) : 0
        return {
          a: topicA?.label ?? `T${lnk.source_id - 1}`,
          b: topicB?.label ?? `T${lnk.target_id - 1}`,
          w: lnk.strength,
          color: TOPIC_COLORS[idxA % TOPIC_COLORS.length],
        }
      })
  })()

  const dominantTopic = topics[0]
  const dominantPct   = dominantTopic && totalDocs > 0 ? Math.round((dominantTopic.count / totalDocs) * 100) : 0

  const dynamicsData = (() => {
    const withDates = docTopics.filter(d => d.date && d.topic >= 0)
    if (withDates.length === 0) return null
    const byDate: Record<string, Record<number, number>> = {}
    withDates.forEach(d => {
      if (!byDate[d.date!]) byDate[d.date!] = {}
      byDate[d.date!][d.topic] = (byDate[d.date!][d.topic] ?? 0) + 1
    })
    return Object.entries(byDate).sort(([a], [b]) => a.localeCompare(b)).map(([date, topicCounts]) => ({ date, topicCounts }))
  })()

  const vosParameters = {
    dark_ui: true, show_item_labels: true, item_size_variation: 0.5,
    min_link_strength_large_network: 0, show_isolated_items: true,
  }
  const vosKeywordsParameters = {
    dark_ui: true, show_item_labels: true, item_size_variation: 0.7,
    min_link_strength_large_network: 0, show_isolated_items: false,
  }

  if (!btResult) {
    return (
      <div className="animate-fadeUp" style={{ textAlign: 'center', padding: '80px 0' }}>
        <div style={{ fontSize: 40, marginBottom: 16 }}>📊</div>
        <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 8 }}>Нет данных для отображения</h2>
        <p style={{ fontSize: 13, color: 'var(--text-mid)' }}>Вернитесь на шаг назад и запустите BERTopic анализ</p>
      </div>
    )
  }

  return (
    <div className="animate-fadeUp">
      {showReport && <ReportModal onClose={() => setShowReport(false)} btResult={btResult} />}
      {detailTopic && (
        <TopicDetailModal topic={detailTopic} docTopics={docTopics} natashaDocs={natashaDocs} onClose={() => setDetailTopic(null)} />
      )}

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <div className="badge badge-green">RESULTS</div>
            <h2 style={{ fontSize: 20, fontWeight: 800 }}>Результаты анализа</h2>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-mid)' }}>Итоговая аналитика и семантическая визуализация корпуса документов</p>
        </div>
        <button className="btn btn-amber" onClick={() => setShowReport(true)}>
          <Icon name="pdf" size={14} /> Сформировать PDF отчёт
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
        {([
          [String(topics.length), 'Тем',           'var(--cyan)'],
          [String(totalDocs),     'Документов',    'var(--amber)'],
          [`${coherence}%`,       'Когерентность', 'var(--green)'],
          [`${noisePct}%`,        'Шум',           'var(--red)'],
        ] as [string, string, string][]).map(([n, l, c]) => (
          <div key={l} className="card" style={{ textAlign: 'center', padding: '16px 12px' }}>
            <div className="stat-num" style={{ color: c }}>{n}</div>
            <div className="stat-label">{l}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom: 20 }}>
        <button className={`tab${tab === 'analytics' ? ' active' : ''}`} onClick={() => setTab('analytics')}>
          <Icon name="bar_chart" size={13} /> Аналитика
        </button>
        <button className={`tab${tab === 'vos' ? ' active' : ''}`} onClick={() => setTab('vos')}>
          <Icon name="network" size={13} /> VOSviewer
        </button>
      </div>

      {/* Analytics tab */}
      {tab === 'analytics' && (
        <div className="animate-fadeIn">
          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 20, marginBottom: 20 }}>
            <div className="card">
              <p className="field-label" style={{ marginBottom: 12 }}>Выявленные темы</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {topics.map((t, i) => (
                  <div key={t.id} className={`topic-chip${selectedTopic === t.id ? ' selected' : ''}`}
                    onClick={() => setDetailTopic(t)} style={{ cursor: 'pointer' }}>
                    <div className="topic-dot" style={{ background: TOPIC_COLORS[i % TOPIC_COLORS.length] }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>{t.label}</div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {t.words.slice(0, 4).map(w => <span key={w} style={{ fontSize: 10, color: 'var(--text-lo)', fontFamily: 'var(--mono)' }}>{w}</span>)}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--mono)', color: TOPIC_COLORS[i % TOPIC_COLORS.length] }}>{t.count}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-lo)' }}>docs</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {barData.length > 0 && (
                <div className="card">
                  <p className="field-label" style={{ marginBottom: 10 }}>Распределение документов по темам</p>
                  <MiniBarChart data={barData} color="var(--cyan)" />
                  <p style={{ fontSize: 10, color: 'var(--text-lo)', textAlign: 'center', marginTop: 6, fontFamily: 'var(--mono)' }}>количество документов на тему</p>
                </div>
              )}
              <div className="card">
                <p className="field-label" style={{ marginBottom: 10 }}>Аномалии и шум</p>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                  <div><div style={{ fontSize: 12, fontWeight: 600 }}>Топик -1</div><div style={{ fontSize: 10, color: 'var(--text-mid)' }}>Нераспознанные документы</div></div>
                  <span className={`badge badge-${noisePct > 10 ? 'red' : 'amber'}`}>{noiseCount} doc</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0' }}>
                  <div><div style={{ fontSize: 12, fontWeight: 600 }}>Процент шума</div><div style={{ fontSize: 10, color: 'var(--text-mid)' }}>От общего корпуса</div></div>
                  <span className={`badge badge-${noisePct > 20 ? 'red' : noisePct > 10 ? 'amber' : 'green'}`}>{noisePct}%</span>
                </div>
              </div>
              {clusterLinks.length > 0 && (
                <div className="card">
                  <p className="field-label" style={{ marginBottom: 4 }}>Межкластерные связи</p>
                  <p style={{ fontSize: 10, color: 'var(--text-lo)', marginBottom: 10, fontFamily: 'var(--mono)' }}>// cosine similarity · топ-6 наиболее близких пар</p>
                  {clusterLinks.map(({ a, b, w, color }: any) => (
                    <div key={`${a}-${b}`} style={{ marginBottom: 10 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                        <span style={{ fontSize: 11, color: 'var(--text-mid)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '80%' }}>
                          <span style={{ color, fontWeight: 600 }}>{a}</span><span style={{ opacity: .5, margin: '0 4px' }}>↔</span><span>{b}</span>
                        </span>
                        <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-hi)', flexShrink: 0, marginLeft: 8 }}>{w.toFixed(3)}</span>
                      </div>
                      <div className="progress-track">
                        <div className="progress-fill" style={{ width: `${w * 100}%`, background: `linear-gradient(90deg, ${color}, ${color}66)` }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {dynamicsData && dynamicsData.length > 0 && (
            <div className="card" style={{ marginBottom: 20 }}>
              <p className="field-label" style={{ marginBottom: 12 }}>Динамика тем · по датам из документов</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {dynamicsData.map(({ date, topicCounts }) => (
                  <div key={date} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text-lo)', minWidth: 90, flexShrink: 0 }}>{date}</span>
                    <div style={{ flex: 1, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {Object.entries(topicCounts).map(([tid, count]) => {
                        const topicIdx = topics.findIndex(t => t.id === Number(tid))
                        const color    = TOPIC_COLORS[topicIdx % TOPIC_COLORS.length]
                        const label    = topics[topicIdx]?.label ?? `T${tid}`
                        return (
                          <div key={tid} title={`${label}: ${count} doc`} style={{ height: 22, minWidth: 32, padding: '0 6px', background: color, borderRadius: 4, opacity: 0.85, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <span style={{ fontSize: 9, color: '#000', fontWeight: 700, fontFamily: 'var(--mono)' }}>T{tid}·{String(count)}</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
              <p style={{ fontSize: 10, color: 'var(--text-lo)', marginTop: 10, fontFamily: 'var(--mono)' }}>// даты извлечены Natasha · наведите на блок для подсказки</p>
            </div>
          )}

          <div className="card" style={{ borderLeft: '3px solid var(--cyan)' }}>
            <p className="field-label" style={{ marginBottom: 8 }}>Краткая выжимка · Auto-summary</p>
            <p style={{ fontSize: 13, color: 'var(--text-mid)', lineHeight: 1.8 }}>
              Корпус из <span style={{ color: 'var(--cyan)', fontWeight: 700 }}>{totalDocs} документов</span> разбит на <span style={{ color: 'var(--cyan)', fontWeight: 700 }}>{topics.length} тематических кластеров</span>.
              {dominantTopic && <> Доминирующая тема — <b style={{ color: 'var(--text-hi)' }}>«{dominantTopic.label}»</b> ({dominantPct}% документов, {dominantTopic.count} ед.).</>}
              {' '}Когерентность {coherence}% —{coherence >= 70 ? ' высокая, что свидетельствует о чётком тематическом разграничении.' : coherence >= 40 ? ' средняя, темы частично перекрываются.' : ' низкая, рекомендуется пересмотреть параметры анализа.'}
              {noiseCount > 0 && <> Обнаружено <span style={{ color: 'var(--amber)', fontWeight: 700 }}>{noiseCount} документов шума</span> ({noisePct}%) — рекомендуется дополнительная фильтрация стоп-слов.</>}
              {dynamicsData && dynamicsData.length > 0 && <> Временной охват: <span style={{ color: 'var(--cyan)', fontWeight: 700 }}>{dynamicsData[0].date}</span> — <span style={{ color: 'var(--cyan)', fontWeight: 700 }}>{dynamicsData[dynamicsData.length - 1].date}</span>.</>}
            </p>
          </div>
        </div>
      )}

      {/* VOSviewer tab */}
      {tab === 'vos' && (
        <div className="animate-fadeIn">

          {/* Переключатель карт */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, padding: '10px 14px', background: 'var(--bg-deep)', borderRadius: 8, border: '1px solid var(--border)' }}>
            <span style={{ fontSize: 11, color: 'var(--text-lo)', fontFamily: 'var(--mono)', marginRight: 4 }}>Режим карты:</span>
            {([
              ['clusters', 'Тематические кластеры', 'Связи между темами по cosine similarity'],
              ['keywords', 'Ключевые слова',         'Слова из эмбеддингов sentence-transformers'],
            ] as [typeof vosView, string, string][]).map(([v, label, hint]) => (
              <button key={v} onClick={() => setVosView(v)} title={hint} style={{
                padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: 'pointer', transition: 'all .15s',
                border: vosView === v ? '1px solid var(--cyan)' : '1px solid var(--border)',
                background: vosView === v ? 'var(--cyan-dim)' : 'transparent',
                color: vosView === v ? 'var(--cyan)' : 'var(--text-mid)',
              }}>{label}</button>
            ))}
            <span style={{ fontSize: 10, color: 'var(--text-lo)', fontFamily: 'var(--mono)', marginLeft: 'auto', fontStyle: 'italic' }}>
              {vosView === 'clusters'
                ? '// тема = узел · размер = кол-во документов · связь = cosine sim'
                : '// слово = узел · размер = TF-IDF score · связь = cosine sim слов'}
            </span>
          </div>

          {/* Карта тематических кластеров */}
          {vosView === 'clusters' && (
            vosData && vosData.network?.items?.length >= 3 ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 20 }}>
                <div style={{ height: 500, borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border)', position: 'relative' }}>
                  <VOSviewerOnline data={vosData} parameters={vosParameters} />
                  <div style={{ position: 'absolute', top: 12, left: 12, display: 'flex', gap: 6, zIndex: 5, pointerEvents: 'none' }}>
                    <span className="badge badge-cyan">VOSviewer Online</span>
                    <span className="badge badge-amber">Cluster Map</span>
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div className="card">
                    <p className="field-label" style={{ marginBottom: 10 }}>Легенда</p>
                    <div style={{ maxHeight: 240, overflowY: 'auto' }}>
                      {topics.map((t, i) => (
                        <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                          <div style={{ width: 10, height: 10, borderRadius: '50%', background: TOPIC_COLORS[i % TOPIC_COLORS.length], flexShrink: 0, opacity: .85 }} />
                          <span style={{ fontSize: 11, flex: 1 }}>{t.label}</span>
                          <span style={{ fontSize: 10, color: 'var(--text-lo)', fontFamily: 'var(--mono)' }}>×{t.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="card">
                    <p className="field-label" style={{ marginBottom: 10 }}>Сеть</p>
                    {([['Узлов', String(vosData.network?.items?.length ?? 0)], ['Связей', String(vosData.network?.links?.length ?? 0)], ['Кластеров', String(topics.length)]] as [string,string][]).map(([k, v]) => (
                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontSize: 11, color: 'var(--text-mid)' }}>{k}</span>
                        <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-hi)' }}>{v}</span>
                      </div>
                    ))}
                  </div>
                  <div className="card">
                    <p className="field-label" style={{ marginBottom: 8 }}>Подсказка</p>
                    <p style={{ fontSize: 11, color: 'var(--text-mid)', lineHeight: 1.6 }}>Колёсико мыши — масштабирование.<br />Перетаскивание — перемещение графа.</p>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-mid)' }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>⚠️</div>
                <p style={{ fontSize: 13 }}>VOSviewer требует минимум 3 темы.<br />Сейчас: <b style={{ color: 'var(--amber)' }}>{vosData?.network?.items?.length ?? 0}</b> — загрузите больше документов.</p>
              </div>
            )
          )}

          {/* Карта ключевых слов */}
          {vosView === 'keywords' && (
            // Состояние 1: идёт загрузка файла
            kwLoading ? (
              <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-mid)' }}>
                <div style={{ fontSize: 28, marginBottom: 12, animation: 'spin-slow 1.2s linear infinite', display: 'inline-block' }}>⟳</div>
                <p style={{ fontSize: 13 }}>Загрузка карты ключевых слов...</p>
              </div>

            // Состояние 2: ошибка загрузки
            ) : kwError ? (
              <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-mid)' }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>⚠️</div>
                <p style={{ fontSize: 13, color: 'var(--red)' }}>{kwError}</p>
              </div>

            // Состояние 3: данные загружены, достаточно узлов
            ) : keywordsVosData && keywordsVosData.network?.items?.length >= 3 ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 20 }}>
                <div style={{ height: 500, borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border)', position: 'relative' }}>
                  <VOSviewerOnline data={keywordsVosData} parameters={vosKeywordsParameters} />
                  <div style={{ position: 'absolute', top: 12, left: 12, display: 'flex', gap: 6, zIndex: 5, pointerEvents: 'none' }}>
                    <span className="badge badge-cyan">VOSviewer Online</span>
                    <span className="badge badge-green">Keyword Map</span>
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div className="card">
                    <p className="field-label" style={{ marginBottom: 10 }}>Темы · цвета</p>
                    <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                      {topics.map((t, i) => (
                        <div key={t.id} style={{ marginBottom: 10 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                            <div style={{ width: 10, height: 10, borderRadius: '50%', background: TOPIC_COLORS[i % TOPIC_COLORS.length], flexShrink: 0 }} />
                            <span style={{ fontSize: 11, fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.label}</span>
                          </div>
                          <div style={{ paddingLeft: 18, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                            {t.words.slice(0, 3).map(w => (
                              <span key={w} style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--text-lo)', background: 'var(--bg-deep)', padding: '1px 5px', borderRadius: 3, border: '1px solid var(--border)' }}>{w}</span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="card">
                    <p className="field-label" style={{ marginBottom: 10 }}>Карта слов</p>
                    {([
                      ['Слов',      String(keywordsVosData.network.items.length)],
                      ['Связей',    String(keywordsVosData.network.links.length)],
                      ['Кластеров', String(topics.length)],
                    ] as [string,string][]).map(([k, v]) => (
                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontSize: 11, color: 'var(--text-mid)' }}>{k}</span>
                        <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-hi)' }}>{v}</span>
                      </div>
                    ))}
                  </div>
                  <div className="card">
                    <p className="field-label" style={{ marginBottom: 8 }}>Как читать</p>
                    <p style={{ fontSize: 11, color: 'var(--text-mid)', lineHeight: 1.65 }}>
                      Размер узла — вес слова (c-TF-IDF).<br />
                      Цвет — тема которой принадлежит слово.<br />
                      Связи — реальное косинусное сходство эмбеддингов слов.<br />
                      Слова разных тем могут быть близки семантически.
                    </p>
                  </div>
                </div>
              </div>

            // Состояние 4: нет данных / мало узлов
            ) : (
              <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-mid)' }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>🔤</div>
                <p style={{ fontSize: 13 }}>
                  {!btResult?.keywords_vos_path
                    ? 'Запустите BERTopic анализ для получения карты ключевых слов'
                    : 'Недостаточно семантически связанных слов для отображения карты'}
                </p>
              </div>
            )
          )}
        </div>
      )}
    </div>
  )
}

export default PageAnalytics
