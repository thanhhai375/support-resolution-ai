import { useEffect, useMemo, useState } from "react";
import {
  LayoutDashboard, List, Plus, Library, BarChart3,
  Settings, Search, CircleHelp, Bell, ChevronDown, CalendarDays,
  FileText, Wrench, ArrowUpRight, AlertTriangle, Clock3,
  Menu, X, ChevronLeft, ChevronRight, MoreHorizontal,
  ShieldAlert, SlidersHorizontal
} from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, PieChart, Pie, Cell
} from "recharts";
import { mockTickets } from "./data/mockTickets";
import type { Ticket } from "./types/ticket";

type Page = "dashboard" | "tickets";
const trendData = [
  { day:"T2", count:7 }, { day:"T3", count:9 }, { day:"T4", count:11 },
  { day:"T5", count:13 }, { day:"T6", count:12 }, { day:"T7", count:18 },
  { day:"CN", count:15 }, { day:"T2", count:21 }, { day:"T3", count:17 },
  { day:"T4", count:24 }, { day:"T5", count:19 }
];
const categoryData = [
  { name:"Tài liệu", value:102, color:"#6658f5" },
  { name:"Tiến độ dịch vụ", value:98, color:"#9185ff" },
  { name:"Chuyển cấp kỹ thuật", value:56, color:"#e58a27" }
];

function Sidebar({ page, setPage, onCreate }: { page: Page; setPage: (p: Page) => void; onCreate: () => void }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const nav = [
    { id:"dashboard" as Page, label:"Tổng quan", icon:LayoutDashboard },
    { id:"tickets" as Page, label:"Danh sách ticket", icon:List }
  ];
  return <>
    <button className="mobile-toggle" type="button" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Mở menu">{mobileOpen ? <X/> : <Menu/>}</button>
    {mobileOpen && <button className="mobile-scrim" type="button" onClick={() => setMobileOpen(false)} aria-label="Đóng menu"/>}
    <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
      <div className="brand"><div className="brand-symbol">SN</div><div><strong>SONGNHAT</strong><small>Support Resolution AI</small></div></div>
      <nav className="side-nav">
        {nav.map(item => { const Icon = item.icon; return <button key={item.id} className={`nav-link ${page===item.id?"selected":""}`} onClick={() => {setPage(item.id);setMobileOpen(false);}}><Icon size={16}/><span>{item.label}</span></button>; })}
        <button className="nav-link" onClick={() => { setPage("tickets"); onCreate(); }}><Plus size={17}/><span>Tạo ticket</span></button>
        <button className="nav-link nav-link-disabled" type="button" disabled title="Tính năng sẽ được triển khai sau"><Library size={16}/><span>Thư viện tài liệu</span><small>Sắp có</small></button>
        <button className="nav-link nav-link-disabled" type="button" disabled title="Tính năng sẽ được triển khai sau"><BarChart3 size={16}/><span>Báo cáo & Thống kê</span><small>Sắp có</small></button>
      </nav>
      <div className="sidebar-bottom">
        <button className="nav-link nav-link-disabled" type="button" disabled title="Cài đặt sẽ được triển khai sau"><Settings size={15}/><span>Cài đặt</span></button>
        <div className="profile-wrap">
          <button className="profile profile-button" type="button" aria-expanded={profileOpen} onClick={()=>setProfileOpen(v=>!v)}>
            <div className="avatar">MN</div><div className="profile-copy"><strong>Minh Von</strong><small>Support Agent</small></div><ChevronDown size={13}/>
          </button>
          {profileOpen&&<div className="profile-menu"><strong>Minh Von</strong><span>minh.von@songnhat.vn</span><div className="profile-menu-note">Tài khoản nhân viên</div><button type="button" onClick={()=>setProfileOpen(false)}>Đóng menu</button></div>}
        </div>
      </div>
    </aside>
  </>;
}

function Topbar({ searchValue, onSearchChange }: { searchValue: string; onSearchChange: (value: string) => void }) {
  const [panel,setPanel]=useState<"help"|"notifications"|null>(null);
  const [language,setLanguage]=useState(false);
  return <header className="topbar">
    <div className="global-search"><Search size={15}/><input aria-label="Tìm kiếm toàn hệ thống" value={searchValue} onChange={e=>onSearchChange(e.target.value)} placeholder="Tìm kiếm ticket, thiết bị, tài liệu..."/>{searchValue&&<button type="button" onClick={()=>onSearchChange("")} aria-label="Xóa tìm kiếm"><X size={13}/></button>}</div>
    <div className="top-actions">
      <div className="top-action-wrap"><button type="button" onClick={()=>setPanel(panel==="help"?null:"help")} aria-expanded={panel==="help"}><CircleHelp size={15}/> Trợ giúp</button>
        {panel==="help"&&<div className="top-popover help-popover"><strong>Trung tâm trợ giúp</strong><p>Hướng dẫn nhanh sử dụng SongNhat</p><ul><li><b>Tổng quan:</b> theo dõi chỉ số và cảnh báo.</li><li><b>Danh sách ticket:</b> tìm kiếm, lọc và xem chi tiết.</li><li><b>Tạo ticket:</b> thêm yêu cầu hỗ trợ mới.</li></ul><button type="button" className="popover-close" onClick={()=>setPanel(null)}>Đã hiểu</button></div>}
      </div><span>•</span>
      <div className="top-action-wrap"><button type="button" onClick={()=>setPanel(panel==="notifications"?null:"notifications")} aria-expanded={panel==="notifications"}><Bell size={15}/> Thông báo<span className="notification-dot"/></button>
        {panel==="notifications"&&<div className="top-popover notification-popover"><div className="popover-title"><strong>Thông báo</strong><span>2 mới</span></div><div className="notification-item unread"><i/><div><b>Cảnh báo an toàn</b><p>TK-1042: Quá nhiệt biến tần — nguy cơ cháy nổ.</p><small>Vừa cập nhật</small></div></div><div className="notification-item unread"><i/><div><b>Ticket chờ duyệt</b><p>Có yêu cầu đang chờ bạn xem xét.</p><small>10 phút trước</small></div></div><div className="notification-item"><i/><div><b>Chào mừng đến SongNhat</b><p>Không gian làm việc đã sẵn sàng.</p><small>Hôm nay</small></div></div><button type="button" className="popover-close" onClick={()=>setPanel(null)}>Đóng</button></div>}
      </div><span>•</span>
      <div className="top-action-wrap"><button className="language" type="button" onClick={()=>setLanguage(v=>!v)}>VN <ChevronDown size={12}/></button>{language&&<div className="language-menu"><button type="button" onClick={()=>setLanguage(false)}>✓ Tiếng Việt</button><button type="button" disabled>English (sắp có)</button></div>}</div>
    </div>
  </header>;
}

function Dashboard() {
  const stats = [
    {label:"Tổng ticket",value:"256",change:"↑ 12,8%",icon:FileText,tone:"purple"},
    {label:"Tài liệu",value:"102",change:"↑ 9,6%",icon:Library,tone:"purple"},
    {label:"Tiến độ dịch vụ",value:"98",change:"↑ 6,1%",icon:Clock3,tone:"purple"},
    {label:"Chuyển cấp kỹ thuật",value:"56",change:"↑ 15,3%",icon:Wrench,tone:"purple"},
    {label:"Cảnh báo an toàn",value:"8",change:"2 ca mới",icon:ShieldAlert,tone:"red"}
  ];
  return <div className="page dashboard-page">
    <div className="page-heading"><div><h1>Tổng quan hệ thống</h1><p>Theo dõi và điều phối các yêu cầu hỗ trợ trong SongNhat</p></div><button className="date-chip"><CalendarDays size={12}/> 7 ngày gần nhất <ChevronDown size={12}/></button></div>
    <section className="stats-grid">
      {stats.map(({label,value,change,icon:Icon,tone})=><article className="stat-card" key={label}><div className={`stat-icon ${tone}`}><Icon size={15}/></div><span className="stat-name">{label}</span><strong>{value}</strong><small className={tone==="red"?"red-text":""}>{change}</small></article>)}
    </section>
    <section className="chart-grid">
      <article className="panel trend-panel"><div className="panel-heading"><div><h2>Xu hướng ticket</h2><p>Số lượng tiếp nhận theo ngày</p></div><button className="icon-button" type="button" aria-label="Tùy chọn"><MoreHorizontal size={18}/></button></div><div className="trend-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={trendData} margin={{top:12,right:4,left:-24,bottom:0}}><CartesianGrid vertical={false} stroke="#e9edfb"/><XAxis dataKey="day" tick={false} axisLine={false} tickLine={false}/><YAxis tick={false} axisLine={false} tickLine={false}/><Tooltip cursor={{fill:"#f5f4ff"}}/><Bar dataKey="count" fill="#aea4ff" radius={[5,5,5,5]} barSize={20}/></BarChart></ResponsiveContainer></div></article>
      <article className="panel category-panel"><div className="panel-heading"><div><h2>Phân bổ ticket theo danh mục</h2></div><button className="icon-button" type="button" aria-label="Tùy chọn"><MoreHorizontal size={18}/></button></div><div className="category-content"><div className="donut-wrap"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={categoryData} dataKey="value" nameKey="name" innerRadius="67%" outerRadius="94%" paddingAngle={2} stroke="none">{categoryData.map(d=><Cell key={d.name} fill={d.color}/>)}</Pie></PieChart></ResponsiveContainer><strong>256</strong></div><div className="legend">{categoryData.map(d=><div key={d.name}><i style={{background:d.color}}/><span>{d.name}</span><b>{d.value}</b></div>)}</div></div></article>
    </section>
    <section className="bottom-grid">
      <article className="panel alerts-panel"><div className="panel-heading"><h2 className="alert-heading"><AlertTriangle size={15}/> Cảnh báo an toàn gần đây</h2><button className="text-link" type="button">Xem tất cả</button></div><div className="alert-row"><strong>TK-1042</strong><span>Quá nhiệt biến tần — nguy cơ cháy nổ</span><ArrowUpRight size={14}/></div><div className="alert-row"><strong>TK-1037</strong><span>Dòng rò động cơ vượt ngưỡng an toàn</span><ArrowUpRight size={14}/></div></article>
      <article className="panel workload-panel"><div className="panel-heading"><h2>Ticket cần xử lý</h2><button className="icon-button" type="button" aria-label="Tùy chọn"><MoreHorizontal size={18}/></button></div><div className="workload-stats"><div><strong className="blue-number">48</strong><small>Đang xử lý</small></div><div><strong className="orange-number">18</strong><small>Chờ duyệt</small></div><div><strong className="red-number">6</strong><small>Quá hạn</small></div></div></article>
    </section>
  </div>;
}

function TicketList({ onCreate, tickets, globalSearch }: { onCreate: () => void; tickets: Ticket[]; globalSearch: string }) {
  const [search,setSearch]=useState(globalSearch);
  useEffect(()=>{setSearch(globalSearch);setCurrentPage(1);},[globalSearch]);
  const [status,setStatus]=useState("Tất cả");
  const [category,setCategory]=useState("Tất cả");
  const [priority,setPriority]=useState("Tất cả");
  const [page,setCurrentPage]=useState(1);
  const [selected,setSelected]=useState<Ticket|null>(null);
  const tabs=["Tất cả","Tài liệu","Tiến độ dịch vụ","Chuyển cấp kỹ thuật","Cảnh báo an toàn"];
  const filtered=useMemo(()=>tickets.filter(t=>{
    const q=search.toLowerCase();
    return (!q || `${t.code} ${t.title} ${t.equipment}`.toLowerCase().includes(q))
      && (status==="Tất cả"||t.status===status)
      && (category==="Tất cả"||t.category===category)
      && (priority==="Tất cả"||t.priority===priority);
  }),[tickets,search,status,category,priority]);
  const pageSize=5;
  const pageCount=Math.max(1,Math.ceil(filtered.length/pageSize));
  const visible=filtered.slice((page-1)*pageSize,page*pageSize);
  const tabCounts=[256,102,98,56,8];
  return <div className="page ticket-page">
    <div className="page-heading"><div><h1>Danh sách ticket</h1><p>Quản lý, phân loại và xử lý các yêu cầu hỗ trợ kỹ thuật</p></div><button className="primary-button" onClick={onCreate}><Plus size={15}/> Tạo ticket</button></div>
    <section className="filter-panel">
      <div className="ticket-search"><Search size={14}/><input value={search} onChange={e=>{setSearch(e.target.value);setCurrentPage(1);}} placeholder="Tìm theo mã ticket, tiêu đề hoặc thiết bị..."/></div>
      <select value={status} onChange={e=>{setStatus(e.target.value);setCurrentPage(1);}} aria-label="Lọc theo trạng thái"><option>Tất cả</option><option>Mới</option><option>Đang xử lý</option><option>Chờ duyệt</option><option>Đã giải quyết</option></select>
      <select value={category} onChange={e=>{setCategory(e.target.value);setCurrentPage(1);}} aria-label="Lọc theo danh mục"><option>Tất cả</option><option>Tài liệu</option><option>Tiến độ dịch vụ</option><option>Chuyển cấp kỹ thuật</option><option>Cảnh báo an toàn</option></select>
      <select value={priority} onChange={e=>{setPriority(e.target.value);setCurrentPage(1);}} aria-label="Lọc theo mức ưu tiên"><option>Tất cả</option><option>Khẩn cấp</option><option>Cao</option><option>Trung bình</option><option>Thấp</option></select>
      <button className="filter-icon" type="button" title="Bộ lọc nâng cao" aria-label="Bộ lọc nâng cao"><SlidersHorizontal size={16}/></button>
    </section>
    <div className="ticket-tabs">{tabs.map((tab,i)=><button key={tab} className={(category===tab||(category==="Tất cả"&&i===0))?"tab active-tab":`tab ${i===4?"danger-tab":""}`} onClick={()=>{setCategory(tab);setCurrentPage(1);}}>{tab} ({tabCounts[i]})</button>)}</div>
    <section className="table-panel"><div className="table-scroll"><table className="ticket-table"><thead><tr><th>MÃ TICKET</th><th>TIÊU ĐỀ</th><th>DANH MỤC</th><th>MỨC ƯU TIÊN</th><th>TRẠNG THÁI</th><th>CẬP NHẬT</th></tr></thead><tbody>
      {visible.map(t=><tr key={t.id} onClick={()=>setSelected(t)}><td className="ticket-code">{t.code}</td><td className="ticket-name">{t.title}</td><td>{t.category}</td><td><span className={`priority priority-${t.priority==="Khẩn cấp"?"urgent":t.priority==="Cao"?"high":t.priority==="Trung bình"?"medium":"low"}`}>{t.priority}</span></td><td><span className={`status status-${t.status==="Đang xử lý"?"working":t.status==="Chờ duyệt"?"review":t.status==="Đã giải quyết"?"resolved":"new"}`}>{t.status}</span></td><td className="updated">{t.updatedAt}</td></tr>)}
    </tbody></table>{visible.length===0&&<div className="empty-state">Không tìm thấy ticket phù hợp.</div>}</div></section>
    <div className="pagination"><span>Hiển thị {filtered.length?((page-1)*pageSize+1):0}–{Math.min(page*pageSize,filtered.length)} trên {filtered.length} ticket</span><div><button disabled={page===1} onClick={()=>setCurrentPage(p=>p-1)}><ChevronLeft size={14}/></button><span>{page} / {pageCount}</span><button disabled={page===pageCount} onClick={()=>setCurrentPage(p=>p+1)}><ChevronRight size={14}/></button></div></div>
    {selected&&<div className="modal-backdrop" onClick={()=>setSelected(null)}><div className="detail-modal" role="dialog" aria-modal="true" aria-labelledby="ticket-detail-title" onClick={e=>e.stopPropagation()}><button className="modal-close" type="button" aria-label="Đóng chi tiết" onClick={()=>setSelected(null)}><X size={18}/></button><span className="modal-kicker">CHI TIẾT TICKET</span><h2 id="ticket-detail-title">{selected.code}</h2><h3>{selected.title}</h3><dl><dt>Thiết bị</dt><dd>{selected.equipment}</dd><dt>Danh mục</dt><dd>{selected.category}</dd><dt>Mức ưu tiên</dt><dd>{selected.priority}</dd><dt>Trạng thái</dt><dd>{selected.status}</dd><dt>Nhãn an toàn</dt><dd>{selected.safetyLabel === "High Risk" ? "Rủi ro cao" : selected.safetyLabel === "Medium" ? "Trung bình" : "Thấp"}</dd></dl></div></div>}
  </div>;
}

function CreateTicketModal({close,onAdd}:{close:()=>void;onAdd:(t:Ticket)=>void}) {
  const [title,setTitle]=useState(""); const [equipment,setEquipment]=useState(""); const [category,setCategory]=useState("Tài liệu");
  return <div className="modal-backdrop" onClick={close}><form className="detail-modal create-modal" role="dialog" aria-modal="true" aria-labelledby="create-ticket-title" onSubmit={e=>{e.preventDefault();onAdd({id:String(Date.now()),code:`TK-${Date.now().toString().slice(-4)}`,title,equipment,category,priority:"Trung bình",status:"Mới",updatedAt:"Vừa xong",safetyLabel:"Low"});close();}} onClick={e=>e.stopPropagation()}><button type="button" className="modal-close" onClick={close}><X size={18}/></button><span className="modal-kicker">YÊU CẦU MỚI</span><h2 id="create-ticket-title">Tạo ticket mới</h2><label>Tiêu đề ticket<input required value={title} onChange={e=>setTitle(e.target.value)} placeholder="Nhập nội dung yêu cầu"/></label><label>Thiết bị<input required value={equipment} onChange={e=>setEquipment(e.target.value)} placeholder="VD: Motor M-204"/></label><label>Danh mục<select value={category} onChange={e=>setCategory(e.target.value)}><option>Tài liệu</option><option>Tiến độ dịch vụ</option><option>Chuyển cấp kỹ thuật</option><option>Cảnh báo an toàn</option></select></label><div className="modal-actions"><button type="button" className="secondary-button" onClick={close}>Hủy</button><button className="primary-button" type="submit">Tạo ticket</button></div></form></div>;
}

export default function App() {
  const [page,setPage]=useState<Page>("dashboard");
  const [createOpen,setCreateOpen]=useState(false);
  const [tickets,setTickets]=useState(mockTickets);
  const [globalSearch,setGlobalSearch]=useState("");
  const handleAdd=(ticket:Ticket)=>setTickets(prev=>[ticket,...prev]);
  return <div className="app-shell"><Sidebar page={page} setPage={setPage} onCreate={()=>setCreateOpen(true)}/><main className="main-area"><Topbar searchValue={globalSearch} onSearchChange={value=>{setGlobalSearch(value);if(value.trim())setPage("tickets");}}/>{page==="dashboard"?<Dashboard/>:<TicketList tickets={tickets} globalSearch={globalSearch} onCreate={()=>setCreateOpen(true)}/>}</main>{createOpen&&<CreateTicketModal close={()=>setCreateOpen(false)} onAdd={handleAdd}/>}</div>;
}