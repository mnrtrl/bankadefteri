import io
import datetime
import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import A3, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

st.set_page_config(page_title="Okul Yatırım Defteri Yönetim Sistemi", layout="wide")

# ---------------------------------------------------------
# KALICI KULLANICI VE HAF IZA DEPOSU
# ---------------------------------------------------------
if "users" not in st.session_state:
    st.session_state["users"] = {
        "mnrtrl": {"pass": "123456", "role": "Ana Yönetici", "name": "Münür Teralı"}
    }

if "teachers_classes" not in st.session_state:
    st.session_state["teachers_classes"] = {}

if "students" not in st.session_state:
    st.session_state["students"] = {}

if "ledger_data" not in st.session_state:
    st.session_state["ledger_data"] = {}

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
# GİRİŞ EKRANI
# ---------------------------------------------------------
if not st.session_state["logged_user"]:
    st.title("🔒 Okul Yatırım Defteri Sistem Girişi")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("Kullanıcı Adı").strip()
        password = st.text_input("Şifre", type="password").strip()
        
        if st.button("Giriş Yap", use_container_width=True):
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

# ---------------------------------------------------------
# ÜST BİLGİ VE ŞİFRE DEĞİŞTİRME MENÜSÜ
# ---------------------------------------------------------
col_head1, col_head2, col_head3 = st.columns([3, 2, 1])
with col_head1:
    st.subheader(f"Hoş Geldiniz, {user_info['name']}")
    st.caption(f"Sistemdeki Rolünüz: **{user_role}**")

with col_head2:
    with st.popover("🔑 Şifremi Değiştir"):
        new_self_pass = st.text_input("Yeni Şifreniz", type="password", key="self_pass")
        if st.button("Şifreyi Güncelle"):
            if new_self_pass:
                st.session_state["users"][curr_user]["pass"] = new_self_pass
                st.success("Şifreniz başarıyla değiştirildi.")
            else:
                st.warning("Lütfen yeni bir şifre girin.")

with col_head3:
    if st.button("🚪 Çıkış Yap", use_container_width=True):
        st.session_state["logged_user"] = None
        st.rerun()

st.divider()

# ---------------------------------------------------------
# YÖNETİCİ VE ANA YÖNETİCİ PANELİ (mnrtrl VE YÖNETİCİLER İÇİN)
# ---------------------------------------------------------
if user_role in ["Ana Yönetici", "Yönetici"]:
    st.header("👑 Yönetici Kontrol Paneli")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "➕ Yeni Kullanıcı Ekle", 
        "✏️ Kullanıcı Düzenle ve Sınıf Atama", 
        "👀 Sınıf Verilerini İzle", 
        "📄 PDF Raporu İndir"
    ])
    
    # TAB 1: KULLANICI EKLEME
    with tab1:
        st.subheader("Yeni Yönetici veya Öğretmen Tanımla")
        c1, c2, c3, c4 = st.columns(4)
        new_u = c1.text_input("Kullanıcı Adı", key="nu").strip()
        new_p = c2.text_input("Şifre", key="np").strip()
        new_n = c3.text_input("Adı Soyadı", key="nn").strip()
        
        roles = ["Öğretmen", "Yönetici"] if user_role == "Ana Yönetici" else ["Öğretmen"]
        new_r = c4.selectbox("Sistem Rolü", roles, key="nr")
        
        if st.button("Kullanıcıyı Kaydet", use_container_width=True):
            if new_u and new_p and new_n:
                if new_u in st.session_state["users"]:
                    st.error("Bu kullanıcı adı zaten mevcut!")
                else:
                    st.session_state["users"][new_u] = {"pass": new_p, "role": new_r, "name": new_n}
                    st.success(f"'{new_n}' hesabı başarıyla oluşturuldu.")
                    st.rerun()
            else:
                st.warning("Lütfen tüm alanları eksiksiz doldurun.")

    # TAB 2: KULLANICI DÜZENLEME VE SINIF ATAMA
    with tab2:
        st.subheader("Kayıtlı Kullanıcı Yönetimi ve Sınıf Atama")
        all_users = st.session_state["users"]
        editable_users = {u: data for u, data in all_users.items() if data["role"] != "Ana Yönetici"}
        
        if editable_users:
            selected_edit_user = st.selectbox("Düzenlenecek Kullanıcıyı Seçin", list(editable_users.keys()))
            u_data = editable_users[selected_edit_user]
            
            ec1, ec2, ec3, ec4 = st.columns(4)
            edit_name = ec1.text_input("Adı Soyadı", value=u_data["name"])
            edit_pass = ec2.text_input("Şifre", value=u_data["pass"])
            
            curr_class = st.session_state["teachers_classes"].get(selected_edit_user, "")
            edit_class = ec3.text_input("Atanan Sınıf (Örn: 2B)", value=curr_class)
            
            st.write("")
            if ec4.button("Gerekli Güncellemeleri Kaydet", use_container_width=True):
                st.session_state["users"][selected_edit_user]["name"] = edit_name
                st.session_state["users"][selected_edit_user]["pass"] = edit_pass
                if edit_class:
                    st.session_state["teachers_classes"][selected_edit_user] = edit_class
                st.success(f"'{selected_edit_user}' bilgileri güncellendi.")
                st.rerun()
                
            st.divider()
            if st.button("❌ Bu Kullanıcıyı Sistemden Sil"):
                del st.session_state["users"][selected_edit_user]
                if selected_edit_user in st.session_state["teachers_classes"]:
                    del st.session_state["teachers_classes"][selected_edit_user]
                st.success("Kullanıcı silindi.")
                st.rerun()
        else:
            st.info("Sistemde henüz düzenlenebilecek öğretmen veya yönetici bulunmuyor.")

    # TAB 3: SINIF VERİLERİNİ İZLEME
    with tab3:
        st.subheader("Sınıfların Haftalık Yatırım Durumları")
        classes = list(set(st.session_state["teachers_classes"].values()))
        if classes:
            sel_cl = st.selectbox("İzlenecek Sınıf", classes)
            students = st.session_state["students"].get(sel_cl, [])
            st.write(f"**Öğrenci Sayısı:** {len(students)}")
            
            c_data = st.session_state["ledger_data"].get(sel_cl, {})
            if c_data:
                df = pd.DataFrame(c_data).fillna(0)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Bu sınıfa henüz veri girişi yapılmamış.")
        else:
            st.info("Sistemde henüz tanımlı bir sınıf yok.")

    # TAB 4: PDF RAPOR
    with tab4:
        st.subheader("Orijinal Formatlı PDF Rapor Oluştur")
        classes = list(set(st.session_state["teachers_classes"].values()))
        if classes:
            pdf_cl = st.selectbox("Sınıf Seçin", classes, key="pdf_c")
            if st.button("📄 Orijinal PDF Raporu Üret"):
                students = st.session_state["students"].get(pdf_cl, [])
                c_data = st.session_state["ledger_data"].get(pdf_cl, {})
                
                if not students or not c_data:
                    st.error("Rapor oluşturmak için veri eksik.")
                else:
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=landscape(A3), rightMargin=10, leftMargin=10, topMargin=10, bottomMargin=10)
                    elements = []
                    styles = getSampleStyleSheet()
                    
                    elements.append(Paragraph(make_turkish_safe(f"{pdf_cl} SINIFI YATIRIM DEFTERI SAĞLAMA RAPORU"), styles['Heading1']))
                    elements.append(Spacer(1, 10))
                    
                    dates = sorted(list(c_data.keys()))
                    header = ["Sira", "Ogrenci Adi Soyadi"] + [make_turkish_safe(d) for d in dates] + ["Toplam", "Durum"]
                    table_data = [header]
                    
                    for idx, st_name in enumerate(students, 1):
                        row = [str(idx), make_turkish_safe(st_name)]
                        tot = 0
                        for d in dates:
                            amt = c_data.get(d, {}).get(st_name, 0)
                            tot += amt
                            row.append(f"{amt:,}" if amt > 0 else "-")
                        row.extend([f"{tot:,} TL", "OK"])
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
                    
                    st.download_button("⬇️ PDF Raporunu İndir", data=buffer, file_name=f"{pdf_cl}_Yatirim_Defteri.pdf", mime="application/pdf")

# ---------------------------------------------------------
# ÖĞRETMEN PANELİ (SADECE ÖĞRETMENLER İÇİN)
# ---------------------------------------------------------
elif user_role == "Öğretmen":
    my_class = st.session_state["teachers_classes"].get(curr_user, None)
    
    if not my_class:
        st.warning("Henüz bir sınıfa atanmadınız. Lütfen yöneticinizle iletişime geçin.")
        st.stop()
        
    st.header(f"🏫 {my_class} Sınıfı Öğretmen Paneli")
    
    t_tab1, t_tab2 = st.tabs(["📝 Haftalık Yatırım Girişi", "👨‍🎓 Öğrenci Listesi"])
    
    if my_class not in st.session_state["students"]:
        st.session_state["students"][my_class] = []
        
    with t_tab2:
        st.subheader("Sınıf Öğrenci Listesi")
        raw_st_list = st.text_area("Öğrenci İsimleri (Her satıra bir öğrenci):", 
                                   value="\n".join(st.session_state["students"][my_class]), height=200)
        if st.button("Öğrenci Listesini Kaydet"):
            st_names = [s.strip() for s in raw_st_list.split("\n") if s.strip()]
            st.session_state["students"][my_class] = st_names
            st.success(f"{len(st_names)} öğrenci kaydedildi.")

    with t_tab1:
        st.subheader("Haftalık Yatırım Girişi")
        students = st.session_state["students"][my_class]
        
        if not students:
            st.info("Lütfen önce 'Öğrenci Listesi' sekmesinden öğrencilerinizi kaydedin.")
        else:
            if "selected_monday" not in st.session_state:
                today = datetime.date.today()
                st.session_state["selected_monday"] = today - datetime.timedelta(days=today.weekday())

            c_d1, c_d2, c_d3 = st.columns([1, 2, 1])
            if c_d1.button("← Önceki Hafta"):
                st.session_state["selected_monday"] -= datetime.timedelta(days=7)
                st.rerun()
            if c_d3.button("Sonraki Hafta →"):
                st.session_state["selected_monday"] += datetime.timedelta(days=7)
                st.rerun()
                
            sel_monday = c_d2.date_input("Yatırım Pazartesisi", st.session_state["selected_monday"])
            
            if sel_monday.weekday() != 0:
                st.error("⚠️ Lütfen sadece PAZARTESİ gününü seçiniz.")
            else:
                date_key = sel_monday.strftime("%d.%m.%Y")
                st.info(f"Seçili Tarih: **{date_key} (Pazartesi)**")
                
                is_holiday = st.checkbox("🌴 Bu Hafta Resmi Tatil / Yatırım Alınmadı")
                
                if my_class not in st.session_state["ledger_data"]:
                    st.session_state["ledger_data"][my_class] = {}
                    
                current_entry = st.session_state["ledger_data"][my_class].get(date_key, {})
                
                if is_holiday:
                    if st.button("Tatil Olarak Kaydet"):
                        st.session_state["ledger_data"][my_class][date_key] = {st_name: 0 for st_name in students}
                        st.success("Tatil olarak kaydedildi.")
                else:
                    st.write("### 💰 Öğrenci Yatırım Miktarları")
                    updated_entry = {}
                    total_day_sum = 0
                    
                    cols = st.columns(3)
                    for idx, st_name in enumerate(students):
                        col = cols[idx % 3]
                        existing_val = current_entry.get(st_name, 0)
                        val = col.number_input(f"👤 {st_name}", min_value=0, step=50, value=existing_val, key=f"inp_{st_name}_{date_key}")
                        updated_entry[st_name] = val
                        total_day_sum += val
                        
                    st.divider()
                    st.metric(label="Günün Toplam Yatırımı", value=f"{total_day_sum:,} TL")
                    
                    if st.button("✅ Bu Günün Verilerini Onayla ve Kaydet", use_container_width=True):
                        st.session_state["ledger_data"][my_class][date_key] = updated_entry
                        st.success(f"{date_key} verileri ({total_day_sum:,} TL) kaydedildi.")
