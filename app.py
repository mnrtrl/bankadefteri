import os
import io
import json
import base64
import requests
import pandas as pd
import streamlit as st
from PIL import Image
from groq import Groq
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Sayfa Yapılandırması
st.set_page_config(page_title="Yatırım Defteri Sağlama Uygulaması", layout="wide")

st.title("📊 Yatırım Defteri Sağlama ve Kontrol Sistemi")
st.write("Lütfen 1. Dönem ve 2. Dönem defter görsellerini yükleyin.")

# API Key'i Gizli Kasadan (Secrets) Alır
API_KEY = st.secrets.get("GROQ_API_KEY", "")

col1, col2 = st.columns(2)
with col1:
    file_d1 = st.file_uploader("1. Dönem Defter Görseli", type=["jpg", "jpeg", "png"])
with col2:
    file_d2 = st.file_uploader("2. Dönem Defter Görseli", type=["jpg", "jpeg", "png"])

def image_to_base64(img):
    buffered = io.BytesIO()
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def get_active_groq_vision_model(key):
    """Groq üzerindeki en güncel ve aktif Vision modelini dinamik olarak seçer."""
    headers = {"Authorization": f"Bearer {key}"}
    try:
        res = requests.get("https://api.groq.com/openai/v1/models", headers=headers).json()
        if "data" in res:
            for m in res["data"]:
                m_id = m.get("id", "")
                if "vision" in m_id and "preview" not in m_id:
                    return m_id
            for m in res["data"]:
                m_id = m.get("id", "")
                if "vision" in m_id:
                    return m_id
    except Exception:
        pass
    return "llama-3.2-11b-vision-instruct"

def process_ledger_images(img1, img2, key):
    client = Groq(api_key=key)
    img1_b64 = image_to_base64(img1)
    img2_b64 = image_to_base64(img2)
    
    # Otomatik tespit edilen aktif model
    active_model = get_active_groq_vision_model(key)
    
    prompt = """
    Bu iki görsel bir okulun yatırım defterine aittir (1. ve 2. Dönem).
    Lütfen her iki sayfadaki öğrenci isimlerini, tarihlerdeki yatırımları ve toplamları analiz et.
    SADECE aşağıdaki JSON formatında yanıt ver, başka hiçbir açıklama veya markdown kodu ekleme:
    {
      "students": [
        {
          "name": "Öğrenci Adı Soyadı",
          "term1_total": 1300,
          "term2_total": 2100,
          "written_total": 3400
        }
      ],
      "term1_date_total": 57050,
      "term2_date_total": 65400,
      "written_grand_total": 122450,
      "uncertain_cells": []
    }
    """
    
    response = client.chat.completions.create(
        model=active_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img1_b64}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img2_b64}"}}
                ]
            }
        ],
        response_format={"type": "json_object"}
    )
    
    clean_text = response.choices[0].message.content.strip()
    return json.loads(clean_text)

def generate_pdf(data, is_success, errors):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()

    if is_success:
        title_style = ParagraphStyle('SuccessTitle', parent=styles['Heading1'], fontSize=28, textColor=colors.HexColor('#15803d'), alignment=1, spaceAfter=15)
        elements.append(Paragraph("SAĞLAMA BAŞARILI", title_style))
    else:
        title_style = ParagraphStyle('FailTitle', parent=styles['Heading1'], fontSize=28, textColor=colors.HexColor('#b91c1c'), alignment=1, spaceAfter=15)
        elements.append(Paragraph("SAĞLAMA BAŞARISIZ", title_style))
        
        err_style = ParagraphStyle('ErrText', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#991b1b'))
        for err in errors:
            elements.append(Paragraph(f"• {err}", err_style))
        elements.append(Spacer(1, 10))

    table_data = [["Sıra", "Öğrenci Adı Soyadı", "1. Dönem Toplamı", "2. Dönem Toplamı", "Hesaplanan Toplam", "Defterdeki Toplam", "Durum"]]
    
    for idx, st_info in enumerate(data['students'], 1):
        calc_tot = st_info['term1_total'] + st_info['term2_total']
        status = "OK" if calc_tot == st_info['written_total'] else "HATALI"
        table_data.append([
            str(idx),
            st_info['name'],
            f"{st_info['term1_total']:,} TL",
            f"{st_info['term2_total']:,} TL",
            f"{calc_tot:,} TL",
            f"{st_info['written_total']:,} TL",
            status
        ])

    pdf_table = Table(table_data, colWidths=[30, 200, 100, 100, 110, 110, 60])
    pdf_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    
    elements.append(pdf_table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

if st.button("Sağlamayı Yap ve Raporla") and file_d1 and file_d2:
    if not API_KEY:
        st.error("Sistem API Anahtarı tanımlanmamış. Lütfen Streamlit Secrets alanını kontrol edin.")
    else:
        with st.spinner("Görseller analiz ediliyor ve çapraz sağlama yapılıyor..."):
            try:
                img1 = Image.open(file_d1)
                img2 = Image.open(file_d2)
                
                result = process_ledger_images(img1, img2, API_KEY)
                
                if result.get("uncertain_cells"):
                    st.warning("⚠️ Bazı rakamlar net okunamadı. Lütfen kontrol edip doğrulayın:")
                    for cell in result["uncertain_cells"]:
                        st.text_input(f"{cell['student']} - {cell['field']}", value="")
                
                errors = []
                calc_grand_total = 0
                for student in result['students']:
                    c_tot = student['term1_total'] + student['term2_total']
                    calc_grand_total += c_tot
                    if c_tot != student['written_total']:
                        errors.append(f"{student['name']}: Dönem toplamları ({c_tot} TL), yazılan toplam ile ({student['written_total']} TL) uyuşmuyor.")
                
                is_success = len(errors) == 0 and calc_grand_total == result['written_grand_total']
                
                pdf_bytes = generate_pdf(result, is_success, errors)
                
                if is_success:
                    st.success("✅ SAĞLAMA BAŞARILI! Tüm yatay ve dikey toplamlar %100 eşleşiyor.")
                else:
                    st.error("❌ SAĞLAMA BAŞARISIZ! Hatalar tespit edildi.")
                    for e in errors:
                        st.write(f"- {e}")
                        
                st.download_button(
                    label="📄 Detaylı PDF Raporunu İndir",
                    data=pdf_bytes,
                    file_name="Yatirim_Defteri_Saglama_Raporu.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"İşlem sırasında bir hata oluştu: {e}")
