import os
import json
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel, field_validator
from typing import Dict, Any
import datetime
from dotenv import load_dotenv
from groq import Groq


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY is not set in the environment variables.")

client = Groq(api_key=api_key)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="AI-Driven Restaurant Assistant API",
    version="1.0.2",
    docs_url="/docs" if os.getenv("ENABLE_DOCS", "false").lower() == "true" else None,
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


MAX_MESSAGE_LENGTH = 500 
VALID_INTENTS = {"BOOKING", "BILLING", "COMPLAINT", "GENERAL_INQUIRY"}


class IncomingMessage(BaseModel):
    message_id: str
    raw_message: str

    @field_validator("raw_message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        if len(v) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"raw_message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters."
            )
        v = v.strip()
        injection_markers = ["ignore previous", "system:", "assistant:", "###"]
        lower_v = v.lower()
        for marker in injection_markers:
            if marker in lower_v:
                raise ValueError("Invalid characters or patterns detected in message.")
        return v

    @field_validator("message_id")
    @classmethod
    def validate_message_id(cls, v: str) -> str:
        if not v or len(v) > 64:
            raise ValueError("message_id must be between 1 and 64 characters.")
        return v


class AIAnalyzedResult(BaseModel):
    message_id: str
    intent: str
    confidence_score: float
    extracted_entities: Dict[str, Any]
    reply_message: str


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )



@app.post("/api/v1/analyze", response_model=AIAnalyzedResult)
@limiter.limit("20/minute")
async def analyze_text(request: Request, payload: IncomingMessage):
    try:
        text = payload.raw_message.lower()
        hari_ini = datetime.date.today().strftime("%Y-%m-%d")

        system_prompt = f"""
        Anda adalah asisten AI pintar untuk sebuah restoran. 
        Tugas Anda adalah mengekstrak niat (intent) dari pesan pelanggan dan WAJIB mengembalikannya dalam format JSON.
        
        Konteks Waktu Saat Ini: Hari ini adalah tanggal {hari_ini}. 
        Jika pelanggan menyebut "besok", hitung tanggalnya dari hari ini.
        Jika pelanggan tidak menyebutkan jam, gunakan default "19:00".
        Jika pelanggan tidak menyebutkan jumlah orang, gunakan default 2.
        
        Pilihan Intent yang valid HANYA: 
        - "BOOKING" (ingin reservasi/pesan meja)
        - "BILLING" (menanyakan tagihan/pembayaran)
        - "COMPLAINT" (marah/komplain layanan)
        - "GENERAL_INQUIRY" (pertanyaan umum)

        Format JSON yang WAJIB Anda kembalikan persis seperti ini:
        {{
            "intent": "BOOKING",
            "confidence_score": 0.95,
            "extracted_entities": {{
                "table_type": "VIP/REGULAR",
                "pax": 5,
                "date": "YYYY-MM-DD",
                "time": "HH:MM"
            }},
            "reply_message": "Kalimat balasan konfirmasi yang ramah dan profesional untuk pelanggan."
        }}
        
        PENTING: Hanya kembalikan JSON. Jangan tambahkan teks lain.
        """

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Pesan: {text}\nKeluarkan hanya JSON."},
            ],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        response_text = chat_completion.choices[0].message.content
        ai_response = json.loads(response_text)
        raw_intent = ai_response.get("intent", "GENERAL_INQUIRY")
        intent = raw_intent if raw_intent in VALID_INTENTS else "GENERAL_INQUIRY"
        raw_confidence = ai_response.get("confidence_score", 0.5)
        try:
            confidence = max(0.0, min(1.0, float(raw_confidence)))
        except (TypeError, ValueError):
            confidence = 0.5

        return AIAnalyzedResult(
            message_id=payload.message_id,
            intent=intent,
            confidence_score=confidence,
            extracted_entities=ai_response.get("extracted_entities", {}),
            reply_message=ai_response.get("reply_message", "Baik Pesanan anda akan segera kami proses. Terima kasih!"),
        )

    except HTTPException:
        raise
    except json.JSONDecodeError:
        logger.warning("Model returned non-JSON response for message_id=%s", payload.message_id)
        raise HTTPException(status_code=502, detail="AI service returned an unexpected format.")
    except Exception as e:
        logger.error("Error processing message_id=%s: %s", payload.message_id, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        )


@app.get("/health")
async def health_check():
    return {"status": "OK"}