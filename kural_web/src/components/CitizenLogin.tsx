import React, { useEffect, useState } from "react";
import { User, X, LogOut } from "lucide-react";

interface CitizenLoginProps {
  language: "English" | "Tamil";
}

interface CitizenSession {
  name: string;
  aadhaarMasked: string;
}

const STORAGE_KEY = "kural_citizen_session";

/**
 * Prototype-only citizen login. No real Aadhaar / UIDAI integration —
 * credentials are stored in localStorage for the demo session only.
 * Clearly labelled as a hackathon prototype so it is never mistaken for
 * an official government login.
 */
export default function CitizenLogin({ language }: CitizenLoginProps) {
  const [session, setSession] = useState<CitizenSession | null>(null);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [aadhaar, setAadhaar] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setSession(JSON.parse(raw));
    } catch {
      /* ignore corrupt localStorage */
    }
  }, []);

  const maskAadhaar = (digits: string) => {
    const clean = digits.replace(/\D/g, "").slice(0, 12);
    if (clean.length < 4) return "XXXX";
    return `XXXX-XXXX-${clean.slice(-4)}`;
  };

  const validate = (): string | null => {
    const digits = aadhaar.replace(/\D/g, "");
    if (digits.length !== 12) {
      return language === "English"
        ? "Enter a 12-digit Aadhaar number (prototype only)."
        : "12 இலக்க ஆதார் எண்ணை உள்ளிடவும் (மாதிரி மட்டும்).";
    }
    if (password.length < 4) {
      return language === "English"
        ? "Password must be at least 4 characters."
        : "கடவுச்சொல் குறைந்தது 4 எழுத்துகள் வேண்டும்.";
    }
    if (mode === "register" && name.trim().length < 2) {
      return language === "English"
        ? "Enter your name to create an account."
        : "கணக்கு உருவாக்க உங்கள் பெயரை உள்ளிடவும்.";
    }
    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const err = validate();
    if (err) {
      setError(err);
      return;
    }

    const digits = aadhaar.replace(/\D/g, "");
    const accountKey = `kural_citizen_${digits}`;

    if (mode === "register") {
      const existing = localStorage.getItem(accountKey);
      if (existing) {
        setError(
          language === "English"
            ? "An account with this Aadhaar already exists. Try logging in."
            : "இந்த ஆதாருடன் ஏற்கனவே கணக்கு உள்ளது. உள்நுழைய முயற்சிக்கவும்."
        );
        return;
      }
      localStorage.setItem(
        accountKey,
        JSON.stringify({ name: name.trim(), password, aadhaar: digits })
      );
      const newSession: CitizenSession = {
        name: name.trim(),
        aadhaarMasked: maskAadhaar(digits),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newSession));
      setSession(newSession);
      setOpen(false);
      resetForm();
      return;
    }

    // login
    const raw = localStorage.getItem(accountKey);
    if (!raw) {
      setError(
        language === "English"
          ? "No account found. Create one with Register."
          : "கணக்கு இல்லை. பதிவு செய்து உருவாக்கவும்."
      );
      return;
    }
    try {
      const account = JSON.parse(raw) as { name: string; password: string };
      if (account.password !== password) {
        setError(
          language === "English" ? "Incorrect password." : "தவறான கடவுச்சொல்."
        );
        return;
      }
      const newSession: CitizenSession = {
        name: account.name,
        aadhaarMasked: maskAadhaar(digits),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newSession));
      setSession(newSession);
      setOpen(false);
      resetForm();
    } catch {
      setError(
        language === "English"
          ? "Could not read saved account. Try registering again."
          : "சேமித்த கணக்கைப் படிக்க முடியவில்லை."
      );
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(STORAGE_KEY);
    setSession(null);
    setOpen(false);
  };

  const resetForm = () => {
    setName("");
    setAadhaar("");
    setPassword("");
    setError("");
  };

  return (
    <>
      {session ? (
        <div className="flex items-center gap-2">
          <button
            onClick={() => setOpen(true)}
            className="hidden sm:flex items-center gap-2 text-sm font-bold text-[#00274c] bg-[#00274c]/5 hover:bg-[#00274c]/10 px-3 py-1.5 rounded-full transition-all"
            title={`${session.name} · ${session.aadhaarMasked}`}
          >
            <User className="w-4 h-4" />
            <span className="max-w-[100px] truncate">{session.name.split(" ")[0]}</span>
          </button>
          <button
            onClick={handleLogout}
            className="text-gray-500 hover:text-[#ba1a1a] transition-colors p-1.5"
            aria-label="Logout"
            title={language === "English" ? "Logout" : "வெளியேறு"}
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <button
          onClick={() => {
            setMode("login");
            setOpen(true);
          }}
          className="flex items-center gap-1.5 text-sm font-bold text-white bg-[#00274c] hover:bg-[#003a6b] px-3.5 py-1.5 rounded-full transition-all"
          id="citizen-login-btn"
        >
          <User className="w-4 h-4" />
          {language === "English" ? "Login" : "உள்நுழை"}
        </button>
      )}

      {open && (
        <div
          className="fixed inset-0 z-[100] bg-black/40 flex items-center justify-center p-4"
          onClick={() => {
            setOpen(false);
            resetForm();
          }}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4 animate-fadeIn"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-extrabold text-[#00274c]">
                  {mode === "login"
                    ? language === "English"
                      ? "Citizen Login"
                      : "குடிமகன் உள்நுழைவு"
                    : language === "English"
                      ? "Create Citizen Account"
                      : "குடிமகன் கணக்கு உருவாக்கு"}
                </h2>
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-2.5 py-1.5 mt-2 font-semibold">
                  {language === "English"
                    ? "Prototype only — not linked to UIDAI / official Aadhaar. Data stays in this browser."
                    : "மாதிரி மட்டும் — உண்மையான ஆதாருடன் இணைக்கப்படவில்லை. தரவு இந்த உலாவியில் மட்டுமே."}
                </p>
              </div>
              <button
                onClick={() => {
                  setOpen(false);
                  resetForm();
                }}
                className="text-gray-400 hover:text-gray-700 p-1"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {session && mode === "login" ? (
              <div className="space-y-3">
                <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                  <p className="text-sm font-bold text-[#00274c]">{session.name}</p>
                  <p className="text-xs text-gray-500 font-mono mt-1">{session.aadhaarMasked}</p>
                </div>
                <button
                  onClick={handleLogout}
                  className="w-full h-11 rounded-xl bg-gray-100 hover:bg-gray-200 text-[#00274c] font-bold text-sm transition-all"
                >
                  {language === "English" ? "Logout" : "வெளியேறு"}
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-3">
                {mode === "register" && (
                  <div>
                    <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                      {language === "English" ? "Full Name" : "முழு பெயர்"}
                    </label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="mt-1 w-full h-11 px-3 bg-gray-50 border border-gray-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-[#00274c]"
                      placeholder={language === "English" ? "e.g. R. Kumar" : "எ.கா. ஆர். குமார்"}
                    />
                  </div>
                )}
                <div>
                  <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                    {language === "English" ? "Aadhaar Number" : "ஆதார் எண்"}
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={aadhaar}
                    onChange={(e) => setAadhaar(e.target.value.replace(/\D/g, "").slice(0, 12))}
                    className="mt-1 w-full h-11 px-3 bg-gray-50 border border-gray-200 rounded-xl text-sm font-mono outline-none focus:ring-2 focus:ring-[#00274c]"
                    placeholder="XXXX XXXX XXXX"
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                    {language === "English" ? "Password" : "கடவுச்சொல்"}
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="mt-1 w-full h-11 px-3 bg-gray-50 border border-gray-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-[#00274c]"
                    placeholder="••••"
                  />
                </div>

                {error && (
                  <p className="text-xs font-semibold text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  className="w-full h-11 rounded-xl bg-[#00274c] hover:bg-[#003a6b] text-white font-bold text-sm transition-all"
                >
                  {mode === "login"
                    ? language === "English"
                      ? "Login"
                      : "உள்நுழை"
                    : language === "English"
                      ? "Create Account"
                      : "கணக்கு உருவாக்கு"}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setMode(mode === "login" ? "register" : "login");
                    setError("");
                  }}
                  className="w-full text-xs font-bold text-[#00274c] hover:underline py-1"
                >
                  {mode === "login"
                    ? language === "English"
                      ? "New citizen? Create an account"
                      : "புதிய குடிமகன்? கணக்கு உருவாக்கவும்"
                    : language === "English"
                      ? "Already have an account? Login"
                      : "ஏற்கனவே கணக்கு உள்ளதா? உள்நுழையவும்"}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}
