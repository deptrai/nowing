# Memory

## Rủi ro đang mở (nhắc mỗi session cho tới khi đóng)

**Postgres production không có backup.** Xem `incidents.md` [I-07]. Chưa có backup định kỳ, chưa từng restore thử. Đây là thứ dễ mất nhiều nhất và dễ sửa nhất trên hạ tầng này. Không im lặng về nó.

**Không có staging.** nowing chỉ có env `production`, `autoDeploy=true` trên branch `production`. Mọi deploy là đi thật. Xem [I-08].

## Việc cần làm cùng owner

- Cấu hình backup Postgres + thử restore thật (ưu tiên cao nhất).
- Xác nhận `frontend` được deploy bằng cách nào: nó vừa khai `sourceType=github` (repo `deptrai/nowing`, branch `production`, path `/nowing_web`) vừa có `dockerImage=ghcr.io/deptrai/nowing-web:develop`. Hai nguồn khác nhau, và tag là `develop` chứ không phải `production`. Cần hỏi cho rõ trước khi deploy frontend lần đầu.
- Xin xác nhận về `NEXT_PUBLIC_*` của frontend — nếu chưa có ARG/ENV trong builder stage của Dockerfile thì mọi lần đổi URL sẽ không có tác dụng. Xem [I-02].

## Câu hỏi chưa có đáp án (hỏi khi có dịp tự nhiên)

- Ranh giới tự quyết: tôi được tự chạy deploy hay luôn phải hỏi trước? Được sửa env production hay chỉ đề xuất diff? **Chưa biết → mặc định hỏi trước mọi thao tác ghi.**
- Endpoint nào là bằng chứng "hệ thống còn sống"? Đoán `https://api.nowing.net/health` nhưng chưa xác nhận.
- Có cửa sổ nào tránh deploy không? Cần leo thang thì gọi ai?
- Sự cố cũ nào đã từng làm mất thời gian? (sổ sự cố hiện chỉ có bài học kế thừa, chưa có lịch sử thật của nowing)

## Quan sát về owner

- Owner nói tiếng Việt. Config để `communication_language: English` nhưng bằng chứng thực tế ngược lại → tôi dùng tiếng Việt, đã ghi vào BOND.
- Config không có `user_name`, nên BOND đang để `friend`. Cần biết tên gọi thật.
- Owner quan tâm tới việc làm đúng chuẩn và hoàn chỉnh, không thích thứ dựng lên rồi vỡ (chính vì bản devops cũ ship thiếu file mà tôi được dựng lại từ đầu).
