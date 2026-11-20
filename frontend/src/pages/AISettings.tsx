
import { useCallback, useEffect, useState } from 'react'
import { useBeforeUnload, useBlocker } from 'react-router-dom'
import { Bot, ShieldCheck, CheckCircle2, AlertCircle } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'

interface AIConfig {
  safetyChecker: boolean
  intentModel: string
  confidenceThreshold: number
}

const STORAGE_KEY = 'support-ai-settings-demo-v1'

const defaultConfig: AIConfig = {
  safetyChecker: true,
  intentModel: 'default',
  confidenceThreshold: 75,
}

const safeKeywords = [
  'Quá nhiệt',
  'Cháy',
  'Tia lửa',
  'Rò điện',
  'Khói',
  'Mùi khét',
]

function loadConfig(): AIConfig {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (!saved) return { ...defaultConfig }

    const parsed: unknown = JSON.parse(saved)

    if (typeof parsed !== 'object' || parsed === null) {
      return { ...defaultConfig }
    }

    const data = parsed as Record<string, unknown>

    return {
      safetyChecker:
        typeof data.safetyChecker === 'boolean'
          ? data.safetyChecker
          : defaultConfig.safetyChecker,

      intentModel:
        data.intentModel === 'default' ||
        data.intentModel === 'enhanced'
          ? data.intentModel
          : defaultConfig.intentModel,

      confidenceThreshold:
        typeof data.confidenceThreshold === 'number' &&
        Number.isFinite(data.confidenceThreshold)
          ? Math.max(0, Math.min(100, data.confidenceThreshold))
          : defaultConfig.confidenceThreshold,
    }
  } catch {
    return { ...defaultConfig }
  }
}

export default function AISettings() {
  const { role } = useAuth()
  const isAdmin = role === 'ADMIN'


const [config, setConfig] = useState<AIConfig>(loadConfig)
const [savedConfig, setSavedConfig] = useState<AIConfig>(loadConfig)
const [message, setMessage] = useState('')

const hasChanges =
  config.safetyChecker !== savedConfig.safetyChecker ||
  config.intentModel !== savedConfig.intentModel ||
  config.confidenceThreshold !== savedConfig.confidenceThreshold

  const blocker = useBlocker(isAdmin && hasChanges)

  useEffect(() => {
    if (blocker.state !== 'blocked') return

    const confirmed = window.confirm(
      'Bạn có thay đổi cấu hình AI chưa lưu.\n\n' +
      'Bạn có chắc muốn rời trang và bỏ các thay đổi này?'
    )

    if (confirmed) {
      blocker.proceed()
    } else {
      blocker.reset()
    }
  }, [blocker])

  useBeforeUnload(
    useCallback(
      (event) => {
        if (!isAdmin || !hasChanges) return

        event.preventDefault()
        event.returnValue = ''
      },
      [isAdmin, hasChanges]
    )
  )

  useEffect(() => {
    if (!isAdmin || !hasChanges) return

    function handleBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault()
      event.returnValue = ''
    }

    window.addEventListener('beforeunload', handleBeforeUnload)

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [isAdmin, hasChanges])

function saveSettings() {
  if (!isAdmin || !hasChanges) return

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
    setSavedConfig({ ...config })
    setMessage('Đã lưu cấu hình thử nghiệm trên trình duyệt.')
  } catch {
    setMessage('Không thể lưu cấu hình trên trình duyệt.')
  }
}

function resetSettings() {
  if (!isAdmin) return

  const confirmed = window.confirm(
    'Bạn có chắc muốn khôi phục cấu hình AI về mặc định?'
  )

  if (!confirmed) return

  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(defaultConfig)
    )

    setConfig({ ...defaultConfig })
    setSavedConfig({ ...defaultConfig })

    setMessage(
      'Đã khôi phục và lưu cấu hình mặc định thành công.'
    )
  } catch {
    setMessage('Không thể khôi phục cấu hình.')
  }
}


  return (
    <>
      <div className="page-title-row">
        <div>
          <h1>AI Settings</h1>
          <p className="subtitle">
            Quản lý cấu hình trợ lý AI cho không gian làm việc.
          </p>
        </div>
      </div>

      <section className="panel ai-config-panel">
        <div className="ai-config-heading">
          <span className="settings-icon">
            <Bot size={26} aria-hidden="true" />
          </span>

          <div>
            <h2>Cấu hình trợ lý AI</h2>
            <p>
              Điều chỉnh các tham số hỗ trợ phân loại ticket
              và kiểm tra an toàn.
            </p>
          </div>
        </div>

        <p className="ai-config-access">
          {isAdmin
            ? 'Quyền ADMIN: Bạn có thể thay đổi và lưu cấu hình thử nghiệm.'
            : 'Quyền chỉ xem: Chỉ ADMIN mới được thay đổi và lưu cấu hình.'}
        </p>

        <div className="ai-config-grid">
          <div className="ai-config-item">
            <h3>Safety Checker</h3>
            <p>Bật hoặc tắt chức năng kiểm tra cảnh báo an toàn.</p>

            <label className="ai-config-toggle">
              <input
                type="checkbox"
                checked={config.safetyChecker}
                disabled={!isAdmin}
                onChange={event => {
                  setConfig(current => ({
                    ...current,
                    safetyChecker: event.target.checked,
                  }))
                  setMessage('')
                }}
              />
            <span
              className={`ai-safety-state ${
                config.safetyChecker
                  ? 'ai-safety-state--on'
                  : 'ai-safety-state--off'
              }`}
            >
              {config.safetyChecker ? (
                <ShieldCheck size={16} aria-hidden="true" />
              ) : (
                <AlertCircle size={16} aria-hidden="true" />
              )}

              {config.safetyChecker ? 'Đang bật' : 'Đang tắt'}
            </span>
            </label>
          </div>

          <div className="ai-config-item">
            <h3>Intent Model</h3>
            <p>Chọn mô hình phân loại ý định của ticket.</p>

            <select
              aria-label="Intent Model"
              value={config.intentModel}
              disabled={!isAdmin}
              onChange={event => {
                setConfig(current => ({
                  ...current,
                  intentModel: event.target.value,
                }))
                setMessage('')
              }}
            >
              <option value="default">
                Default Model (Demo)
              </option>
              <option value="enhanced">
                Enhanced Model (Demo)
              </option>
            </select>
              <p className="ai-model-description">
                {config.intentModel === 'default'
                  ? 'Default Model: Cấu hình phân loại ý định mặc định dùng để minh họa giao diện.'
                  : 'Enhanced Model: Tùy chọn mô hình nâng cao ở chế độ demo, chưa kết nối mô hình AI thực tế.'}
              </p>
          </div>

          <div className="ai-config-item">
            <h3>Confidence Threshold</h3>
            <p>Ngưỡng độ tin cậy của kết quả phân loại.</p>

            <div className="ai-threshold-value">
              {config.confidenceThreshold}%
            </div>

            <input
              type="range"
              min="0"
              max="100"
              step="5"
              aria-label="Confidence Threshold"
              value={config.confidenceThreshold}
              disabled={!isAdmin}
              onChange={event => {
                setConfig(current => ({
                  ...current,
                  confidenceThreshold: Number(event.target.value),
                }))
                setMessage('')
              }}
            />
            <div className="ai-threshold-marks" aria-hidden="true">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </div>

            <p className="ai-threshold-description">
              {config.confidenceThreshold < 50
                ? 'Ngưỡng thấp: AI có thể đưa ra nhiều gợi ý hơn, nhưng độ tin cậy có thể thấp.'
                : config.confidenceThreshold < 80
                  ? 'Ngưỡng trung bình: Cân bằng giữa số lượng gợi ý và độ tin cậy.'
                  : 'Ngưỡng cao: AI cần độ tin cậy lớn hơn trước khi đưa ra gợi ý.'}
            </p>
          </div>

          <div className="ai-config-item">
            <h3>SAFE Keywords</h3>
            <p>
              Danh sách từ khóa cảnh báo an toàn (minh họa, chỉ đọc).
            </p>

            <div className="ai-keyword-list">
              {safeKeywords.map(keyword => (
                <span className="ai-keyword" key={keyword}>
                  {keyword}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="ai-config-footer">
          <span className="settings-policy">
            <ShieldCheck size={17} aria-hidden="true" />
            Nhân viên cần kiểm tra gợi ý AI trước khi áp dụng.
          </span>
        <div className="ai-config-actions">
          <span
            className={`ai-save-status ${
              hasChanges
                ? 'ai-save-status--pending'
                : 'ai-save-status--saved'
            }`}
            role="status"
            aria-live="polite"
          >
            {hasChanges ? (
              <>
                <AlertCircle size={17} aria-hidden="true" />
                Có thay đổi chưa lưu
              </>
            ) : (
              <>
                <CheckCircle2 size={17} aria-hidden="true" />
                Đã lưu tất cả thay đổi
              </>
            )}
          </span>
          <button
            type="button"
            className="ai-reset-button"
            disabled={!isAdmin}
            onClick={resetSettings}
          >
            Khôi phục mặc định
          </button>

          <button
            type="button"
            className="primary-button"
            disabled={!isAdmin || !hasChanges}
            onClick={saveSettings}
          >
            {hasChanges && isAdmin
              ? 'Lưu thay đổi'
              : 'Đã lưu cài đặt'}
          </button>
        </div>

        </div>

        {message && (
          <p className="ai-config-message" role="status">
            {message}
          </p>
        )}

        <p className="ai-config-disclaimer">
          Chế độ thử nghiệm: cấu hình chỉ được lưu trên trình duyệt,
          chưa kết nối API Backend.
        </p>
      </section>
    </>
  )
}
