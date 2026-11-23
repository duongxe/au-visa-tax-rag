# Deploy lên AWS (Giai đoạn 7)

Ứng dụng chạy trên **Amazon ECS Express Mode**: 2 service Fargate (API + giao diện Streamlit) dùng chung 1 load balancer HTTPS do AWS tự tạo.

Ban đầu kế hoạch là dùng **AWS App Runner**, nhưng App Runner đã ngừng nhận khách hàng mới từ 30/4/2026 ([thông báo của AWS](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html)). AWS khuyên chuyển sang ECS Express Mode. Express Mode còn có một điểm hơn App Runner: load balancer của nó hỗ trợ WebSocket, nên Streamlit chạy được trên cùng hạ tầng.

Image được build trên GitHub Actions, nên máy bạn không cần cài Docker hay AWS CLI. Workflow lấy quyền AWS qua OIDC (chỉ cấp quyền tạm thời), nên GitHub không phải lưu access key nào.

```
GitHub Actions ──build──▶ ECR (image api-<sha>, ui-<sha>)
      │                      │
      └─cloudformation deploy▼
   au-visa-tax-rag-service:  ALB HTTPS ─┬─▶ UI  (Fargate 0.25 vCPU / 0.5 GB, Streamlit)
                                        └─▶ API (Fargate 1 vCPU / 4 GB, FastAPI + bge-m3)
                                                 └─ đọc key LLM từ Secrets Manager
```

| File | Vai trò |
|---|---|
| [bootstrap.yml](bootstrap.yml) | Tạo 1 lần. Gồm ECR, S3 (chứa index), secret chứa key LLM, các IAM role, budget cảnh báo chi phí. Phần này **không tính tiền theo giờ**. |
| [service.yml](service.yml) | Phần chạy app: API + UI + load balancer. Phần này **tính tiền theo giờ**. Workflow tạo ra khi deploy và xoá đi khi destroy. |
| [../.github/workflows/deploy-aws.yml](../.github/workflows/deploy-aws.yml) | `deploy`: build image, push lên ECR rồi tạo hoặc cập nhật service. `destroy`: xoá service để ngừng tính tiền. |

## Chi phí (ước tính, us-east-1)

| Thành phần | $/giờ | $/tháng nếu chạy 24/7 |
|---|---|---|
| API Fargate 1 vCPU / 4 GB | 0.058 | ~42 |
| UI Fargate 0.25 vCPU / 0.5 GB | 0.012 | ~9 |
| Application Load Balancer | ~0.03 | ~22 |
| IPv4 công khai (ALB + 2 task, $0.005/IP) | ~0.02 | ~15 |
| Secrets Manager, ECR (~4 GB), S3, log | — | ~1 |
| **Tổng** | **~0.12** | **~$85–90** |

Với $100 credit, chạy 24/7 chỉ được khoảng 1 tháng. Nên:
- Chỉ bật khi cần demo (khi quay video hoặc chụp ảnh cho LinkedIn). Demo xong chạy workflow với action **destroy**. Bật lại bằng **deploy**, mất khoảng 10–15 phút.
- Stack bootstrap tạo sẵn budget **$30/tháng**. AWS gửi email khi chi phí thực vượt 50% hoặc 100% mức này, hoặc khi dự báo vượt 100%. Budget **không trừ credit**, nên vẫn cảnh báo khi app đang tiêu vào credit.
- Bản cloud **không dùng reranker** (`WITH_RERANKER=0`, `RETRIEVAL_MODE=hybrid`). Nếu dùng reranker thì cần 2 vCPU / 8 GB, tức gấp khoảng 2 lần tiền Fargate, và CPU sẽ chậm thêm khoảng 20–40 giây mỗi câu hỏi. Theo đánh giá ở Giai đoạn 5, chế độ `hybrid` vẫn có hit@5 = 42/42.
- API giới hạn **200 câu/ngày và 6 câu/phút** (`MAX_ASKS_PER_DAY`, `MAX_ASKS_PER_MINUTE`), để người lạ không dùng hết quota LLM miễn phí của bạn.
- Mỗi service chỉ chạy đúng 1 task (`MinTaskCount = MaxTaskCount = 1`). App không tự scale, nên hoá đơn không thể tăng vọt.

## Cài đặt lần đầu (~20 phút, làm trên trình duyệt)

1. **Chọn region.** Template mặc định dùng `us-east-1`, vì đây là region rẻ nhất. Nếu muốn dùng `ap-southeast-2` (Sydney), đắt hơn khoảng 20%, hãy chọn region đó ở góc phải trên của AWS Console và đặt biến `AWS_REGION` ở bước 5 cho khớp.
2. **Tạo stack bootstrap.** Vào CloudFormation › *Create stack* › *With new resources* › *Upload a template file* › chọn `deploy/bootstrap.yml`.
   - Stack name: **`au-visa-tax-rag-bootstrap`**. Phải đúng tên này, vì workflow tìm stack theo tên.
   - `BudgetEmail`: email nhận cảnh báo chi phí.
   - `CreateGitHubOidcProvider`: để `true`. Chỉ đổi thành `false` nếu tài khoản đã có identity provider `token.actions.githubusercontent.com` (xem ở IAM › Identity providers).
   - Tick ô *I acknowledge that AWS CloudFormation might create IAM resources*, rồi bấm *Submit*. Đợi đến khi trạng thái là `CREATE_COMPLETE`.
   - Mở tab **Outputs** để lấy giá trị dùng ở các bước sau.
3. **Điền key LLM.** Vào Secrets Manager › `au-visa-tax-rag/app` › *Retrieve secret value* › *Edit* › chọn *Plaintext*, rồi dán JSON có dạng như sau (chỉ cần các key bạn có):
   ```json
   {"GEMINI_API_KEY": "...", "GROQ_API_KEY": "...", "MISTRAL_API_KEY": "...", "OPENROUTER_API_KEY": "..."}
   ```
   Key chỉ nằm trong Secrets Manager. Nó không vào image, không vào GitHub, và không hiện trong log. Đổi key thì sửa secret, rồi chạy lại workflow `deploy` để task mới đọc giá trị mới.
4. **Upload index.** Vào S3 › bucket có tên trong output `IndexBucket` › *Create folder* tên `index` › mở folder đó › *Upload* 3 file `data/index/faiss.index`, `chunks.jsonl`, `meta.json` (tổng khoảng 35 MB). Sau mỗi lần build lại index, nhớ upload lại.
5. **Cấu hình GitHub.** Vào repo › *Settings* › *Secrets and variables* › *Actions* › tab **Variables** › *New repository variable*, rồi tạo:
   - `AWS_DEPLOY_ROLE_ARN` = output `GitHubDeployRoleArn`. Đây là ARN, không phải thông tin bí mật.
   - `AWS_REGION` = region đã chọn ở bước 1. Bỏ qua nếu dùng `us-east-1`.
6. **Deploy.** Vào *Actions* › **Deploy to AWS** › *Run workflow* › chọn `deploy`. Lần đầu mất khoảng 20–25 phút: build image khoảng 10 phút, tạo load balancer và chứng chỉ khoảng 10 phút. Khi xong, URL của UI và API hiện trong phần *Summary* của lần chạy, và trong tab Outputs của stack `au-visa-tax-rag-service`.

## Hằng ngày

| Muốn | Làm |
|---|---|
| Cập nhật code | Push lên `main`, rồi chạy *Deploy to AWS* › `deploy`. ECS thay task cũ bằng task mới, không có downtime. |
| Ngừng tính tiền | Chạy *Deploy to AWS* › `destroy`. Lệnh này xoá service và load balancer; phần bootstrap vẫn giữ nguyên. |
| Xem log | CloudWatch › Log groups › nhóm log của service `au-visa-tax-rag-api`. |
| Xoá hết | Chạy `destroy`, rồi xoá stack `au-visa-tax-rag-bootstrap`. Bucket S3 được giữ lại (`Retain`) để không mất index; nếu muốn thì xoá tay. |

## Khi deploy lỗi

- **Stack ở trạng thái `ROLLBACK_COMPLETE`:** stack không cập nhật được nữa. Chạy `destroy` rồi chạy lại `deploy`. Lý do lỗi nằm trong bước *Show URLs* của workflow, hoặc trong tab Events của stack.
- **Task khởi động rồi bị dừng liên tục:** xem log của API. Thường do thiếu RAM (`MemoryError` / exit code 137), cách sửa là tăng tham số `ApiMemory` lên 6144. Lỗi cũng có thể do JSON trong secret sai cú pháp; khi đó log có dòng `APP_SECRETS is not valid JSON`.
- **`/health` báo `llm_chain: []`:** secret còn rỗng `{}`, hoặc task chưa được deploy lại sau khi sửa secret.
- **Lỗi 504 sau khoảng 60 giây:** load balancer cắt request im lặng quá 60 giây. API đã giới hạn mỗi lần gọi LLM ở 20 giây và mỗi chuỗi dự phòng ở 25 giây, nên lỗi này hiếm gặp (xem KNOWN_ISSUES 10c).
