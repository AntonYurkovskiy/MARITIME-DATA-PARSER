<svg width="800" height="200">
  <rect width="800" height="200" rx="20" fill="#003366"/>
  <text x="400" y="110" font-size="36" fill="white" text-anchor="middle">MARITIME DATA PARSER</text>
</svg>
 
 <div align="center">

<br>

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
