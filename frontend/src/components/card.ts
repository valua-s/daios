export const card = (content: string, style = '') =>
  `<div style="background:#181818; border:1px solid #2a2a2a; border-radius:10px; padding:20px; ${style}">${content}</div>`

export const sectionTitle = (title: string, action = '') =>
  `<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px;">
    <h2 style="margin:0; font-size:15px; font-weight:600; color:#e8e8e8;">${title}</h2>
    ${action}
  </div>`

export const emptyState = (text: string) =>
  `<div style="text-align:center; padding:40px 0; color:#444; font-size:14px;">${text}</div>`
