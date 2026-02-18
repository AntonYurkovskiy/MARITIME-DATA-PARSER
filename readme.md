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
