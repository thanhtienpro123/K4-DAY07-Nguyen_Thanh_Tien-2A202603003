# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Nguyễn Thành Tiến
**Nhóm:** [Tên nhóm]
**Ngày:** 20-09-2026

> **Nộp 1 bản / sinh viên.** Phần nhóm (lựa chọn tài liệu, thiết kế chiến lược, bộ câu hỏi đánh giá, demo) nộp chung 1 bản trong `REPORT_NHOM.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần cá nhân: 60** = Khởi động (5) + Hướng tiếp cận (10) + Hoàn thiện code (30) + Dự đoán độ tương tự (5) + Kết quả truy xuất của tôi (10).

---

## 1. Khởi động (Warm-up) — Cá nhân (5 điểm)

### Độ tương tự Cosine (Cosine Similarity) (Bài tập 1.1)

**Độ tương tự cosine cao (High cosine similarity) nghĩa là gì?**
> Hai vector embedding có hướng gần nhau, cho thấy hai đoạn văn có nội dung hoặc ý nghĩa gần nhau. Cosine chỉ đo góc giữa vector nên phù hợp để so sánh văn bản có độ dài khác nhau.

**Ví dụ có độ tương tự CAO:**
- Câu A: Người mua có thể yêu cầu trả hàng trong vòng 15 ngày.
- Câu B: Khách hàng được gửi yêu cầu hoàn trả trong 15 ngày sau khi nhận hàng.
- Tại sao tương đồng: Hai câu cùng nói về thời hạn trả hàng, dù dùng cách diễn đạt khác nhau.

**Ví dụ có độ tương tự THẤP:**
- Câu A: Người bán phải phản hồi yêu cầu hoàn tiền trong 02 ngày.
- Câu B: Amazon hướng dẫn cách đổi trả một sản phẩm đã mua.
- Tại sao khác: Một câu nói về thời hạn phản hồi của người bán, câu còn lại là hướng dẫn của nền tảng khác.

**Tại sao độ tương tự cosine (cosine similarity) được ưu tiên hơn khoảng cách Euclid (Euclidean distance) cho text embeddings?**
> Khoảng cách Euclid bị ảnh hưởng bởi độ lớn và độ dài vector. Cosine tập trung vào hướng ngữ nghĩa, vì vậy ổn định hơn khi hai văn bản có độ dài khác nhau.

### Bài toán tính toán Chunking (Bài tập 1.2)

**Tài liệu 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
> Bước nhảy là `500 - 50 = 450`. Số chunk theo công thức của `FixedSizeChunker` là `ceil((10000 - 50) / 450) = ceil(22.11) = 23` chunks.

**Nếu độ chồng chéo (overlap) tăng lên 100, số lượng chunk thay đổi thế nào? Tại sao muốn độ chồng chéo nhiều hơn?**
> Bước nhảy còn `500 - 100 = 400`, nên số chunk là `ceil((10000 - 100) / 400) = 25`. Overlap lớn hơn giúp giữ ngữ cảnh ở biên chunk nhưng làm tăng số chunk và chi phí embedding.

---

## 2. Hướng tiếp cận của tôi (My Approach) — Cá nhân (10 điểm)

Giải thích cách tiếp cận của bạn khi lập trình (implement) các phần chính trong gói `src`.

### Các hàm chia nhỏ (Chunking Functions)

**`SentenceChunker.chunk`** — hướng tiếp cận:
> Dùng `re.split(r"(?<=[.!?])(?: +|\n+)", text)` để tách sau dấu kết thúc câu và giữ lại dấu câu. Các câu rỗng được loại bỏ, sau đó gom theo `max_sentences_per_chunk`; text rỗng trả về danh sách rỗng. Điểm hạn chế là chữ viết tắt hoặc số thập phân có thể bị nhận diện chưa hoàn hảo.

**`RecursiveChunker.chunk` / `_split`** — hướng tiếp cận:
> Thuật toán thử các separator theo thứ tự `\n\n`, `\n`, `. `, khoảng trắng rồi mới cắt theo ký tự. Nếu đoạn đã nhỏ hơn `chunk_size` thì dừng; nếu còn quá dài thì đệ quy xuống separator thấp hơn và cuối cùng hard-split theo kích thước.

### Lớp EmbeddingStore

**`add_documents` + `search`** — hướng tiếp cận:
> Mỗi `Document` được chuyển thành record gồm `id`, `content`, `metadata` và embedding. Khi tìm kiếm, store tạo embedding cho query, tính dot product với các vector đã lưu, sắp xếp giảm dần và trả về tối đa `top_k` kết quả. Với embedding đã chuẩn hóa, dot product tương đương cosine similarity.

**`search_with_filter` + `delete_document`** — hướng tiếp cận:
> Metadata được pre-filter trước khi tính similarity để loại ứng viên sai đối tượng. `delete_document` xóa các record có `metadata.doc_id` hoặc id tương ứng và trả về trạng thái có xóa được hay không.

### Tác tử KnowledgeBaseAgent

**`answer`** — hướng tiếp cận:
> Agent lấy các chunk liên quan, đánh số nguồn trong context rồi đưa vào prompt cùng câu hỏi. Prompt yêu cầu chỉ dùng context, tránh bịa thông tin và trích dẫn nguồn; nếu store rỗng thì trả thông báo thay vì gọi mô hình không cần thiết.

---

## 3. Hoàn thiện code (Core Implementation) — Cá nhân (30 điểm)

Vượt qua bộ kiểm thử là điều kiện tính điểm phần này.

### Kết Quả Kiểm Thử (Test Results)

```text
42 passed in 0.09s
```

**Số lượng bài test vượt qua (pass):** **42 / 42**

---

## 4. Dự đoán độ tương tự (Similarity Predictions) — Cá nhân (5 điểm)

| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | Người mua có thể yêu cầu trả hàng trong vòng 15 ngày. | Khách hàng được gửi yêu cầu hoàn trả trong 15 ngày sau khi nhận hàng. | cao | 0.902807 | Đúng |
| 2 | Người bán phải phản hồi yêu cầu hoàn tiền trong 02 ngày. | Amazon hướng dẫn cách đổi trả một sản phẩm đã mua. | thấp | 0.263700 | Đúng |
| 3 | Người bán TikTok cần cung cấp video mở kiện hàng và hình ảnh 6 mặt. | Mã giảm giá Shopee được hoàn lại trong vòng 48 giờ. | thấp | 0.157480 | Đúng |
| 4 | Người bán TikTok có thể gửi khiếu nại trong vòng 15 ngày. | Người bán được gửi khiếu nại trong thời hạn 15 ngày kể từ khi nhận hàng. | cao | 0.806407 | Đúng |
| 5 | Chính sách trả hàng của Shopee áp dụng cho người mua. | Điều khoản TikTok Mall quy định bằng chứng hàng chính hãng. | thấp | 0.449860 | Đúng |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn ý nghĩa?**
> Local multilingual embedding phản ánh tốt hơn MockEmbedder vì có thể xếp các câu cùng chủ đề gần nhau. Tuy nhiên score cao vẫn có thể chọn sai section, nên phải kiểm tra nội dung chunk thay vì chỉ nhìn similarity.

---

## 5. Kết quả truy xuất của tôi (Competition Results) — Cá nhân (10 điểm)

Chạy **5 câu hỏi đánh giá của nhóm** trên mã nguồn cá nhân của bạn trong gói `src`. **5 câu hỏi này phải trùng với các thành viên cùng nhóm** (xem `REPORT_NHOM.md`).

**Cấu hình chạy:** local multilingual embedding (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`), chiến lược `heading`, `chunk_size=600`, có filter theo `audience` và đối chiếu A/B với trường hợp không filter. Chi tiết Top-3 nằm trong `ket_qua_benchmark.txt`.

| # | Câu hỏi (Query) | Top-3 truy xuất được (doc_id/chunk_id) | Top-1 score | Chunk đáp án trong Top-3? | Điểm |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | Người mua có thể gửi yêu cầu trả hàng/hoàn tiền trong bao nhiêu ngày? | `shopee-return-regulation#3`, `shopee-return-regulation#2`, `ebay-money-back-guarantee#23` | 0.751170 | Có; chứa `15 ngày`, `trả hàng`, `hoàn tiền` | 2/2 |
| 2 | Người bán Shopee phải phản hồi trong bao lâu? | `shopee-return-refund-policy#26`, `#39`, `#43` | 0.869925 | Có; Top-1 chứa `02 ngày`, `phản hồi`, `Người Bán` | 2/2 |
| 3 | Người bán TikTok có thể gửi khiếu nại trong bao nhiêu ngày? | `tiktok-return-refund#6`, `tiktok-mall-terms#55`, `tiktok-mall-terms#45` | 0.775720 | Có; Top-1 chứa `15 ngày`, `khiếu nại`, `người bán` | 2/2 |
| 4 | Người bán TikTok cần bằng chứng gì khi mở kiện hàng trả về? | `tiktok-mall-terms#28`, `tiktok-return-refund#41`, `tiktok-return-refund#35` | 0.749550 | Không; gold document có mặt nhưng chunk không đủ `6 mặt` | 0/2 |
| 5 | Mã giảm giá Shopee được hoàn lại trong bao lâu? | `shopee-return-regulation#14`, `shopee-return-claim-process#6`, `shopee-return-shipping-fee#10` | 0.803703 | Không; gold document có mặt nhưng chunk không có `48 giờ` và `Mã giảm giá` cùng nhau | 0/2 |

**Bao nhiêu câu hỏi trả về chunk có liên quan trong top-3?** 3 / 5

**Tổng điểm chiến lược heading:** 7 / 10.

**Kết quả A/B filter:** Filter làm thay đổi Top-3 ở Q1, Q2, Q4 và Q5; Q3 không thay đổi Top-3. Q1 là ví dụ filter hữu ích: có filter đưa chunk Shopee chứa đáp án lên Top-1, còn không filter trả về các chunk TikTok cùng chủ đề nhưng không phải nguồn gold.

**Failure case:** Q4 lấy đúng tài liệu TikTok trong Top-3 nhưng thông tin `video mở kiện hàng` và `6 mặt` nằm ở các section/chunk khác nhau, nên không có answer chunk hoàn chỉnh. Có thể sửa bằng overlap hoặc chunk theo section bằng cách giữ toàn bộ khối hướng dẫn bằng chứng trong cùng chunk.

**Điều hay nhất tôi học được từ thành viên khác / nhóm khác (qua demo):**
So sánh phải kiểm tra nội dung chunk, không chỉ kiểm tra `doc_id`. Một tài liệu đúng chủ đề vẫn có thể trả về sai section; metadata filter giúp tăng precision nhưng có thể giảm recall nếu gán `audience` quá cứng.

---

## Tự Đánh Giá (Phần Cá Nhân)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Khởi động (Warm-up) | 5 / 5 |
| Hướng tiếp cận của tôi (My Approach) | 10 / 10 |
| Hoàn thiện code (Core Implementation — tests) | 30 / 30 |
| Dự đoán độ tương tự (Similarity Predictions) | 5 / 5 |
| Kết quả truy xuất của tôi (Competition Results) | 7 / 10 |
| **Tổng phần cá nhân** | **57 / 60** |
