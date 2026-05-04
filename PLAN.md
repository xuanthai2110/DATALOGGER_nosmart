# Phương Án Refactor Quy Trình Polling Theo Batch Từng Project

## Tóm tắt
Thiết kế lại luồng xử lý theo nguyên tắc `project-scoped batch` thay vì `streaming từng inverter`. Với mỗi project, hệ thống phải:
1. Đọc hết toàn bộ inverter đang active của project.
2. Giữ kết quả trong bộ nhớ tạm của vòng poll hiện tại, chưa ghi ngay vào `CacheDB`.
3. Khi đã đọc xong toàn bộ inverter của project, mới commit đồng loạt dữ liệu AC/MPPT/String/Error vào cache cho project đó.
4. Sau khi cache batch của project đã hoàn tất, mới chạy tracking năng lượng, max tracking, string monitoring, mapping lỗi/history cho project đó.
5. Chỉ khi bước logic của project hoàn tất mới build telemetry cho project đó.
6. Persistence snapshot vẫn chỉ đọc cache đã commit; không được chen vào giữa một batch đang poll dở của cùng project.

Kết quả mong muốn: không còn trạng thái cache “nửa vòng cũ, nửa vòng mới” trong cùng một project; telemetry luôn được build từ một snapshot nhất quán theo project.

## Thay đổi triển khai chính
- Đổi `PollingService.poll_all_inverters(...)` từ kiểu “đọc xong inverter nào upsert cache ngay inverter đó” sang kiểu “thu thập toàn bộ raw/normalized/result cho cả project rồi trả về một `project poll batch`”.
- Tách rõ 3 pha trong xử lý project:
  - `Poll phase`: chỉ đọc thiết bị và chuẩn hóa dữ liệu thô.
  - `Commit phase`: ghi batch AC/MPPT/String/Error của toàn bộ inverter project vào cache trong một lần commit logic.
  - `Post-process phase`: chạy energy/monthly delta, max tracking, string fault state, fault history/state mapping trên dữ liệu cache đã hoàn tất.
- Chuyển fault/state mapping và string fault merge ra khỏi bước poll từng inverter nếu muốn giữ đúng thứ tự bạn yêu cầu. Poll phase chỉ thu raw state/fault + số đo; post-process phase mới tạo payload lỗi cuối cùng và ghi `error_cache`.
- `LogicWorker` không còn quét `get_all_ac_cache()` mỗi giây cho toàn hệ thống như hiện tại. Thay vào đó, nó cần xử lý theo `project_id` sau khi project đó vừa commit xong batch.
- `BuildTeleWorker` không chạy trên cache “đang có gì thì lấy nấy” cho project vừa đổi. Nó chỉ được trigger sau khi post-process của project hoàn tất. Có thể giữ periodic build dự phòng cho retry/rebuild, nhưng event-trigger phải bám theo batch-complete của project.
- `PersistenceWorker` cần đọc snapshot theo dữ liệu cache đã ổn định. Để tránh đụng giữa lúc commit batch project:
  - dùng một khóa ghi/đọc chung quanh cache commit và snapshot, hoặc
  - dùng cờ batch-in-progress theo project và bỏ qua project đang commit.
  - Khuyến nghị: khóa ngắn quanh bước commit batch + snapshot read để đơn giản và chắc chắn.
- Logging cần phản ánh đúng pha:
  - `Poll start/end project`
  - `Poll success inverter X/Y`
  - `Cache commit complete for project`
  - `Logic complete for project`
  - `Telemetry build complete for project`
  Như vậy nhìn log sẽ thấy đúng chuỗi “đọc đủ 5 inverter project 1 rồi mới lưu cache 5 inverter project 1”.

## API / interface nội bộ cần chốt
- Bổ sung một object nội bộ kiểu `ProjectPollBatch` chứa:
  - `project_id`
  - danh sách inverter active đã kỳ vọng
  - kết quả poll thành công/thất bại theo inverter
  - dữ liệu normalized AC/MPPT/String
  - raw state/fault dùng cho post-process
  - timestamp chung của batch hoặc timestamp theo inverter
- `PollingWorker` đổi từ flow hiện tại sang:
  - lấy config project
  - poll tạo `ProjectPollBatch`
  - commit batch vào cache cho project
  - gọi xử lý logic cho đúng `project_id`
  - gọi trigger build telemetry cho đúng `project_id`
  - rồi mới sang project tiếp theo
- `CacheDB` nên có nhóm thao tác batch cho project:
  - upsert AC/MPPT/String/Error theo danh sách
  - tùy chọn clear/replace dữ liệu MPPT/String cũ của các inverter thuộc batch trước khi ghi mới
- `LogicWorker` nên có entrypoint kiểu `process_project(project_id)` thay cho loop toàn cục quét toàn bộ cache liên tục.

## Test và kịch bản xác nhận
- Project 1 có 5 inverter, Project 2 có 8 inverter:
  - xác nhận project 1 poll đủ 5 inverter rồi mới có log cache commit project 1
  - chỉ sau đó mới chạy logic/build tele cho project 1
  - project 2 không bị ảnh hưởng bởi trạng thái dang dở của project 1
- Trong lúc poll inverter 4/5 của project 1, kiểm tra không có snapshot/telemetry nào dùng dữ liệu mới của inverter 1-3 kèm dữ liệu cũ của inverter 4-5 trong cùng project.
- Một inverter fail timeout:
  - batch vẫn hoàn tất cho project
  - cache commit chỉ chứa kết quả poll mới của inverter thành công và trạng thái lỗi/disconnect rõ ràng cho inverter fail theo policy đã chọn
  - build telemetry vẫn chạy sau batch-complete, không chạy giữa chừng
- Có meter trong project:
  - xác nhận meter không làm phá vỡ thứ tự batch của inverter
  - nếu giữ meter trong cùng chu kỳ project thì meter phải xử lý sau commit inverter hoặc trong một pha riêng nhưng trước build tele
- Snapshot interval trùng lúc project đang commit:
  - không đọc được nửa batch
  - record count và timestamp trong realtime DB phải nhất quán theo project
- Trigger do fault change:
  - chỉ bắn telemetry sau khi post-process của project xong
  - không còn trigger giữa lúc cache project chưa hoàn chỉnh

## Giả định và mặc định chốt
- Phạm vi chính là inverter flow; meter giữ nguyên hoặc xử lý trong cùng chu kỳ project nhưng không được phép làm build tele chạy sớm hơn batch inverter.
- Nếu một vài inverter trong project lỗi đọc, batch của project vẫn được “đóng” và commit như một vòng hoàn chỉnh của project; không chờ vô hạn.
- Telemetry event-trigger cho project là nguồn chính; periodic build vẫn có thể giữ để dự phòng/retry nhưng không được coi là nguồn dữ liệu thời gian thực chính.
- Snapshot nhất quán theo `project batch`, không cần chờ toàn hệ thống đọc xong tất cả project.
- Mục tiêu là nhất quán theo từng project đúng như ví dụ của bạn: project 1 có 5 inverter thì phải poll xong 5 inverter rồi mới cache 5 inverter, sau đó mới tracking/mapping lỗi, và build tele luôn là bước cuối.
