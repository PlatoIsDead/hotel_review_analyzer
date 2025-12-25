import io
from typing import List, Dict

import pandas as pd


def parse_reviews_file(filename: str, content: bytes) -> List[Dict]:
    """Parse reviews from uploaded file (CSV, Excel, or TXT)."""
    name = (filename or "").lower()

    if name.endswith(".csv"):
        return _parse_csv(content)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(io.BytesIO(content))
        return _df_to_reviews(df)

    if name.endswith(".txt"):
        text = _decode_text(content)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return [{"review_text": ln} for ln in lines]

    raise ValueError("Неподдерживаемый формат файла. Используйте CSV, XLSX или TXT.")


def _decode_text(content: bytes) -> str:
    """Try multiple encodings to decode text."""
    encodings = ['utf-8', 'cp1251', 'cp1252', 'latin-1', 'iso-8859-1']

    for encoding in encodings:
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

    # Last resort: ignore errors
    return content.decode('utf-8', errors='ignore')


def _parse_csv(content: bytes) -> List[Dict]:
    """Parse CSV with automatic encoding detection."""
    encodings = ['utf-8', 'cp1251', 'cp1252', 'latin-1', 'iso-8859-1']

    for encoding in encodings:
        try:
            df = pd.read_csv(io.BytesIO(content), encoding=encoding)
            # Verify we got readable data by checking first row
            if len(df) > 0:
                first_val = str(df.iloc[0, 0])
                # Check if it looks like garbled text
                if '�' not in first_val:
                    return _df_to_reviews(df)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue

    # Fallback: try with errors='replace'
    df = pd.read_csv(io.BytesIO(content), encoding='utf-8', encoding_errors='replace')
    return _df_to_reviews(df)


def _df_to_reviews(df: pd.DataFrame) -> List[Dict]:
    """Extract review text from DataFrame."""
    if df.empty:
        return []

    cols_lower = [c.lower() for c in df.columns]

    # Try to find review/text column
    review_col = None
    for target in ['review', 'text', 'comment', 'отзыв', 'комментарий', 'текст']:
        if target in cols_lower:
            review_col = df.columns[cols_lower.index(target)]
            break

    # Fallback to first column
    if review_col is None:
        review_col = df.columns[0]

    reviews = []
    for _, row in df.iterrows():
        text = str(row[review_col]).strip()
        if text and text.lower() not in ['nan', 'none', '']:
            reviews.append({"review_text": text})

    return reviews
