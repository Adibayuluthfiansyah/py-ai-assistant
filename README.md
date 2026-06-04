Masalah utama yang ingin di selesaikan adalah kemacetan operasional. Saat admin memegang satu nomor WhatsApp, pesan yang masuk tercampur aduk ada yang mau booking meja, ada yang minta tagihan (billing), ada yang komplain makanan dingin, dan ada yang sekadar tanya menu. Manusia akan lambat memilah ini.

BISNIS FLOW

Fase 1: Inbound 
Pelanggan Mengirim Pesan: Seorang pelanggan mengetik di WhatsApp: "Malam kak, saya mau reservasi meja VIP untuk besok jam 7 malam, 4 orang atas nama Joko."

Penangkapan oleh Sistem (Golang): Pesan ini dikirim oleh server Meta/WhatsApp langsung ke endpoint Webhook Golang.

Pencatatan Aman (PostgreSQL): Sebelum melakukan apa pun, Golang langsung menyimpan pesan mentah ini ke tabel incoming_messages dengan status PENDING_AI. Ini adalah jaminan keamanan agar tidak ada satu pun chat pelanggan yang hilang jika tiba-tiba listrik padam.

Fase 2: Analisis Kognitif 
Di titik ini, Golang tahu ada pesan masuk, tapi tidak mengerti apa maksudnya.

Delegasi Tugas: Golang secara asynchronous mengirim teks pesan tadi ke Python (AI Microservice).

Pemahaman Niat (Intent Recognition): AI membaca pola teks dan menyimpulkan: "Oh, ini bukan komplain, ini adalah pesanan. Kategorinya: BOOKING."

Ekstraksi Data (Entity Extraction): AI membedah kalimat pelanggan dan menarik variabel pentingnya:
Tipe: VIP
Waktu: Besok, 19:00
Pax: 4 orang
Nama: Joko
Pengembalian Jawaban: Python mengembalikan data JSON terstruktur ini ke Golang.

Fase 3: Routing & Eksekusi 
Sekarang Golang sudah memegang data matang dari AI. Golang bertindak sebagai manajer lantai dan langsung mengeksekusi logika bisnis berdasarkan Intent 

Skenario A (Jika Intent = BOOKING):
Golang mengecek tabel reservations di database. Apakah meja VIP besok jam 7 malam masih kosong?

Jika Kosong: Golang membalas WhatsApp otomatis: "Reservasi VIP untuk 4 orang besok jam 19:00 atas nama Joko telah dikonfirmasi." Data langsung masuk ke sistem.

Jika Penuh: Golang membalas: "Mohon maaf, meja VIP besok jam 19:00 penuh. Apakah berkenan di jam 20:00?"

Skenario B (Jika Intent = BILLING):
Pelanggan chat: "Meja 12 minta bill dong." Golang tidak perlu membalas WA. Golang langsung mengirim sinyal WebSocket ke Next.js Admin Dashboard. Tablet kasir akan berbunyi dan memunculkan pop-up: "Cetak Bill: Meja 12".

Skenario C (Jika Intent = COMPLAINT):
Pelanggan chat: "Layanan lama banget, minuman saya belum datang." Golang mendeteksi ini darurat. Pesan otomatis diteruskan ke tab khusus di Dashboard Manajer dengan warna merah agar segera ditangani.

Fase 4: Fulfillment (Penyelesaian oleh Staf)
Di Next.js Admin Dashboard, staf tidak lagi melihat ratusan chat WA yang menumpuk. Layar mereka sudah terpecah rapi:

Kasir hanya melihat layar pesanan dan tagihan.
Admin Reservasi hanya melihat kalender dan draft booking.
Semua sinkronisasi data ini ditarik dari PostgreSQL.