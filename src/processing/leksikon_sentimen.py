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
