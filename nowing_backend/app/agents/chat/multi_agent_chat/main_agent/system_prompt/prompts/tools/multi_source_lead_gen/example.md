<example>
user: "Tôi muốn bán SaaS HR cho công ty logistics tại Hà Nội"
→ Ask 1-2 discovery questions, then run smoke test:
multi_source_lead_gen(
  query="công ty logistics tại Hà Nội",
  locations=["Hà Nội"],
  intent="sell",
  product_type="SaaS HR",
  price_segment="mid-market",
  target_sources=["masothue", "mua_sam_cong"],
  smoke_test=true,
  limit=5
)
tool returns: a markdown table with 4-5 logistics companies
(Reply: "Tìm thấy 5 công ty logistics Hà Nội phù hợp mid-market. Duyệt chạy 50 leads đầy đủ gồm email/SĐT và lưu vào bảng không?")
</example>

<example>
user: "Find 10 real estate companies in Hanoi"
→ multi_source_lead_gen(
  query="công ty bất động sản tại Hà Nội",
  locations=["Hà Nội"],
  intent="sell",
  product_type="BĐS",
  target_sources=["batdongsan", "masothue"],
  enrichment_depth="standard",
  limit=10,
  preferred_channels=["phone", "zalo"]
)
tool returns: a markdown table with 10 real estate leads
(Reply: "Tìm thấy 10 công ty BĐS Hà Nội. Bạn muốn mở khóa số điện thoại, gửi Zalo hàng loạt hay xuất bảng?")
</example>

<example>
user: "Tuyển Senior Python Developer ở TP.HCM"
→ multi_source_lead_gen(
  query="công ty tuyển Senior Python Developer tại TP.HCM",
  locations=["TP.HCM"],
  intent="hire",
  product_type="recruitment",
  target_sources=["topcv", "itviec"],
  target_keywords=["Python", "Senior"],
  negative_keywords=["intern", "freshers"],
  limit=20
)
tool returns: a markdown table with companies and job postings
(Reply: "Tìm thấy 18 công ty đang tuyển Senior Python. Bạn muốn lưu vào pipeline tuyển dụng và dự thảo tin nhắn tuyển không?")
</example>
