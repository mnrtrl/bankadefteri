import os
import io
import json
import base64
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from PIL import Image
from openai import OpenAI
from reportlab.lib.pagesizes import A3, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="Yatırım Defteri İnteraktif Sağlama Sistemi", layout="wide")

st.title("📊 Yatırım Defteri Kontrol ve İnteraktif Onay Sistemi")
st.write("Lütfen 1. Dönem ve/veya 2. Dönem defter görsellerini yükleyin.")

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

def fix_dates_with_calendar(raw_dates):
    """Pazartesi döngüsüyle tarihleri saat formatına kaçmayacak net metin formatına dönüştürür."""
    fixed_dates = []
    base_date = datetime(2025, 9, 22) # İlk Pazartesi
    
    current_date = base_date
    for idx in range(len(raw_dates)):
        # Tarihlerin saat sanılmaması için gün/ay/yıl metni (Örn: "22/09/2025")
        fixed_dates.append(current_date.strftime("%d/%m/%Y"))
        current_date += timedelta(days=7)
        
    return fixed_dates

def read_ledger_strict(img1, img2, key):
    client = OpenAI(api_key=key)
    
    prompt = """
    Sana bir okulun yatırım defterine ait görseller verildi.
    İSTİSNASIZ TÜM ÖĞRENCİLERİ (11 Öğrenci) VE TÜM TARİH SÜTUNLARINI OKU. KESİNLİKLE İSİM VEYA RAKAM UYDURMA.
    Okuyamadığın veya emin olamadığın sayısal hücrelere 0 yaz.
    
    Çıktıyı SADECE aşağıdaki JSON formatında ver:
    {
      "read_accuracy_percentage": 85,
      "dates": ["22.09.2025", "29.09.2025", "06.10.2025", "13.10.2025", "20.10.2025"],
      "students": [
        {
          "name": "Asel Gul Camruk",
          "values": [200, 200, 0, 100, 200],
          "written_total": 3400
        }
      ]
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

def generate_pdf(df_data, dates, errors):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A3), rightMargin=10, leftMargin=10, topMargin=10, bottomMargin=10)
    elements = []
    styles = getSampleStyleSheet()

    is_success = len(errors) == 0

    if is_success:
        title_style = ParagraphStyle('SuccessTitle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#15803d'), spaceAfter=8)
        elements.append(Paragraph(make_turkish_safe("SAGLAMA BASARILI - Onaylanmis Defter Matris Raporu"), title_style))
    else:
        title_style = ParagraphStyle('FailTitle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#b91c1c'), spaceAfter=8)
        elements.append(Paragraph(make_turkish_safe("SAGLAMA BASARISIZ - Onaylanmis Defter Matris Raporu"), title_style))
        
        err_style = ParagraphStyle('ErrText', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#dc2626'))
        elements.append(Paragraph(make_turkish_safe("<b>TESPIT EDILEN HATALAR:</b>"), err_style))
        for err in errors:
            elements.append(Paragraph(make_turkish_safe(f"• {err}"), err_style))
        elements.append(Spacer(1, 8))

    header_row = ["Sira", "Ogrenci Adi Soyadi"] + [make_turkish_safe(d) for d in dates] + ["Hesaplanan", "Defterdeki", "Durum"]
    table_data = [header_row]
    
    for idx, row in df_data.iterrows():
        name = make_turkish_safe(row["Öğrenci Adı Soyadı"])
        written = int(row["Defterdeki Toplam"])
        vals = [int(row[d]) for d in dates]
        calc_sum = sum(vals)
        status = "OK" if calc_sum == written else "HATALI"
        
        r = [str(idx+1), name] + [f"{v:,}" if v > 0 else "-" for v in vals] + [f"{calc_sum:,}", f"{written:,}", status]
        table_data.append(r)

    matrix_table = Table(table_data, repeatRows=1)
    matrix_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,-1), 7),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#94a3b8')),
    ]))
    
    elements.append(matrix_table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ADIM 1: GÖRSEL ANALİZİ
if st.button("Görselleri Tara ve Kontrol Et") and (file_d1 or file_d2):
    if not API_KEY:
        st.error("Sistem API Anahtarı tanımlanmamış. Lütfen Streamlit Secrets alanını kontrol edin.")
    else:
        with st.spinner("Görsel taranıyor ve takvim eşleştiriliyor..."):
            img1 = Image.open(file_d1) if file_d1 else None
            img2 = Image.open(file_d2) if file_d2 else None
            
            res = read_ledger_strict(img1, img2, API_KEY)
            accuracy = res.get("read_accuracy_percentage", 0)
            
            if accuracy < 75:
                st.error(f"❌ Görsel verilerinin çoğunluğu (%{100-accuracy}) okunamadı. Lütfen daha net bir fotoğraf yükleyin.")
            else:
                st.success(f"✅ Görsel okuma oranı: %{accuracy}. Lütfen aşağıdaki tablodan eksik verileri kontrol edip onaylayın.")
                
                # Arka Plan Takvimiyle Tarih Formatını Sabitleme
                fixed_dates = fix_dates_with_calendar(res.get("dates", []))
                
                # Tablo Verisi Hazırlama
                students_data = []
                for st_info in res.get("students", []):
                    row_dict = {"Öğrenci Adı Soyadı": st_info.get("name", "")}
                    vals = st_info.get("values", [])
                    for idx, d in enumerate(fixed_dates):
                        val = vals[idx] if idx < len(vals) else 0
                        row_dict[d] = int(val) if val is not None else 0
                    row_dict["Defterdeki Toplam"] = int(st_info.get("written_total", 0))
                    students_data.append(row_dict)
                
                st.session_state["raw_df"] = pd.DataFrame(students_data)
                st.session_state["dates"] = fixed_dates

# ADIM 2: İNTERAKTİF DÜZELTME TABLOSU
if "raw_df" in st.session_state:
    st.subheader("📝 Öğretmen Veri Onay ve Düzeltme Tablosu")
    st.info("Tablodaki '0' görünen veya eksik olan hücreleri defterinize bakarak düzeltebilir, ardından raporu onaylayabilirsiniz.")
    
    # Tarih kolonlarını metin (string) biçimine zorlayarak saat algılanmasını engelliyoruz
    column_config = {col: st.column_config.NumberColumn(format="%d") for col in st.session_state["dates"]}
    column_config["Öğrenci Adı Soyadı"] = st.column_config.TextColumn()
    column_config["Defterdeki Toplam"] = st.column_config.NumberColumn(format="%d")

    edited_df = st.data_editor(
        st.session_state["raw_df"], 
        column_config=column_config,
        num_rows="dynamic",
        use_container_width=True
    )
    
    if st.button("Verileri Onayla ve Raporu Üret"):
        dates = st.session_state["dates"]
        errors = []
        
        for idx, row in edited_df.iterrows():
            calc_sum = sum(int(row[d]) for d in dates)
            written = int(row["Defterdeki Toplam"])
            if calc_sum != written:
                errors.append(f"{row['Öğrenci Adı Soyadı']}: Girilen Toplam ({calc_sum} TL), Defterdeki Toplam ({written} TL) ile uyuşmuyor.")
                
        pdf_bytes = generate_pdf(edited_df, dates, errors)
        
        if len(errors) == 0:
            st.success("✅ SAĞLAMA BAŞARILI! Tüm veriler tam olarak eşleşti.")
        else:
            st.error("❌ SAĞLAMA BAŞARISIZ! Uyuşmayan satırlar tespit edildi.")
            for e in errors:
                st.write(f":red[• {e}]")
                
        st.download_button(
            label="📄 Onaylanmış Detaylı PDF Raporunu İndir",
            data=pdf_bytes,
            file_name="Onaylanmis_Yatirim_Defteri_Raporu.pdf",
            mime="application/pdf"
        )
