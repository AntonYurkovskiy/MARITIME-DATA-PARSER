<svg width="800" height="200">
  <rect width="800" height="200" rx="20" fill="#003366"/>
  <text x="400" y="110" font-size="36" fill="white" text-anchor="middle">MARITIME DATA PARSER</text>
</svg>
 
 <div align="center">

<br>

<svg width="800" height="200" viewBox="0 0 800 200" xmlns="http://www.w3.org/2000/svg">
  <!-- Navy blue фон с градиентом -->
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#001F3F"/>
      <stop offset="100%" style="stop-color:#003366"/>
    </linearGradient>
  </defs>
  
  <rect width="800" height="200" rx="25" fill="url(#bgGrad)"/>
  
  <!-- Корабль (корпус + мачта + парус) -->
  <g fill="none" stroke="#E6F3FF" stroke-width="3" stroke-linecap="round">
    <!-- Корпус -->
    <path d="M150 120 Q180 140 220 130 Q260 125 300 135 L320 135"/>
    <!-- Мачта -->
    <line x1="235" y1="80" x2="235" y2="20"/>
    <!-- Парус -->
    <path d="M235 20 L200 60 L235 90 Z" fill="#B8D9FF" stroke="#66B3FF"/>
    <!-- Волны -->
    <path d="M100 160 Q140 155 180 165 Q220 160 260 170 Q300 165 340 170" fill="none" stroke="#66CCFF" stroke-width="4"/>
  </g>
  
  <!-- Якорь (база данных) -->
  <g transform="translate(450,90)">
    <rect x="0" y="0" width="30" height="60" rx="5" fill="#FF9900"/>
    <circle cx="15" cy="70" r="12" fill="#FFAA33"/>
    <line x1="15" y1="70" x2="15" y2="90" stroke="#CC7700" stroke-width="6"/>
  </g>
  
  <!-- Силуэт моряка -->
  <g fill="#E6F3FF" stroke="#B8D9FF" stroke-width="2">
    <!-- Голова -->
    <circle cx="380" cy="60" r="12"/>
    <!-- Тело + руки -->
    <rect x="375" y="72" width="10" height="25" rx="5"/>
    <line x1="375" y1="80" x2="355" y2="90" stroke-width="3"/>
    <line x1="385" y1="80" x2="405" y2="90" stroke-width="3"/>
    <!-- Ноги -->
    <line x1="378" y1="97" x2="372" y2="120" stroke-width="3"/>
    <line x1="382" y1="97" x2="388" y2="120" stroke-width="3"/>
    <!-- Фуражка -->
    <path d="M370 50 L390 50 L382 45 Z" fill="#003366"/>
  </g>
  
  <!-- Стрелка данных (pipeline) -->
  <g stroke="#66CCFF" stroke-width="5" stroke-linecap="round" fill="none">
    <line x1="500" y1="100" x2="580" y2="100"/>
    <polygon points="580,100 565,95 565,105"/>
  </g>
  
  <!-- База данных (цилиндр) -->
  <g transform="translate(600,80)">
    <rect x="0" y="0" width="35" height="40" rx="8" fill="#66CCFF"/>
    <rect x="5" y="40" width="25" height="10" rx="5" fill="#99DDFF"/>
    <line x1="17.5" y1="50" x2="17.5" y2="70" stroke="#99DDFF" stroke-width="8"/>
  </g>
  
  <!-- Текст -->
  <text x="400" y="35" font-family="Arial, sans-serif" font-size="28" 
        font-weight="bold" fill="white" text-anchor="middle" letter-spacing="1">
    MARITIME DATA PARSER
  </text>
  <text x="400" y="170" font-family="Arial, sans-serif" font-size="16" 
        fill="#E6F3FF" text-anchor="middle" font-weight="500">
    Sailors Database → Server Pipeline
  </text>
</svg>


<!-- <img src="https://via.placeholder.com/800x200/001F3F/E6F3FF?text=🚢+MARITIME+DATA+PARSER+-+Sailors+DB+%E2%86%92+Server" width="800"> -->

# 🚢 **Maritime Data Parser** ⚓

**Парсер базы данных моряков → Сервер API**

> BeautifulSoup + Python + Regex → JSON

## ✨ **Что делает**

| Функция | Код |
|---------|-----|
| 🧹 **Фильтр заглушек** | `iVBORw0KGgoAAAANSUhEUgAAARgAAAEZCAY` |
| 📊 **Парсинг таблиц** | `soup.find('table', class_='cv_body')` |
| 🔍 **Следующая ячейка** | `.find_next_sibling('td')` |
| 💾 **Очистка текста** | `re.sub(r'[^\x20-\\x7Eа-яА-ЯёЁ\\s]+|\\s+', ' ', text)` |

## 🚀 **Запуск**

```bash
pip install beautifulsoup4 lxml requests
python parser.py input.html --server https://api.example.com
