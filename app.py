import os
import io
import json
import base64
import pandas as pd
import streamlit as st
from PIL import Image
from openai import OpenAI
from reportlab.lib.pagesizes import A3, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="Yatırım Defteri Sağlama Uygulaması", layout="wide")

st.title("📊 Yatırım Defteri Birebir Matris Sağlama Sistemi")
st.write("Lütfen 1. Dönem ve 2. Dönem defter görsellerini yükleyin.")

API_KEY = st.secrets.get("OPENAI_API_KEY", "")

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

def make_turkish_safe(text):
    if not isinstance(text, str):
        return str(text)
    replacements = {
        'Ğ': 'G', 'ğ': 'g', 'Ş': 'S', 'ş': 's',
        'İ': 'I', 'ı': 'i', 'Ö': 'O', 'ö': 'o',
        'Ü': 'U', 'ü': 'u', 'Ç': 'C', 'ç': 'c'
    }
    for search, replace in replacements.items():
        text = text.replace(search, replace)
    return text

def process_full_ledger_matrix(img1, img2, key):
    client = OpenAI(api_key=key)
    
    prompt = """
    Sana bir okulun yatırım defterine ait görseller verildi.
    İSTİSNASIZ TÜM ÖĞRENCİLERİ (11 Öğrenci) VE TÜM TARİH SÜTUNLARINI tam bir matris olarak çıkar.
    Hiçbir öğrenciyi ve hiçbir tarih hücresini atlama.
    
    Çıktıyı SADECE aşağıdaki JSON formatında ver:
    {
      "dates": [
        "22.09", "29.09", "06.10", "13.10", "18.10", "20.10", "27.10", "29.10", "10.11", "17.11", "24.11", "27.11", "12.05", "15.12", "22.12", "29.12", "12.01", "19.01",
        "26.01", "16.02", "23.02", "02.03", "09.03", "16.03", "23.03", "13.04", "27.04", "04.05", "11.05", "26.05", "28.05", "01.06"
      ],
      "students": [
        {
          "name": "Asel Gul Camruk",
          "values": [200, 200, 0, 0, 100, 0, 200, 200, 0, 0, 0, 0, 0, 100, 100, 100, 0, 100, 100, 0, 0, 200, 200, 100, 200, 100, 0, 200, 0, 200, 0, 200],
          "written_total": 3400
        }
      ],
      "column_written_totals": [1600, 3700, 6050, 4500, 5800, 4750, 6800, 3300, 5050, 5400, 4650, 6000, 3300, 4400, 2350, 5450, 1400, 6700, 3750, 3500, 4050, 2300, 6400, 2900, 3200, 2900, 2050, 1800, 2900, 1200, 2300, 2500],
      "grand_written_total": 122450
    }
    """
    
    msg_content = [{"type": "text", "text": prompt}]
    if img1 is not None:
        msg_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_to_base64(img1)}"}})
    if img2 is not None:
        msg_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_to_base64(img2)}"}})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": msg_content}],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content.strip())

def generate_pdf(data, errors):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A3), rightMargin=10, leftMargin=10, topMargin=10, bottomMargin=10)
    elements = []
    styles = getSampleStyleSheet()

    is_success = len(errors) == 0

    if is_success:
        title_style = ParagraphStyle('SuccessTitle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#15803d'), spaceAfter=8)
        elements.append(Paragraph(make_turkish_safe("SAGLAMA BASARILI - Tum Ogrenciler Birebir Defter Matrisi"), title_style))
    else:
        title_style = ParagraphStyle('FailTitle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#b91c1c'), spaceAfter=8)
        elements.append(Paragraph(make_turkish_safe("SAGLAMA BASARISIZ - Tum Ogrenciler Birebir Defter Matrisi"), title_style))
        
        err_style = ParagraphStyle('ErrText', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#dc2626'))
        elements.append(Paragraph(make_turkish_safe("<b>TESPIT EDILEN HATALAR:</b>"), err_style))
        for err in errors:
            elements.append(Paragraph(make_turkish_safe(f"• {err}"), err_style))
        elements.append(Spacer(1, 8))

    dates = data.get("dates", [])
    header_row = ["Sira", "Ogrenci Adi Soyadi"] + [make_turkish_safe(d) for d in dates] + ["Hesaplanan", "Defterdeki", "Durum"]
    
    table_data = [header_row]
    
    for idx, st_info in enumerate(data.get("students", []), 1):
        vals = st_info.get("values", [])
        calc_sum = sum(vals)
        written_sum = st_info.get("written_total", 0)
        status = "OK" if calc_sum == written_sum else "HATALI"
        
        row = [str(idx), make_turkish_safe(st_info.get("name", ""))]
        row.extend([f"{v}" if v > 0 else "-" for v in vals])
        row.extend([f"{calc_sum:,}", f"{written_sum:,}", status])
        table_data.append(row)

    # Dikey Toplam Satırı
    num_dates = len(dates)
    col_calculated = []
    for d_idx in range(num_dates):
        d_sum = sum(st_info.get("values", [])[d_idx] for st_info in data.get("students", []) if d_idx < len(st_info.get("values", [])))
        col_calculated.append(d_sum)
        
    row_calc_total = ["", "Hesaplanan Sutun Toplami"] + [f"{c:,}" for c in col_calculated] + ["-", "-", "-"]
    table_data.append(row_calc_total)

    matrix_table = Table(table_data, repeatRows=1)
    matrix_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,-1), 7),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (1,-1), (-1,-1), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (1,-1), (-1,-1), colors.HexColor('#0f172a')),
    ]))
    
    elements.append(matrix_table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

if st.button("Sağlamayı Yap ve Bütün Öğrencilerin Raporunu Üret") and (file_d1 or file_d2):
    if not API_KEY:
        st.error("Sistem API Anahtarı tanımlanmamış. Lütfen Streamlit Secrets alanını kontrol edin.")
    else:
        with st.spinner("Tüm öğrenciler ve bütün tarihler matris olarak hazırlanıyor..."):
            try:
                img1 = Image.open(file_d1) if file_d1 else None
                img2 = Image.open(file_d2) if file_d2 else None
                
                result = process_full_ledger_matrix(img1, img2, API_KEY)
                
                errors = []
                for student in result.get('students', []):
                    c_tot = sum(student.get('values', []))
                    if c_tot != student.get('written_total', 0):
                        errors.append(f"{student.get('name')}: Hesaplanan ({c_tot} TL), Defterde Yazan ({student.get('written_total')} TL) ile uyuşmuyor.")
                
                pdf_bytes = generate_pdf(result, errors)
                
                st.download_button(
                    label="📄 Tüm Öğrencileri Ve Bütün Tarihleri İçeren PDF Raporunu İndir",
                    data=pdf_bytes,
                    file_name="Tam_Yatirim_Defteri_Saglama_Raporu.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"İşlem sırasında bir hata oluştu: {e}")
