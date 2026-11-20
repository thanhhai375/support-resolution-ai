
import { Users } from 'lucide-react'

export default function UserManagement() {
  return (
    <>
      <div className="page-title-row">
        <div>
          <h1>Quản lý người dùng</h1>
          <p className="subtitle">
            Quản lý tài khoản và quyền truy cập hệ thống.
          </p>
        </div>
      </div>

      <section className="panel settings-panel">
        <span className="settings-icon">
          <Users size={28} aria-hidden="true" />
        </span>

        <h2>User Management</h2>
        <p>Chức năng quản lý người dùng đang được phát triển.</p>
        <p>
          Trang này dành riêng cho ADMIN.
          Chưa tích hợp chức năng quản lý tài khoản thực tế.
        </p>
      </section>
    </>
  )
}
