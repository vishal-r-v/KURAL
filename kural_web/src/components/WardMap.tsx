import React, { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { getWardDetails, listComplaints, friendlyErrorMessage, WardDetail, BackendComplaintRecord } from "../lib/api.ts";

interface WardMapProps {
  language: "English" | "Tamil";
}

// Approximate Chennai city centroid — used purely to frame the initial map
// view, not for any per-complaint geocoding (Part E deliberately plots only
// static, real ward-level coordinates, no live GPS/geocoding).
const CHENNAI_CENTER: [number, number] = [13.0475, 80.2415];

type WardMix = "escalated" | "resolved" | "mixed" | "none";

const MIX_COLOR: Record<WardMix, string> = {
  escalated: "#dc2626", // red — at least one escalated complaint in this ward
  resolved: "#16a34a", // green — every complaint in this ward is resolved/closed
  mixed: "#f59e0b", // amber — open (filed/in_progress) but nothing escalated
  none: "#94a3b8", // grey — no complaints on record for this ward yet
};

const MIX_LABEL_EN: Record<WardMix, string> = {
  escalated: "Has escalated complaints",
  resolved: "All complaints resolved",
  mixed: "Open / in progress",
  none: "No complaints filed yet",
};

const MIX_LABEL_TA: Record<WardMix, string> = {
  escalated: "தீவிரப்படுத்தப்பட்ட புகார்கள் உள்ளன",
  resolved: "அனைத்து புகார்களும் தீர்க்கப்பட்டன",
  mixed: "நடப்பில் / செயல்பாட்டில்",
  none: "இதுவரை புகார் இல்லை",
};

function computeWardMix(records: BackendComplaintRecord[], wardDisplay: string): { mix: WardMix; total: number; escalated: number; resolved: number; open: number } {
  const wardRecords = records.filter((r) => r.ward === wardDisplay);
  const total = wardRecords.length;
  if (total === 0) return { mix: "none", total: 0, escalated: 0, resolved: 0, open: 0 };

  const escalated = wardRecords.filter((r) => r.status === "escalated").length;
  const resolved = wardRecords.filter((r) => r.status === "resolved" || r.status === "closed").length;
  const open = total - escalated - resolved;

  let mix: WardMix;
  if (escalated > 0) mix = "escalated";
  else if (resolved === total) mix = "resolved";
  else mix = "mixed";

  return { mix, total, escalated, resolved, open };
}

export default function WardMap({ language }: WardMapProps) {
  const [wards, setWards] = useState<WardDetail[]>([]);
  const [records, setRecords] = useState<BackendComplaintRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [wardDetails, complaintsRes] = await Promise.all([
          getWardDetails(),
          listComplaints({ limit: 200 }),
        ]);
        if (cancelled) return;
        setWards(wardDetails.filter((w) => typeof w.lat === "number" && typeof w.lng === "number"));
        setRecords(complaintsRes.complaints);
        setErrorMsg("");
      } catch (err) {
        if (!cancelled) setErrorMsg(friendlyErrorMessage(err, language));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const wardStats = useMemo(
    () => wards.map((w) => ({ ward: w, stats: computeWardMix(records, w.display) })),
    [wards, records]
  );

  const mixLabel = language === "English" ? MIX_LABEL_EN : MIX_LABEL_TA;

  return (
    <div className="bg-white rounded-3xl border border-gray-100 shadow-xl shadow-gray-50 overflow-hidden">
      <div className="p-5 pb-3 flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-lg font-black text-gray-900">
            {language === "English" ? "Ward Coverage Map" : "வார்டு பரப்பு வரைபடம்"}
          </h3>
          <p className="text-xs text-gray-500">
            {language === "English"
              ? "Real GCC ward locations, coloured by current complaint status mix."
              : "நிஜ GCC வார்டு இருப்பிடங்கள், நடப்பு புகார் நிலைமையின் அடிப்படையில் வண்ணமிடப்பட்டவை."}
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-bold text-gray-500">
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: MIX_COLOR.escalated }} />Escalated</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: MIX_COLOR.mixed }} />Open</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: MIX_COLOR.resolved }} />Resolved</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: MIX_COLOR.none }} />None yet</span>
        </div>
      </div>

      {errorMsg && (
        <div className="mx-5 mb-3 p-3 bg-red-50 border border-red-100 rounded-xl text-red-700 text-xs font-semibold">
          {errorMsg}
        </div>
      )}

      <div className="h-[420px] w-full relative">
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
            <span className="w-8 h-8 border-3 border-[#00274c] border-t-transparent rounded-full animate-spin"></span>
          </div>
        ) : (
          <MapContainer
            center={CHENNAI_CENTER}
            zoom={11}
            scrollWheelZoom={false}
            style={{ height: "100%", width: "100%" }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {wardStats.map(({ ward, stats }) => (
              <CircleMarker
                key={ward.id}
                center={[ward.lat as number, ward.lng as number]}
                radius={stats.total > 0 ? 8 + Math.min(stats.total, 6) : 6}
                pathOptions={{
                  color: MIX_COLOR[stats.mix],
                  fillColor: MIX_COLOR[stats.mix],
                  fillOpacity: 0.65,
                  weight: 2,
                }}
              >
                <Popup>
                  <div style={{ fontFamily: "Inter, sans-serif", minWidth: 160 }}>
                    <div style={{ fontWeight: 800, color: "#00274c", marginBottom: 4 }}>{ward.display}</div>
                    <div style={{ fontSize: 12, color: "#475569", marginBottom: 6 }}>{mixLabel[stats.mix]}</div>
                    {stats.total > 0 && (
                      <div style={{ fontSize: 12, color: "#334155" }}>
                        <div>Total: <strong>{stats.total}</strong></div>
                        <div style={{ color: MIX_COLOR.escalated }}>Escalated: {stats.escalated}</div>
                        <div style={{ color: "#b45309" }}>Open: {stats.open}</div>
                        <div style={{ color: MIX_COLOR.resolved }}>Resolved: {stats.resolved}</div>
                      </div>
                    )}
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        )}
      </div>
    </div>
  );
}
