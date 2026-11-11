export interface LoginFormInputs {
  email: string
  password: string
}

export interface LoginFormErrors {
  email?: string
  password?: string
}

export function validateLogin(
  values: LoginFormInputs
): LoginFormErrors {
  const errors: LoginFormErrors = {}

  const email = values.email.trim()

  if (!email) {
    errors.email = 'Vui lòng nhập email.'
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.email = 'Email không đúng định dạng.'
  }

  if (!values.password) {
    errors.password = 'Vui lòng nhập mật khẩu.'
  } else if (values.password.length < 6) {
    errors.password = 'Mật khẩu phải có ít nhất 6 ký tự.'
  }

  return errors
}
