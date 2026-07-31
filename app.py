import os
import io
import json
import base64
import pandas as pd
import streamlit as st
from PIL import Image
from groq import Groq
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

# Sayfa Yapılandırması
st.set_page_config(page_title="Yatırım Defteri Sağlama Uygulaması", layout="wide")

st.title("📊 Yatırım Defteri Sağlama ve Kontrol Sistemi")
st.write("Lütfen 1. Dönem, 2. Dönem veya her iki dönemin defter görsellerini yükleyin.")

API_KEY = st.secrets.get("GROQ_API_KEY", "")

col1, col2 = st.columns(2)
with col1:
    file_d1 = st.file_uploader("1. Dönem Defter Görseli (Opsiyonel)", type=["jpg", "jpeg", "png"])
with col2:
    file_d2 = st.file_uploader("2. Dönem Defter Görseli (Opsiyonel)", type=["jpg", "jpeg", "png"])

def image_to_base64(img):
    buffered = io.BytesIO()
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def process_ledger_images(img1, img2, key):
    client = Groq(api_key=key)
    
    contents = []
    prompt = """
    Sana bir okulun yatırım defterine ait 1. Dönem ve/veya 2. Dönem sayfalarının görselleri verildi.
    Lütfen sayfaları dikkatle incele, öğrenci isimlerini, her öğrencinin dönem toplamlarını ve gün/tarih bazlı dikey sütun toplamlarını analiz et.
    
    SADECE ve SADECE aşağıdaki JSON formatında yanıt ver, başka hiçbir açıklama ekleme:
    {
      "students": [
        {
          "name": "Öğrenci Adı Soyadı",
          "term1_total": 57050,
          "term2_total": 65400,
          "written_total": 122450
        }
      ],
      "daily_totals": [
        {
          "date": "22.9.25",
          "calculated_sum": 1600,
          "written_sum": 1600
        }
      ],
      "grand_total_written": 122450
    }
    """
    
    msg_content = [{"type": "text", "text": prompt}]
    
    if img1 is not None:
        img1_b64 = image_to_base64(img1)
        msg_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img1_b64}"}})
    if img2 is not None:
        img2_b64 = image_to_base64(img2)
        msg_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img2_b64}"}})

    response = client.chat.completions.create(
        model="llama-3.2-90b-vision-preview",
        messages=[{"role": "user", "content": msg_content}],
        response_format={"type": "json_object"}
    )
    
    clean_text = response.choices[0].message.content.strip()
    return json.loads(clean_text)

# Türkçe karakter destekli Canvas Sınıfı
class UnicodeCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

def generate_pdf(data, errors):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()

    is_success = len(errors) == 0

    # Başlık
    if is_success:
        title_style = ParagraphStyle('SuccessTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#15803d'), alignment=1, spaceAfter=15)
        elements.append(Paragraph("SAĞLAMA BAŞARILI", title_style))
    else:
        title_style = ParagraphStyle('FailTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#b91c1c'), alignment=1, spaceAfter=15)
        elements.append(Paragraph("SAĞLAMA BAŞARISIZ", title_style))
        
        # Kırmızı Yazılı Hata Detayları
        err_style = ParagraphStyle('ErrText', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#dc2626'))
        elements.append(Paragraph("<b>TESPİT EDİLEN HATALAR / OLASI NEDENLER:</b>", err_style))
        for err in errors:
            elements.append(Paragraph(f"• {err}", err_style))
        elements.append(Spacer(1, 12))

    # 1. ÖĞRENCİ BAZLI SAĞLAMA TABLOSU
    elements.append(Paragraph("<b>1. Öğrenci Bazı Yatırım Toplamları</b>", styles['Heading3']))
    table_data = [["Sıra", "Öğrenci Adı Soyadı", "1. Dönem Toplam", "2. Dönem Toplam", "Hesaplanan Toplam", "Defterdeki Toplam", "Durum"]]
    
    for idx, st_info in enumerate(data.get('students', []), 1):
        t1 = st_info.get('term1_total', 0)
        t2 = st_info.get('term2_total', 0)
        written = st_info.get('written_total', 0)
        calc = t1 + t2
        
        status = "OK" if calc == written else "HATALI"
        table_data.append([
            str(idx),
            st_info.get('name', 'Bilinmiyor'),
            f"{t1:,} TL",
            f"{t2:,} TL",
            f"{calc:,} TL",
            f"{written:,} TL",
            status
        ])

    pdf_table = Table(table_data, colWidths=[35, 220, 100, 100, 110, 110, 60])
    pdf_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    elements.append(pdf_table)
    elements.append(Spacer(1, 15))

    # 2. GÜN BAZLI YATIRIM SAĞLAMA TABLOSU
    if data.get('daily_totals'):
        elements.append(Paragraph("<b>2. Gün / Tarih Bazlı Sütun Toplamları Sağlaması</b>", styles['Heading3']))
        daily_table_data = [["Tarih", "Hesaplanan Günlük Toplam", "Defterde Yazan Günlük Toplam", "Durum"]]
        
        for d in data['daily_totals']:
            c_sum = d.get('calculated_sum', 0)
            w_sum = d.get('written_sum', 0)
            d_status = "OK" if c_sum == w_sum else "HATALI"
            daily_table_data.append([
                d.get('date', '-'),
                f"{c_sum:,} TL",
                f"{w_sum:,} TL",
                d_status
            ])
            
        d_table = Table(daily_table_data, colWidths=[120, 200, 200, 115])
        d_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#334155')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        elements.append(d_table)

    doc.build(elements, canvasmaker=UnicodeCanvas)
    buffer.seek(0)
    return buffer

if st.button("Sağlamayı Yap ve Raporla") and (file_d1 or file_d2):
    if not API_KEY:
        st.error("Sistem API Anahtarı tanımlanmamış. Lütfen Streamlit Secrets alanını kontrol edin.")
    else:
        with st.spinner("Görseller detaylı şekilde analiz ediliyor ve çapraz sağlama yapılıyor..."):
            try:
                img1 = Image.open(file_d1) if file_d1 else None
                img2 = Image.open(file_d2) if file_d2 else None
                
                result = process_ledger_images(img1, img2, API_KEY)
                
                # Hata Tespiti
                errors = []
                for student in result.get('students', []):
                    c_tot = student.get('term1_total', 0) + student.get('term2_total', 0)
                    if c_tot != student.get('written_total', 0):
                        errors.append(f"{student.get('name')}: Dönem toplamları ({c_tot} TL), defterde yazan toplam ({student.get('written_total')} TL) ile uyuşmuyor.")
                
                for d in result.get('daily_totals', []):
                    if d.get('calculated_sum') != d.get('written_sum'):
                        errors.append(f"{d.get('date')} Tarihli Sütun: Sütun içi toplam ({d.get('calculated_sum')} TL), defter altındaki dikey toplam ({d.get('written_sum')} TL) ile uyuşmuyor.")

                is_success = len(errors) == 0
                pdf_bytes = generate_pdf(result, errors)
                
                if is_success:
                    st.success("✅ SAĞLAMA BAŞARILI! Tüm yatay ve dikey toplamlar %100 eşleşiyor.")
                else:
                    st.error("❌ SAĞLAMA BAŞARISIZ! Hatalar tespit edildi.")
                    for e in errors:
                        st.write(f":red[• {e}]")
                        
                st.download_button(
                    label="📄 Detaylı PDF Raporunu İndir",
                    data=pdf_bytes,
                    file_name="Yatirim_Defteri_Saglama_Raporu.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"İşlem sırasında bir hata oluştu: {e}")
