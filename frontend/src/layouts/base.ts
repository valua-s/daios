export const baseLayout = (title: string, content: string, activePage: string) => `
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="theme-color" content="#0f0f0f" />
  <link rel="manifest" href="/manifest.json" />
  <link rel="stylesheet" href="/style.css" />
  <title>DAIOS — ${title}</title>
</head>
<body style="background:#0f0f0f; color:#e8e8e8; font-family: 'Inter', system-ui, sans-serif; margin:0;">

  <!-- Mobile header -->
  <header class="mobile-header">
    <span style="font-size:16px; font-weight:700; letter-spacing:-0.5px;">DAIOS</span>
    <button class="burger-btn" onclick="document.querySelector('.layout-sidebar').classList.toggle('open'); document.querySelector('.sidebar-overlay').classList.toggle('open');">
      <span></span><span></span><span></span>
    </button>
  </header>

  <!-- Sidebar overlay -->
  <div class="sidebar-overlay" onclick="document.querySelector('.layout-sidebar').classList.remove('open'); this.classList.remove('open');"></div>

  <div class="layout-root">

    <!-- Sidebar -->
    <nav class="layout-sidebar">
      <div class="sidebar-logo" style="padding:0 20px 24px; font-size:18px; font-weight:700; letter-spacing:-0.5px; color:#e8e8e8;">
        DAIOS
      </div>

      ${navItem('/today', '📋', 'Сегодня', activePage === 'today')}
      ${navItem('/backlog', '🗂', 'Бэклог', activePage === 'backlog')}
      ${navItem('/workouts', '🏋️', 'Тренировки', activePage === 'workouts')}
      ${navItem('/focus', '🎯', 'Фокус', activePage === 'focus')}
      ${navItem('/settings', '⚙️', 'Настройки', activePage === 'settings')}
    </nav>

    <!-- Main -->
    <main class="layout-main">
      ${content}
    </main>

  </div>

</body>
</html>
`

const navItem = (href: string, icon: string, label: string, active: boolean) => `
  <a href="${href}" data-active="${active}" style="
    display:flex; align-items:center; gap:10px;
    padding:10px 20px;
    font-size:14px;
    text-decoration:none;
    color: ${active ? '#e8e8e8' : '#666'};
    background: ${active ? '#1e1e1e' : 'transparent'};
    border-left: 2px solid ${active ? '#7c6aff' : 'transparent'};
    transition: all 0.15s;
  "><span style="width:20px; text-align:center;">${icon}</span>${label}</a>
`
