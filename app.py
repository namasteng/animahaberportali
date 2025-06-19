from flask import Flask, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask import render_template, flash, session
import requests, time, threading
from bs4 import BeautifulSoup

app = Flask(__name__)

# Windows Authentication için bağlantı string'i
app.config['SQLALCHEMY_DATABASE_URI'] = (
    r'mssql+pyodbc://@DESKTOP-4GET9SL\SQLEXPRESS/AnimeHaberDB?'
    'trusted_connection=yes&driver=ODBC+Driver+17+for+SQL+Server'
)

# Örnek (Yerel sunucu için):
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mssql+pyodbc://@SQLEXPRESS/AnimeDB?trusted_connection=yes&driver=ODBC+Driver+17+for+SQL+Server'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "canzumrut"
db = SQLAlchemy(app)

with app.app_context():
    try:
        db.engine.connect()
        print("✅ MS SQL Server'a başarıyla bağlanıldı!")
    except Exception as e:
        print(f"❌ Hata: {e}")

class Anime(db.Model):  # Küçük harfle başlıyor (veritabanındaki tablo adı)
    __tablename__ = 'animebilgileri'
    __table_args__ = {'schema': 'dbo'}  # Şema belirtiyoruz
    
    id = db.Column(db.Integer, primary_key=True)  # PK ve int
    anime_adi = db.Column(db.String(100))  # varchar(100)
    anime_gorsel_link = db.Column(db.String(255))  # varchar(255)
    anime_paragraf = db.Column(db.Text)  # varchar(MAX) yerine Text kullanıyoruz
    tarih = db.Column(db.DateTime)  # null olabilir

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'dbo'}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())

@app.route('/')
def yonlendir():
    return redirect(url_for('animeleri_listele'))

@app.route('/animeler')
def animeleri_listele():
    try:
        sayfa = request.args.get('sayfa', 1, type=int)
        sayfa_basi = 6

        animeler_query = Anime.query.order_by(Anime.tarih.desc())
        toplam = animeler_query.count()

        animeler = animeler_query.offset((sayfa - 1) * sayfa_basi).limit(sayfa_basi).all()
        toplam_sayfa = (toplam + sayfa_basi - 1) // sayfa_basi

        return render_template('a.html', animeler=animeler, sayfa=sayfa, toplam_sayfa=toplam_sayfa)
    
    except Exception as e:
        print(f"❌ Veritabanı hatası: {e}")
        return render_template('hata.html', hata_mesaji=e), 500
    
@app.route('/admin')
def admin_panel():
    return render_template('admin_panel.html')

@app.route('/admin/haber-ekle', methods=['GET', 'POST'])
def haber_ekle():
    if request.method == 'POST':
        anime_adi = request.form['anime_adi']
        anime_gorsel_link = request.form['anime_gorsel_link']
        anime_paragraf = request.form['anime_paragraf']

        yeni_haber = Anime(
            anime_adi=anime_adi,
            anime_gorsel_link=anime_gorsel_link,
            anime_paragraf=anime_paragraf,
            tarih=datetime.now()
        )
        db.session.add(yeni_haber)
        db.session.commit()
        flash("✅ Haber başarıyla eklendi!")

        return redirect(url_for('admin_panel'))

    return render_template('haber_ekle.html')

@app.route('/admin/kullanici-ekle', methods=['GET', 'POST'])
def kullanici_ekle():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Email zaten var mı kontrol et
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("❌ Bu e-posta adresi zaten kayıtlı!")
            return redirect(url_for('kullanici_ekle'))

        yeni_kullanici = User(
            username=username,
            email=email,
            password=password
        )
        try:
            db.session.add(yeni_kullanici)
            db.session.commit()
        except:
            db.session.rollback()
            flash("❌ Bu e-posta adresi zaten var!")

        flash("✅ Kullanıcı başarıyla eklendi!")
        return redirect(url_for('kullanici_ekle'))

    users = User.query.all()
    return render_template('kullanici_ekle.html', users=users)

@app.route('/admin/kullanici-listesi')
def kullanici_listesi():
    users = User.query.all()
    return render_template('kullanici_listesi.html', users=users)

@app.route('/admin/kullanici-sil/<int:user_id>', methods=['POST'])
def kullanici_sil(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("✅ Kullanıcı başarıyla silindi.")
    return redirect(url_for('kullanici_listesi'))

@app.route('/admin/haber-listesi')
def haber_listesi():
    haberler = Anime.query.order_by(Anime.tarih.desc()).all()
    return render_template('haber_listesi.html', haberler=haberler)

@app.route('/admin/haber-sil/<int:haber_id>', methods=['POST'])
def haber_sil(haber_id):
    haber = Anime.query.get_or_404(haber_id)
    db.session.delete(haber)
    db.session.commit()
    flash("🗑 Haber başarıyla silindi.")
    return redirect(url_for('haber_listesi'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session["user_id"] = user.id
            session["username"] = user.username
            flash("✅ Giriş başarılı.")
            return redirect(url_for("animeleri_listele"))  # Girişten sonra anasayfaya yönlen
        else:
            flash("❌ E-posta veya şifre yanlış!")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("👋 Başarıyla çıkış yapıldı.")
    return redirect(url_for("animeleri_listele"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        # Aynı e-posta ile kayıtlı kullanıcı var mı?
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("❌ Bu e-posta adresi zaten kullanılıyor.")
            return redirect(url_for("register"))

        # Kullanıcıyı oluştur ve kaydet
        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        flash("✅ Kayıt başarılı. Şimdi giriş yapabilirsiniz.")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/anime/<int:anime_id>")
def anime_detay(anime_id):
    anime = Anime.query.get_or_404(anime_id)
    return render_template("anime_detay.html", anime=anime)


def haberleri_webden_cek_ve_kaydet():
    url = "https://www.fantastikdiyarlar.com/blog/categories/anime-haberleri"

    try:
        response = requests.get(url)
        response.raise_for_status()
        print('İlk item çekiliyor')
    except requests.RequestException as e:
        print(f"❌ Haberleri çekerken hata oluştu: {e}")
        return
    
    soup = BeautifulSoup(response.content, "html.parser")
    
    picture = soup.find("img", class_="gallery-item-visible gallery-item gallery-item-preloaded")
    link = soup.find("a", class_="O16KGI pu51Xe TBrkhx mqysW5")
    name = soup.find("h2", class_="bD0vt9 KNiaIk")

    if not (picture and link and name):
        print("❌ Gerekli öğeler bulunamadı.")
        return
    
    url2 = link.get("href")
    if url2 and url2.startswith("/"):
        url2 = "https://www.fantastikdiyarlar.com" + url2

    try:
        response2 = requests.get(url2)
        response2.raise_for_status()
        print('İkinci item çekiliyor')
    except requests.RequestException as e:
        print(f"❌ İçerik sayfası çekilirken hata oluştu: {e}")
        return
    
    soup2 = BeautifulSoup(response2.content, "html.parser")
    all_p = ""

    main_texts = soup2.find_all("span", class_="mVzZr")
    for text in main_texts:
        all_p += text.get_text()

    # DÜZGÜN STRİNG VERİLER:
    anime_adi = name.get_text(strip=True)
    anime_gorsel_link = picture.get("src")
    anime_paragraf = all_p.strip()

    # Duplicate kontrolü (aynı başlıktan varsa ekleme)
    if Anime.query.filter_by(anime_adi=anime_adi).first():
        print(f"⚠ {anime_adi} zaten var, eklenmedi.")
        return

    yeni_haber = Anime(
        anime_adi=anime_adi,
        anime_gorsel_link=anime_gorsel_link,
        anime_paragraf=anime_paragraf,
        tarih=datetime.now()
    )

    db.session.add(yeni_haber)
    db.session.commit()
    print("✅ Yeni haber başarıyla eklendi.")

    with app.app_context():
        haberleri_webden_cek_ve_kaydet()

@app.route('/admin/haber-duzenle/<int:haber_id>', methods=['GET', 'POST'])
def haber_duzenle(haber_id):
    haber = Anime.query.get_or_404(haber_id)

    if request.method == 'POST':
        haber.anime_adi = request.form['anime_adi']
        haber.anime_gorsel_link = request.form['anime_gorsel_link']
        haber.anime_paragraf = request.form['anime_paragraf']
        haber.tarih = datetime.now()

        db.session.commit()
        flash("📝 Haber başarıyla güncellendi.")
        return redirect(url_for('haber_listesi'))

    return render_template('haber_duzenle.html', haber=haber)

@app.route("/profil")
def profil():
    if "user_id" not in session:
        flash("Lütfen önce giriş yapınız.")
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    return render_template("profil.html", user=user)

def zamanli_haber_cek():
    with app.app_context():
        print("⏰ Otomatik haber kontrolü başlatıldı.")
        haberleri_webden_cek_ve_kaydet()
    
    # 24 saat sonra yeniden çalıştır (86400 saniye)
    threading.Timer(86400, zamanli_haber_cek).start()


if __name__ == '__main__':
    zamanli_haber_cek()
    app.run(debug=True, port=4000)
