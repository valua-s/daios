export const table = (headers: string[], rows: string[][], columnStyles?: string[], columnClasses?: string[]) => `
  <div style="overflow-x:auto;">
    <table style="width:100%; border-collapse:collapse; font-size:14px; table-layout:fixed;">
      <thead>
        <tr style="border-bottom:1px solid #2a2a2a;">
          ${headers.map((h, i) => `<th class="${columnClasses?.[i] ?? ''}" style="text-align:left; padding:10px 12px; color:#666; font-weight:500; white-space:nowrap; ${columnStyles?.[i] ?? ''}">${h}</th>`).join('')}
        </tr>
      </thead>
      <tbody>
        ${rows.map(row => `
          <tr style="border-bottom:1px solid #1e1e1e; transition:background 0.1s;" onmouseover="this.style.background='#161616'" onmouseout="this.style.background='transparent'">
            ${row.map((cell, i) => `<td class="${columnClasses?.[i] ?? ''}" style="padding:12px 12px; color:#e8e8e8; vertical-align:middle; ${columnStyles?.[i] ?? ''}">${cell}</td>`).join('')}
          </tr>
        `).join('')}
      </tbody>
    </table>
  </div>
`

export const badge = (label: string, color: string) =>
  `<span style="display:inline-block; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:500; background:${color}22; color:${color};">${label}</span>`

export const btn = (label: string, href: string, variant: 'primary' | 'ghost' | 'danger' = 'ghost') => {
  const colors = {
    primary: 'background:#7c6aff; color:#fff; border:none;',
    ghost: 'background:transparent; color:#666; border:1px solid #2a2a2a;',
    danger: 'background:transparent; color:#e05252; border:1px solid #e0525233;',
  }
  return `<a href="${href}" style="display:inline-block; padding:6px 14px; border-radius:6px; font-size:13px; text-decoration:none; cursor:pointer; ${colors[variant]}">${label}</a>`
}

export const iconBtn = (icon: string, title: string, href: string, color = '#555') =>
  `<a href="${href}" title="${title}" style="color:${color}; text-decoration:none; font-size:16px; padding:4px 6px;">${icon}</a>`
