/* ── PAGE 1: Upload ── */
import { useState, useEffect } from 'react'
import Icon from '../components/Icon'
import { openFileDialog, onResult } from '../bridge'

interface PageUploadProps {
  files: { name: string; ext: string; size: number }[]
  setFiles: React.Dispatch<React.SetStateAction<{ name: string; ext: string; size: number }[]>>
}

const PageUpload = ({ files, setFiles }: PageUploadProps) => {
  const [drag, setDrag] = useState(false)
  const [loading, setLoading]         = useState(false)          // ← новое
  const [loadProgress, setLoadProgress] = useState({             // ← новое
    current: 0, total: 0, name: ''
  })

  // Слушаем ответ от Python — один раз при монтировании
  useEffect(() => {
      onResult((data) => {
        if (data.action === 'file_loading_started') {
          setLoading(true)
          setLoadProgress({ current: 0, total: data.total, name: '' })
          return
        }
        if (data.action === 'file_loading_progress') {
          setLoadProgress({ current: data.current, total: data.total, name: data.name })
          return
        }
        if (data.action === 'files_selected') {
          setLoading(false)
          if (data.files?.length > 0) {
            setFiles(prev => {
              const newFiles = data.files.filter(
                (f: any) => !prev.find(p => p.name === f.name)
              )
              return [...prev, ...newFiles]
            })
          }
        }
      })
  }, [])

  const handleClick = () => openFileDialog()

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDrag(false)
    // Drag-and-drop в Qt WebEngine не даёт реальных путей
    // поэтому открываем диалог
    openFileDialog()
  }

  const remove = (name: string) =>
    setFiles(prev => prev.filter(f => f.name !== name))

  const extColor = (name: string) => {
    const ext = name.split('.').pop()?.toLowerCase()
    return ({ pdf: 'var(--red)', docx: 'var(--cyan)', txt: 'var(--green)', csv: 'var(--amber)' } as Record<string, string>)[ext ?? ''] || 'var(--text-mid)'
  }

  return (
    <div className="animate-fadeUp">
      {/* Hero */}
      <div style={{ marginBottom: 36, display: 'flex', gap: 24, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 260 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <div style={{ width: 48, height: 48, borderRadius: 12, background: 'var(--cyan-dim)', border: '1px solid var(--border-hi)', display: 'flex', alignItems: 'center', justifyContent: 'center', animation: 'float 3s ease-in-out infinite' }}>
              <Icon name="network" size={22} color="var(--cyan)" />
            </div>
            <div>
              <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-.02em', lineHeight: 1.2 }}>
                Semantic<span style={{ color: 'var(--cyan)' }}>Analyzer</span>
              </h1>
              <p style={{ fontSize: 11, color: 'var(--text-mid)', fontFamily: 'var(--mono)' }}>
                Аналитическая система семантической обработки и визуализации текстовых документов
              </p>
            </div>
          </div>
          <p style={{ fontSize: 14, color: 'var(--text-mid)', lineHeight: 1.7, maxWidth: 440 }}>
            Загрузите документы для автоматического извлечения смысловых связей,
            тематического моделирования и построения семантических карт.
          </p>
        </div>

        {/* Форматы */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, minWidth: 240 }}>
          {([['PDF','Полный текст'],['DOCX','Word документы'],['TXT','Текстовые файлы'],['CSV','Табличные данные']] as [string,string][]).map(([fmt, desc]) => (
            <div key={fmt} className="card" style={{ padding: '12px 14px' }}>
              <div className={`badge badge-${fmt==='PDF'?'red':fmt==='DOCX'?'cyan':fmt==='TXT'?'green':'amber'}`} style={{ marginBottom: 6, fontSize: 10 }}>{fmt}</div>
              <div style={{ fontSize: 11, color: 'var(--text-mid)' }}>{desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Drop zone — вызывает Qt диалог */}
      <div
        className={`dropzone${drag ? ' drag-over' : ''}`}
        onClick={handleClick}
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={handleDrop}
        style={{ marginBottom: 20 }}
      >
        <div className="scan" />
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, pointerEvents: 'none' }}>
          <div style={{ width: 56, height: 56, borderRadius: '50%', border: '2px solid var(--border-hi)', background: 'var(--cyan-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="upload" size={24} color="var(--cyan)" />
          </div>
          <div>
            <p style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-hi)', marginBottom: 4 }}>
              Перетащите файлы или нажмите для выбора
            </p>
            <p style={{ fontSize: 12, color: 'var(--text-mid)' }}>
              Поддерживаемые форматы: PDF, DOCX, TXT, CSV · Максимум 50 МБ
            </p>
          </div>
        </div>
      </div>

      {loading && (
          <div className="card" style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--text-mid)' }}>
                Загрузка файлов...
              </span>
              <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--cyan)' }}>
                {loadProgress.current}/{loadProgress.total}
              </span>
            </div>
            <div className="progress-track">
              <div className="progress-fill shimmer" style={{
                width: `${loadProgress.total > 0
                  ? (loadProgress.current / loadProgress.total) * 100
                  : 0}%`
              }} />
            </div>
            {loadProgress.name && (
              <p style={{ fontSize: 11, color: 'var(--text-lo)', fontFamily: 'var(--mono)', marginTop: 6 }}>
                ↳ {loadProgress.name}
              </p>
            )}
          </div>
      )}

      {/* Files list */}
      {files.length > 0 && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-mid)', textTransform: 'uppercase', letterSpacing: '.06em' }}>
              Очередь · {files.length} файл{files.length > 1 ? 'а' : ''}
            </span>
            <button className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 11 }} onClick={() => setFiles([])}>
              Очистить всё
            </button>
          </div>
          <div className="files-list">
            {files.map(f => (
              <div key={f.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: 'var(--bg-deep)', borderRadius: 6, border: '1px solid var(--border)' }}>
                <Icon name="file" size={15} color={extColor(f.name)} />
                <span style={{ flex: 1, fontSize: 13, fontFamily: 'var(--mono)', color: 'var(--text-hi)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                <span style={{ fontSize: 11, color: 'var(--text-mid)', whiteSpace: 'nowrap' }}>
                  {f.size ? (f.size / 1024).toFixed(1) + ' KB' : '—'}
                </span>
                <button
                  onClick={() => remove(f.name)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: 'var(--text-lo)', transition: 'color .15s' }}
                  onMouseEnter={e => e.currentTarget.style.color = 'var(--red)'}
                  onMouseLeave={e => e.currentTarget.style.color = 'var(--text-lo)'}
                >
                  <Icon name="trash" size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {files.length === 0 && (
        <div style={{ textAlign: 'center', padding: '12px 0', color: 'var(--text-lo)', fontSize: 12, fontFamily: 'var(--mono)' }}>
          Файлы не выбраны
        </div>
      )}
    </div>
  )
}

export default PageUpload