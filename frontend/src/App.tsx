import { useState } from 'react'
import StepIndicator, { steps } from './components/StepIndicator'
import Icon from './components/Icon'
import PageUpload from './pages/PageUpload'
import PageNatasha from './pages/PageNatasha'
import PageBERTopic from './pages/PageBERTopic'
import PageAnalytics from './pages/PageAnalytics'
import type { ProcessedDocument } from './pages/TopicDetailModal'
import type { ThesaurusData } from './components/ThesaurusModal'

interface BtSettings {
  model: string
  minTopic: number
  numTopics: string
  umapComp: number
  outlierReduce: boolean
  dynamicTopics: boolean
  diversity: boolean
}

export interface TopicResult {
  id: number
  label: string
  count: number
  words: string[]
  scores: number[]
}

export interface DocTopic {
  name: string
  topic: number
  date: string | null
}

export interface BertopicResult {
  topics: TopicResult[]
  total_docs: number
  noise_pct: number
  coherence: number
  noise_count: number
  vos_data?: any
  // Путь к файлу vosviewer_keywords.json в сессии.
  // Данные не передаются через сигнал (может быть >100KB) — фронт читает файл сам.
  keywords_vos_path?: string | null
  doc_topics?: DocTopic[]
}

function App() {
  const [step, setStep]   = useState(0)
  const [files, setFiles] = useState<{ name: string; ext: string; size: number }[]>([])

  const [natSettings, setNatSettings] = useState<Record<string, any>>({})
  const [btSettings, setBtSettings]   = useState<BtSettings>({
    model: 'rubert-tiny2', minTopic: 5, numTopics: 'auto',
    umapComp: 5, outlierReduce: true, dynamicTopics: true, diversity: true
  })
  const [btResult, setBtResult]       = useState<BertopicResult | null>(null)
  const [natashaDocs, setNatashaDocs] = useState<ProcessedDocument[]>([])
  const [theme, setTheme]             = useState<'dark' | 'light'>('dark')
  const [thesaurus, setThesaurus]     = useState<ThesaurusData | null>(null)

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.body.className = next === 'light' ? 'theme-light' : ''
  }

  const canNext = () => {
    if (step === 0) return files.length > 0
    return true
  }

  // Страницы рендерим ВСЕ сразу, скрываем через display:none.
  // Это сохраняет state и ref при переходах между шагами —
  // PageAnalytics не размонтируется и не теряет загруженные keywords данные.
  return (
    <div style={{ minHeight: '100vh', position: 'relative', zIndex: 1 }}>
      <div style={{ borderBottom: '1px solid var(--border)', background: 'rgba(7,11,20,.8)', backdropFilter: 'blur(10px)', padding: '0 32px', display: 'flex', alignItems: 'center', gap: 16, height: 52, position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 28, height: 28, borderRadius: 7, background: 'var(--cyan-dim)', border: '1px solid var(--border-hi)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="network" size={14} color="var(--cyan)" />
          </div>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700, color: 'var(--cyan)' }}>SemanticAnalyzer</span>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button onClick={toggleTheme} className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 11 }}>
            {theme === 'dark' ? '☀ Светлая' : '☾ Тёмная'}
          </button>
          {files.length > 0 && <span className="badge badge-cyan">{files.length} файл{files.length > 1 ? 'а' : ''}</span>}
          {thesaurus && <span className="badge badge-amber" title="Тезаурус активен">📚 {Object.keys(thesaurus).length} записей</span>}
          {btResult && <span className="badge badge-green">{btResult.topics.length} тем</span>}
          <span className="badge badge-amber">Python 3.11</span>
          <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-lo)' }}>v1.0.0</span>
        </div>
      </div>

      <div style={{ maxWidth: 960, margin: '0 auto', padding: '36px 24px 60px' }}>
        <StepIndicator current={step} />

        {/* Все страницы рендерятся сразу — скрываем через display:none */}
        {/* Это сохраняет state/ref/данные при переходах между шагами */}
        <div style={{ minHeight: 480 }}>
          <div style={{ display: step === 0 ? 'block' : 'none' }}>
            <PageUpload files={files} setFiles={setFiles} thesaurus={thesaurus} setThesaurus={setThesaurus} />
          </div>
          <div style={{ display: step === 1 ? 'block' : 'none' }}>
            <PageNatasha settings={natSettings} setSettings={setNatSettings} setNatashaDocs={setNatashaDocs} thesaurus={thesaurus} />
          </div>
          <div style={{ display: step === 2 ? 'block' : 'none' }}>
            <PageBERTopic btSettings={btSettings} setBtSettings={setBtSettings} setBtResult={setBtResult} />
          </div>
          <div style={{ display: step === 3 ? 'block' : 'none' }}>
            <PageAnalytics btResult={btResult} natashaDocs={natashaDocs} />
          </div>
        </div>

        <div style={{ marginTop: 32, display: 'flex', alignItems: 'center', gap: 16, justifyContent: 'space-between' }}>
          <button className="nav-arrow" onClick={() => setStep(s => s - 1)} disabled={step === 0}>
            <Icon name="arrow_l" size={18} />
          </button>
          <div style={{ display: 'flex', gap: 8, flex: 1, justifyContent: 'center' }}>
            {steps.map((_, i) => (
              <div key={i} style={{
                width: i === step ? 24 : 8, height: 8, borderRadius: 4,
                background: i < step ? 'var(--green)' : i === step ? 'var(--cyan)' : 'var(--border)',
                transition: 'all .3s',
                boxShadow: i === step ? '0 0 10px rgba(0,212,255,.5)' : 'none',
                cursor: i <= step ? 'pointer' : 'default',
              }} onClick={() => i <= step && setStep(i)} />
            ))}
          </div>
          <button className="nav-arrow" onClick={() => setStep(s => s + 1)}
            disabled={step === steps.length - 1 || !canNext()}
            style={{ background: canNext() && step < steps.length - 1 ? 'var(--cyan-dim)' : undefined }}>
            <Icon name="arrow_r" size={18} />
          </button>
        </div>

        {step === 0 && files.length === 0 && (
          <p style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-lo)', marginTop: 10, fontFamily: 'var(--mono)' }}>
            Загрузите минимум 1 файл для продолжения
          </p>
        )}

        <div style={{ marginTop: 60, textAlign: 'center', fontSize: 11, color: 'var(--text-lo)', fontFamily: 'var(--mono)', borderTop: '1px solid var(--border)', paddingTop: 20 }}>
          <div>Автор: Лебедева Елизавета</div>
          <div>© 2026 Все права защищены</div>
          <div>Разработано в рамках выпускной квалификационной работы гр. ИДБ-22-12</div>
        </div>
      </div>
    </div>
  )
}

export default App
