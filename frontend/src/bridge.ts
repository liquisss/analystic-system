declare const QWebChannel: any

export type BridgeCallback = (data: any) => void

let backendObject: any = null
const resultCallbacks: BridgeCallback[] = []

export async function initBridge(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof (window as any).qt === 'undefined') {
      console.warn('[Bridge] Qt не обнаружен — режим браузера')
      resolve()
      return
    }

    const script = document.createElement('script')
    script.src = 'qrc:///qtwebchannel/qwebchannel.js'
    script.onload = () => {
      new QWebChannel((window as any).qt.webChannelTransport, (channel: any) => {
        backendObject = channel.objects.backend

        // Подключаем сигнал ОДИН РАЗ при инициализации
        backendObject.result_ready.connect((raw: string) => {
          const data = JSON.parse(raw)
          console.log('[Bridge] получено:', data)
          resultCallbacks.forEach(cb => cb(data))
        })

        console.log('[Bridge] мост установлен')
        resolve()
      })
    }
    script.onerror = () => {
      console.error('[Bridge] не удалось загрузить qwebchannel.js')
      resolve()
    }
    document.head.appendChild(script)
  })
}

export function callPython(method: string, arg: string = ''): void {
  if (!backendObject) {
    console.warn('[Bridge] мост не инициализирован')
    return
  }
  backendObject[method](arg)
}

// Теперь onResult просто регистрирует колбек в массив
export function onResult(callback: BridgeCallback): void {
  resultCallbacks.push(callback)
}

export function openFileDialog(): void {
  if (!backendObject) {
    console.warn('[Bridge] мост не инициализирован')
    return
  }
  backendObject.open_file_dialog()
}

export function runNatasha(settings: Record<string, any>): void {
  if (!backendObject) {
    console.warn('[Bridge] мост не инициализирован')
    return
  }
  backendObject.run_natasha(JSON.stringify(settings))
}

export function runBertopic(settings: Record<string, any>): void {
  if (!backendObject) {
    console.warn('[Bridge] мост не инициализирован')
    return
  }
  backendObject.run_bertopic_analysis(JSON.stringify(settings))
}

export function generatePdfReport(sections: Record<string, boolean>): void {
  if (!backendObject) return
  backendObject.generate_pdf_report(JSON.stringify({ sections }))
}

export function saveFileDialog(sourcePath: string): void {
  if (!backendObject) return
  backendObject.save_file_dialog(sourcePath)
}