import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from "recharts";
import { LayoutDashboard, RefreshCcw, ArrowRight, Clock } from "lucide-react";
import { friendlyErrorMessage, listComplaints, BackendComplaintRecord } from "../lib/api.ts";
import { toFrontendComplaint } from "../lib/adapters.ts";
import WardMap from "./WardMap.tsx";

interface DashboardViewProps {
  language: "English" | "Tamil";
  setTab: (tab: string) => void;
  setSearchId: (id: string) => void;
}

const AUTO_REFRESH_MS = 15000;

const CATEGORY_LABELS: Record<BackendComplaintRecord["category"], string> = {
  roads: "Roads",
  garbage: "Sanitation",
  water: "Water",
  electricity: "Electricity",
  streetlights: "Streetlights",
};

export default function DashboardView({ language, setTab, setSearchId }: DashboardViewProps) {
  const [records, setRecords] = useState<BackendComplaintRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  const fetchData = async () => {
    try {
      const res = await listComplaints({ limit: 200 });
      setRecords(res.complaints);
      setErrorMsg("");
    } catch (err) {
      setErrorMsg(friendlyErrorMessage(err, language));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, AUTO_REFRESH_MS);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const complaints = records.map((r) => toFrontendComplaint(r));

  // Calculate stats directly off backend statuses (source of truth).
  const total = records.length;
  const active = records.filter((r) => r.status === "filed" || r.status === "in_progress").length;
  const escalated = records.filter((r) => r.status === "escalated").length;
  const resolved = records.filter((r) => r.status === "resolved" || r.status === "closed").length;

  // Average resolution time: filed_at -> last_checked_at (set at resolution time).
  const resolutionDurationsHours = records
    .filter((r) => (r.status === "resolved" || r.status === "closed") && r.last_checked_at)
    .map((r) => (new Date(r.last_checked_at as string).getTime() - new Date(r.filed_at).getTime()) / 3_600_000)
    .filter((h) => h >= 0);
  const avgResolutionHours =
    resolutionDurationsHours.length > 0
      ? resolutionDurationsHours.reduce((a, b) => a + b, 0) / resolutionDurationsHours.length
      : null;

  // Ward data aggregation
  const wardCounts: { [key: string]: number } = {};
  records.forEach((r) => {
    wardCounts[r.ward] = (wardCounts[r.ward] || 0) + 1;
  });
  const wardData = Object.keys(wardCounts)
    .map((ward) => ({ name: ward.replace(/^Ward \d+ - /, ""), Complaints: wardCounts[ward] }))
    .sort((a, b) => b.Complaints - a.Complaints)
    .slice(0, 5);

  // Category data aggregation
  const catCounts: { [key: string]: number } = {};
  records.forEach((r) => {
    const label = CATEGORY_LABELS[r.category] ?? r.category;
    catCounts[label] = (catCounts[label] || 0) + 1;
  });
  const categoryData = Object.keys(catCounts).map((cat) => ({ name: cat, value: catCounts[cat] }));

  // Department distribution
  const deptCounts: { [key: string]: number } = {};
  records.forEach((r) => {
    deptCounts[r.department] = (deptCounts[r.department] || 0) + 1;
  });
  const departmentData = Object.keys(deptCounts)
    .map((dept) => ({ name: dept, Complaints: deptCounts[dept] }))
    .sort((a, b) => b.Complaints - a.Complaints);

  // Recharts colors
  const COLORS = ["#00274c", "#feae2c", "#ba1a1a", "#55b985", "#737780"];

  const handleTrackClick = (id: string) => {
    setSearchId(id);
    setTab("track");
  };

  return (
    <div className="space-y-8 animate-fadeIn" id="dashboard-view">
      
      {/* Header */}
      <div className="space-y-2 flex items-start justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-3xl font-extrabold text-[#00274c] flex items-center gap-2">
            <LayoutDashboard className="w-8 h-8 text-[#feae2c]" />
            {language === "English" ? "Civic Analytics Dashboard" : "நகர பகுப்பாய்வு கட்டுப்பாட்டகம்"}
          </h1>
          <p className="text-sm text-gray-500">
            {language === "English"
              ? "Live metrics computed from the KURAL backend — refreshes automatically every 15 seconds."
              : "சென்னையின் வார்டு வாரியான புகார்கள் மற்றும் தீர்வு நடவடிக்கைகளின் நேரடி பகுப்பாய்வு தரவுகள்."}
          </p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 text-xs font-bold text-[#00274c] bg-gray-50 hover:bg-gray-100 border border-gray-200 px-3.5 py-2 rounded-lg transition-all cursor-pointer"
        >
          <RefreshCcw className="w-3.5 h-3.5" />
          {language === "English" ? "Refresh" : "புதுப்பிக்க"}
        </button>
      </div>

      {errorMsg && (
        <div className="p-4 bg-red-50 border border-red-100 rounded-2xl text-red-700 text-sm font-semibold">
          {errorMsg}
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3 text-gray-500 animate-pulse">
          <span className="w-8 h-8 border-3 border-[#00274c] border-t-transparent rounded-full animate-spin"></span>
          <span className="text-sm font-semibold">Loading live statistics…</span>
        </div>
      ) : (
      <>
      {/* Counters Grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        
        <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-lg shadow-gray-50 flex flex-col gap-2">
          <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Total Logs</span>
          <span className="text-3xl font-black text-[#00274c]">{total}</span>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-lg shadow-gray-50 flex flex-col gap-2">
          <span className="text-xs font-bold text-gray-400 uppercase tracking-widest text-amber-600 flex items-center gap-1">
            <RefreshCcw className="w-3.5 h-3.5 animate-spin" />
            Active
          </span>
          <span className="text-3xl font-black text-amber-600">{active}</span>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-lg shadow-gray-50 flex flex-col gap-2">
          <span className="text-xs font-bold text-gray-400 uppercase tracking-widest text-red-600">Escalated SLA</span>
          <span className="text-3xl font-black text-red-600">{escalated}</span>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-lg shadow-gray-50 flex flex-col gap-2">
          <span className="text-xs font-bold text-gray-400 uppercase tracking-widest text-green-600">Resolved</span>
          <span className="text-3xl font-black text-green-600">{resolved}</span>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-lg shadow-gray-50 flex flex-col gap-2">
          <span className="text-xs font-bold text-gray-400 uppercase tracking-widest text-gray-500 flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            Avg Resolution
          </span>
          <span className="text-3xl font-black text-[#00274c]">
            {avgResolutionHours !== null ? `${avgResolutionHours.toFixed(1)}h` : "—"}
          </span>
        </div>

      </div>

      {/* Charts Side-by-Side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Bar Chart: Ward Reach */}
        <div className="bg-white rounded-3xl p-6 border border-gray-100 shadow-xl shadow-gray-50">
          <h3 className="text-sm font-black text-gray-400 uppercase tracking-widest mb-4">Grievances by Ward</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={wardData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f3f8" />
                <XAxis dataKey="name" stroke="#737780" fontSize={11} tickLine={false} />
                <YAxis stroke="#737780" fontSize={11} tickLine={false} allowDecimals={false} />
                <Tooltip cursor={{ fill: "#00274c", opacity: 0.03 }} />
                <Bar dataKey="Complaints" fill="#00274c" radius={[4, 4, 0, 0]} barSize={36} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Pie Chart: Categories */}
        <div className="bg-white rounded-3xl p-6 border border-gray-100 shadow-xl shadow-gray-50">
          <h3 className="text-sm font-black text-gray-400 uppercase tracking-widest mb-4">Category Distribution</h3>
          <div className="h-64 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={categoryData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {categoryData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend iconSize={10} iconType="circle" wrapperStyle={{ fontSize: 12, fontWeight: "semibold" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Bar Chart: Department distribution (full width) */}
        <div className="bg-white rounded-3xl p-6 border border-gray-100 shadow-xl shadow-gray-50 md:col-span-2">
          <h3 className="text-sm font-black text-gray-400 uppercase tracking-widest mb-4">Grievances by Department</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={departmentData} layout="vertical" margin={{ left: 24 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f3f3f8" />
                <XAxis type="number" stroke="#737780" fontSize={11} tickLine={false} allowDecimals={false} />
                <YAxis type="category" dataKey="name" stroke="#737780" fontSize={11} tickLine={false} width={180} />
                <Tooltip cursor={{ fill: "#00274c", opacity: 0.03 }} />
                <Bar dataKey="Complaints" fill="#feae2c" radius={[0, 4, 4, 0]} barSize={20} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>

      {/* Real interactive ward coverage map (Leaflet + OpenStreetMap — static
          real ward coordinates only, no live GPS/geocoding, see WardMap.tsx) */}
      <WardMap language={language} />

      {/* Live Active Grievance Queue */}
      <div className="bg-white rounded-3xl p-6 md:p-8 border border-gray-100 shadow-xl shadow-gray-50">
        <div className="flex items-center justify-between border-b border-gray-100 pb-3 mb-6">
          <h3 className="text-lg font-black text-gray-900">
            {language === "English" ? "Live Grievance Queue" : "நடப்பு புகார்களின் பட்டியல்"}
          </h3>
          <button
            onClick={() => setTab("history")}
            className="text-xs font-bold text-[#00274c] hover:underline flex items-center gap-1 cursor-pointer"
          >
            {language === "English" ? "View Full History" : "முழு பதிவேட்டைக் காண"}
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-gray-200/60 text-xs font-bold text-gray-400 uppercase tracking-widest">
                <th className="py-3 px-2">Ticket ID</th>
                <th className="py-3 px-2">Title / Ward</th>
                <th className="py-3 px-2">Category</th>
                <th className="py-3 px-2">Status</th>
                <th className="py-3 px-2 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {complaints.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-sm text-gray-400 font-semibold">
                    {language === "English" ? "No complaints filed yet." : "இதுவரை புகார்கள் இல்லை."}
                  </td>
                </tr>
              )}
              {complaints.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="py-3.5 px-2 font-bold text-[#00274c] text-sm font-mono">{c.ticketId}</td>
                  <td className="py-3.5 px-2">
                    <span className="font-semibold text-gray-800 text-sm block leading-snug">{c.title}</span>
                    <span className="text-xs text-gray-400 font-bold">{c.ward}</span>
                  </td>
                  <td className="py-3.5 px-2">
                    <span className="text-xs font-bold text-gray-500 bg-gray-100 px-2.5 py-1 rounded-md">{c.category}</span>
                  </td>
                  <td className="py-3.5 px-2">
                    <span className={`inline-flex items-center gap-1 text-[11px] font-extrabold px-2.5 py-1 rounded-full uppercase border ${
                      c.status === "Escalated" ? "bg-red-50 text-red-700 border-red-200/50" :
                      c.status === "Resolved" ? "bg-green-50 text-green-700 border-green-200/50" :
                      "bg-amber-50 text-amber-700 border-amber-200/50"
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        c.status === "Escalated" ? "bg-red-600 animate-pulse" :
                        c.status === "Resolved" ? "bg-green-600" : "bg-amber-500 animate-pulse"
                      }`}></span>
                      {c.status}
                    </span>
                  </td>
                  <td className="py-3.5 px-2 text-right">
                    <button
                      onClick={() => handleTrackClick(c.ticketId)}
                      className="inline-flex items-center gap-1 bg-gray-50 hover:bg-[#00274c] hover:text-white text-gray-700 border border-gray-200 text-xs font-bold px-3 py-1.5 rounded-lg transition-all cursor-pointer"
                    >
                      Track
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      </>
      )}

    </div>
  );
}
