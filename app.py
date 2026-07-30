import os
import io
import re
import pandas as pd
import streamlit as st
from PIL import Image
import pytesseract
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="Yatırım Defteri Sağlama Uygulaması", layout="wide")

st.title("📊 Yatırım Defteri Sağlama ve Kontrol Sistemi")
st.write("Lütfen 1. Dönem ve 2. Dönem defter görsellerini yükleyin.")

col1, col2 = st.columns(2)
with col1:
    file_d1 = st.file_uploader("1. Dönem Defter Görseli", type=["jpg", "jpeg", "png"])
with col2:
    file_d2 = st.file_uploader("2. Dönem Defter Görseli", type=["jpg", "jpeg", "png"])

def parse_ledger_text(text):
    """Görselden okunan metni analiz eder ve rakamları ayıklar."""
    lines = text.split('\n')
    students = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Satırdaki tüm sayıları bulur
        numbers = re.findall(r'\b\d+\b', line)
        # İsmi bulmak için sayı olmayan kısımları alır
        words = re.findall(r'[a-zA-ZçğıöşüÇĞİÖŞÜ]+', line)
        
        if len(numbers) >= 3 and len(words) >= 1:
            name = " ".join(words)
            t1 = int(numbers[0])
            t2 = int(numbers[1])
            written = int(numbers[-1])
            
            students.append({
                "name": name,
                "term1_total": t1,
                "term2_total": t2,
                "written_total": written
            })
            
    return students

def generate_pdf(students, is_success, errors):
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
    
    for idx, st_info in enumerate(students, 1):
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
    with st.spinner("Görseller doğrudan okunuyor ve çapraz sağlama yapılıyor..."):
        try:
            img1 = Image.open(file_d1)
            img2 = Image.open(file_d2)
            
            # Görselleri doğrudan Tesseract OCR ile oku (Dış API yok)
            text1 = pytesseract.image_to_string(img1, lang='tur+eng')
            text2 = pytesseract.image_to_string(img2, lang='tur+eng')
            
            students1 = parse_ledger_text(text1)
            students2 = parse_ledger_text(text2)
            
            # Verileri birleştir ve kontrol et
            students = students1 if students1 else students2
            
            errors = []
            if not students:
                st.warning("⚠️ Görsellerden sayısal veri okunamadı. Lütfen fotoğrafların net ve düzgün çekildiğinden emin olun.")
            else:
                for student in students:
                    c_tot = student['term1_total'] + student['term2_total']
                    if c_tot != student['written_total']:
                        errors.append(f"{student['name']}: Dönem toplamları ({c_tot} TL), yazılan toplam ile ({student['written_total']} TL) uyuşmuyor.")
                
                is_success = len(errors) == 0
                pdf_bytes = generate_pdf(students, is_success, errors)
                
                if is_success:
                    st.success("✅ SAĞLAMA BAŞARILI! Tüm hesaplamalar eşleşiyor.")
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
