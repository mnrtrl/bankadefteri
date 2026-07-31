import io
import datetime
import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import A3, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="Okul Yatırım Defteri Yönetim Sistemi", layout="wide")

# Session State Hazırlıkları (Sistem Hafızası)
if "users" not in st.session_state:
    st.session_state["users"] = {
        "mnrtrl": {"pass": "123456", "role": "main_admin", "name": "Münür Teralı (Ana Yönetici)"}
    }

if "teachers_classes" not in st.session_state:
    st.session_state["teachers_classes"] = {} # teacher_username: class_name

if "students" not in st.session_state:
    st.session_state["students"] = {} # class_name: [student_names]

if "ledger_data" not in st.session_state:
    st.session_state["ledger_data"] = {} # class_name: {date_str: {student_name: amount}}

if "logged_user" not in st.session_state:
    st.session_state["logged_user"] = None

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

# ---------------------------------------------------------
# GİRİŞ EKRANI (LOGIN)
# ---------------------------------------------------------
if not st.session_state["logged_user"]:
    st.title("🔒 Okul Yatırım Defteri Sistem Girişi")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("Kullanıcı Adı")
        password = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap"):
            users = st.session_state["users"]
            if username in users and users[username]["pass"] == password:
                st.session_state["logged_user"] = username
                st.rerun()
            else:
                st.error("Kullanıcı adı veya şifre hatalı!")
    st.stop()

# Oturum Açan Kullanıcı Bilgileri
curr_user = st.session_state["logged_user"]
user_info = st.session_state["users"][curr_user]
user_role = user_info["role"]

# Üst Menü / Çıkış Yap
col_head1, col_head2 = st.columns([4, 1])
with col_head1:
    st.caption(f"Aktif Kullanıcı: **{user_info['name']}** ({user_role.upper()})")
with col_head2:
    if st.button("🚪 Çıkış Yap"):
        st.session_state["logged_user"] = None
        st.rerun()

st.divider()

# ---------------------------------------------------------
# YÖNETİCİ PANELİ (MAIN ADMIN & ADMIN)
# ---------------------------------------------------------
if user_role in ["main_admin", "admin"]:
    st.header("👑 Yönetici Kontrol Paneli")
    
    tab1, tab2, tab3 = st.tabs(["👥 Kullanıcı & Öğretmen Atama", "👀 Sınıf & Veri İzleme", "📄 PDF Rapor Al"])
    
    with tab1:
        st.subheader("Yeni Kullanıcı Ekle")
        c1, c2, c3, c4 = st.columns(4)
        new_u = c1.text_input("Kullanıcı Adı", key="new_u")
        new_p = c2.text_input("Şifre", key="new_p")
        new_n = c3.text_input("Adı Soyadı", key="new_n")
        
        # Ana yönetici alt yönetici de atayabilir
        role_options = ["teacher", "admin"] if user_role == "main_admin" else ["teacher"]
        new_r = c4.selectbox("Rol", role_options, key="new_r")
        
        if st.button("Kullanıcı Oluştur"):
            if new_u and new_p and new_n:
                st.session_state["users"][new_u] = {"pass": new_p, "role": new_r, "name": new_n}
                st.success(f"'{new_n}' başarıyla eklendi.")
            else:
                st.warning("Lütfen tüm alanları doldurun.")
                
        st.divider()
        st.subheader("Öğretmene Sınıf Atama")
        teachers = [u for u, data in st.session_state["users"].items() if data["role"] == "teacher"]
        if teachers:
            tc1, tc2 = st.columns(2)
            sel_teacher = tc1.selectbox("Öğretmen Seç", teachers)
            assigned_class = tc2.text_input("Atanacak Sınıf (Örn: 2B)", value=st.session_state["teachers_classes"].get(sel_teacher, ""))
            if st.button("Sınıfı Atayarak Kaydet"):
                st.session_state["teachers_classes"][sel_teacher] = assigned_class
                st.success(f"{sel_teacher} kullanıcısı {assigned_class} sınıfına atandı.")
        else:
            st.info("Sistemde henüz kayıtlı öğretmen bulunmuyor.")

    with tab2:
        st.subheader("Sınıf Verilerini Canlı İzleme")
        all_classes = list(set(st.session_state["teachers_classes"].values()))
        if all_classes:
            selected_class = st.selectbox("İzlenecek Sınıfı Seçin", all_classes)
            students = st.session_state["students"].get(selected_class, [])
            st.write(f"**{selected_class} Sınıfı Öğrenci Sayısı:** {len(students)}")
            
            class_data = st.session_state["ledger_data"].get(selected_class, {})
            if class_data:
                df_view = pd.DataFrame(class_data).fillna(0)
                st.dataframe(df_view, use_container_width=True)
            else:
                st.info("Bu sınıfa ait henüz girilmiş haftalık veri yok.")
        else:
            st.info("Henüz oluşturulmuş bir sınıf yok.")

    with tab3:
        st.subheader("Orijinal Defter Formatında PDF Raporu İndir")
        all_classes = list(set(st.session_state["teachers_classes"].values()))
        if all_classes:
            pdf_class = st.selectbox("PDF Rapor Alınacak Sınıf", all_classes, key="pdf_cl")
            term_option = st.radio("Dönem Seçimi", ["Tüm Yıl", "1. Dönem", "2. Dönem"], horizontal=True)
            
            if st.button("📄 Orijinal PDF Raporu Oluştur"):
                # PDF Hazırlama Mantığı
                students = st.session_state["students"].get(pdf_class, [])
                class_data = st.session_state["ledger_data"].get(pdf_class, {})
                
                if not students or not class_data:
                    st.error("Rapor oluşturmak için yeterli veri veya öğrenci kaydı bulunamadı.")
                else:
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=landscape(A3), rightMargin=10, leftMargin=10, topMargin=10, bottomMargin=10)
                    elements = []
                    styles = getSampleStyleSheet()
                    
                    title = f"{pdf_class} SINIFI YATIRIM DEFTERI SAĞLAMA RAPORU ({term_option.upper()})"
                    elements.append(Paragraph(make_turkish_safe(title), styles['Heading1']))
                    elements.append(Spacer(1, 10))
                    
                    dates = sorted(list(class_data.keys()))
                    header = ["Sira", "Ogrenci Adi Soyadi"] + [make_turkish_safe(d) for d in dates] + ["Toplam", "Durum"]
                    table_data = [header]
                    
                    for idx, st_name in enumerate(students, 1):
                        row = [str(idx), make_turkish_safe(st_name)]
                        st_total = 0
                        for d in dates:
                            amt = class_data.get(d, {}).get(st_name, 0)
                            st_total += amt
                            row.append(f"{amt:,}" if amt > 0 else "-")
                        row.extend([f"{st_total:,} TL", "OK"])
                        table_data.append(row)
                        
                    pdf_table = Table(table_data, repeatRows=1)
                    pdf_table.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
                        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#94a3b8')),
                        ('FONTSIZE', (0,0), (-1,-1), 8),
                    ]))
                    elements.append(pdf_table)
                    doc.build(elements)
                    buffer.seek(0)
                    
                    st.download_button(
                        label="⬇️ PDF Raporunu Bilgisayara İndir",
                        data=buffer,
                        file_name=f"{pdf_class}_Yatirim_Defteri.pdf",
                        mime="application/pdf"
                    )

# ---------------------------------------------------------
# ÖĞRETMEN PANELİ (TEACHER)
# ---------------------------------------------------------
elif user_role == "teacher":
    my_class = st.session_state["teachers_classes"].get(curr_user, None)
    
    if not my_class:
        st.warning("Henüz yönetici tarafından bir sınıfa atanmadınız. Lütfen yöneticinizle iletişime geçin.")
        st.stop()
        
    st.header(f"🏫 {my_class} Sınıfı Öğretmen Paneli")
    
    t_tab1, t_tab2 = st.tabs(["📝 Haftalık Yatırım Girişi", "👨‍🎓 Öğrenci Listesi Tanımlama"])
    
    # Sınıf Öğrencileri
    if my_class not in st.session_state["students"]:
        st.session_state["students"][my_class] = []
        
    with t_tab2:
        st.subheader("Sınıf Öğrenci Listesini Ekle / Düzenle")
        raw_st_list = st.text_area("Öğrenci İsimlerini Her Satıra Bir İsim Gelecek Şekilde Yazın:", 
                                   value="\n".join(st.session_state["students"][my_class]), height=200)
        if st.button("Öğrenci Listesini Kaydet"):
            st_names = [s.strip() for s in raw_st_list.split("\n") if s.strip()]
            st.session_state["students"][my_class] = st_names
            st.success(f"{len(st_names)} öğrenci başarıyla kaydedildi.")

    with t_tab1:
        st.subheader("Haftalık Yatırım Girişi")
        students = st.session_state["students"][my_class]
        
        if not students:
            st.info("Lütfen önce 'Öğrenci Listesi Tanımlama' sekmesinden sınıf öğrencilerini giriniz.")
        else:
            # Tarih Seçimi (Sadece Pazartesi)
            if "selected_monday" not in st.session_state:
                today = datetime.date.today()
                st.session_state["selected_monday"] = today - datetime.timedelta(days=today.weekday())

            c_date1, c_date2, c_date3 = st.columns([1, 2, 1])
            
            if c_date1.button("← Önceki Hafta"):
                st.session_state["selected_monday"] -= datetime.timedelta(days=7)
                st.rerun()
                
            if c_date3.button("Sonraki Hafta →"):
                st.session_state["selected_monday"] += datetime.timedelta(days=7)
                st.rerun()
                
            sel_monday = c_date2.date_input("Yatırım Pazartesisi", st.session_state["selected_monday"])
            
            if sel_monday.weekday() != 0:
                st.error("⚠️ Lütfen sadece PAZARTESİ günlerini seçiniz. Yatırım toplama günü Pazartesi'dir.")
            else:
                date_key = sel_monday.strftime("%d.%m.%Y")
                st.info(f"Seçili Tarih: **{date_key} (Pazartesi)**")
                
                is_holiday = st.checkbox("🌴 Bu Hafta Resmi Tatil / Yatırım Yapılmadı")
                
                if my_class not in st.session_state["ledger_data"]:
                    st.session_state["ledger_data"][my_class] = {}
                    
                current_entry = st.session_state["ledger_data"][my_class].get(date_key, {})
                
                if is_holiday:
                    st.warning("Bu hafta yatırım yapılmadı olarak işaretlenecektir.")
                    if st.button("Tatil Olarak Kaydet"):
                        st.session_state["ledger_data"][my_class][date_key] = {st_name: 0 for st_name in students}
                        st.success("Bu hafta tatil olarak kaydedildi.")
                else:
                    st.write("### 💰 Öğrenciye Tıkla ve Tutar Gir")
                    st.caption("Para yatırmayan öğrenciler için herhangi bir işlem yapmanıza gerek yoktur (0 TL kabul edilir).")
                    
                    updated_entry = {}
                    total_day_sum = 0
                    
                    cols = st.columns(3)
                    for idx, st_name in enumerate(students):
                        col = cols[idx % 3]
                        existing_val = current_entry.get(st_name, 0)
                        val = col.number_input(f"👤 {st_name}", min_value=0, step=50, value=existing_val, key=f"input_{st_name}_{date_key}")
                        updated_entry[st_name] = val
                        total_day_sum += val
                        
                    st.divider()
                    st.metric(label="Günün Toplam Yatırım Miktarı", value=f"{total_day_sum:,} TL")
                    
                    if st.button("✅ Bu Günün Verilerini Onayla ve Kaydet"):
                        st.session_state["ledger_data"][my_class][date_key] = updated_entry
                        st.success(f"{date_key} tarihli yatırımlar ({total_day_sum:,} TL) başarıyla onaylandı ve kaydedildi.")
