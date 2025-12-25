from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import io

from services.parser import parse_reviews_file
from services.llm_client import analyze_reviews_with_llm
from services.report_pdf import build_pdf

app = FastAPI(
    title="Hotel Review Analyzer API",
    version="0.2.0",
    description="API для анализа отзывов отелей с помощью AI"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"ok": True, "status": "healthy"}


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(..., description="Файл с отзывами (xlsx, csv, txt)"),
    custom_prompt: str = Form("", description="Собственный промпт (необязательно)"),
    max_reviews: int = Form(200, description="Максимум отзывов для анализа"),
):
    """
    Анализ отзывов отеля.

    - **file**: Файл с отзывами (Excel, CSV или TXT)
    - **custom_prompt**: Собственный промпт для анализа (необязательно)
    - **max_reviews**: Максимальное количество отзывов для обработки
    """
    try:
        content = await file.read()
        reviews = parse_reviews_file(filename=file.filename or "", content=content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {str(e)}")

    if not reviews:
        raise HTTPException(status_code=400, detail="Не удалось найти отзывы в файле")

    # Limit reviews
    reviews_limited = reviews[:max_reviews]

    try:
        report = analyze_reviews_with_llm(
            reviews=reviews_limited,
            custom_prompt=custom_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")

    return {
        "report": report,
        "total_reviews": len(reviews),
        "analyzed_reviews": len(reviews_limited)
    }


@app.post("/analyze/pdf")
async def analyze_pdf(
    file: UploadFile = File(..., description="Файл с отзывами"),
    custom_prompt: str = Form("", description="Собственный промпт"),
    max_reviews: int = Form(200, description="Максимум отзывов"),
):
    """
    Анализ отзывов с возвратом PDF-отчета.
    """
    try:
        content = await file.read()
        reviews = parse_reviews_file(filename=file.filename or "", content=content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {str(e)}")

    if not reviews:
        raise HTTPException(status_code=400, detail="Не удалось найти отзывы в файле")

    reviews_limited = reviews[:max_reviews]

    try:
        report = analyze_reviews_with_llm(
            reviews=reviews_limited,
            custom_prompt=custom_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")

    try:
        pdf_bytes = build_pdf(report, title="Отчет по анализу отзывов")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации PDF: {str(e)}")

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=hotel_reviews_report.pdf"}
    )
