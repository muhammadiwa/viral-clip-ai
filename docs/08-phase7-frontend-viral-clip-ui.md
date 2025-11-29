# 08 – Phase 7: Frontend – AI Viral Clip UI

## 1. Goal

Membangun UI lengkap untuk menu **AI Viral Clip** sesuai layout referensi yang kamu kirim:

- Sidebar multi-fitur.
- Halaman AI Viral Clip dengan:
  - Upload section.
  - Riwayat video.
  - Section AI Clipping (konfigurasi).
  - Grid hasil clips.
  - Modal Segment Detail.

## 2. Struktur Frontend

Direktori:

```txt
frontend/
  src/
    app/
      routes/
        AiViralClipPage.tsx
    components/
      layout/
        Sidebar.tsx
        AppShell.tsx
      viral-clip/
        UploadCard.tsx
        VideoHistoryGrid.tsx
        AiClippingPanel.tsx
        ClipsGrid.tsx
        ClipCard.tsx
        ClipDetailModal.tsx
    lib/
      apiClient.ts
      hooks/...

3. Halaman AI Viral Clip
3.1. Layout

    Gunakan AppShell:

        Sidebar kiri (menu).

        Content kanan (scrollable).

Sidebar:

    Avatar + nama user.

    Menu sections:

        Home

        Create (dummy)

        AI Tools:

            AI Video (dummy)

            AI Viral Clip (active)

            dll.

        Publish, My Projects, Pricing (dummy).

3.2. UploadCard

Komponen:

    Input text:

        Placeholder: Drop a YouTube link or paste URL...

    Button:

        Upload → file picker.

        Google Drive (dummy).

    Primary button:

        Get Clips

    Link kecil:

        Click here to try a sample project.

Interaksi:

    Saat klik Get Clips:

        Jika ada youtube_url → POST /viral-clip/video/youtube.

        Jika ada file → POST /viral-clip/video/upload.

        Tampilkan toast/hint bahwa job dibuat.

3.3. VideoHistoryGrid

    Panggil GET /viral-clip/videos.

    Tampilkan card:

        Thumbnail

        Title

        Badge status (Processing, Ready, Failed).

        Info jumlah clip (kalau ada).

    Klik card → set selectedVideo.

3.4. AiClippingPanel

Muncul jika selectedVideo ada.

Elemen:

    Info Video (thumbnail + title + durasi).

    Dropdown:

        Video Type

        Aspect Ratio

        Clip Length

        Subtitle (Yes/No)

    Input text:

        Include specific moments.

    Range slider:

        Processing timeframe.

    Subtitle Style:

        Grid style cards dari /subtitle-styles (global + user).

    Button:

        Generate Clips → membuat clip_batch.

3.5. ClipsGrid

    Panggil GET /viral-clip/clip-batches/{batch_id}/clips.

    Tampilkan grid card:

        Thumbnail

        Viral score (pojok kiri atas)

        Durasi (pojok kanan atas)

        Title.

        Icon:

            Download

            Export SRT

            Export/Publish.

3.6. ClipDetailModal

Di-trigger klik card.

Isi:

    Kiri: preview video (lokal atau thumbnail besar).

    Kanan:

        Title (editable field).

        Viral Score + breakdown (Hook / Flow / Value / Trend).

        Scene Analysis (table transcript per segment).

    Footer:

        Button Download.

        Button Export SRT.

        Button Publish on Social (dummy).

4. State Management

    Gunakan React Query:

        useVideos()

        useClipBatches(videoId)

        useClips(batchId)

        useClipDetail(clipId)

5. UX Detail

    Loading skeleton untuk grid clips.

    Toast untuk error (network / API).

    Hover animation menggunakan Framer Motion.

    Responsive:

        Desktop: sidebar + 3–5 kolom.

        Tablet: sidebar collapsible.

        Mobile (optional belakangan).

6. Testing Checklist

    ✅ Flow end-to-end: Paste URL → Get Clips → lihat clips di grid.

    ✅ Error saat job belum selesai → UI menunjukkan status processing.

    ✅ Modal detail tampil benar.