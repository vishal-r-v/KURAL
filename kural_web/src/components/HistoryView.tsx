import React, { useEffect, useMemo, useState } from "react";
import { ClipboardList, Search, ArrowUpDown, RefreshCcw, ArrowRight } from "lucide-react";
import { BackendComplaintRecord, friendlyErrorMessage, listComplaints } from "../lib/api.ts";

interface HistoryViewProps {
  language: "English" | "Tamil";
  setTab: (tab: string) => void;
  setSearchId: (id: string) => void;
}

type SortKey = "ticket_id" | "category" | "ward" | "filed_at" | "resolved_at" | "status" | "duplicate_count";
type SortDir = "asc" | "desc";

const AUTO_REFRESH_MS = 20000;

const CATEGORY_LABELS: Record<BackendComplaintRecord["category"], string> = {
  roads: "Roads",
  garbage: "Sanitation",
  water: "Water",
  electricity: "Electricity",
  streetlights: "Streetlights",
};

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

/** Resolved date = last_checked_at, but only meaningful once status is resolved/closed. */
function resolvedAt(record: BackendComplaintRecord): string | null {
  if (record.status === "resolved" || record.status === "closed") {
    return record.last_checked_at;
  }
  return null;
}

export default function HistoryView({ language, setTab, setSearchId }: HistoryViewProps) {
  const [records, setRecords] = useState<BackendComplaintRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [sortKey, setSortKey] = useState<SortKey>("filed_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

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

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const filteredAndSorted = useMemo(() => {
    const q = search.trim().toLowerCase();
    let rows = records.filter((r) => {
      if (statusFilter !== "all" && r.status !== statusFilter) return false;
      if (categoryFilter !== "all" && r.category !== categoryFilter) return false;
      if (!q) return true;
      return (
        (r.ticket_id || "").toLowerCase().includes(q) ||
        r.ward.toLowerCase().includes(q) ||
        r.summary.toLowerCase().includes(q) ||
        r.department.toLowerCase().includes(q)
      );
    });

    rows = [...rows].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "ticket_id":
          cmp = (a.ticket_id || a.id).localeCompare(b.ticket_id || b.id);
          break;
        case "category":
          cmp = a.category.localeCompare(b.category);
          break;
        case "ward":
          cmp = a.ward.localeCompare(b.ward);
          break;
        case "filed_at":
          cmp = new Date(a.filed_at).getTime() - new Date(b.filed_at).getTime();
          break;
        case "resolved_at": {
          const ra = resolvedAt(a);
          const rb = resolvedAt(b);
          cmp = (ra ? new Date(ra).getTime() : 0) - (rb ? new Date(rb).getTime() : 0);
          break;
        }
        case "status":
          cmp = a.status.localeCompare(b.status);
          break;
        case "duplicate_count":
          cmp = (a.duplicate_count || 0) - (b.duplicate_count || 0);
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    return rows;
  }, [records, search, statusFilter, categoryFilter, sortKey, sortDir]);

  const handleTrackClick = (identifier: string) => {
    setSearchId(identifier);
    setTab("track");
  };

  const SortHeader = ({ label, sortKeyId }: { label: string; sortKeyId: SortKey }) => (
    <th
      className="py-3 px-2 cursor-pointer select-none hover:text-[#00274c] transition-colors"
      onClick={() => toggleSort(sortKeyId)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <ArrowUpDown className={`w-3 h-3 ${sortKey === sortKeyId ? "text-[#00274c]" : "text-gray-300"}`} />
      </span>
    </th>
  );

  return (
    <div className="space-y-6 animate-fadeIn" id="history-view">
      {/* Header */}
      <div className="space-y-2 flex items-start justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-3xl font-extrabold text-[#00274c] flex items-center gap-2">
            <ClipboardList className="w-8 h-8 text-[#feae2c]" />
            {language === "English" ? "Complaint History" : "புகார் பதிவேடு"}
          </h1>
          <p className="text-sm text-gray-500">
            {language === "English"
              ? "Full, filterable record of every complaint filed with KURAL — sourced live from the backend."
              : "KURAL-இல் பதிவான அனைத்து புகார்களின் விரிவான பட்டியல் — நேரடியாக backend தரவிலிருந்து."}
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

      {/* Filters toolbar */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-lg shadow-gray-50 p-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={language === "English" ? "Search ticket ID, ward, department…" : "தேடு..."}
            className="w-full pl-9 pr-3 h-[40px] bg-gray-50 border border-gray-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-[#00274c] focus:border-[#00274c] transition-all"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-[40px] px-3 bg-gray-50 border border-gray-200 rounded-xl text-sm font-semibold text-gray-700 outline-none focus:ring-2 focus:ring-[#00274c]"
        >
          <option value="all">{language === "English" ? "All Statuses" : "அனைத்து நிலைகள்"}</option>
          <option value="filed">Filed</option>
          <option value="in_progress">In Progress</option>
          <option value="escalated">Escalated</option>
          <option value="resolved">Resolved</option>
          <option value="closed">Closed</option>
        </select>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="h-[40px] px-3 bg-gray-50 border border-gray-200 rounded-xl text-sm font-semibold text-gray-700 outline-none focus:ring-2 focus:ring-[#00274c]"
        >
          <option value="all">{language === "English" ? "All Categories" : "அனைத்து வகைகள்"}</option>
          {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>

        <span className="text-xs font-bold text-gray-400 uppercase tracking-widest ml-auto">
          {filteredAndSorted.length} / {records.length} {language === "English" ? "records" : "பதிவுகள்"}
        </span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-3xl p-2 sm:p-4 border border-gray-100 shadow-xl shadow-gray-50 overflow-x-auto">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-gray-500 animate-pulse">
            <span className="w-8 h-8 border-3 border-[#00274c] border-t-transparent rounded-full animate-spin"></span>
            <span className="text-sm font-semibold">Loading complaint records…</span>
          </div>
        ) : (
          <table className="w-full text-left border-collapse min-w-[900px]">
            <thead>
              <tr className="border-b border-gray-200/60 text-xs font-bold text-gray-400 uppercase tracking-widest">
                <SortHeader label="Ticket ID" sortKeyId="ticket_id" />
                <SortHeader label="Category" sortKeyId="category" />
                <SortHeader label="Ward" sortKeyId="ward" />
                <SortHeader label="Filed" sortKeyId="filed_at" />
                <SortHeader label="Resolved" sortKeyId="resolved_at" />
                <SortHeader label="Status" sortKeyId="status" />
                <SortHeader label="Dupes" sortKeyId="duplicate_count" />
                <th className="py-3 px-2 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredAndSorted.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-sm text-gray-400 font-semibold">
                    {language === "English" ? "No complaints match these filters." : "பொருந்தும் புகார்கள் இல்லை."}
                  </td>
                </tr>
              )}
              {filteredAndSorted.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="py-3 px-2 font-bold text-[#00274c] text-sm font-mono">{r.ticket_id || r.id.slice(0, 8) + "…"}</td>
                  <td className="py-3 px-2">
                    <span className="text-xs font-bold text-gray-500 bg-gray-100 px-2.5 py-1 rounded-md">
                      {CATEGORY_LABELS[r.category] ?? r.category}
                    </span>
                  </td>
                  <td className="py-3 px-2 text-sm text-gray-700">{r.ward}</td>
                  <td className="py-3 px-2 text-sm text-gray-500">{formatDate(r.filed_at)}</td>
                  <td className="py-3 px-2 text-sm text-gray-500">{formatDate(resolvedAt(r))}</td>
                  <td className="py-3 px-2">
                    <span className={`inline-flex items-center gap-1 text-[11px] font-extrabold px-2.5 py-1 rounded-full uppercase border ${
                      r.status === "escalated" ? "bg-red-50 text-red-700 border-red-200/50" :
                      r.status === "resolved" || r.status === "closed" ? "bg-green-50 text-green-700 border-green-200/50" :
                      "bg-amber-50 text-amber-700 border-amber-200/50"
                    }`}>
                      {r.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="py-3 px-2 text-sm text-gray-500">
                    {r.duplicate_count > 0 ? (
                      <span className="text-xs font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-md">+{r.duplicate_count}</span>
                    ) : "—"}
                  </td>
                  <td className="py-3 px-2 text-right">
                    <button
                      onClick={() => handleTrackClick(r.ticket_id || r.id)}
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
        )}
      </div>
    </div>
  );
}
