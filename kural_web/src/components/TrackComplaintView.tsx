import React, { useEffect, useState } from "react";
import { Search, MapPin, CheckCircle, AlertTriangle, Phone, ShieldAlert, CheckSquare, Users, Sparkles, Smartphone } from "lucide-react";
import { Complaint } from "../types.ts";
import { friendlyErrorMessage, getComplaint, listComplaints } from "../lib/api.ts";
import { toFrontendComplaint } from "../lib/adapters.ts";
import SingleWardMap from "./SingleWardMap.tsx";

interface TrackComplaintViewProps {
  language: "English" | "Tamil";
  searchId: string;
  setSearchId: (id: string) => void;
  allComplaints: Complaint[];
  onStatusUpdated: (complaint: Complaint) => void;
}

export default function TrackComplaintView({ language, searchId, setSearchId }: TrackComplaintViewProps) {
  const [inputId, setInputId] = useState(searchId || "");
  const [activeComplaint, setActiveComplaint] = useState<Complaint | null>(null);
  const [loading, setLoading] = useState(false);
  const [notFoundMsg, setNotFoundMsg] = useState("");
  const [sampleIds, setSampleIds] = useState<string[]>([]);

  // Populate "quick sample" IDs from real, recently filed complaints (best-effort;
  // silently skipped if the backend is unavailable — this is a convenience only).
  useEffect(() => {
    listComplaints({ limit: 3 })
      .then((res) => setSampleIds(res.complaints.map((c) => c.ticket_id || c.id)))
      .catch(() => setSampleIds([]));
  }, []);

  const handleSearch = async (idToSearch: string) => {
    if (!idToSearch.trim()) return;
    setLoading(true);
    setNotFoundMsg("");
    setActiveComplaint(null);

    try {
      const formattedId = idToSearch.trim().replace("#", "");
      const data = await getComplaint(formattedId);
      setActiveComplaint(toFrontendComplaint(data.complaint, data.escalation_trail));
    } catch (err) {
      setNotFoundMsg(friendlyErrorMessage(err, language));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (searchId) {
      setInputId(searchId);
      handleSearch(searchId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchId]);

  const onSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchId(inputId);
    handleSearch(inputId);
  };

  return (
    <div className="max-w-4xl mx-auto py-4 space-y-8 animate-fadeIn" id="track-view">
      
      {/* Search Header */}
      <div className="space-y-4">
        <h1 className="text-3xl font-extrabold text-[#00274c]">
          {language === "English" ? "Track My Complaint" : "புகாரை பின்தொடர"}
        </h1>
        <form onSubmit={onSearchSubmit} className="relative w-full md:w-2/3">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            value={inputId}
            onChange={(e) => setInputId(e.target.value)}
            placeholder={language === "English" ? "Enter Ticket ID (e.g. GCC/SWM/2026/00147)" : "புகார் எண்ணை உள்ளிடவும் (எ.கா. GCC/SWM/2026/00147)"}
            className="w-full pl-12 pr-28 h-[52px] bg-white border border-gray-300 rounded-xl text-sm font-semibold outline-none focus:ring-2 focus:ring-[#00274c] focus:border-[#00274c] shadow-sm transition-all"
          />
          <button
            type="submit"
            className="absolute right-2 top-1/2 -translate-y-1/2 bg-[#00274c] text-white px-5 h-[38px] rounded-lg font-bold text-xs hover:bg-[#0b3d6e] transition-all cursor-pointer"
          >
            {language === "English" ? "Track" : "தேடுக"}
          </button>
        </form>

        {/* Quick select samples from real, recently filed complaints */}
        {!activeComplaint && sampleIds.length > 0 && (
          <div className="pt-2">
            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider block mb-2">
              {language === "English" ? "Recent Ticket IDs" : "சமீபத்திய புகார் எண்கள்"}
            </span>
            <div className="flex gap-2 flex-wrap">
              {sampleIds.map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    setInputId(s);
                    setSearchId(s);
                    handleSearch(s);
                  }}
                  className="bg-gray-100 hover:bg-gray-200 border border-gray-200 text-xs font-bold font-mono text-gray-700 px-3.5 py-1.5 rounded-lg transition-all cursor-pointer"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {notFoundMsg && (
        <div className="p-4 bg-red-50 border border-red-100 rounded-2xl text-red-700 text-sm font-semibold">
          {notFoundMsg}
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center justify-center py-12 gap-3 text-gray-500 animate-pulse">
          <span className="w-8 h-8 border-3 border-[#00274c] border-t-transparent rounded-full animate-spin"></span>
          <span className="text-sm font-semibold">Fetching complaint timeline...</span>
        </div>
      )}

      {/* Complaint Detailed Track Board */}
      {activeComplaint && (
        <div className="space-y-8 animate-fadeIn">
          
          {/* Main Status Badge Summary Card */}
          <div className="bg-white rounded-3xl p-6 md:p-8 border border-gray-100 shadow-xl shadow-gray-50 relative overflow-hidden">
            {/* Status Pill on Mockup top right */}
            <div className="absolute top-6 right-6 flex items-center gap-1.5">
              <span className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-extrabold uppercase border ${
                activeComplaint.status === "Escalated" ? "bg-red-50 text-red-700 border-red-200/50" :
                activeComplaint.status === "Resolved" ? "bg-green-50 text-green-700 border-green-200/50" :
                "bg-amber-50 text-amber-700 border-amber-200/50"
              }`}>
                <span className={`w-2 h-2 rounded-full ${
                  activeComplaint.status === "Escalated" ? "bg-red-600 animate-pulse" :
                  activeComplaint.status === "Resolved" ? "bg-green-600" : "bg-amber-500 animate-pulse"
                }`}></span>
                {activeComplaint.status}
              </span>
            </div>

            <div className="space-y-2 max-w-xl">
              <span className="text-xs font-bold text-gray-400 uppercase tracking-widest font-mono">{activeComplaint.ticketId}</span>
              <h2 className="text-xl sm:text-2xl font-black text-gray-900 leading-snug">{activeComplaint.title}</h2>
              <div className="flex items-center gap-1.5 text-gray-500 text-sm font-semibold pt-1">
                <MapPin className="w-4.5 h-4.5 text-[#00274c]" />
                <span>{activeComplaint.location}</span>
                {activeComplaint.ward && <span className="bg-gray-100 text-gray-600 text-xs px-2.5 py-0.5 rounded font-bold ml-2">{activeComplaint.ward}</span>}
              </div>

              {/* B3: urgency badge + Claude's one-sentence rationale */}
              <div className="flex items-start gap-2 pt-1">
                <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-extrabold uppercase shrink-0 ${
                  activeComplaint.urgency === "High" ? "bg-red-50 text-red-700" :
                  activeComplaint.urgency === "Medium" ? "bg-amber-50 text-amber-700" : "bg-green-50 text-green-700"
                }`}>
                  <Sparkles className="w-3 h-3" />
                  {activeComplaint.urgency} Urgency
                </span>
                {activeComplaint.urgencyReason && (
                  <span className="text-xs text-gray-500 italic leading-snug pt-0.5">{activeComplaint.urgencyReason}</span>
                )}
              </div>

              {/* B1: duplicate detection banners */}
              {!!activeComplaint.duplicateCount && (
                <div className="flex items-center gap-2 bg-blue-50 text-blue-800 text-xs font-bold px-3 py-2 rounded-xl mt-1">
                  <Users className="w-4 h-4 shrink-0" />
                  {activeComplaint.duplicateCount} other citizen{activeComplaint.duplicateCount > 1 ? "s" : ""} have reported this same issue
                </div>
              )}
              {activeComplaint.duplicateOf && (
                <button
                  type="button"
                  onClick={() => {
                    const originalId = activeComplaint.duplicateOf!;
                    setInputId(originalId);
                    setSearchId(originalId);
                    handleSearch(originalId);
                  }}
                  className="flex items-center gap-2 bg-purple-50 hover:bg-purple-100 text-purple-800 text-xs font-bold px-3 py-2 rounded-xl mt-1 cursor-pointer transition-all"
                >
                  <Users className="w-4 h-4 shrink-0" />
                  {language === "English" ? "Linked as a duplicate — view original complaint" : "நகல் புகார் — முதல் புகாரை காண"}
                </button>
              )}
            </div>

            {/* Stepper progress timeline (Horizontal) */}
            <div className="mt-8 pt-6 border-t border-gray-100">
              <div className="relative flex justify-between items-center w-full">
                {/* Horizontal progress bar line */}
                <div className="absolute left-0 right-0 top-4 h-[2px] bg-gray-200 -z-10"></div>
                
                {/* Active progress bar highlight */}
                <div 
                  className="absolute left-0 top-4 h-[2px] bg-[#00274c] -z-10 transition-all duration-500"
                  style={{
                    width: activeComplaint.status === "Resolved" ? "100%" : 
                           activeComplaint.status === "Escalated" ? "75%" : 
                           activeComplaint.status === "In Progress" ? "50%" : "25%"
                  }}
                ></div>

                {/* Steps */}
                {[
                  { id: "Filed", label: "Filed" },
                  { id: "Routed", label: "Routed" },
                  { id: "In Progress", label: "In Progress" },
                  { id: "Escalated", label: "Escalated", warning: true },
                  { id: "Resolved", label: "Resolved" }
                ].map((step, index) => {
                  const isCurrent = activeComplaint.status === step.id;
                  const isFuture = (
                    (activeComplaint.status === "Filed" && index > 0) ||
                    (activeComplaint.status === "Routed" && index > 1) ||
                    (activeComplaint.status === "In Progress" && index > 2) ||
                    (activeComplaint.status === "Escalated" && index > 3)
                  );
                  const isPast = !isCurrent && !isFuture;

                  // Handle warning (Escalated) state styling
                  let circleClass = "bg-[#00274c] text-white";
                  if (step.id === "Escalated") {
                    circleClass = activeComplaint.status === "Escalated" ? "bg-[#ba1a1a] text-white animate-pulse" : "bg-gray-200 text-gray-400";
                  } else if (isFuture) {
                    circleClass = "bg-gray-100 border-2 border-gray-200 text-gray-400";
                  } else if (isCurrent) {
                    circleClass = "bg-[#00274c] text-white shadow-md shadow-[#00274c]/25 ring-4 ring-[#00274c]/10";
                  }

                  return (
                    <div key={step.id} className="flex flex-col items-center gap-2">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${circleClass}`}>
                        {step.id === "Escalated" && activeComplaint.status === "Escalated" ? (
                          <AlertTriangle className="w-4 h-4" />
                        ) : isPast ? (
                          <CheckCircle className="w-4.5 h-4.5" />
                        ) : (
                          <span>{index + 1}</span>
                        )}
                      </div>
                      <span className={`text-xs font-bold ${
                        isCurrent ? "text-gray-950 font-black" : 
                        step.id === "Escalated" && activeComplaint.status === "Escalated" ? "text-[#ba1a1a]" : "text-gray-400"
                      }`}>
                        {step.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

          </div>

          {/* Detailed Timeline & Context Side-by-Side Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            
            {/* Left Col: Vertical Detailed Timeline */}
            <div className="md:col-span-2 bg-white rounded-3xl p-6 sm:p-8 border border-gray-100 shadow-xl shadow-gray-50">
              <h3 className="text-lg font-black text-gray-900 mb-6 border-b border-gray-100 pb-3">
                {language === "English" ? "Detailed Timeline" : "நடவடிக்கை காலவரிசை"}
              </h3>

              <div className="relative pl-6 space-y-8 before:absolute before:inset-y-0 before:left-[11px] before:w-[2px] before:bg-gray-100">
                
                {activeComplaint.timeline.map((event, index) => {
                  const isEscalatedEvent = event.status === "Escalated" && !event.isNotification;
                  
                  return (
                    <div key={index} className="relative">
                      {/* Node Bullet Circle */}
                      <div className={`absolute -left-[20px] top-1 w-4 h-4 rounded-full border-4 border-white shadow-md z-10 ${
                        event.isNotification ? "bg-blue-500" :
                        isEscalatedEvent ? "bg-[#ba1a1a]" : 
                        event.isCompleted ? "bg-[#00274c]" : "bg-gray-200"
                      }`}></div>

                      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-baseline gap-1">
                        <h4 className={`text-[15px] font-extrabold ${
                          event.isNotification ? "text-blue-700" :
                          isEscalatedEvent ? "text-[#ba1a1a]" : "text-gray-900"
                        }`}>
                          {event.title}
                        </h4>
                        <time className="text-xs font-bold text-gray-400">{event.date}</time>
                      </div>

                      {/* B2: simulated citizen-notification callout — distinct from real transitions */}
                      {event.isNotification ? (
                        <div className="bg-blue-50 border border-blue-100 rounded-2xl p-4.5 mt-2.5 flex gap-3">
                          <Smartphone className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                          <p className="text-xs font-medium text-gray-700 leading-relaxed">
                            {event.description}
                            <span className="block text-[10px] text-blue-500 font-bold uppercase mt-1">Simulated — no real SMS sent</span>
                          </p>
                        </div>
                      ) : isEscalatedEvent ? (
                        <div className="bg-[#ffdad6]/40 border border-[#ffdad6] rounded-2xl p-4.5 mt-2.5 flex gap-3">
                          <ShieldAlert className="w-5 h-5 text-[#ba1a1a] shrink-0 mt-0.5" />
                          <p className="text-xs font-medium text-gray-700 leading-relaxed">
                            {event.description}
                          </p>
                        </div>
                      ) : (
                        <p className="text-sm text-gray-500 mt-1 leading-relaxed">
                          {event.description}
                        </p>
                      )}
                    </div>
                  );
                })}

              </div>
            </div>

            {/* Right Col: Sidebar Contact & Maps context */}
            <div className="space-y-6">
              
              {/* Assigned Department Contact Card */}
              <div className="bg-white rounded-3xl p-6 border border-gray-100 shadow-xl shadow-gray-50 space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-11 h-11 rounded-xl bg-[#00274c]/5 text-[#00274c] flex items-center justify-center">
                    <CheckSquare className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-xs font-black text-gray-400 uppercase tracking-widest">Assigned Dept</h3>
                    <p className="text-base font-bold text-[#00274c]">{activeComplaint.department}</p>
                  </div>
                </div>

                <div className="bg-gray-50 rounded-2xl p-4 space-y-2 border border-gray-100">
                  <div className="text-xs font-semibold text-gray-600 flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                    {activeComplaint.officer || "Awaiting officer assignment"}
                  </div>
                </div>

                <a
                  href={`tel:${activeComplaint.contact}`}
                  className="w-full h-[46px] flex items-center justify-center gap-2 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-xl text-xs font-bold text-[#00274c] transition-all cursor-pointer"
                >
                  <Phone className="w-4 h-4 text-[#feae2c]" />
                  Call Helpline ({activeComplaint.contact})
                </a>
              </div>

              {/* Real per-ward map — looks up this complaint's actual ward
                  coordinates each time (see SingleWardMap.tsx), instead of
                  reusing the same static street photo for every complaint
                  regardless of location. */}
              <SingleWardMap ward={activeComplaint.ward} />

            </div>

          </div>

        </div>
      )}

    </div>
  );
}
