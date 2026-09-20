# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** G99
**Thành viên:** Nguyễn Thị Thùy Dương, Lê Công Tâm, Nguyễn Thành Tiến
**Ngày:** 20-09-2026

> **Nộp 1 bản / nhóm.** Phần cá nhân (hướng tiếp cận, kết quả riêng, dự đoán…) mỗi thành viên nộp riêng trong `REPORT_CANHAN.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề (Domain) & Lý Do Chọn

**Chủ đề:** [ví dụ: Customer support FAQ, Luật Việt Nam, công thức nấu ăn, ...]

**Tại sao nhóm chọn chủ đề này?**
> *Viết 2-3 câu:*

### Danh sách tài liệu (Data Inventory)

**Chủ đề:** Chính sách đổi trả & hoàn tiền trên sàn thương mại điện tử (e-commerce return/refund policies)

**Lý do chọn chủ đề:** Đây là chủ đề có nhiều nguồn công khai, dễ kiểm chứng, và phù hợp với yêu cầu benchmark retrieval. Nội dung có nhiều điều kiện, ngoại lệ và quy trình xử lý khác nhau nên rất thuận lợi để so sánh hiệu quả của các chiến lược chunking và metadata filtering.

| # | Tên tài liệu | Nguồn (Source URL) | Ngày lấy / Phiên bản | Số ký tự | Metadata đã gán |
|---|--------------|------------|--------------------|----------|-----------------|
| 1 | Chính sách trả hàng và hoàn tiền (Shopee) | https://help.shopee.vn/portal/4/article/77251 | 2026-09-20 / 2026-09 | 19,873 | `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience`, `category`, `language` |
| 2 | Quy định chung về trả hàng/hoàn tiền (Shopee) | https://help.shopee.vn/portal/4/article/188931 | 2026-09-20 / 2026-09 | 6,578 | `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience`, `category`, `language` |
| 3 | Quy trình xử lý yêu cầu trả hàng/hoàn tiền (Shopee) | https://help.shopee.vn/portal/4/article/190242 | 2026-09-20 / 2026-09 | 8,379 | `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience`, `category`, `language` |
| 4 | Phương thức gửi hàng hoàn trả và phí hoàn trả (Shopee) | https://help.shopee.vn/portal/4/article/189477 | 2026-09-20 / 2026-09 | 6,205 | `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience`, `category`, `language` |
| 5 | Trả hàng và hoàn tiền (TikTok Shop) | https://seller-vn.tiktok.com/university/essay?course_type=1&from=search&identity=1&knowledge_id=1766935302801169&role=1 | 2026-09-20 / 2026-09 | 20,377 | `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience`, `category`, `language` |
| 6 | Điều khoản & điều kiện chương trình TikTok Shop Mall | https://seller-vn.tiktok.com/university/essay?knowledge_id=1220088829724418 | 2026-09-20 / 2026-09 | 24,835 | `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience`, `category`, `language` |
| 7 | Money Back Guarantee Policy (eBay) | https://www.ebay.com/help/policies/ebay/ebay?id=4210 | 2026-09-20 / 2026-09 | 36,117 | `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience`, `category`, `language` |
| 8 | Seller protection policy (eBay) | https://www.ebay.com/help/selling/seller-protection/seller-protection-policy?id=4763 | 2026-09-20 / 2026-09 | 6,514 | `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience`, `category`, `language` |
| 9 | Amazon Return Policy | https://digprjsurvey.amazon.com/csad/help/node/GKM69DUUYKQWKWX7 | 2026-09-20 / 2026-09 | 9,549 | `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience`, `category`, `language` |
| 10 | How to Return or Exchange an Item on Etsy | https://help.etsy.com/hc/en-us/articles/115015440807-How-to-Return-or-Exchange-an-Item-on-Etsy | 2026-09-20 / 2026-09 | 3,706 | `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience`, `category`, `language` |

**Danh sách kiểm tra quản trị dữ liệu (Data governance checklist):**
- [x] Tập tài liệu (Corpus) chỉ chứa nguồn công khai/được phép dùng và không chứa dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ.
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version` (hoặc ngày hiệu lực) trong metadata.
- [x] `audience` có ít nhất 2 giá trị khác nhau (`buyer`, `seller`) để hỗ trợ metadata filter, tránh trường hợp filter không có gì để lọc.

### Cấu trúc Metadata (Metadata Schema)

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho truy xuất (retrieval)? |
|----------------|------|---------------|-------------------------------|
| `doc_id` | string | `shopee-return-refund-policy` | Dùng để định danh file/tài liệu, liên kết 1-1 với `sources.csv`. |
| `title` | string | `Chính sách trả hàng và hoàn tiền` | Trợ giúp xác định nội dung và phục vụ review nhanh đối với từng tài liệu. |
| `source_url` | string | `https://help.shopee.vn/...` | Minh bạch nguồn, cho phép kiểm tra lại công khai và traceability. |
| `retrieved_at` | date | `2026-09-20` | Ghi lại thời điểm lấy dữ liệu để dễ theo dõi tính cập nhật. |
| `document_version` | string | `2026-09` | Dùng khi site sửa chính sách; giúp đánh giá tính mới của tài liệu. |
| `audience` | string | `buyer`, `seller` | Cho phép filter theo đối tượng người dùng, ví dụ lọc buyer-only hoặc seller-only. |
| `category` | string | `return-refund`, `marketplace-policy` | Phân loại nội dung để rút gọn không gian tìm kiếm và tăng độ chính xác. |
| `language` | string | `vi`, `en` | Hỗ trợ lọc theo ngôn ngữ, tránh nhầm lẫn khi cùng chủ đề nhưng khác ngôn ngữ. |

---

## 2. Thiết kế chiến lược (Strategy Design) — Nhóm (15 điểm)

> Mỗi thành viên thử **một chiến lược khác nhau** trên cùng bộ tài liệu; nhóm tổng hợp và so sánh ở đây.

### Phân tích đường cơ sở (Baseline Analysis)

Chạy `ChunkingStrategyComparator().compare()` trên 2-3 tài liệu:

| Tài liệu | Chiến lược (Strategy) | Số lượng Chunk | Độ dài trung bình | Giữ được ngữ cảnh không? |
|-----------|----------|-------------|------------|-------------------|
| `shopee-return-refund-policy.md` | FixedSizeChunker (`fixed_size`) | 34 | 584.12 | Độ dài đều nhưng có thể cắt giữa điều khoản |
| `shopee-return-refund-policy.md` | SentenceChunker (`by_sentences`) | 43 | 459.09 | Khá, giữ ranh giới câu |
| `shopee-return-refund-policy.md` | RecursiveChunker (`recursive`) | 51 | 386.69 | Tốt hơn ở đoạn dài, nhưng có thể nhiều chunk |
| `tiktok-return-refund.md` | FixedSizeChunker (`fixed_size`) | 34 | 599.00 | Dễ cắt rời hướng dẫn bằng chứng |
| `tiktok-return-refund.md` | SentenceChunker (`by_sentences`) | 37 | 548.16 | Giữ câu nhưng có thể tách các ý liên quan |
| `tiktok-return-refund.md` | RecursiveChunker (`recursive`) | 44 | 460.98 | Giữ cấu trúc đoạn tốt hơn |

### Chiến lược của từng thành viên

> Mỗi thành viên điền một khối dưới đây (copy thêm nếu nhóm có nhiều hơn 3 người).

**Thành viên 1 — [Tên]**
- **Loại chiến lược:** Chưa cập nhật
- **Mô tả & lý do chọn cho chủ đề này:** Bổ sung sau khi thành viên chạy benchmark riêng.
- **Code snippet (nếu custom):**
```python
# Dán mã nguồn (implementation) vào đây
```

**Thành viên 2 — Nguyễn Thanh Tiến**
- **Loại chiến lược:** `HeadingChunker` custom, `chunk_size=600`
- **Mô tả & lý do chọn:** Chính sách được tổ chức theo tiêu đề và mục điều khoản, nên giữ heading trong chunk giúp bảo toàn ngữ cảnh. Nếu section dài, chunker tiếp tục chia theo câu rồi recursive split.
- **Code snippet (nếu custom):**

**Thành viên 3 — [Bổ sung nếu có]**
- **Loại chiến lược:** Chưa cập nhật
- **Mô tả & lý do chọn:** Bổ sung sau khi có file benchmark của thành viên.
- **Code snippet (nếu custom):**

### So Sánh Giữa Các Thành Viên

| Thành viên | Chiến lược (Strategy) | Điểm truy xuất (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Nguyễn Thanh Tiến | `HeadingChunker`, `chunk_size=600` | 7/10 | Giữ heading và truy xuất tốt Q1-Q3 | Q4/Q5 bị tách bằng chứng giữa các chunk |
| Thành viên khác | Chưa có dữ liệu | — | Chờ benchmark để so sánh | Chưa đánh giá |

**Kết quả thành viên hiện tại:** chiến lược `heading`, local multilingual embedding, `chunk_size=600`, đạt **7/10**. Chưa có log của các thành viên khác nên bảng trên cần được bổ sung khi nhóm chạy các cấu hình còn lại; không dùng kết quả này để đại diện cho cả nhóm.

**Chiến lược nào tốt nhất cho chủ đề này? Tại sao?**
> Với kết quả hiện có, `HeadingChunker` phù hợp vì giữ được tiêu đề và giúp giải thích nguồn. Tuy nhiên cần overlap hoặc section lớn hơn cho các câu hỏi yêu cầu nhiều chi tiết trong cùng câu trả lời. Chưa thể kết luận chiến lược tốt nhất của cả nhóm trước khi có log của các thành viên còn lại.

---

## 3. Câu hỏi đánh giá & Chất lượng truy xuất (Retrieval Quality) — Nhóm (10 điểm)

### Câu hỏi đánh giá & Câu trả lời chuẩn (nhóm thống nhất)

> **Đúng 5 câu hỏi**, đa dạng, có thể kiểm chứng; **ít nhất 1 câu** cần lọc metadata mới trả lời tốt. Đây là bộ câu hỏi chung cho mọi thành viên chạy.

| # | Câu hỏi (Query) | Câu trả lời chuẩn (Gold Answer) | Chunk nào chứa thông tin? |
|---|-------|-------------------------------|--------------------------|
| 1 | Người mua có thể gửi yêu cầu trả hàng/hoàn tiền trong bao nhiêu ngày? | 15 ngày kể từ khi giao hàng thành công. | `shopee-return-regulation` |
| 2 | Người bán Shopee phải phản hồi trong bao lâu? | 02 ngày lịch kể từ khi nhận thông báo. | `shopee-return-refund-policy` |
| 3 | Người bán TikTok có thể gửi khiếu nại trong bao nhiêu ngày? | 7 ngày với hàng nhận qua bưu cục/lấy hàng; 15 ngày với trả hàng tự sắp xếp. | `tiktok-return-refund` |
| 4 | Người bán TikTok cần bằng chứng gì khi mở kiện hàng trả về? | Video liên tục, thông tin đơn, tất cả 6 mặt kiện hàng và quá trình mở. | `tiktok-return-refund` |
| 5 | Mã giảm giá Shopee được hoàn lại trong bao lâu? | 48 giờ, không kể cuối tuần và ngày lễ. | `shopee-return-regulation` |

### Tổng hợp chất lượng truy xuất của nhóm

> Cách chấm (theo `docs/SCORING.md`): **2 điểm/câu** — top-3 chứa chunk liên quan + agent trả lời đúng (2), có liên quan nhưng thiếu/không ở top-1 (1), không có trong top-3 (0).

| # | Câu hỏi | Chiến lược tốt nhất cho câu này | Có chunk liên quan trong top-3? | Ghi chú |
|---|---------|-------------------------------|-------------------------------|---------|
| 1 | Thời hạn trả hàng của người mua | HeadingChunker | Có, Top-1 | Filter buyer đưa Shopee lên Top-1; 2/2 điểm |
| 2 | Thời hạn phản hồi của người bán Shopee | HeadingChunker | Có, Top-1 | Chunk chứa `02 ngày`; 2/2 điểm |
| 3 | Thời hạn khiếu nại của người bán TikTok | HeadingChunker | Có, Top-1 | Chunk chứa `15 ngày`; 2/2 điểm |
| 4 | Bằng chứng video mở kiện hàng | HeadingChunker | Không hoàn chỉnh | Đúng tài liệu nhưng thiếu `6 mặt` trong cùng chunk; 0 điểm |
| 5 | Thời gian hoàn mã giảm giá | HeadingChunker | Không hoàn chỉnh | Gold document có mặt nhưng thiếu `48 giờ` cùng `Mã giảm giá`; 0 điểm |

**Lọc bằng metadata có giúp ích không? Ở câu hỏi nào?**
> Filter có ích rõ nhất ở Q1: khi lọc `audience=buyer`, Top-1 là tài liệu Shopee chứa đáp án; không filter thì Top-3 bị chiếm bởi các chunk TikTok cùng chủ đề nhưng không phải nguồn gold. Q3 không thay đổi Top-3 giữa hai chế độ, nên đây là câu hỏi chưa thực sự cần filter.

---

## 4. Thuyết trình (Demo) & Bài học nhóm — Nhóm (5 điểm)

**Những phân tích (insights) hay nhất nhóm sẽ trình bày:**
1. Không thể chỉ kiểm tra `doc_id`; phải kiểm tra chunk có chứa bằng chứng trả lời hay không.
2. Local multilingual embedding có ý nghĩa semantic, còn `MockEmbedder` chỉ phù hợp test cấu trúc và không dùng để kết luận retrieval quality.
3. Filter làm tăng precision nhưng có thể giảm recall nếu metadata `audience` gán quá cứng.

**Bài học rút ra khi so sánh trong nhóm:**
> Cùng corpus nhưng chunk boundary khác nhau làm thay đổi việc một đáp án có nằm trọn trong Top-3 hay không. Heading giữ ngữ cảnh tốt cho điều khoản, còn sentence/recursive có thể tạo nhiều chunk nhỏ hơn; cần dùng cùng backend và cùng query để so sánh công bằng.

**Nếu làm lại, nhóm sẽ thay đổi gì trong chiến lược dữ liệu (data strategy)?**
Sẽ bổ sung overlap hoặc giữ nguyên các khối hướng dẫn bằng chứng có liên quan trong cùng section. Với Q4, việc giữ `video mở kiện hàng` cùng chi tiết `6 mặt` sẽ giúp chunk vừa đúng tài liệu vừa trả lời đủ câu hỏi. Nhóm cũng cần tiếp tục kiểm tra A/B để tránh filter `audience` loại nhầm nguồn cần thiết.

### Failure case bắt buộc

Q4 là failure case thực: Top-3 có `tiktok-return-refund`, nhưng không chunk nào đồng thời chứa đủ các từ khóa `video mở kiện hàng`, `6 mặt` và `kiện hàng`. Nguyên nhân là thông tin bằng chứng bị tách theo section/chunk; cosine similarity ưu tiên chủ đề TikTok/đổi trả chứ không đảm bảo mật độ chi tiết trả lời. Đề xuất là dùng overlap hoặc chunk theo section lớn hơn, sau đó chạy lại benchmark để kiểm tra answer chunk.

---

## Tự Đánh Giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu (Document Set Quality) | / 10 |
| Thiết kế chiến lược (Strategy Design) | / 15 |
| Chất lượng truy xuất (Retrieval Quality) | / 10 |
| Thuyết trình (Demo) | / 5 |
| **Tổng phần nhóm** | **/ 40** |
