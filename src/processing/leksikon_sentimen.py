"""Leksikon sentimen Bahasa Indonesia (Fase F).

Daftar kata kurasi manual untuk analisis sentimen berbasis leksikon
khusus domain BERITA (bukan media sosial).
Catatan 6 Okt 2026: InSet (Koto & Rahmaningtyas, leksikon Twitter
3.609+6.609 kata) diuji dan DITOLAK — kata netral berita seperti
"hutan", "atas", "tradisional" punya skor liar dari slang Twitter.
Kualitas > kuantitas untuk domain berita.
Semua lowercase.
"""

POSITIF = frozenset("""
baik bagus sukses berhasil meningkat naik tumbuh apresiasi bangga hebat
maju positif untung laba rekor menang juara selamat aman damai
sejahtera makmur optimis yakin kuat cepat efisien inovatif kreatif cemerlang
gemilang prestasi penghargaan bantuan peduli solusi perbaikan pulih sembuh
sehat bahagia senang gembira syukur dukungan kerjasama sepakat setuju
puas lega ringan mudah lancar tertib rapi bersih indah cantik
murah diskon promo gratis hadiah bonus berkah rahmat nikmat
adil jujur bijak cerdas pintar pandai tanggap sigap siap
solid kompak bersatu rukun harmonis toleran inklusif ramah sopan
terbaik unggul prima favorit populer
melesat meroket melambung lampaui atasi redam padam
resmikan diresmikan raih meraih terobosan stabil surplus ekspor
diakui pengakuan investasi apresiasi ulang tahun
""".split())

NEGATIF = frozenset("""
buruk gagal jatuh turun rugi korban tewas meninggal mati luka cedera
kebakaran banjir bencana krisis parah kritis darurat bahaya ancaman
takut khawatir cemas panik marah kecewa sedih duka prihatin miris ngeri
seram rusak hancur runtuh ambruk macet kacau kisruh gaduh demo protes
konflik perang korupsi curang bohong hoaks fitnah denda penjara vonis
tersangka terdakwa phk pengangguran miskin lapar sakit wabah virus
polusi asap kabut kekeringan kelaparan haus kekurangan langka mahal
bengkak jebol bocor tumpah ledak terbakar hangus gosong abu debu
lumpuh buntu tutup bangkrut pailit sengsara menderita tersiksa terancam
terdampak karhutla hotspot ispa sesak batuk
ditangkap penangkapan mengungsi pengungsi meluas longsor gempa tsunami
tenggelam tabrakan kecelakaan meledak ledakan rob abrasi kabut
hilang puting beliung endemi klaster terbongkar
""".split())

# Kata negasi: membalik polaritas kata sentimen dalam 2 token sesudahnya.
# ("tidak baik" -> negatif; "tidak buruk" -> positif)
NEGASI = frozenset(["tidak", "bukan", "jangan", "belum", "tanpa"])

# Penguat: mengalikan bobot 1.5 bila muncul dalam 2 token sebelumnya.
INTENSIF = frozenset(["sangat", "sekali", "amat", "sungguh", "benar-benar",
                      "paling", "semakin", "kian"])


# --- Leksikon Bahasa Inggris (ditambahkan 9 Okt 2026) ---
# Untuk artikel media internasional (Reuters, BBC, CNN, dll).
# Kurasi manual domain BERITA, sejajar dengan kamus Indonesia.

POSITIF_EN = frozenset("""
good great success successful increase rise grow growth praise proud
excellent advance positive profit record win winner safe secure peaceful
prosperous optimistic confident strong fast efficient innovative creative
brilliant achievement award help aid solution improve recovery recover
healthy happy glad grateful support cooperation agree agreement
satisfied relief easy smooth orderly clean beautiful
cheap discount promo free gift bonus blessing
fair honest wise smart quick responsive ready
solid united harmonious tolerant inclusive friendly polite
best superior prime favorite popular
surge soar outperform overcome stabilize surplus export
recognized recognition investment breakthrough stable
launch launched achieve achieved
""".split())

NEGATIF_EN = frozenset("""
bad fail failed fall drop loss victim killed dead died death injured injury
fire wildfire flood disaster crisis severe critical emergency danger threat
fear worried anxious panic angry disappointed sad grief concerned
damaged destroyed collapsed stuck jammed chaos riot protest
conflict war corrupt fraud lie hoax slander fine jail sentence
suspect defendant layoff unemployment poor hungry sick outbreak virus
pollution smoke haze drought famine thirst shortage scarce expensive
leak spill explode exploded burned burnt ash dust
paralyzed closed bankrupt miserable suffering threatened
affected arrested arrest evacuate evacuated widespread landslide
earthquake tsunami drowned collision accident explosion
missing tornado endemic cluster exposed
kill kills killing wounded casualties death toll
""".split())

# English negation: flips polarity within 2 tokens after.
NEGASI_EN = frozenset(["not", "no", "never", "without", "neither", "nor",
                       "hardly", "barely", "against"])

# English intensifiers: multiply weight 1.5 within 2 tokens before.
INTENSIF_EN = frozenset(["very", "highly", "extremely", "incredibly",
                         "particularly", "especially", "most", "more",
                         "increasingly"])
