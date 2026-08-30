# T-Designer Lite — FBD Logic Editor (prototype)

Bản mô phỏng thu nhỏ nguyên lý của T-Designer: vẽ logic điều khiển bằng
**function block**, nối dây, gán tag, **sinh mã `.DEF`**, **mô phỏng** chạy thử,
và **đọc lại logic** từ các file `.db` của dự án.

> Công cụ minh họa/giáo dục. KHÔNG nạp chương trình xuống PLC/CPU thật
> và KHÔNG thay thế phần mềm T-Designer gốc.

---

## 1. Cài đặt

Cần **Python 3.8+**. Mở CMD/PowerShell trong thư mục này rồi chạy:

```
pip install PySide6
```

## 2. Chạy

```
python main.py
```

## 3. Thư viện khối — ĐÃ NẠP ĐẦY ĐỦ

Bản này đã nạp **toàn bộ 986 khối hàm thật** trích từ dự án của bạn
(`DEF/SR21E/macro_master.csv`) + 9 khối cơ bản = **995 khối**.

Cột trái có **ô tìm kiếm** (gõ tên, mô tả hoặc mã hex như `8204`) và cây
**phân nhóm** theo loại:

- Co ban (Primitive): DI, DO, AND, OR, NOT, XOR, FF, TON, MOVE
- Logic · Toan hoc (Math) · Timer/Counter · Du lieu (Data/Move)
- Chon/Nut nhan (Selector/PB) · Van/Dong co (Valve/Motor) · Canh bao (Alarm)
- Chuyen doi (Converter) · Vao/Ra (I/O) · Tuan tu (Sequence) · Khac

Ví dụ: gõ `mov2` sẽ thấy **MOV2-NSH (mã 8204, 14 vào / 4 ra)**.

Tra cứu ngoài app: mở file **`DanhMuc_986_Khoi.csv`** (mở bằng Excel).

## 4. Thao tác

1. **Thêm khối:** bấm đúp khối trong cây bên trái. DI/DO hỏi tag, TON hỏi preset.
2. **Nối dây:** bấm **cổng RA** (phải) rồi **cổng VÀO** (trái). Mỗi cổng vào 1 dây.
3. **Di chuyển / Xóa:** kéo khối; chọn rồi nhấn **Delete**.
4. **Sinh `.DEF`:** nút **Sinh .DEF** → panel dưới.
5. **Mô phỏng:** nút **Mo phong**, bấm khối **DI** để bật/tắt; khối/dây mức 1 xanh.
6. **Lưu/Mở:** file `.tdl` (JSON).

## 5. Đọc lại logic

- **Import DB** → chọn 1 file `.db` của dự án, dựng lại sheet đúng như bản vẽ gốc.
- **Import folder** → nạp cả thư mục `.db`, gom theo Project/CPU.

> Nút **Import PDF** đã bỏ: bản đóng gói không kèm thư viện đọc PDF nên nút luôn
> báo lỗi, và trên bản vẽ thật nó chỉ trích ra text phẳng đã mất hết toạ độ khối.
> Đọc từ `.db` cho ra sơ đồ dùng được, nên đó là đường duy nhất còn lại.

## 6. Mức độ mô phỏng & sinh mã

- **9 khối cơ bản**: mô phỏng logic ĐÚNG (AND/OR/NOT/XOR/FF/TON/MOVE...) và
  sinh Instruction List chuẩn (`A / OR / XOR / OUT / SET / CL / TON`).
- **986 khối macro thật**: hiển thị đúng SỐ chân vào/ra và tên; khi mô phỏng
  coi là "hộp đen" (mỗi ngõ ra = OR các ngõ vào) vì logic nội bộ là độc quyền
  của Toshiba. Khi sinh mã tạo khung gọi khối:

  ```
  ; ==== MOV2-NSH (macro M2NSH_TG, code 8204) ====
  .MCR    MOV2-NSH    8204    IN=(...)
  OUT     Dw001
  ...
  .MCREND
  ```

## 7. Cấu trúc mã nguồn

```
T_Designer_Lite/
├─ main.py
├─ DanhMuc_986_Khoi.csv        # danh mục toàn bộ khối (mo bang Excel)
├─ core/
│  ├─ model.py                 # Block/Circuit + Simulator + DefGenerator
│  └─ macro_catalog.json       # 986 khối trích từ dự án gốc
└─ ui/
   ├─ canvas.py                # BlockItem/WireItem/LogicScene (kéo-thả)
   └─ app.py                   # cửa sổ chính + palette tìm kiếm
```

## 8. Đọc file DB dự án + hiển thị kiểu báo cáo 7 cột

Nút **Import DB** mở file `.db` (SQLite) → chọn sheet → dựng lại theo bố cục gốc:

```
Line Name | From | LID | Logic Chart | LID | To | Line Name
```

- **Terminal hai mép** với 3 cột con; **đường kẻ dọc + tiêu đề cột**.
- **Tên tín hiệu (Line Name)** giải mã CHÍNH XÁC qua `CAD_DATA`:
  tag `HA035AG-11` → PA=HA, sheet=035AG → sheet 867, sig 11 →
  `CAD_ID[867,11]` = "PULV A PAFL CTRL AUTO CTRL CMD".
- **From/To** = LOOPNO+SHEETNO của sheet nguồn/đích (vd 16712, 16742) — khớp bản gốc.
- **Khối logic ở giữa**, **dây vuông góc**.

## 9. Thông tin & TÊN CHÂN thật của khối (từ manual Toshiba)

Từ 2 manual (`VP1-...-00018` TAG Macro, `VP1-...-00019` Macro) tôi trích được
`core/macro_manual.json` (315 khối có giải thích; 255 khối có **danh sách chân**).

- **Palette + canvas hiển thị tên chân thật** thay vì I1..In/O1. Ví dụ:
  - **MV-FF (8210)**: 17 vào (Auto, Manual, DLT MV, OR-R-MV1, OR-R-MV2, Hold,
    OR-MV1, OR-MV2, HL-MV, LL-MV, MV, REF1, REF2, REF3, FF, CTL-ABN, DRV-ABN)
    / 5 ra (In F-OP1, In F-OP2, Auto, MV, ABN).
  - **MOV2-NSH (8204)**: 14 vào / 4 ra (Auto, Manual, Auto OP, F-OP…).
- Khi **Import DB**, khối logic (MV, MOV…) được vẽ đúng số chân + tên theo manual,
  map PINNO của DB vào đúng chân.
- **Bấm 1 khối** → dock "Thông tin khối" hiện mã, chân vào/ra, mô tả và giải thích.

Khối chưa có trong manual (hoặc parse tên chân chưa đủ) vẫn hiển thị theo số chân
thực tế trong DB (nhãn I1..In) — không bị mất chân.

## 10. Hiển thị TAG (KKS) trên khối — như UCS.pdf

Khi **Import DB**, các khối loại TAG (van MOV, MV Station, DI/AI có cảnh báo…)
hiện **mã tag thiết bị (KKS)** + mô tả **phía trên khối** (chữ đỏ), đọc từ
`CAD_TAG_FID` (FIDSUFFIX = `Ttag` / `TID` / `TDes1`). Ví dụ khối MV:

```
10HFE61EZ001
PULV A PAFL CTRL
   ┌──────┐
   │  MV  │
   └──────┘
```

Bấm vào khối → dock "Thông tin khối" hiện thêm **Tag (KKS), Tag ID, Mô tả tag**.

Lưu ý: chỉ khối **loại TAG** mới có tag thiết bị (đúng như file gốc); các khối
số học/logic (A, Tb, AND, OR…) không có tag — điều này khớp với UCS.db và UCS.pdf.
Trong DB này có **1.244 khối TAG đã gán KKS**; phần gán I/O vật lý
(module/kênh) thì file chưa có.

## 11. Sửa lỗi kết nối & terminal (quan trọng)

Đã sửa lỗi gốc: net của terminal lấy nhầm từ `CAD_LIN` (bảng này KHÔNG map
theo block_id) → giờ lấy đúng từ **chân khối (`CAD_BLOCK_PIN`)**. Kết quả:

- **Terminal đầu vào hiện đúng tên + From + LID** (trước bị trống hoặc hiện net
  nội bộ a1/a2…). Đối chiếu UCS.pdf: khớp từng dòng (vd sheet 620 = trang 1010).
- **Fanout 1 → nhiều**: một chân ra nối tới nhiều điểm (vd tín hiệu HA212-18 vào
  3 khối). Mô hình nối theo net (SIGNALID): 1 nguồn → tất cả các chân đọc net đó.
- Áp dụng cho mọi sheet (869 giờ 15/15 terminal có tên).

## 12. Bộ XEM SHEET TRUNG THỰC (geometry gốc — MỚI)

Khi **Import DB**, app giờ dùng bộ vẽ mới (`core/sheet_render.py` +
`ui/sheetview.py`) tái dựng sheet **đúng như UCS.pdf**, lấy đầy đủ:

- **Khối** đặt đúng toạ độ gốc, kèm: **số thực thi (đỏ, EXEORDER)**,
  **nhãn góc** (35-103, A-2…), **tham số dưới khối** (A= 50, degC, R12=99999…),
  **tag KKS + mô tả** phía trên.
- **Dây nối vẽ ĐÚNG TOẠ ĐỘ GỐC** từ `CAD_LIN_DETAIL` (mỗi net có thể có
  nhiều nhánh — fanout 1→nhiều), kèm **tên net (a0, a1…)** trên dây.
- **Terminal 2 mép** dạng 7 cột: Line Name / From / LID │ Logic │ LID / To / Line Name.
- **Tên chân theo instance** (ISTD/OSTD) khi có, thay tên chung của manual.
- **Chữ chú thích** (CAD_TEXT) và **khung tên** (PA-sheet, tiêu đề, mã bản vẽ).

Dữ liệu lấy đúng theo tài liệu **`CAU_TRUC_UCS_DB.md`** (ánh xạ đầy đủ 25 bảng).

Đây là chế độ **xem** (không sửa). Bấm "Moi"/"Mo" để về chế độ soạn thảo.

## 13. Click terminal → NHẢY sheet liên kết (như DCS — MỚI)

Sau khi Import DB và xem 1 sheet, các **terminal có chữ MÀU XANH** (cột From/To,
LID) là điểm có liên kết chéo. **Bấm vào** → app mở thẳng sheet nguồn/đích:

- **Đầu vào (trái)** → nhảy tới **sheet nguồn** (nơi tín hiệu được tạo ra),
  giải mã từ LID qua `CAD_DATA` (vd `HAI21D-11` → sheet 1661).
- **Đầu ra (phải)** → nhảy tới **sheet đích** qua `CAD_ID_CRS`. Nếu đi tới **nhiều
  sheet**, cột To hiện **TẤT CẢ số trang đích xếp chồng** (như PDF, vd 13515 /
  13569 / 22045 / 21306); bấm vào sẽ hiện **danh sách để chọn** sheet cần mở.
- Nút **`< Back`** trên thanh công cụ để quay lại sheet trước (có lịch sử).

Đây chính là cơ chế "double-click tín hiệu để nhảy" của T-Designer/DCS, dựng
đúng theo cấu trúc DB (LID + `CAD_DATA` + `CAD_ID_CRS`).

## 14. Zoom màn hình logic (MỚI)

- **Lăn chuột** = phóng to / thu nhỏ (zoom vào vị trí con trỏ).
- **Giữ chuột GIỮA + kéo** = di chuyển (pan) khắp sơ đồ.
- Nút **Zoom +**, **Zoom -**, **Fit** (vừa màn hình), **100%** trên thanh công cụ.
- Click trái vẫn dùng để nối dây (editor) / nhảy sheet (xem DB).
- Khi Import DB, app tự động **Fit** để thấy trọn sheet.

## 15. Sửa bố trí khối (số/tên chân) — đã kiểm TOÀN BỘ khối

Tên & số chân của khối lấy TỪ MANUAL Toshiba (khớp UCS.pdf). Ví dụ SV (820C):
8 vào (Auto, Manual, Auto SV, OR-R-SV, OR SV, HL-SV, LL-SV, PV) + 2 ra (Auto, SV).

Đã bỏ dùng ISTD/OSTD làm tên chân (dữ liệu này chỉ là mô tả tag lặp lại, vd
"LO REG LM", và nhiều mục hơn số chân thật → làm khối phình sai). Khối nào manual
chưa đủ chân thì vẽ theo ĐÚNG số chân thật trong DB (không tên).

**Audit toàn bộ:** đã đối chiếu 152 mã khối đang dùng — **100% vẽ đúng số chân**
theo DB. Tên chân chỉ hiện khi manual khớp chính xác tổng số chân (38 mã: SV, MV,
MOV, DDL, ADL…); khối logic/toán (AND/OR/MUL/DIF/timer) vẽ đúng số chân, không
gán tên (giống ký hiệu nhỏ trong PDF) để tránh tên sai.


## 16. Ban ve mo phong — nut **Internal logic** trên thanh công cụ

Bấm là **ra ngay bảng vẽ** để tự rắp sơ đồ và cho chạy thử. Bên trái có ba thẻ:

- **Ký hiệu** — 931 hình khối trong thư viện, nháy đúp để thêm. Mặc định lọc theo
  những ký hiệu thực sự có dùng trong DB dự án; bỏ tick để xem hết.
- **F(x)** — toàn bộ **4.290 khối hàm thật** của dự án, kèm tên mô tả, CPU, trang.
  Thả vào bản vẽ là **kèm đúng bảng gãy khúc của riêng khối đó**. Chỗ này quan trọng:
  4.290 khối F(x) đều chung mã `4035`, nên tên mã không nói lên được gì — phải kéo
  đúng bảng của đúng khối thì mô phỏng mới ra đúng số.
- **Khối chức năng** — 299 mã khối của các DB, kèm số khối / có hình manual chưa /
  đã mô phỏng được chưa / đã có bản vẽ chưa. Chọn một mã là chuyển sang bản vẽ nội bộ
  của mã đó. Tick *"chỉ mã CHƯA có mô hình"* + *"chỉ mã có hình manual"* để lọc ra
  đúng phần việc còn thiếu.

> Đo thực tế trên 21 DB thư viện: 299 mã / 192.389 khối chức năng (đã trừ `E0B1` là
> terminal, không phải khối tính), trong đó **132 mã / 28.206 khối chưa mô phỏng
> được, và 31 mã / 9.742 khối đã có hình sơ đồ nội bộ trong manual để chép lại.**

### Cài đặt khối F(x)

Mỗi khối F(x) mang **bảng gãy khúc của riêng nó** — không suy ra được từ mã khối (cả
4.290 khối đều là mã `4035`). Có ba cách cài:

1. **Thả từ thẻ F(x)** — kéo nguyên bảng của khối thật trong DB về.
2. **Nháy đúp vào khối** — mở bảng cài đặt: bấm **"Lấy bảng từ một khối F(x) thật
   trong dự án…"** để chép nguyên bảng của bất kỳ khối nào, hoặc gõ tay / dán từ Excel
   (mỗi dòng một cặp `x  y`). Có xem trước đồ thị ngay bên dưới.
3. **Thêm `FNG_I` từ thẻ Ký hiệu** — bảng cài đặt tự mở ngay lúc thả.

**Không có đường cong dựng sẵn** kiểu `y = x` hay căn bậc hai, và đó là chủ ý: một
bảng bịa ra vẫn cho ra số và sơ đồ vẫn chạy trơn tru, nên không còn dấu hiệu nào để
biết là đang mô phỏng nhầm đường cong. Bảng phải là bảng **thật** — chép từ một khối
F(x) của dự án, hoặc gõ/dán từ tài liệu.

Khối F(x) **chưa cài bảng** mang nhãn *"CHƯA CÀI BẢNG"* và khi chạy sẽ được báo riêng.
Không cho nó một đường cong mặc định là có chủ ý: khối rỗng trả `None`, kéo theo cả
nhánh phía sau cũng `None` — nhìn ra như sơ đồ ráp sai chứ không như thiếu dữ liệu.

Bảng luôn được **sắp theo X** và bỏ điểm trùng X trước khi dùng, đúng như
`core/sheet_sim.func_points` xử lý bảng đọc từ DB.

### Nối dây

Hai cách, dùng cách nào cũng được:

- **Kéo** — giữ chuột ở một chân, kéo sang chân kia rồi thả.
- **Bấm – bấm** — bấm một chân, cuộn màn hình thoải mái, rồi bấm chân thứ hai. Dùng khi
  hai khối ở xa nhau: kéo thì phải vừa giữ nút vừa cuộn. **Esc** hoặc bấm ra chỗ trống
  để bỏ.

Ba chỗ được nới cho dễ trúng:

- **Thả vào thân khối cũng được** — không cần ngắm trúng chấm tròn 4px. Máy tự chọn
  chân đúng chiều, ưu tiên chân **chưa có dây**, và trong số đó lấy chân gần con trỏ
  nhất theo chiều dọc.
- **Vùng bắt chân rộng hơn hình vẽ** — 22px khi bấm, 30px khi thả.
- **Không nối được sai chiều** — ra–ra hay vào–vào bị chặn ngay, và dòng nhắc việc nói
  rõ đang cần thả vào loại chân nào.

Một **ngõ vào chỉ nhận một nguồn**: nối chồng lên thì dây cũ bị thay, và câu nhắc việc
ghi rõ *"(thay dây cũ vào chân đó)"*. Trước đây hai dây cùng vào một chân thì dây nối
sau im lặng không có tác dụng.

### Chạy thử

1. **+ Node vào** / **+ Node ra** để tạo đầu vào, đầu ra (bản vẽ tự do không gắn với
   mã khối nào nên không có chân mặc định).
2. Thêm khối tính, hoặc thả một F(x) từ thẻ giữa.
3. Nối dây (xem trên).
4. **Nháy đúp node VÀO** để gõ giá trị — **đầu ra hiện ra ngay**, không phải bấm nút
   nào. Sơ đồ tự tính lại sau mỗi thay đổi: nối thêm dây, xóa khối, cài bảng F(x),
   đổi TI của khối tích phân.

Nút *"Tính logic nội (chạy sơ đồ)"* đã bỏ vì không còn việc gì để làm.

### Thanh công cụ — nút nào hiện lúc nào

Thanh trên cùng chỉ giữ nút **có việc để làm trên bản vẽ đang mở**. Nút xám hoặc nút
không bao giờ dùng vẫn chiếm chỗ, và còn làm người dùng tưởng mình thiếu bước nào đó
khi bấm vào mà không thấy gì xảy ra.

| Nút | Khi nào hiện |
|---|---|
| Xóa khối chọn (Del) · + Node vào · + Node ra · Xóa hết khối thêm · Nhập netlist… · Lưu | luôn |
| Đặt lại node vào/ra | chỉ khi mã khối **có bảng chân mặc định** — bản vẽ tự do không có bảng đó, nút chỉ còn mỗi tác dụng xóa sạch node |
| Tính giá trị (từ DB) | chỉ khi bản vẽ **gắn với một khối đang mở trên trang**; trước đây nút vẫn hiện nhưng luôn xám |
| dt · bước · Run (tích phân) | chỉ khi trên bản vẽ **thật sự có khối tích phân** (`F_INL1_I`…`F_INL4_I`) |
| Tính logic nội (chạy sơ đồ) | đã bỏ hẳn |

### Nơi lưu

| Loại bản vẽ | Lưu ở |
|---|---|
| Tự do (không thuộc mã nào) | `data/design/so_do_tu_do.json` — cạnh app, không bị bản cập nhật đè |
| Theo mã khối | `core/internal_design/<mã>.json` — đi kèm mã nguồn, dùng chung mọi dự án |

Khối F(x) được **chép hẳn bảng gãy khúc vào bản vẽ**, không lưu tham chiếu tới file
DB, nên bản vẽ mở lại được cả khi máy không còn file DB đó.
