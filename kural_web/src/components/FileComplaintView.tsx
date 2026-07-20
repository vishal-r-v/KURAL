import React, { useEffect, useRef, useState } from "react";
import { Mic, Send, MapPin, CheckCircle, ArrowRight, Sparkles, Volume2, Upload, Loader2 } from "lucide-react";
import { Complaint } from "../types.ts";
import { friendlyErrorMessage, SubmitComplaintResponse, submitTextComplaint, submitVoiceComplaint } from "../lib/api.ts";
import { toFrontendComplaint } from "../lib/adapters.ts";

interface FileComplaintViewProps {
  language: "English" | "Tamil";
  onComplaintSubmitted: (complaint: Complaint) => void;
  setTab: (tab: string) => void;
  setSearchId: (id: string) => void;
}

type VoiceState = "idle" | "recording" | "uploading" | "error";

export default function FileComplaintView({ language, onComplaintSubmitted, setTab, setSearchId }: FileComplaintViewProps) {
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedComplaint, setSubmittedComplaint] = useState<Complaint | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [wardWarning, setWardWarning] = useState("");
  const [duplicateInfo, setDuplicateInfo] = useState<SubmitComplaintResponse["duplicate"] | null>(null);

  // Voice recording state
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [voiceError, setVoiceError] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const popularLocations = [
    "Mylapore",
    "Anna Nagar",
    "Velachery",
    "Adyar",
    "Besant Nagar",
    "Nungambakkam"
  ];

  // Soundwave bars animation simulation
  const [soundwaveBars, setSoundwaveBars] = useState<number[]>([10, 20, 15, 30, 25, 40, 10, 20, 35, 15]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (voiceState === "recording") {
      interval = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
        setSoundwaveBars(Array.from({ length: 15 }, () => Math.floor(Math.random() * 50) + 10));
      }, 500);
    } else {
      setRecordingSeconds(0);
    }
    return () => clearInterval(interval);
  }, [voiceState]);

  // Release the microphone if the component unmounts mid-recording.
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const applySubmittedComplaint = (data: SubmitComplaintResponse) => {
    const complaint = toFrontendComplaint(data.complaint);
    setSubmittedComplaint(complaint);
    onComplaintSubmitted(complaint);
    setWardWarning(
      data.ward_matched
        ? ""
        : language === "English"
        ? "We couldn't confidently identify your ward from this complaint, so it was routed to a default ward. An officer may follow up to confirm your exact location."
        : "இந்த புகாரிலிருந்து உங்கள் வார்டை உறுதியாக அறிய முடியவில்லை, எனவே இயல்புநிலை வார்டுக்கு அனுப்பப்பட்டது."
    );
    setDuplicateInfo(data.duplicate?.is_duplicate ? data.duplicate : null);
  };

  // ---------------------------------------------------------------------
  // Text submission -> POST /complaint/text
  // ---------------------------------------------------------------------
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) {
      setErrorMsg(language === "English" ? "Please enter or record a description" : "விளக்கத்தை எழுதவும் அல்லது பதிவுசெய்யவும்");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg("");

    try {
      const text = location.trim() ? `${description.trim()} (Location: ${location.trim()})` : description.trim();
      const data = await submitTextComplaint(text);
      applySubmittedComplaint(data);
    } catch (err) {
      setErrorMsg(friendlyErrorMessage(err, language));
    } finally {
      setIsSubmitting(false);
    }
  };

  // ---------------------------------------------------------------------
  // Voice submission -> POST /complaint/voice (real mic recording OR file upload)
  // ---------------------------------------------------------------------
  const uploadAudio = async (blob: Blob, filename: string) => {
    setVoiceState("uploading");
    setVoiceError("");
    setUploadProgress(0);
    try {
      const data = await submitVoiceComplaint(blob, filename, setUploadProgress);
      applySubmittedComplaint(data);
      setVoiceState("idle");
    } catch (err) {
      setVoiceError(friendlyErrorMessage(err, language));
      setVoiceState("error");
    }
  };

  const handleStartRecording = async () => {
    setVoiceError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || "audio/webm" });
        if (blob.size === 0) {
          setVoiceError(
            language === "English"
              ? "No audio was captured. Please try recording again."
              : "எந்த ஒலியும் பதிவு செய்யப்படவில்லை. மீண்டும் முயற்சிக்கவும்."
          );
          setVoiceState("error");
          return;
        }
        await uploadAudio(blob, "recording.webm");
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setVoiceState("recording");
    } catch (err: any) {
      console.error(err);
      setVoiceError(
        err?.name === "NotAllowedError"
          ? (language === "English"
              ? "Microphone access was denied. Please allow microphone access, or upload an audio file instead."
              : "மைக்ரோஃபோன் அனுமதி மறுக்கப்பட்டது. அனுமதி வழங்கவும் அல்லது ஒலி கோப்பை பதிவேற்றவும்.")
          : (language === "English"
              ? "Could not access the microphone. Please upload an audio file instead."
              : "மைக்ரோஃபோனை அணுக முடியவில்லை. ஒலி கோப்பை பதிவேற்றவும்.")
      );
      setVoiceState("error");
    }
  };

  const handleStopRecording = () => {
    mediaRecorderRef.current?.stop();
  };

  const handleFileChosen = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    await uploadAudio(file, file.name);
  };

  const handleTrackCreated = () => {
    if (submittedComplaint) {
      setSearchId(submittedComplaint.ticketId);
      setTab("track");
    }
  };

  if (submittedComplaint) {
    return (
      <div className="max-w-xl mx-auto py-6 animate-fadeIn" id="success-view">
        <div className="bg-white rounded-3xl border border-gray-100 shadow-xl p-8 relative overflow-hidden">
          {/* Decorative Top Accent */}
          <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-green-500 to-emerald-400"></div>

          <div className="flex flex-col items-center text-center gap-4">
            <div className="w-16 h-16 rounded-full bg-green-50 text-green-600 flex items-center justify-center shadow-inner">
              <CheckCircle className="w-9 h-9" />
            </div>

            <h2 className="text-2xl font-extrabold text-gray-900">
              {language === "English" ? "Complaint Filed Successfully" : "புகார் வெற்றிகரமாக சமர்ப்பிக்கப்பட்டது"}
            </h2>
            <p className="text-sm text-gray-500 max-w-sm">
              {language === "English" 
                ? "Your complaint was analyzed and auto-routed by KURAL's AI pipeline (Claude + Whisper)." 
                : "உங்கள் புகார் ஆய்வு செய்யப்பட்டு தானாகவே தகுந்த துறைக்கு அனுப்பப்பட்டுள்ளது."}
            </p>

            {wardWarning && (
              <div className="w-full p-3.5 rounded-xl bg-amber-50 text-amber-800 text-xs font-semibold text-left">
                ⚠️ {wardWarning}
              </div>
            )}

            {/* B1: duplicate detection — surfaced immediately on the success screen */}
            {duplicateInfo && (
              <div className="w-full p-3.5 rounded-xl bg-blue-50 text-blue-800 text-xs font-semibold text-left">
                📌 {language === "English"
                  ? `${duplicateInfo.duplicate_count} citizen${duplicateInfo.duplicate_count > 1 ? "s" : ""} have now reported this same issue nearby — we've linked your report to the existing case (${duplicateInfo.original_ticket_id ?? duplicateInfo.original_complaint_id}) instead of opening a separate one.`
                  : `இந்த பிரச்சினையை ${duplicateInfo.duplicate_count} குடிமக்கள் புகாரளித்துள்ளனர் — உங்கள் புகார் ஏற்கனவே உள்ள வழக்குடன் இணைக்கப்பட்டது (${duplicateInfo.original_ticket_id ?? duplicateInfo.original_complaint_id}).`}
              </div>
            )}

            {/* Complaint summary container */}
            <div className="w-full bg-gray-50 rounded-2xl p-6 text-left space-y-4 my-2 border border-gray-100">
              <div className="flex justify-between items-center pb-2.5 border-b border-gray-200/60">
                <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Ticket ID</span>
                <span className="text-base font-extrabold text-[#00274c] font-mono">{submittedComplaint.ticketId}</span>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">AI Generated Summary</span>
                <p className="font-bold text-gray-800 text-sm leading-snug">{submittedComplaint.title}</p>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-2">
                <div>
                  <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Category</span>
                  <span className="block text-sm font-semibold text-gray-800 mt-0.5">{submittedComplaint.category}</span>
                </div>
                <div>
                  <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Urgency</span>
                  <span className={`inline-block text-xs font-bold px-2 py-0.5 rounded-md mt-0.5 ${
                    submittedComplaint.urgency === "High" ? "bg-red-50 text-red-700" :
                    submittedComplaint.urgency === "Medium" ? "bg-amber-50 text-amber-700" : "bg-blue-50 text-blue-700"
                  }`}>
                    {submittedComplaint.urgency}
                  </span>
                  {submittedComplaint.urgencyReason && (
                    <span className="block text-[11px] text-gray-400 italic mt-1 leading-snug">{submittedComplaint.urgencyReason}</span>
                  )}
                </div>
                <div>
                  <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Assigned Dept</span>
                  <span className="block text-sm font-semibold text-[#00274c] mt-0.5">{submittedComplaint.department}</span>
                </div>
                <div>
                  <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Ward</span>
                  <span className="block text-sm font-semibold text-gray-800 mt-0.5">{submittedComplaint.ward}</span>
                </div>
              </div>
            </div>

            <button
              onClick={handleTrackCreated}
              className="w-full bg-[#00274c] text-white font-semibold py-4 rounded-xl hover:bg-[#0b3d6e] hover:shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer"
              id="success-track-btn"
            >
              {language === "English" ? "Track Complaint Status" : "புகாரின் நிலையை பின்தொடர"}
              <ArrowRight className="w-5 h-5" />
            </button>

            <button
              onClick={() => {
                setSubmittedComplaint(null);
                setDescription("");
                setLocation("");
                setWardWarning("");
                setDuplicateInfo(null);
              }}
              className="w-full text-sm font-semibold text-gray-500 hover:text-[#00274c] py-2 cursor-pointer"
            >
              {language === "English" ? "File Another Complaint" : "மேலும் ஒரு புகார் அளிக்க"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto py-4 animate-fadeIn" id="file-complaint-view">
      <div className="space-y-4 mb-6">
        <h1 className="text-3xl font-extrabold text-[#00274c]">
          {language === "English" ? "File a Complaint" : "புகார் சமர்ப்பிக்கவும்"}
        </h1>
        <p className="text-sm text-gray-500 leading-relaxed">
          {language === "English"
            ? "Submit your complaint via voice or text. KURAL's AI Engine will instantly analyze the text, determine urgency, classify category, and assign the proper municipal department."
            : "உங்கள் புகாரை குரல் அல்லது உரை மூலம் சமர்ப்பிக்கவும். எங்கள் AI உங்களை பகுப்பாய்வு செய்து தகுந்த அதிகாரிக்கு மாற்றும்."}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-3xl border border-gray-100 shadow-xl p-8 space-y-6">
        
        {/* Location selector */}
        <div className="space-y-2">
          <label className="text-sm font-bold text-gray-700 flex items-center gap-1.5">
            <MapPin className="w-4.5 h-4.5 text-[#00274c]" />
            {language === "English" ? "Location / Area" : "இடம் / பகுதி"}
          </label>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder={language === "English" ? "e.g., Mylapore, Anna Nagar East" : "உதாரணமாக: மயிலாப்பூர், அண்ணா நகர்"}
            className="w-full h-[48px] px-4 rounded-xl border border-gray-300 focus:ring-2 focus:ring-[#00274c] focus:border-[#00274c] outline-none transition-all text-sm"
          />
          {/* Popular select shortcuts */}
          <div className="flex flex-wrap gap-2 pt-1">
            {popularLocations.map((loc) => (
              <button
                key={loc}
                type="button"
                onClick={() => setLocation(loc)}
                className={`text-xs px-3 py-1.5 rounded-lg border font-semibold transition-all ${
                  location === loc
                    ? "bg-[#00274c] text-white border-[#00274c]"
                    : "bg-gray-50 hover:bg-gray-100 text-gray-600 border-gray-200"
                }`}
              >
                {loc}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-400">
            {language === "English"
              ? "For text complaints, this is merged into the description so KURAL AI can identify your ward."
              : "இது உங்கள் வார்டை அறிய உங்கள் புகார் விளக்கத்துடன் இணைக்கப்படும்."}
          </p>
        </div>

        {/* Voice recorder action section */}
        <div className="bg-gray-50 rounded-2xl p-5 border border-gray-100 flex flex-col items-center gap-4 relative">
          <div className="flex justify-between items-center w-full">
            <span className="text-xs font-extrabold text-[#00274c] uppercase tracking-wider flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-[#feae2c]" />
              AI Speech Assistant
            </span>
            <span className="text-xs font-semibold text-gray-500">
              {language === "English" ? "English & தமிழ் supported" : "தமிழ் & ஆங்கிலம்"}
            </span>
          </div>

          {voiceState === "recording" ? (
            <div className="flex flex-col items-center gap-4 py-2 w-full animate-pulse">
              <div className="flex items-center gap-1 justify-center h-12 w-full">
                {soundwaveBars.map((height, idx) => (
                  <div
                    key={idx}
                    className="w-1.5 bg-[#ba1a1a] rounded-full transition-all duration-300"
                    style={{ height: `${height}%` }}
                  ></div>
                ))}
              </div>
              <div className="text-center">
                <span className="text-sm font-bold text-red-600 flex items-center gap-1 justify-center">
                  <span className="w-2 h-2 rounded-full bg-red-600 animate-ping"></span>
                  Recording... {recordingSeconds}s
                </span>
                <p className="text-xs text-gray-400 mt-1">Speak clearly into your microphone</p>
              </div>
              <button
                type="button"
                onClick={handleStopRecording}
                className="bg-red-600 hover:bg-red-700 text-white font-bold px-6 py-2.5 rounded-full text-xs shadow-md shadow-red-200 transition-all cursor-pointer"
              >
                Stop & Transcribe
              </button>
            </div>
          ) : voiceState === "uploading" ? (
            <div className="flex flex-col items-center gap-3 py-2 w-full">
              <Loader2 className="w-8 h-8 text-[#00274c] animate-spin" />
              <div className="text-center">
                <span className="text-sm font-bold text-[#00274c]">
                  {language === "English" ? "Transcribing & analyzing…" : "பகுப்பாய்வு செய்யப்படுகிறது…"}
                </span>
                <p className="text-xs text-gray-400 mt-1">Whisper STT → Claude extraction → routing</p>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-[#00274c] h-2 rounded-full transition-all duration-200"
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3 w-full">
              <p className="text-xs text-gray-500 leading-normal text-center">
                {language === "English"
                  ? "Choose whichever is easier — both go straight through KURAL's voice pipeline (Whisper + Claude)."
                  : "எது வசதியானதோ அதை தேர்வுசெய்யவும் — இரண்டும் KURAL இன் குரல் பகுப்பாய்வு தொடர்வழியை நேரடியாகப் பயன்படுத்தும்."}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full">
                <button
                  type="button"
                  onClick={handleStartRecording}
                  className="flex-1 flex flex-col items-center gap-2 bg-white border-2 border-[#feae2c]/40 hover:border-[#feae2c] rounded-xl py-4 px-3 transition-all cursor-pointer"
                  id="mic-record-btn"
                  aria-label="Start Voice Recording"
                >
                  <div className="w-11 h-11 rounded-full bg-[#feae2c] text-white flex items-center justify-center shadow-md">
                    <Mic className="w-5 h-5" />
                  </div>
                  <span className="text-sm font-bold text-gray-800">
                    {language === "English" ? "Record Live" : "நேரடியாக பதிவு செய்"}
                  </span>
                  <span className="text-xs text-gray-500 text-center leading-snug">
                    {language === "English" ? "Speak now using your microphone" : "மைக்ரோஃபோன் மூலம் இப்போது பேசவும்"}
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex-1 flex flex-col items-center gap-2 bg-white border-2 border-[#00274c]/20 hover:border-[#00274c] rounded-xl py-4 px-3 transition-all cursor-pointer"
                >
                  <div className="w-11 h-11 rounded-full bg-[#00274c] text-white flex items-center justify-center shadow-md">
                    <Upload className="w-5 h-5" />
                  </div>
                  <span className="text-sm font-bold text-gray-800">
                    {language === "English" ? "Upload a Voice Note" : "குரல் குறிப்பை பதிவேற்று"}
                  </span>
                  <span className="text-xs text-gray-500 text-center leading-snug">
                    {language === "English" ? ".wav, .mp3, .m4a, .webm" : "ஏற்கனவே பதிவு செய்த ஒலி கோப்பு"}
                  </span>
                </button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*"
                className="hidden"
                onChange={handleFileChosen}
              />
            </div>
          )}

          {voiceState === "error" && voiceError && (
            <div className="w-full p-3 rounded-xl bg-red-50 text-red-700 text-xs font-semibold">
              {voiceError}
            </div>
          )}
        </div>

        {/* Text Area Description */}
        <div className="space-y-2">
          <label className="text-sm font-bold text-gray-700 flex items-center gap-1.5">
            <Volume2 className="w-4.5 h-4.5 text-[#00274c]" />
            {language === "English" ? "Grievance Description" : "புகாரின் விவரம்"}
          </label>
          <textarea
            rows={5}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={language === "English" ? "Describe the issue in your own words. (e.g., Overflowing drainage block causing dirty water collection on Mylapore road for the past 3 days.)" : "உங்கள் புகாரை விரிவாக எழுதவும்..."}
            className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-[#00274c] focus:border-[#00274c] outline-none transition-all text-sm leading-relaxed"
          ></textarea>
        </div>

        {errorMsg && (
          <div className="p-4 rounded-xl bg-red-50 text-red-700 text-sm font-semibold">
            {errorMsg}
          </div>
        )}

        {/* Submit button */}
        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-[#00274c] text-white font-semibold py-4 rounded-xl hover:bg-[#0b3d6e] disabled:bg-gray-300 disabled:cursor-not-allowed hover:shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer"
          id="submit-grievance-btn"
        >
          {isSubmitting ? (
            <div className="flex items-center gap-2">
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
              <span>{language === "English" ? "AI Routing & Classifying..." : "AI பகுப்பாய்வு செய்கிறது..."}</span>
            </div>
          ) : (
            <>
              <Send className="w-5 h-5 text-[#feae2c]" />
              <span>{language === "English" ? "Submit Text Complaint" : "புகார் சமர்ப்பி"}</span>
            </>
          )}
        </button>

      </form>
    </div>
  );
}
