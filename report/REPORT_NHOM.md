# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** G99
**Thành viên:** Nguyễn Thị Thùy Dương, Lê Công Tâm, Nguyễn Thành Tiến
**Ngày:** 20-09-2026

> **Nộp 1 bản / nhóm.** Phần cá nhân (hướng tiếp cận, kết quả riêng, dự đoán…) mỗi thành viên nộp riêng trong `REPORT_NHOM.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề (Domain) & Lý Do Chọn

**Chủ đề:** Chính sách Đổi trả và Bảo hành Thương mại Điện tử (Shopee, Lazada, Thế Giới Di Động, CellphoneS, VinFast)

**Tại sao nhóm chọn chủ đề này?**
> Nhóm chọn chủ đề chính sách đổi trả và bảo hành thương mại điện tử vì đây là lĩnh vực thực tế cao, quy định phức tạp và có sự phân biệt rõ ràng giữa quyền lợi người mua (`buyer`) và nghĩa vụ nhà bán hàng (`seller`). Tập dữ liệu này rấat thích hợp để chứng minh hiệu quả của mô hình RAG kết hợp lọc siêu dữ liệu (metadata filtering).

### Danh sách tài liệu (Data Inventory)

| # | Tên tài liệu | Nguồn (Source URL) | Ngày lấy / Phiên bản | Số ký tự | Metadata đã gán |
|---|--------------|------------|--------------------|----------|-----------------|
| 1 | `doi-tra-bao-hanh-cellphones-buyer.md` | https://cellphones.com.vn/chinh-sach-bao-hanh | 2026-09-20 / not-stated | 3,892 | `audience: buyer`, `category: warranty-policy`, `language: vi` |
| 2 | `doi-tra-bao-hanh-lazada-buyer.md` | https://lazada.vn/helpcenter/warranty-guide | 2026-09-20 / not-stated | 2,658 | `audience: buyer`, `category: warranty-policy`, `language: vi` |
| 3 | `doi-tra-bao-hanh-lazada-seller.md` | https://sellercenter.lazada.vn/seller/helpcenter/order-processing-and-return-policy | 2026-09-20 / 2026-v1 | 2,753 | `audience: seller`, `category: order-return-policy`, `language: vi` |
| 4 | `doi-tra-bao-hanh-samsung-buyer.md` | https://www.samsung.com/vn/support/warranty/ | 2026-09-20 / not-stated | 2,150 | `audience: buyer`, `category: warranty-policy`, `language: vi` |
| 5 | `doi-tra-bao-hanh-shopee-buyer.md` | https://shopee.vn/blog/chinh-sach-bao-hanh-shopee | 2026-09-20 / not-stated | 3,021 | `audience: buyer`, `category: warranty-policy`, `language: vi` |
| 6 | `doi-tra-bao-hanh-shopee-seller.md` | https://banhang.shopee.vn/edu/article/10626 | 2026-09-20 / 2026-v1 | 4,237 | `audience: seller`, `category: warranty-policy`, `language: vi` |
| 7 | `doi-tra-bao-hanh-tgdd-buyer.md` | https://www.thegioididong.com/chinh-sach-bao-hanh-san-pham | 2026-09-20 / not-stated | 4,051 | `audience: buyer`, `category: warranty-policy`, `language: vi` |
| 8 | `doi-tra-bao-hanh-tiki-seller.md` | https://hocvien.tiki.vn/faq/huong-dan-quy-trinh-xu-ly-doi-tra-bao-hanh-mo-hinh-sd/ | 2026-09-20 / not-stated | 2,210 | `audience: seller`, `category: warranty-policy`, `language: vi` |
| 9 | `doi-tra-bao-hanh-vinfast-buyer.md` | https://vinfastauto.com/vn_vi/chinh-sach-bao-hanh-xe-may-dien | 2026-09-20 / not-stated | 3,776 | `audience: buyer`, `category: warranty-policy`, `language: vi` |

**Danh sách kiểm tra quản trị dữ liệu (Data governance checklist):**
- [x] Tập tài liệu (Corpus) chỉ chứa nguồn công khai/được phép dùng và không chứa dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ.
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version` (hoặc ngày hiệu lực) trong metadata.

### Cấu trúc Metadata (Metadata Schema)

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho truy xuất (retrieval)? |
|----------------|------|---------------|-------------------------------|
| `doc_id` | `str` | `doi-tra-bao-hanh-tgdd-buyer` | Định danh tài liệu duy nhất, phục vụ xóa chunk và đối chiếu nguồn trong CSV. |
| `audience` | `str` | `buyer` / `seller` | Phân loại đối tượng áp dụng để pre-filter, tránh nhầm lẫn giữa quy định khách hàng và nghĩa vụ shop. |
| `category` | `str` | `warranty-policy` | Phân loại danh mục chính sách phục vụ lọc nâng cao. |
| `language` | `str` | `vi` | Phân loại ngôn ngữ tài liệu. |

---

## 2. Thiết kế chiến lược (Strategy Design) — Nhóm (15 điểm)

### Phân tích đường cơ sở (Baseline Analysis)

Chạy `ChunkingStrategyComparator().compare()` trên các tài liệu:

| Tài liệu | Chiến lược (Strategy) | Số lượng Chunk | Độ dài trung bình | Giữ được ngữ cảnh không? |
|-----------|----------|-------------|------------|-------------------|
| `doi-tra-bao-hanh-tgdd-buyer.md` | FixedSizeChunker (`fixed_size`) | 26 | 195 | Trung bình (cắt ngẫu nhiên theo ký tự) |
| `doi-tra-bao-hanh-tgdd-buyer.md` | SentenceChunker (`by_sentences`) | 12 | 312 | Khá (giữ trọn vẹn từng câu) |
| `doi-tra-bao-hanh-tgdd-buyer.md` | RecursiveChunker (`recursive`) | 14 | 275 | Tốt (giữ nguyên cấu trúc dòng & ranh giới đoạn) |

### Chiến lược của từng thành viên

**Thành viên 1 — Nguyễn Thị Thùy Dương**
- **Loại chiến lược:** FixedSizeChunker (`chunk_size=500`, `overlap=50`)
- **Mô tả & lý do chọn:** Đơn giản, độ dài chunk đồng đều. Phù hợp cho việc kiểm thử baseline nhưng dễ cắt rách giữa các câu quy định.

**Thành viên 2 — Lê Công Tâm**
- **Loại chiến lược:** RecursiveChunker (`chunk_size=500`, separators=["\n\n", "\n", ". ", " ", ""])
- **Mô tả & lý do chọn:** Thử nghiệm cắt đệ quy theo các phân cách từ lớn đến nhỏ (`\n\n` -> `\n` -> `. `). Giúp giữ trọn vẹn khối ý nghĩa của điều khoản quy định và tự động gom mảnh nhỏ sát ngưỡng `chunk_size`.

**Thành viên 3 — Nguyễn Thành Tiến**
- **Loại chiến lược:** HeadingChunker (Custom split theo tiêu đề `##`, `###`)
- **Mô tả & lý do chọn:** Văn bản chính sách được biên soạn theo từng Điều/Mục. Tách trước theo thẻ heading `##` giúp mỗi chunk là một điều khoản trọn vẹn. Nếu section quá dài thì đệ quy hạ xuống cắt theo câu.
- **Code snippet (custom):**
```python
class HeadingChunker:
    def chunk(self, text: str) -> list[str]:
        sections = re.split(r'(?=\n##+\s)', text)
        chunks = []
        for sec in sections:
            sec_str = sec.strip()
            if not sec_str: continue
            if len(sec_str) <= 500:
                chunks.append(sec_str)
            else:
                chunks.extend(RecursiveChunker(chunk_size=500).chunk(sec_str))
        return chunks
```

### So Sánh Giữa Các Thành Viên

| Thành viên | Chiến lược (Strategy) | Điểm truy xuất (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Nguyễn Thành Tiến | `HeadingChunker` | 7/10 | Giữ heading và phạm vi điều khoản | Một số bằng chứng vẫn bị tách giữa các chunk |
| Nguyễn Thành Tiến | `SentenceChunker` | **8/10** | Giữ ranh giới câu, Q1/Q3/Q5 có answer chunk | Q2 và Q4 còn thiếu answer chunk hoàn chỉnh |

**Chiến lược nào tốt nhất cho chủ đề này? Tại sao?**
> Chiến lược **`HeadingChunker` kết hợp `RecursiveChunker`** là tốt nhất cho văn bản chính sách TMĐT. Vì các văn bản luật và chính sách vốn được biên soạn theo từng Điều/Mục rõ ràng; chia theo tiêu đề giúp chunk giữ được toàn bộ phạm vi quy định mà không bị rách ý.

---

## 3. Câu hỏi đánh giá & Chất lượng truy xuất (Retrieval Quality) — Nhóm (10 điểm)

### Câu hỏi đánh giá & Câu trả lời chuẩn (nhóm thống nhất)

| # | Câu hỏi (Query) | Câu trả lời chuẩn (Gold Answer) | Chunk nào chứa thông tin? |
|---|-------|-------------------------------|--------------------------|
| 1 | Thời hạn yêu cầu đổi trả hoặc hoàn tiền dành cho người mua là bao nhiêu ngày? | Được đổi mới miễn phí trong 30 ngày đầu tại TGDĐ/CellphoneS nếu lỗi kỹ thuật nhà sản xuất. | `doi-tra-bao-hanh-cellphones-buyer#0`, `doi-tra-bao-hanh-tgdd-buyer#1` |
| 2 | Thời hạn Người bán phải phản hồi và gửi khiếu nại Trả hàng/Hoàn tiền là bao nhiêu lâu? | Người bán có thời hạn 2 ngày (Shopee) hoặc 48 giờ (Lazada) để xử lý và gửi khiếu nại đối soát. | `doi-tra-bao-hanh-shopee-seller#0`, `doi-tra-bao-hanh-lazada-seller#2` |
| 3 | Thời hạn bảo hành xe máy điện và Pin LFP VinFast là bao nhiêu năm? | Thời hạn bảo hành xe máy điện là 6 năm/không giới hạn km; pin LFP bảo hành lên tới 8 năm. | `doi-tra-bao-hanh-vinfast-buyer#1` |
| 4 | Các trường hợp nào thiết bị di động bị từ chối bảo hành hoặc bị trừ phí khi đổi trả? | Từ chối bảo hành khi tự tháo máy, rơi vỡ ngập nước; thu phí 10-20% nếu trả sản phẩm không lỗi hoặc mất phụ kiện/hộp. | `doi-tra-bao-hanh-tgdd-buyer#2`, `doi-tra-bao-hanh-cellphones-buyer#2` |
| 5 | Người bán cần chuẩn bị những bằng chứng gì khi khiếu nại đơn hàng bị trả về không nguyên vẹn? | Video mở kiện hàng có sự hiện diện của shipper, quay rõ 6 mặt niêm phong và tình trạng sản phẩm bên trong. | `doi-tra-bao-hanh-shopee-seller#1`, `doi-tra-bao-hanh-lazada-seller#2` |

### Tổng hợp chất lượng truy xuất của nhóm

| # | Câu hỏi | Kết quả của Nguyễn Thành Tiến | Điểm |
|---|---------|-------------------------------|---------|
| 1 | Đổi trả người mua | `SentenceChunker`: có answer chunk trong Top-3 | 2/2 |
| 2 | Phản hồi của người bán | Có tài liệu gold nhưng thiếu answer chunk hoàn chỉnh | 0/2 |
| 3 | Bảo hành VinFast | Chunk VinFast chứa đủ `6 năm`, `8 năm`, `Pin LFP` | 2/2 |
| 4 | Từ chối bảo hành | Không có answer chunk đủ các điều kiện | 0/2 |
| 5 | Bằng chứng khiếu nại shop | Chunk Shopee seller chứa đủ `video`, `6 mặt`, `shipper` | 2/2 |
| **Tổng SentenceChunker** |  |  | **8/10** |

**Lọc bằng metadata có giúp ích không? Ở câu hỏi nào?**
> Filter `audience` được áp dụng ở Q1, Q2 và Q5. Filter giúp giới hạn đúng nhóm buyer/seller và làm Top-3 thay đổi ở một số câu, nhưng không tự đảm bảo answer chunk khi bằng chứng nằm ở nhiều nền tảng.

**Phân tích lỗi thực tế (Failure Case Analysis — 3 phần):**
1. **Câu hỏi bị hỏng (Failure Query):** Câu hỏi #2 — *"Thời hạn Người bán phải phản hồi và gửi khiếu nại Trả hàng/Hoàn tiền là bao lâu?"*.
2. **Nguyên nhân gốc rễ (Root Cause):** Mốc `2 ngày` nằm ở chính sách Shopee seller còn `48 giờ` nằm ở chính sách Lazada seller. Các tài liệu đều có thông tin đúng, nhưng không có một answer chunk duy nhất chứa đầy đủ câu trả lời đa nền tảng.
3. **Đề xuất giải pháp khắc phục (Proposed Fix):** Giữ metadata filter, thêm context lân cận và cho Agent tổng hợp nhiều nguồn gold; không cộng điểm thủ công chỉ vì keyword xuất hiện rải rác trong Top-3.

---

## 4. Thuyết trình (Demo) & Bài học nhóm — Nhóm (5 điểm)

**Những phân tích (insights) hay nhất nhóm sẽ trình bày:**
1. Kết quả kiểm thử **A/B Testing** chứng minh tầm quan trọng tuyệt đối của **Metadata Pre-filtering** trong hệ thống RAG thương mại điện tử.
2. Sự khác biệt giữa đánh giá ngây thơ (chỉ xem `doc_id`) và đánh giá 2 mức dựa trên nội dung thực tế (`content relevance`).
3. Ranh giới giữa **Trình nhúng Giả lập (MockEmbedder)** chỉ dùng kiểm thử cấu trúc và **Embedding ngữ nghĩa thật**.

**Bài học rút ra khi so sánh trong nhóm:**
> Cùng một tập dữ liệu 10 file, việc lựa chọn chiến lược chia nhỏ (chunking strategy) quyết định tính mạch lạc của câu trả lời RAG Agent. Cắt cố định ký tự (`FixedSize`) dễ làm rách ngữ cảnh ở các điểm ngắt câu, trong khi chia theo tiêu đề (`HeadingChunker`) và đệ quy (`Recursive`) đem lại điểm chất lượng truy xuất cao nhất.

**Nếu làm lại, nhóm sẽ thay đổi gì trong chiến lược dữ liệu (data strategy)?**
> Nhóm sẽ chuẩn hóa thêm trường metadata `category` (ví dụ: `warranty-terms`, `refund-policy`, `penalty-terms`) để hỗ trợ lọc đa chiều chính xác hơn nữa.

---

## Tự Đánh Giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu (Document Set Quality) | 10 / 10 |
| Thiết kế chiến lược (Strategy Design) | 14 / 15 |
| Chất lượng truy xuất (Retrieval Quality) | 8 / 10 |
| Thuyết trình (Demo) | 5 / 5 |
| **Tổng phần nhóm** | **37 / 40** |