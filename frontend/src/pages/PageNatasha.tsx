import { useState, useEffect, useRef } from 'react'
import Icon from '../components/Icon'
import { runNatasha, onResult } from '../bridge'

/* ── LogEntry ── */
const LogEntry = ({ level, text }: { level: string; text: string }) => {
  const cls = { info: 'log-info', ok: 'log-ok', warn: 'log-warn', error: 'log-error', dim: 'log-dim' }[level] ?? 'log-dim'
  const prefix = { info: '[INFO]', ok: '[ OK ]', warn: '[WARN]', error: '[ERR ]', dim: '[    ]' }[level] ?? '[    ]'
  return (
    <div className={cls} style={{ marginBottom: 2 }}>
      <span style={{ opacity: .5, marginRight: 8 }}>{prefix}</span>{text}
    </div>
  )
}

/* ── Toggle ── */
const Toggle = ({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) => (
  <label className="toggle">
    <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
    <span className="toggle-slider" />
  </label>
)

/* ── Types ── */
interface NatSettings {
  segmenter?: boolean
  morph?: boolean
  ner?: boolean
  dates?: boolean
  lemmatize?: boolean
  stopwords?: boolean
  minTokenLen?: number
  lang?: string
  customStop?: string
}

interface DocStat {
  name: string
  tokens_count: number
  chunks_count: number
  entities_count: number
  dates_count: number
}

interface PageNatashaProps {
  settings: NatSettings
  setSettings: React.Dispatch<React.SetStateAction<NatSettings>>
}

/* ── PageNatasha ── */
const PageNatasha = ({ settings, setSettings }: PageNatashaProps) => {
  const [logs, setLogs] = useState([
    { level: 'info', text: 'Инициализация Natasha NLP pipeline...' },
    { level: 'ok',   text: 'Загружена модель NewsEmbedding (rubert-tiny2)' },
    { level: 'ok',   text: 'Segmenter ready · MorphVocab ready' },
    { level: 'ok',   text: 'NER: PER/ORG/LOC pipeline загружен' },
    { level: 'ok',   text: 'DatesExtractor ready' },
    { level: 'dim',  text: 'Ожидание запуска...' },
  ])
  const [running, setRunning]         = useState(false)
  const [done, setDone]               = useState(false)
  const [docStats, setDocStats]       = useState<DocStat[]>([])
  const [totalTokens, setTotalTokens] = useState(0)
  const terminalRef = useRef<HTMLDivElement>(null)

  const addLog = (level: string, text: string) => {
    setLogs(prev => [...prev, { level, text }])
    setTimeout(() => {
      if (terminalRef.current)
        terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }, 50)
  }

  // Слушаем ответ от Python один раз
  useEffect(() => {
    onResult((data) => {
      // Прогресс по документам
      if (data.action === 'natasha_progress') {
        addLog('info', `Обработка ${data.current}/${data.total}: ${data.name}`)
        return
      }
      if (data.action !== 'natasha_done') return


      data.documents.forEach((d: DocStat) => {
        addLog('ok', `${d.name} — ${d.tokens_count.toLocaleString()} токенов, ${d.chunks_count} чанков`)
        if (d.entities_count > 0)
          addLog('info', `  Сущностей: ${d.entities_count} · Дат: ${d.dates_count}`)
      })

      addLog('ok', `Готово · Всего токенов: ${data.total_tokens.toLocaleString()}`)
      setDocStats(data.documents)
      setTotalTokens(data.total_tokens)
      setRunning(false)
      setDone(true)
    })
  }, [])

  const handleRun = () => {
    setRunning(true)
    setDone(false)
    setDocStats([])
    addLog('info', 'Запуск обработки...')
    runNatasha(settings)
  }

  const update = (key: keyof NatSettings, val: any) =>
    setSettings(s => ({ ...s, [key]: val }))

  return (
    <div className="animate-fadeUp">
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <div className="badge badge-cyan">NLP</div>
          <h2 style={{ fontSize: 20, fontWeight: 800 }}>
            Предобработка · <span style={{ color: 'var(--cyan)' }}>Natasha</span>
          </h2>
        </div>
        <p style={{ fontSize: 13, color: 'var(--text-mid)' }}>
          Настройте параметры русскоязычного NLP‑конвейера перед запуском анализа.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>

        {/* Pipeline toggles */}
        <div className="card">
          <p className="field-label" style={{ marginBottom: 14 }}>Компоненты пайплайна</p>
          {([
            ['segmenter', 'Segmenter',      'Разбивка на предложения'],
            ['morph',     'MorphVocab',     'Морфологический анализ'],
            ['ner',       'NER',            'Распознавание сущностей'],
            ['dates',     'DatesExtractor', 'Извлечение дат'],
            ['lemmatize', 'Лемматизация',   'Приведение к начальной форме'],
            ['stopwords', 'Стоп-слова',     'Фильтрация шума'],
          ] as [keyof NatSettings, string, string][]).map(([key, title, desc]) => (
            <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 0', borderBottom: '1px solid var(--border)' }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{title}</div>
                <div style={{ fontSize: 11, color: 'var(--text-mid)' }}>{desc}</div>
              </div>
              <Toggle checked={settings[key] !== false} onChange={v => update(key, v)} />
            </div>
          ))}
        </div>

        {/* Params */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <p className="field-label">Минимальная длина токена</p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <input type="range" min={1} max={5}
                value={settings.minTokenLen ?? 2}
                onChange={e => update('minTokenLen', +e.target.value)}
                style={{ flex: 1 }} />
              <span style={{ fontFamily: 'var(--mono)', fontSize: 14, color: 'var(--cyan)', minWidth: 20, textAlign: 'right' }}>
                {settings.minTokenLen ?? 2}
              </span>
            </div>
          </div>

          <div className="card">
            <p className="field-label">Язык документов</p>
            <select className="field-input field-select"
              value={settings.lang ?? 'ru'}
              onChange={e => update('lang', e.target.value)}>
              <option value="ru">Русский (основной)</option>
              <option value="ru_en">Русский + Английский</option>
              <option value="en">Английский</option>
            </select>
          </div>

          <div className="card">
            <p className="field-label">Пользовательский словарь стоп-слов</p>
            <textarea className="field-input" rows={3}
              style={{ resize: 'none', fontFamily: 'var(--mono)', fontSize: 11 }}
              placeholder={'также\nкроме\nпомимо\n...'}
              value={settings.customStop ?? ''}
              onChange={e => update('customStop', e.target.value)} />
          </div>

          <div className="card" style={{ padding: '12px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <Icon name="info" size={13} color="var(--amber)" />
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--amber)', textTransform: 'uppercase', letterSpacing: '.06em' }}>
                Длинные документы
              </span>
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-mid)', lineHeight: 1.6 }}>
              Текст автоматически делится на чанки по 3000 символов с перекрытием 200.
            </p>
          </div>
        </div>
      </div>

      {/* Кнопка запуска */}
      <button
        className="btn btn-primary"
        onClick={handleRun}
        disabled={running}
        style={{ width: '100%', justifyContent: 'center', padding: '13px', marginBottom: 20 }}
      >
        {running
          ? <><span style={{ animation: 'spin-slow 1s linear infinite', display: 'inline-block' }}>⟳</span> Обработка...</>
          : done ? '↺ Запустить повторно' : '▶ Запустить Natasha'}
      </button>

      {/* Статистика после завершения */}
      {done && docStats.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
          {([
            [String(docStats.length), 'Документов'],
            [totalTokens.toLocaleString(), 'Токенов'],
            [String(docStats.reduce((s, d) => s + d.chunks_count, 0)), 'Чанков'],
            [String(docStats.reduce((s, d) => s + d.entities_count, 0)), 'Сущностей'],
          ] as [string, string][]).map(([n, l]) => (
            <div key={l} className="card" style={{ textAlign: 'center', padding: '16px 12px' }}>
              <div className="stat-num">{n}</div>
              <div className="stat-label">{l}</div>
            </div>
          ))}
        </div>
      )}

      {/* Терминал */}
      <div className="card">
        <p className="field-label" style={{ marginBottom: 10 }}>Системный журнал</p>
        <div className="terminal" ref={terminalRef}>
          {logs.map((l, i) => <LogEntry key={i} level={l.level} text={l.text} />)}
          {running && (
            <div style={{ color: 'var(--cyan)', fontFamily: 'var(--mono)', fontSize: 12, marginTop: 2 }}>
              $ обработка...<span className="cursor" />
            </div>
          )}
          {!running && (
            <div style={{ color: 'var(--cyan)', fontFamily: 'var(--mono)', fontSize: 12, marginTop: 2 }}>
              $ {done ? 'natasha завершена ✓' : 'готов к запуску'}<span className="cursor" />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default PageNatasha