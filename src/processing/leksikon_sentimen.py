"""Leksikon sentimen Bahasa Indonesia (Fase F).

Daftar kata starter untuk analisis sentimen berbasis leksikon.
Bukan kamus lengkap — cukup untuk pilot; kata bisa ditambah seiring
evaluasi terhadap artikel nyata. Semua lowercase.
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
""".split())

# Kata negasi: membalik polaritas kata sentimen dalam 2 token sesudahnya.
# ("tidak baik" -> negatif; "tidak buruk" -> positif)
NEGASI = frozenset(["tidak", "bukan", "jangan", "belum", "tanpa"])

# Penguat: mengalikan bobot 1.5 bila muncul dalam 2 token sebelumnya.
INTENSIF = frozenset(["sangat", "sekali", "amat", "sungguh", "benar-benar",
                      "paling", "semakin", "kian"])
