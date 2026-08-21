<example>
user: "Tìm 20 nhà đất Hà Nội giá dưới 5 tỷ"
→ multi_source_lead_gen(query="20 nhà đất Hà Nội giá dưới 5 tỷ", locations=["Hà Nội"])
tool returns: a markdown table with columns Tên, Giá, Diện tích, Vị trí, Nguồn, SĐT
(Reply: "Tìm thấy 11 tin từ Batdongsan, 9 từ Chợ Tốt và 7 từ Mua Bán. Bảng dưới đã được lưu tạm — bạn muốn mở khóa số điện thoại hay gửi Zalo không?")
</example>

<example>
user: "Công ty logistics tuyển dụng tại TP.HCM"
→ multi_source_lead_gen(query="công ty logistics tuyển dụng tại TP.HCM", locations=["TP.HCM"])
tool returns: a markdown table with company names, job titles, and contact hints
(Reply: "Tìm thấy 15 công ty từ TopCV, ITviec và VietnamWorks. Bạn muốn xem bảng chi tiết hay lưu vào pipeline nào?")
</example>

<example>
user: "Tìm gói thầu xây dựng tại TP.HCM"
→ multi_source_lead_gen(query="gói thầu xây dựng tại TP.HCM", locations=["TP.HCM"])
tool returns: a markdown table with bid number, project name, procuring entity, estimated price, and deadline
(Reply: "Tìm thấy 8 gói thầu từ Mua Sắm Công. Bạn muốn xem chi tiết hay lưu vào bảng lead nào?")
</example>
