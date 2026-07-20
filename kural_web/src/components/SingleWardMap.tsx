import React, { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { getWardDetails } from "../lib/api.ts";

interface SingleWardMapProps {
  /** Full backend ward display string, e.g. "Ward 173 - Adyar". */
  ward: string;
}

// Fallback centroid used only while ward coordinates are loading, or if a
// ward genuinely has no lat/lng on record — never a substitute for a real
// per-ward pin once data is available.
const CHENNAI_CENTER: [number, number] = [13.0475, 80.2415];

/**
 * Small single-pin map for one complaint's ward, used on the Track /
 * Complaint Detail page. Unlike the old placeholder (a single static street
 * photo reused for every complaint regardless of ward), this looks up the
 * real ward coordinates from `GET /meta/wards` and centers a real
 * OpenStreetMap tile view on that specific ward every time.
 */
export default function SingleWardMap({ ward }: SingleWardMapProps) {
  const [coords, setCoords] = useState<[number, number] | null>(null);
  const [areaLabel, setAreaLabel] = useState<string>(ward);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getWardDetails()
      .then((wards) => {
        if (cancelled) return;
        const match = wards.find((w) => w.display === ward);
        if (match && typeof match.lat === "number" && typeof match.lng === "number") {
          setCoords([match.lat, match.lng]);
          setAreaLabel(match.area || match.display);
        } else {
          setCoords(null);
          setAreaLabel(ward);
        }
      })
      .catch(() => {
        if (!cancelled) setCoords(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ward]);

  const center = coords ?? CHENNAI_CENTER;

  return (
    <div className="bg-white rounded-3xl border border-gray-100 shadow-xl shadow-gray-50 overflow-hidden h-48 relative">
      {loading ? (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
          <span className="w-6 h-6 border-3 border-[#00274c] border-t-transparent rounded-full animate-spin"></span>
        </div>
      ) : (
        <MapContainer
          key={`${center[0]}-${center[1]}`}
          center={center}
          zoom={coords ? 14 : 11}
          scrollWheelZoom={false}
          zoomControl={false}
          dragging={false}
          doubleClickZoom={false}
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {coords && (
            <CircleMarker
              center={coords}
              radius={10}
              pathOptions={{ color: "#ba1a1a", fillColor: "#ba1a1a", fillOpacity: 0.75, weight: 2 }}
            >
              <Popup>{ward}</Popup>
            </CircleMarker>
          )}
        </MapContainer>
      )}
      <div className="absolute bottom-3 left-3 bg-white/95 backdrop-blur-sm px-3.5 py-1.5 rounded-xl border border-gray-100 text-xs font-black text-[#00274c] flex items-center gap-1.5 shadow-md z-[400] pointer-events-none">
        <span className="w-2 h-2 rounded-full bg-[#ba1a1a] inline-block" />
        {areaLabel}
      </div>
    </div>
  );
}
