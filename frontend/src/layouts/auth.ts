export const authLayout = (title: string, content: string) => `
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="theme-color" content="#0f0f0f" />
  <link rel="icon" type="image/png" href="/favicon.png" />
  <link rel="apple-touch-icon" href="/favicon.png" />
  <link rel="manifest" href="/manifest.json" />
  <link rel="stylesheet" href="/style.css" />
  <title>DAIOS — ${title}</title>
</head>
<body style="background:#0f0f0f; color:#e8e8e8; font-family: 'Inter', system-ui, sans-serif; margin:0;">
  <div class="auth-container">
    <div class="auth-card">
      <div style="text-align:center; margin-bottom:32px;">
        <div style="font-size:28px; font-weight:700; letter-spacing:-1px; color:#e8e8e8;">DAIOS</div>
        <div style="font-size:13px; color:#555; margin-top:4px;">Personal productivity system</div>
      </div>
      ${content}
    </div>
  </div>
</body>
</html>
`
