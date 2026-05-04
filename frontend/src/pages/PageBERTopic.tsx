import { useState, useEffect, useRef } from 'react'
import { runBertopic, onResult } from '../bridge'
import type { BertopicResult, TopicResult } from '../App'

const ProgressRing = ({ pct, color = 'var(--cyan)', size = 72 }: {
  pct: number; color?: string; size?: number
}) => {
  const r = 28, circ = 2 * Math.PI * r
  return (
    <svg width={size} height={size} viewBox="0 0 72 72">
      <circle cx="36" cy="36" r={r} fill="none" stroke="rgba(255,255,255,.06)" strokeWidth="5" />
      <circle cx="36" cy="36" r={r} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round"
        strokeDasharray={circ} strokeDashoffset={circ * (1 - pct / 100)}
        transform="rotate(-90 36 36)" style={{ transition: 'stroke-dashoffset .6s ease' }}
      />
      <text x="36" y="36" textAnchor="middle" dominantBaseline="middle" fill={color}
        fontSize="13" fontWeight="700" fontFamily="'Space Mono',monospace">{pct}%</text>
    </svg>
  )
}

interface BtSettings {
  model?: string
  minTopic?: number
  numTopics?: string
  umapComp?: number
  outlierReduce?: boolean
  dynamicTopics?: boolean
  diversity?: boolean
}

interface PageBERTopicProps {
  btSettings: BtSettings
  setBtSettings: React.Dispatch<React.SetStateAction<BtSettings>>
  setBtResult: React.Dispatch<React.SetStateAction<BertopicResult | null>>
}

const PageBERTopic = ({ btSettings, setBtSettings, setBtResult }: PageBERTopicProps) => {
  const [running, setRunning]       = useState(false)
  const [progress, setProgress]     = useState(0)
  const [stage, setStage]           = useState('idle')
  const [done, setDone]             = useState(false)
  const [topics, setTopics]         = useState<TopicResult[]>([])
  const [totalDocs, setTotalDocs]   = useState(0)
  const [coherence, setCoherence]   = useState(0)
  const [noisePct, setNoisePct]     = useState(0)
  const [noiseCount, setNoiseCount] = useState(0)
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const STAGES = [
    'Построение TF-IDF матрицы...',
    'UMAP снижение размерности...',
    'HDBSCAN кластеризация...',
    'Формирование тем...',
    'Расчёт когерентности...',
  ]

  const PIPELINE_STAGES = [
    'TF-IDF / CountVectorizer',
    'UMAP (снижение размерности)',
    'HDBSCAN кластеризация',
    'Генерация меток тем',
    'Расчёт когерентности',
  ]

  const CHECKBOXES: [keyof BtSettings, string][] = [
    ['outlierReduce', 'Снижение шума (outlier reduction)'],
    ['dynamicTopics', 'Динамика тем (если есть даты)'],
    ['diversity',     'Максимизация разнообразия слов'],
  ]

  useEffect(() => {
    onResult((data) => {
      if (data.action !== 'bertopic_done') return
      if (tickRef.current) clearInterval(tickRef.current)

      if (data.error) {
        setStage(`Ошибка: ${data.error}`)
        setRunning(false)
        setProgress(0)
        return
      }

      setTopics(data.topics)
      setTotalDocs(data.total_docs)
      setCoherence(data.coherence)
      setNoisePct(data.noise_pct)
      setNoiseCount(data.noise_count)
      setProgress(100)
      setStage('Анализ завершён ✓')
      setRunning(false)
      setDone(true)

      setBtResult({
        topics:            data.topics,
        total_docs:        data.total_docs,
        noise_pct:         data.noise_pct,
        coherence:         data.coherence,
        noise_count:       data.noise_count,
        vos_data:          data.vos_data,
        keywords_vos_path: data.keywords_vos_path ?? null,
        doc_topics:        data.doc_topics ?? [],
      })
    })
  }, [])

  const runAnalysis = () => {
    if (tickRef.current) clearInterval(tickRef.current)
    setRunning(true)
    setDone(false)
    setProgress(0)
    setTopics([])
    setStage(STAGES[0])

    let current = 0
    tickRef.current = setInterval(() => {
      current += Math.random() * 4 + 1
      if (current >= 90) {
        clearInterval(tickRef.current!)
        setProgress(90)
        setStage('Ожидание результатов...')
        return
      }
      setProgress(current)
      setStage(STAGES[Math.min(Math.floor(current / 20), STAGES.length - 1)])
    }, 400)

    runBertopic(btSettings)
  }

  const update = (k: keyof BtSettings, v: any) =>
    setBtSettings(s => ({ ...s, [k]: v }))

  return (
    <div className="animate-fadeUp">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <div className="badge badge-amber">TOPIC</div>
        <h2 style={{ fontSize: 20, fontWeight: 800 }}>
          Тематическое моделирование · <span style={{ color: 'var(--amber)' }}>BERTopic</span>
        </h2>
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-mid)', marginBottom: 24 }}>
        Автоматическое выявление скрытых тем в корпусе документов.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        <div className="card">
          <p className="field-label" style={{ marginBottom: 14 }}>Параметры модели</p>
          <div style={{ marginBottom: 14 }}>
            <label className="field-label">Embedding модель</label>
            <select className="field-input field-select"
              value={btSettings.model ?? 'rubert-tiny2'}
              onChange={e => update('model', e.target.value)}>
              <option value="rubert-tiny2">rubert-tiny2 (рекомендуется)</option>
              <option value="multilingual-e5">multilingual-e5-small</option>
              <option value="labse">LaBSE (тяжёлая)</option>
            </select>
          </div>
          <div style={{ marginBottom: 14 }}>
            <label className="field-label">
              Мин. размер топика: <span style={{ color: 'var(--cyan)' }}>{btSettings.minTopic ?? 5}</span>
            </label>
            <input type="range" min={2} max={20}
              value={btSettings.minTopic ?? 5}
              onChange={e => update('minTopic', +e.target.value)} />
          </div>
          <div style={{ marginBottom: 14 }}>
            <label className="field-label">Количество топиков</label>
            <select className="field-input field-select"
              value={btSettings.numTopics ?? 'auto'}
              onChange={e => update('numTopics', e.target.value)}>
              <option value="auto">Авто (HDBSCAN)</option>
              <option value="5">5</option>
              <option value="10">10</option>
              <option value="20">20</option>
            </select>
          </div>
          <div style={{ marginBottom: 14 }}>
            <label className="field-label">
              UMAP компоненты: <span style={{ color: 'var(--cyan)' }}>{btSettings.umapComp ?? 5}</span>
            </label>
            <input type="range" min={2} max={15}
              value={btSettings.umapComp ?? 5}
              onChange={e => update('umapComp', +e.target.value)} />
          </div>
          {CHECKBOXES.map(([k, label]) => (
            <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <input type="checkbox" id={k}
                checked={btSettings[k] !== false}
                onChange={e => update(k, e.target.checked)} />
              <label htmlFor={k} style={{ fontSize: 13, cursor: 'pointer' }}>{label}</label>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card" style={{ flex: 1 }}>
            <p className="field-label" style={{ marginBottom: 16 }}>Прогресс анализа</p>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
              <ProgressRing
                pct={Math.round(progress)}
                color={done ? 'var(--green)' : running ? 'var(--cyan)' : 'var(--text-lo)'}
              />
            </div>
            <div className="progress-track" style={{ marginBottom: 10 }}>
              <div className={`progress-fill${running ? ' shimmer' : ''}`}
                style={{ width: `${progress}%`, background: done ? 'var(--green)' : undefined }} />
            </div>
            <p style={{ fontSize: 12, textAlign: 'center', color: done ? 'var(--green)' : 'var(--text-mid)', fontFamily: 'var(--mono)', minHeight: 18 }}>
              {stage === 'idle' ? 'Ожидание запуска...' : stage}
            </p>
          </div>
          <div className="card">
            <p className="field-label" style={{ marginBottom: 10 }}>Этапы конвейера</p>
            {PIPELINE_STAGES.map((s, i) => {
              const isDone   = done || progress > (i + 1) * 20
              const isActive = !done && progress > 0 && Math.floor(progress / 20) === i
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: i < 4 ? '1px solid var(--border)' : 'none' }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: isDone ? 'var(--green)' : isActive ? 'var(--cyan)' : 'var(--text-lo)' }} />
                  <span style={{ fontSize: 12, color: isDone ? 'var(--text-hi)' : 'var(--text-mid)' }}>{s}</span>
                  {isDone && <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--green)', fontFamily: 'var(--mono)' }}>✓</span>}
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <button className="btn btn-amber" onClick={runAnalysis} disabled={running}
        style={{ width: '100%', justifyContent: 'center', padding: '13px' }}>
        {running
          ? <><span style={{ animation: 'spin-slow 1s linear infinite', display: 'inline-block' }}>⟳</span> Анализ запущен...</>
          : done ? '↺ Запустить повторно' : '▶ Запустить BERTopic анализ'}
      </button>

      {done && (
        <>
          <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
            {([
              [String(topics.length), 'Тем найдено'],
              [String(totalDocs),     'Документов'],
              [`${coherence}%`,       'Когерентность'],
              [`${noisePct}%`,        'Шум'],
            ] as [string, string][]).map(([n, l]) => (
              <div key={l} className="card" style={{ textAlign: 'center', padding: '16px 12px' }}>
                <div className="stat-num">{n}</div>
                <div className="stat-label">{l}</div>
              </div>
            ))}
          </div>
          {topics.length > 0 && (
            <div className="card" style={{ marginTop: 16 }}>
              <p className="field-label" style={{ marginBottom: 12 }}>Выявленные темы</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {topics.map(t => (
                  <div key={t.id} style={{ padding: '10px 12px', background: 'var(--bg-deep)', borderRadius: 8, border: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: 13, fontWeight: 700 }}>{t.label}</span>
                      <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--amber)' }}>{t.count} doc</span>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {t.words.slice(0, 8).map((w, i) => (
                        <span key={w} style={{
                          fontSize: 10, fontFamily: 'var(--mono)',
                          padding: '2px 7px', borderRadius: 4,
                          background: 'var(--cyan-dim)', color: 'var(--cyan)',
                          opacity: 1 - i * 0.08,
                        }}>{w}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              {noiseCount > 0 && (
                <div style={{ marginTop: 10, padding: '8px 12px', background: 'rgba(245,158,11,.08)', border: '1px solid rgba(245,158,11,.2)', borderRadius: 8 }}>
                  <span style={{ fontSize: 12, color: 'var(--amber)' }}>
                    ⚠ {noiseCount} документов не попали ни в одну тему (шум)
                  </span>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default PageBERTopic
