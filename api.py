from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse, FileResponse
import language_tool_python
import matplotlib.pyplot as plt
from collections import Counter
import io
from googletrans import Translator
from pydantic import BaseModel
import re

app = FastAPI()

class TextAnalyzer:
    def __init__(self):
        self.tool = language_tool_python.LanguageTool('en-US', remote_server='https://api.languagetool.org')
        self.translator = Translator()
        
        self.error_type_colors = {
            'grammar': 'red',
            'typographical': 'blue',
            'spelling': 'green',
            'style': 'orange'
        }

    def apply_corrections(self, text, matches):
        corrected_text = text
        for match in reversed(matches):
            if match.replacements:
                start = match.offset
                end = match.offset + match.errorLength
                corrected_text = (
                    corrected_text[:start]
                    + match.replacements[0]
                    + corrected_text[end:]
                )
        return corrected_text

    def create_error_chart(self, matches):
        error_types = [match.ruleIssueType for match in matches]
        counter = Counter(error_types)

        plt.figure(figsize=(8, 5))
        bars = plt.bar(counter.keys(), counter.values(), color=[self.error_type_colors.get(key, 'gray') for key in counter.keys()])
        plt.title("Распределение типов ошибок")
        plt.xlabel("Тип ошибки")
        plt.ylabel("Количество")

        for bar in bars:
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), int(bar.get_height()), ha='center', va='bottom')

        plt.tight_layout()
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        plt.close()
        return buffer

    def translate_native_words(self, native_words):
        translations = {}

        if not native_words:
            return {"Нет слов на родном языке": "Перевод не требуется"}

        for word in native_words:
            try:
                # Переводим слово с русского на английский
                translation = self.translator.translate(word, src='ru', dest='en')
                translations[word] = translation.text
            except Exception as e:
                # Обработка исключений
                translations[word] = f"Ошибка перевода: {str(e)}"

        return translations

    def analyze_text(self, text):
        matches = self.tool.check(text)
        corrected_text = self.apply_corrections(text, matches)

        word_count = len(text.split())
        error_count = len(matches)

        native_words = [word for word in text.split() if not word.isascii()]
        translations = self.translate_native_words(native_words)

        error_details = [
            {
                "type": match.ruleIssueType,
                "text": text[match.offset:match.offset + match.errorLength],
                "message": match.message,
                "suggestions": match.replacements
            }
            for match in matches
        ]

        return {
            "corrected_text": corrected_text,
            "error_count": error_count,
            "word_count": word_count,
            "error_details": error_details,
            "translations": translations
        }

analyzer = TextAnalyzer()

# Создаём класс для данных, которые будут отправляться в запросах
class TextRequest(BaseModel):
    text: str

@app.post("/corrected_text")
async def corrected_text(request: TextRequest):
    analysis = analyzer.analyze_text(request.text)
    return JSONResponse(content={"corrected_text": analysis["corrected_text"]})

@app.post("/error_count")
async def error_count(request: TextRequest):
    analysis = analyzer.analyze_text(request.text)
    return JSONResponse(content={"error_count": analysis["error_count"]})

@app.post("/word_count")
async def word_count(request: TextRequest):
    analysis = analyzer.analyze_text(request.text)
    return JSONResponse(content={"word_count": analysis["word_count"]})

@app.post("/error_details")
async def error_details(request: TextRequest):
    analysis = analyzer.analyze_text(request.text)
    return JSONResponse(content={"error_details": analysis["error_details"]})

@app.post("/translate_native_words")
async def translations(request: TextRequest):
    analysis = analyzer.analyze_text(request.text)
    return JSONResponse(content={"translations": analysis["translations"]})

@app.post("/error_chart")
async def error_chart(request: TextRequest):
    matches = analyzer.tool.check(request.text)
    if not matches:
        return JSONResponse(content={"message": "Ошибок не обнаружено"})

    chart = analyzer.create_error_chart(matches)
    return FileResponse(chart, media_type="image/png", filename="error_chart.png")


@app.post("/translate_to_russian")
async def translate_to_russian(request: TextRequest):
    try:
        translation = analyzer.translator.translate(request.text, src='en', dest='ru').text
        # Добавляем пробел после точки и восклицательного/вопросительного знака, если его нет
        translation = re.sub(r'([.!?])(\S)', r'\1 \2', translation)
        return JSONResponse(content={"original_text": request.text, "translated_text": translation})
    except Exception as e:
        return JSONResponse(content={"error": str(e)})

@app.get("/")
async def root():
    return {"message": "Text Analyzer API"}
