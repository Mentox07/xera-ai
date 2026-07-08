/* global React, ReactDOM */
const { useState, useEffect, useRef, useCallback } = React;

/* ----------------------------------------------------------
   Router
   ---------------------------------------------------------- */

function useRouter() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const handler = () => setPath(window.location.pathname);
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, []);
  const navigate = (to) => {
    window.history.pushState(null, "", to);
    setPath(to);
  };
  return { path, navigate };
}

/* ----------------------------------------------------------
   Shared bits
   ---------------------------------------------------------- */

const Wordmark = () => <div className="wordmark" role="img" aria-label="Xera AI" />;

const XMark = ({ size = 32, radius }) => (
  <span
    className="x-mark"
    role="img"
    aria-label="Xera AI"
    style={{
      width: size,
      height: size,
      borderRadius: radius ?? Math.round(size * 0.25),
    }}
  />
);

const Icon = {
  Sun: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4"/>
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
    </svg>
  ),
  Moon: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  ),
  Discord: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z"/>
    </svg>
  ),
  Plus: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <path d="M12 5v14M5 12h14"/>
    </svg>
  ),
  Send: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
    </svg>
  ),
  Check: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6L9 17l-5-5"/>
    </svg>
  ),
  Lock: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>
  ),
  Zap: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z"/>
    </svg>
  ),
  Cpu: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>
      <path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2"/>
    </svg>
  ),
  History: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/>
    </svg>
  ),
  Close: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M18 6L6 18M6 6l12 12"/>
    </svg>
  ),
  Sparkle: () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3z"/>
      <path d="M19 14l.6 1.4L21 16l-1.4.6L19 18l-.6-1.4L17 16l1.4-.6L19 14z"/>
    </svg>
  ),
  Gear: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3"/>
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
    </svg>
  ),
  Palette: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="13.5" cy="6.5" r="0.5" fill="currentColor"/>
      <circle cx="17.5" cy="10.5" r="0.5" fill="currentColor"/>
      <circle cx="8.5" cy="7.5" r="0.5" fill="currentColor"/>
      <circle cx="6.5" cy="12.5" r="0.5" fill="currentColor"/>
      <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.83 0 1.5-.67 1.5-1.5 0-.39-.15-.74-.39-1.01-.23-.26-.38-.61-.38-.99 0-.83.67-1.5 1.5-1.5H16c3.31 0 6-2.69 6-6 0-5.52-4.5-10-10-10z"/>
    </svg>
  ),
  Globe: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
  ),
  Brain: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-1.04z"/>
      <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-1.04z"/>
    </svg>
  ),
  Stop: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <rect x="4" y="4" width="16" height="16" rx="2"/>
    </svg>
  ),
  Chat: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  ),
  Robot: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="8" width="16" height="12" rx="2"/>
      <path d="M12 2v4M9 14h.01M15 14h.01M9 18h6"/>
      <path d="M2 14v2M22 14v2"/>
    </svg>
  ),
  Crown: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <path d="M2 18h20l-2-9-5 4-3-7-3 7-5-4-2 9zm0 2h20v2H2v-2z"/>
    </svg>
  ),
  Code: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
    </svg>
  ),
  Search: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35"/>
    </svg>
  ),
  Web: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
  ),
  Doc: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
    </svg>
  ),
  Menu: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M3 6h18M3 12h18M3 18h18"/>
    </svg>
  ),
  ArrowRight: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14M12 5l7 7-7 7"/>
    </svg>
  ),
  Shield: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
  ),
  Server: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/>
      <circle cx="6" cy="6" r="1" fill="currentColor"/><circle cx="6" cy="18" r="1" fill="currentColor"/>
    </svg>
  ),
  Speed: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z"/>
    </svg>
  ),
  Trash: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
    </svg>
  ),
  Pencil: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
    </svg>
  ),
  Copy: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
    </svg>
  ),
  Refresh: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
    </svg>
  ),
  ChevronDown: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9"/>
    </svg>
  ),
  PanelLeft: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="3" x2="9" y2="21"/>
    </svg>
  ),
  Minus: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="5" y1="12" x2="19" y2="12"/>
    </svg>
  ),
  ExternalLink: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
    </svg>
  ),
  Mic: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
      <line x1="12" y1="19" x2="12" y2="23"/>
      <line x1="8" y1="23" x2="16" y2="23"/>
    </svg>
  ),
  Play: () => (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3"/>
    </svg>
  ),
  Download: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="7 10 12 15 17 10"/>
      <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  ),
  Warning: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  CircleDot: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3" fill="currentColor"/>
    </svg>
  ),
  FilePdf: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/>
      <text x="8" y="12" fontSize="5" fill="currentColor" stroke="none" fontFamily="monospace">PDF</text>
    </svg>
  ),
  FileXls: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/>
    </svg>
  ),
  FilePpt: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <circle cx="12" cy="14" r="3"/>
    </svg>
  ),
};

const _LANG_ICON = {
  py: { icon: "🐍", color: "#3776ab", label: "Python" },
  python: { icon: "🐍", color: "#3776ab", label: "Python" },
  js: { icon: "JS", color: "#f7df1e", label: "JavaScript", dark: true },
  javascript: { icon: "JS", color: "#f7df1e", label: "JavaScript", dark: true },
  ts: { icon: "TS", color: "#3178c6", label: "TypeScript" },
  typescript: { icon: "TS", color: "#3178c6", label: "TypeScript" },
  jsx: { icon: "⚛", color: "#61dafb", label: "React", dark: true },
  tsx: { icon: "⚛", color: "#61dafb", label: "React TS", dark: true },
  sh: { icon: "$_", color: "#4eaa25", label: "Shell" },
  bash: { icon: "$_", color: "#4eaa25", label: "Bash" },
  ps1: { icon: "PS", color: "#012456", label: "PowerShell" },
  powershell: { icon: "PS", color: "#012456", label: "PowerShell" },
  html: { icon: "🌐", color: "#e34f26", label: "HTML" },
  css: { icon: "🎨", color: "#264de4", label: "CSS" },
  json: { icon: "{}", color: "#545454", label: "JSON" },
  yaml: { icon: "YML", color: "#cb171e", label: "YAML" },
  yml: { icon: "YML", color: "#cb171e", label: "YAML" },
  toml: { icon: "TOML", color: "#9c4121", label: "TOML" },
  sql: { icon: "🗄", color: "#336791", label: "SQL" },
  go: { icon: "Go", color: "#00add8", label: "Go", dark: true },
  rs: { icon: "🦀", color: "#ce422b", label: "Rust" },
  rust: { icon: "🦀", color: "#ce422b", label: "Rust" },
  java: { icon: "☕", color: "#f89820", label: "Java" },
  cpp: { icon: "C++", color: "#00599c", label: "C++" },
  c: { icon: "C", color: "#a8b9cc", label: "C", dark: true },
  rb: { icon: "💎", color: "#cc342d", label: "Ruby" },
  php: { icon: "🐘", color: "#777bb4", label: "PHP" },
  kt: { icon: "K", color: "#7f52ff", label: "Kotlin" },
  swift: { icon: "S", color: "#f05138", label: "Swift" },
  md: { icon: "MD", color: "#4a4a4a", label: "Markdown" },
  markdown: { icon: "MD", color: "#4a4a4a", label: "Markdown" },
  txt: { icon: "TXT", color: "#888", label: "Text" },
  conf: { icon: "⚙", color: "#607d8b", label: "Config" },
  ini: { icon: "⚙", color: "#607d8b", label: "INI" },
  dockerfile: { icon: "🐳", color: "#2496ed", label: "Docker" },
  pdf: { icon: "📄", color: "#e53935", label: "PDF" },
  xlsx: { icon: "📊", color: "#217346", label: "Excel" },
  xls: { icon: "📊", color: "#217346", label: "Excel" },
  csv: { icon: "📊", color: "#217346", label: "CSV" },
  pptx: { icon: "📑", color: "#d24726", label: "PowerPoint" },
};

function DocFileIcon({ name, size = 16 }) {
  const ext = (name || "").split(".").pop().toLowerCase();
  const info = _LANG_ICON[ext];
  if (!info) return <Icon.Doc />;
  const fontSize = size > 24 ? Math.round(size * 0.38) : Math.round(size * 0.55);
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      width: size, height: size, borderRadius: size > 20 ? 6 : 3,
      background: info.color, color: info.dark ? "#1a1a1a" : "#fff",
      fontSize, fontWeight: "700", fontFamily: "JetBrains Mono, monospace",
      letterSpacing: "-0.5px", flexShrink: 0, userSelect: "none",
    }}>{info.icon}</span>
  );
}

const SENSITIVE_PATTERNS = [
  /password[^\s=:]*\s*[:=]\s*\S+/gi,
  /token[^\s=:]*\s*[:=]\s*\S+/gi,
  /secret[^\s=:]*\s*[:=]\s*\S+/gi,
  /key[^\s=:]*\s*[:=]\s*[A-Za-z0-9+/=]{16,}/gi,
  /:[^@\s]+@/g,
];
function sanitizeOutput(text) {
  if (!text) return text;
  let out = text;
  SENSITIVE_PATTERNS.forEach(re => {
    out = out.replace(re, m => {
      const eqIdx = m.search(/[:=@]/);
      if (eqIdx < 0) return "***";
      return m.slice(0, eqIdx + 1) + " ***";
    });
  });
  return out;
}

/* ----------------------------------------------------------
   i18n + config
   ---------------------------------------------------------- */
const STRINGS = {
  de: {
    pitch: "Dein privater KI-Assistent — 100 % lokal, keine Cloud, keine Daten verlassen dein Netzwerk.",
    f_free: "5 freie Prompts",
    f_pro: "Unlimited mit Pro",
    f_stream: "Streaming-Antworten",
    f_history: "Chat-Verlauf",
    discord_login: "Mit Discord anmelden",
    or_terminal: "oder via Terminal (Xera Pro)",
    footer: "END-TO-END LOKAL",
    no_telemetry: "NULL TELEMETRIE",
    new_chat: "Neuer Chat",
    search_history: "Chats durchsuchen...",
    today: "Heute",
    yesterday: "Gestern",
    last_7_days: "Letzte 7 Tage",
    older: "Aelter",
    delete_chat: "Chat loeschen",
    rename_chat: "Umbenennen",
    connected: "lokal verbunden",
    sign_out: "Abmelden",
    welcome_sub: "Stell mir eine Frage oder gib mir eine Aufgabe. Alles laeuft lokal — niemand schaut zu.",
    placeholder: "Nachricht an Xera AI...",
    disclaimer_local: "LOKAL",
    disclaimer_text: "KEINE DATEN VERLASSEN DEIN NETZWERK",
    you: "Du",
    prompts: "Prompts",
    unlimited: "unlimited",
    limit_title: "Prompt-Limit erreicht",
    limit_body_1: "Du hast deine 5 freien Prompts aufgebraucht.",
    limit_body_2: "Tritt unserem Discord bei und erhalte die Xera Pro Rolle fuer unlimitierten Zugang.",
    limit_body_guest: "Melde dich mit Discord an, um weiterzuchatten.",
    join_discord: "Discord beitreten",
    settings: "Einstellungen",
    sec_appearance: "Erscheinungsbild",
    sec_language: "Sprache",
    theme: "Theme",
    theme_dark: "Dunkel",
    theme_light: "Hell",
    accent: "Akzentfarbe",
    language_label: "Sprache der Oberflaeche",
    err_server: "Fehler: Server nicht erreichbar.",
    err_timeout: "Zeitueberschreitung — bitte erneut versuchen.",
    err_connection: "Verbindung fehlgeschlagen — bitte pruefen ob der Server erreichbar ist.",
    copy_msg: "Nachricht kopieren",
    regenerate: "Neu generieren",
    retry: "Erneut versuchen",
    thinking: "Denkt nach...",
    agent_thinking: "Agent arbeitet...",
    agent_tool_running: "Laeuft...",
    tab_chat: "Chat",
    tab_code: "Code",
    tab_homelab: "Homelab",
    tab_chat_desc: "KI-Chat, Web-Suche, Dokumente & Bilder",
    tab_code_desc: "Big Brain, Code & Terminal",
    tab_homelab_desc: "Doku, Shell & Netzwerk",
    approve: "Genehmigen",
    deny: "Ablehnen",
    sec_admin: "Admin",
    rag_title: "RAG Knowledge Base",
    rag_hint: "Obsidian-Dokumentation in ChromaDB neu indexieren. Wird taeglich um 04:00 automatisch ausgefuehrt.",
    rag_ingest: "Jetzt indexieren",
    rag_ingesting: "Indexierung laeuft...",
    rag_success: "Indexierung abgeschlossen",
    rag_chunks: "Chunks",
    rag_docs: "Dokumente",
    guest_welcome: "Teste Xera AI — 5 Prompts gratis, ohne Anmeldung.",
    try_free: "Kostenlos testen",
    login: "Anmelden",
    landing_hero: "Dein privater KI-Assistent",
    landing_sub: "100 % lokal. Keine Cloud. Keine Daten verlassen dein Netzwerk. Powered by unserem eigenen GPU-Server.",
    landing_feat1_title: "Komplett lokal",
    landing_feat2_title: "Privat & sicher",
    landing_feat3_title: "Blitzschnell",
    landing_feat1_long: "Xera AI laeuft vollstaendig im Homelab — ein bare-metal GPU-Server mit 5x Quadro P4000 und 40 GB VRAM. Kein API-Call verlässt das lokale Netzwerk. Drei Sprachmodelle (Qwen3-Coder-30B, Gemma 4 E2B, Qwen3-4B) laufen direkt auf der Hardware, ohne Cloud-Abhaengigkeiten. Updates, Modellwechsel und Konfiguration liegen komplett in unserer Hand.",
    landing_feat2_long: "Im Homelab gibt es kein Tracking, keine Telemetrie und keine Datenweiterleitung. Alle Chats werden in einer lokalen SQLite-Datenbank gespeichert — auf dem gleichen Server, der auch die KI betreibt. Die Verbindung laeuft ueber HTTPS mit Let's Encrypt, der Reverse Proxy steht in einer isolierten DMZ. Kein Dritter hat Zugriff auf Gespraeche oder Nutzungsdaten.",
    landing_feat3_long: "Big Brain (Qwen3-30B) generiert mit 36.4 t/s auf 3 GPUs, Fast Brain (Gemma 4 E2B) mit ~80 t/s inkl. Vision & Audio, Mini Brain (Qwen3-4B) mit 45 t/s fuer schnelle einfache Antworten. Antworten werden per Server-Sent Events in Echtzeit gestreamt. Das fuehlt sich an wie eine Cloud-API — nur ohne Cloud.",
    landing_feat4_title: "Smarte Agents",
    landing_feat4_long: "Xera AI arbeitet mit 35 spezialisierten Agents und 27 Tools. Ein Orchestrator analysiert jede Anfrage und waehlt automatisch den passenden Agenten — vom Code Agent ueber Web Search bis zum Document Writer. Zusammengesetzte Aufgaben werden auf mehrere Agents parallel verteilt. Die Agents koennen Dateien lesen und schreiben, Python ausfuehren, Git bedienen, das Web durchsuchen und professionelle PDF-, Word- und Excel-Dokumente erstellen. Ein eingebautes Sicherheitssystem mit Risiko-Klassifizierung, Approval-Flow und Kill-Switch blockiert destruktive Befehle — und alles laeuft lokal, kein Befehl verlaesst das Netzwerk.",
    active_label: "Aktiv",
    agents_page_title: "Verfuegbare Agents",
    landing_demo_title: "Erlebe es selbst",
    creator: "Built by",
    back_to_home: "Zurueck zur Startseite",
    sec_routing: "Routing",
    routing_select: "Modell-Auswahl",
    routing_hint: "Xera AI waehlt automatisch das beste Modell fuer deine Anfrage.",
    routing_big_name: "Big Brain",
    routing_big_model: "Qwen3-Coder-30B-A3B",
    routing_big_size: "18 GB",
    routing_big_speed: "36.4 t/s",
    routing_big_desc: "Komplexe Fragen, Code, Recherche, tiefe Analysen",
    routing_fast_name: "Fast Brain",
    routing_fast_model: "Gemma 4 E2B",
    routing_fast_size: "~7 GB",
    routing_fast_speed: "~80 t/s",
    routing_fast_desc: "Einfache Fragen, Vision, Audio, kurze Antworten",
    routing_code_name: "Mini Brain",
    routing_code_model: "Qwen3-4B",
    routing_code_size: "2.4 GB",
    routing_code_speed: "45 t/s",
    routing_code_desc: "Schnelle einfache Fragen, leichte Tasks — minimal, effizient",
    routing_auto: "Automatisches Routing",
    routing_auto_desc: "Anhand von Laenge, Komplexitaet und Kontext wird automatisch das passende Modell gewaehlt. Komplexe Anfragen gehen immer an Big Brain.",
    landing_team_title: "Das Team",
    landing_about_miguel: "Lernender Informatiker EFZ Plattformentwicklung. Entwickelt und betreibt die gesamte Xera-AI-Infrastruktur.",
    landing_about_sascha: "Gymnasiast, schliesst 2026 ab. Co-Developer.",
    landing_howworks_title: "So funktioniert's",
    landing_dual_title: "Drei Gehirne, eine KI",
    landing_dual_desc: "Xera AI nutzt intelligentes Multi-Modell-Routing: Big Brain (30B) fuer komplexe Fragen und tiefe Analysen, Fast Brain (E2B) fuer Vision & Audio, Mini Brain (4B) fuer schnelle einfache Antworten. Alle drei laufen parallel auf 5 GPUs mit 40 GB VRAM.",
    orbit_title: "Ein Orchestrator. 35 Spezialisten.",
    orbit_desc: "Jede Anfrage wird analysiert und automatisch an den passenden Agenten geroutet — komplexe Aufgaben laufen auf mehreren Agents parallel. Mit Sicherheitssystem, Approval-Flow und Kill-Switch.",
    orbit_stat_agents: "Agents",
    orbit_stat_tools: "Tools",
    orbit_stat_parallel: "Parallel-Ausfuehrung",
    orbit_link: "Alle Agents ansehen",
    cli_title: "Xera Code — das Terminal",
    cli_desc: "Das komplette Agenten-System in deiner Shell. Dateien lesen, schreiben und refaktorieren — lokal auf deinem Rechner, gestreamt vom eigenen GPU-Server.",
    cli_pill_1: "Lokale Datei-Tools",
    cli_pill_2: "Sessions & History",
    cli_pill_3: "Brain-Auswahl",
    cli_pill_4: "Pipes & stdin",
    cli_pro_hint: "Exklusiv fuer Xera Pro",
    faq_title: "Haeufige Fragen",
    landing_new_badge: "NEU",
    agents_more: "+ 23 weitere Agents — von Backup ueber Finance bis Incident Response.",
    web_search_toggle: "Web-Suche aktivieren",
    web_search_label: "Web",
    sources_label: "Quellen",
    welcome_chat_title: "Chat",
    welcome_chat_desc: "Beide Modelle, Web-Suche, Dokumente lesen & Bilder erkennen. Ideal fuer Fragen, Recherche und Brainstorming.",
    welcome_code_title: "Code",
    welcome_code_desc: "Big Brain Modell fuer Code-Aufgaben. Auch als CLI verfuegbar: Xera Code (Pro). Kein Web-Search, keine Dokumente.",
    welcome_homelab_title: "Homelab",
    welcome_homelab_desc: "Shell-Zugriff, SSH, Docker, Monitoring und die Homelab-Dokumentation. Nur mit Homelab-Rolle.",
    folder_new: "Neuer Ordner",
    folder_none: "Alle Chats",
    folder_move: "In Ordner verschieben",
  },
  en: {
    pitch: "Your private AI assistant — 100 % local, no cloud, no data leaves your network.",
    f_free: "5 free prompts",
    f_pro: "Unlimited with Pro",
    f_stream: "Streaming responses",
    f_history: "Chat history",
    discord_login: "Sign in with Discord",
    or_terminal: "or via terminal (Xera Pro)",
    footer: "END-TO-END LOCAL",
    no_telemetry: "ZERO TELEMETRY",
    new_chat: "New chat",
    search_history: "Search chats...",
    today: "Today",
    yesterday: "Yesterday",
    last_7_days: "Last 7 days",
    older: "Older",
    delete_chat: "Delete chat",
    rename_chat: "Rename",
    connected: "local connected",
    sign_out: "Sign out",
    welcome_sub: "Ask me a question or give me a task. Everything runs locally — no one's watching.",
    placeholder: "Message Xera AI...",
    disclaimer_local: "LOCAL",
    disclaimer_text: "NO DATA LEAVES YOUR NETWORK",
    you: "You",
    prompts: "prompts",
    unlimited: "unlimited",
    limit_title: "Prompt limit reached",
    limit_body_1: "You've used your 5 free prompts.",
    limit_body_2: "Join our Discord and grab the Xera Pro role for unlimited access.",
    limit_body_guest: "Sign in with Discord to continue chatting.",
    join_discord: "Join Discord",
    settings: "Settings",
    sec_appearance: "Appearance",
    sec_language: "Language",
    theme: "Theme",
    theme_dark: "Dark",
    theme_light: "Light",
    accent: "Accent color",
    language_label: "Interface language",
    err_server: "Error: Server not reachable.",
    err_timeout: "Timeout — please try again.",
    err_connection: "Connection failed — please check if the server is reachable.",
    copy_msg: "Copy message",
    regenerate: "Regenerate",
    retry: "Retry",
    thinking: "Thinking...",
    agent_thinking: "Agent working...",
    agent_tool_running: "Running...",
    tab_chat: "Chat",
    tab_code: "Code",
    tab_homelab: "Homelab",
    tab_chat_desc: "AI chat, web search, documents & images",
    tab_code_desc: "Big Brain, code & terminal",
    tab_homelab_desc: "Docs, shell & network",
    approve: "Approve",
    deny: "Deny",
    sec_admin: "Admin",
    rag_title: "RAG Knowledge Base",
    rag_hint: "Re-index Obsidian documentation into ChromaDB. Runs automatically every day at 04:00.",
    rag_ingest: "Index now",
    rag_ingesting: "Indexing...",
    rag_success: "Indexing complete",
    rag_chunks: "Chunks",
    rag_docs: "Documents",
    guest_welcome: "Try Xera AI — 5 free prompts, no sign-up required.",
    try_free: "Try for free",
    login: "Sign in",
    landing_hero: "Your private AI assistant",
    landing_sub: "100 % local. No cloud. No data leaves your network. Powered by our own GPU server.",
    landing_feat1_title: "Fully local",
    landing_feat2_title: "Private & secure",
    landing_feat3_title: "Lightning fast",
    landing_feat1_long: "Xera AI runs entirely in our homelab — a bare-metal GPU server with 5x Quadro P4000 and 40 GB VRAM. No API call leaves the local network. Three language models (Qwen3-Coder-30B, Gemma 4 E2B, Qwen3-4B) run directly on the hardware, with zero cloud dependencies. Updates, model changes and configuration are fully under our control.",
    landing_feat2_long: "In our homelab there is no tracking, no telemetry and no data forwarding. All chats are stored in a local SQLite database — on the same server that runs the AI. The connection uses HTTPS with Let's Encrypt, and the reverse proxy sits in an isolated DMZ. No third party has access to conversations or usage data.",
    landing_feat3_long: "Big Brain (Qwen3-30B) generates at 36.4 t/s on 3 GPUs, Fast Brain (Gemma 4 E2B) at ~80 t/s with vision & audio, Mini Brain (Qwen3-4B) at 45 t/s for fast simple answers. Responses stream in real time via Server-Sent Events. It feels like a cloud API — just without the cloud.",
    landing_feat4_title: "Smart Agents",
    landing_feat4_long: "Xera AI works with 35 specialised agents and 27 tools. An orchestrator analyses every request and automatically picks the right agent — from Code Agent and Web Search to the Document Writer. Compound tasks are distributed across multiple agents running in parallel. Agents can read and write files, execute Python, drive Git, search the web and create professional PDF, Word and Excel documents. A built-in safety system with risk classification, approval flow and kill switch blocks destructive commands — and everything runs locally, no command ever leaves the network.",
    active_label: "Active",
    agents_page_title: "Available Agents",
    landing_demo_title: "See it in action",
    creator: "Built by",
    back_to_home: "Back to home",
    sec_routing: "Routing",
    routing_select: "Model selection",
    routing_hint: "Xera AI automatically picks the best model for your request.",
    routing_big_name: "Big Brain",
    routing_big_model: "Qwen3-Coder-30B-A3B",
    routing_big_size: "18 GB",
    routing_big_speed: "36.4 t/s",
    routing_big_desc: "Complex questions, code, research, deep analysis",
    routing_fast_name: "Fast Brain",
    routing_fast_model: "Gemma 4 E2B",
    routing_fast_size: "~7 GB",
    routing_fast_speed: "~80 t/s",
    routing_fast_desc: "Simple questions, vision, audio, quick answers",
    routing_code_name: "Mini Brain",
    routing_code_model: "Qwen3-4B",
    routing_code_size: "2.4 GB",
    routing_code_speed: "45 t/s",
    routing_code_desc: "Fast simple questions, light tasks — minimal, efficient",
    routing_auto: "Automatic routing",
    routing_auto_desc: "Based on length, complexity and context, the best model is chosen automatically. Complex requests always go to Big Brain.",
    landing_team_title: "The Team",
    landing_about_miguel: "IT apprentice EFZ platform development. Builds and runs the entire Xera AI infrastructure.",
    landing_about_sascha: "Gymnasium student, graduating 2026. Co-developer.",
    landing_howworks_title: "How it works",
    landing_dual_title: "Three brains, one AI",
    landing_dual_desc: "Xera AI uses smart multi-model routing: Big Brain (30B) for complex questions and deep analysis, Fast Brain (E2B) for vision & audio, Mini Brain (4B) for fast simple answers. All three run in parallel on 5 GPUs with 40 GB VRAM.",
    orbit_title: "One orchestrator. 35 specialists.",
    orbit_desc: "Every request is analysed and automatically routed to the right agent — complex tasks run on multiple agents in parallel. With safety system, approval flow and kill switch.",
    orbit_stat_agents: "Agents",
    orbit_stat_tools: "Tools",
    orbit_stat_parallel: "Parallel execution",
    orbit_link: "View all agents",
    cli_title: "Xera Code — the terminal",
    cli_desc: "The complete agent system in your shell. Read, write and refactor files — locally on your machine, streamed from your own GPU server.",
    cli_pill_1: "Local file tools",
    cli_pill_2: "Sessions & history",
    cli_pill_3: "Brain selection",
    cli_pill_4: "Pipes & stdin",
    cli_pro_hint: "Exclusive to Xera Pro",
    faq_title: "Frequently asked questions",
    landing_new_badge: "NEW",
    agents_more: "+ 23 more agents — from backup and finance to incident response.",
    web_search_toggle: "Enable web search",
    web_search_label: "Web",
    sources_label: "Sources",
    welcome_chat_title: "Chat",
    welcome_chat_desc: "Both models, web search, read documents & recognise images. Ideal for questions, research and brainstorming.",
    welcome_code_title: "Code",
    welcome_code_desc: "Big Brain model for code tasks. Also available as a CLI: Xera Code (Pro). No web search, no documents.",
    welcome_homelab_title: "Homelab",
    welcome_homelab_desc: "Shell access, SSH, Docker, monitoring and the homelab knowledge base. Homelab role required.",
    folder_new: "New folder",
    folder_none: "All chats",
    folder_move: "Move to folder",
  },
};

// Module-level language for leaf components (CodeBlock, DocumentCard, …) that
// sit too deep to thread `t` through. Set by <App/> on every render, so a
// language change re-renders the whole tree with the new value.
let UI_LANG = "de";
const L = (de, en) => (UI_LANG === "de" ? de : en);

const MODELS = [
  { id: "qwen3-30b", name: "Big Brain — Qwen3-Coder-30B", size: "30B", hint_de: "Komplexe Fragen, Code & Analysen — 36.4 t/s auf 3 GPUs", hint_en: "Complex questions, code & analysis — 36.4 t/s on 3 GPUs" },
  { id: "gemma-4-e2b", name: "Fast Brain — Gemma 4 E2B", size: "E2B", hint_de: "Vision & Audio, blitzschnell — ~80 t/s", hint_en: "Vision & audio, blazing fast — ~80 t/s" },
  { id: "qwen3-4b", name: "Mini Brain — Qwen3-4B", size: "4B", hint_de: "Leichte Aufgaben, minimal & effizient — 45 t/s", hint_en: "Light tasks, minimal & efficient — 45 t/s" },
];

const AGENTS = [
  { id: "code", emoji: "⌨️", color: "#4f9cf9", name_de: "Code Agent", name_en: "Code Agent", hint_de: "Schreibt, debuggt und refaktoriert Code", hint_en: "Writes, debugs and refactors code", status: "active", long_de: "Schreibt, debuggt, refaktoriert und reviewt Code in jeder Sprache. Nutzt Datei-Tools, Python-Ausfuehrung und Git direkt auf dem Server.", long_en: "Writes, debugs, refactors and reviews code in any language. Uses file tools, Python execution and Git directly on the server." },
  { id: "web_search", emoji: "🌐", color: "#0ea5e9", name_de: "Web Search Agent", name_en: "Web Search Agent", hint_de: "Web-Suche mit Quellen-Links via SearXNG", hint_en: "Web search with source links via SearXNG", status: "active", long_de: "Schnelle Web-Suche mit Quellen-Links — direkte Antworten aus aktuellen Web-Ergebnissen. Komplett lokal ueber SearXNG, ohne Tracking.", long_en: "Fast web search with source links — direct answers from current web results. Fully local via SearXNG, no tracking." },
  { id: "research", emoji: "🔍", color: "#29b6f6", name_de: "Research Agent", name_en: "Research Agent", hint_de: "Tiefe Recherche, Vergleiche, Benchmarks", hint_en: "Deep research, comparisons, benchmarks", status: "active", long_de: "Tiefgehende Web-Recherche, Vergleiche, Benchmarks und Informationssynthese — mit Volltext-Abruf ganzer Webseiten.", long_en: "In-depth web research, comparisons, benchmarks and information synthesis — with full-page fetching." },
  { id: "document_write", emoji: "✍️", color: "#7c3aed", name_de: "Document Writer", name_en: "Document Writer", hint_de: "Erstellt PDF, Word & Excel im Chat", hint_en: "Creates PDF, Word & Excel in chat", status: "active", long_de: "Erstellt professionelle Dokumente direkt im Chat: PDF mit Branding, Word, Excel und Markdown — inklusive Download-Karte und Live-Vorschau.", long_en: "Creates professional documents right in the chat: branded PDFs, Word, Excel and Markdown — with download card and live preview." },
  { id: "security", emoji: "🛡️", color: "#ef5350", name_de: "Security Agent", name_en: "Security Agent", hint_de: "Schwachstellen-Analyse, CVEs, Hardening", hint_en: "Vulnerability analysis, CVEs, hardening", status: "active", long_de: "Schwachstellen-Analyse, Security-Hardening, CVE-Recherche und Audits — fuer Server, Container und Netzwerk.", long_en: "Vulnerability analysis, security hardening, CVE research and audits — for servers, containers and networks." },
  { id: "devops", emoji: "🚀", color: "#f5a623", name_de: "DevOps Agent", name_en: "DevOps Agent", hint_de: "Deployments, CI/CD, Automatisierung", hint_en: "Deployments, CI/CD, automation", status: "active", long_de: "Deployments, CI/CD-Pipelines, Automatisierung und Release-Management — vom Build bis zum Rollout.", long_en: "Deployments, CI/CD pipelines, automation and release management — from build to rollout." },
  { id: "docker", emoji: "🐳", color: "#039be5", name_de: "Docker Agent", name_en: "Docker Agent", hint_de: "Container, Images, Compose, Logs", hint_en: "Containers, images, compose, logs", status: "active", long_de: "Verwaltet Container, optimiert Images, baut Compose-Setups und analysiert Container-Logs.", long_en: "Manages containers, optimises images, builds compose setups and analyses container logs." },
  { id: "python_repl", emoji: "🐍", color: "#3776ab", name_de: "Python REPL", name_en: "Python REPL", hint_de: "Fuehrt Python-Code sicher aus", hint_en: "Executes Python code safely", status: "active", long_de: "Fuehrt Python-Code in einer Sandbox aus — fuer Berechnungen, Datenanalyse und schnelle Prototypen mit echten Ergebnissen.", long_en: "Runs Python code in a sandbox — for calculations, data analysis and quick prototypes with real results." },
  { id: "git_agent", emoji: "🌿", color: "#66bb6a", name_de: "Git Agent", name_en: "Git Agent", hint_de: "Commits, Branches, Diffs, History", hint_en: "Commits, branches, diffs, history", status: "active", long_de: "Arbeitet mit Git-Repositories: Status, Diffs, Commits, Branches und History — direkt aus dem Chat oder der CLI.", long_en: "Works with Git repositories: status, diffs, commits, branches and history — straight from chat or CLI." },
  { id: "rag_agent", emoji: "📚", color: "#8d6e63", name_de: "RAG Agent", name_en: "RAG Agent", hint_de: "Durchsucht die Knowledge Base (ChromaDB)", hint_en: "Searches the knowledge base (ChromaDB)", status: "active", long_de: "Durchsucht die lokale Knowledge Base: 500+ Chunks aus 74 Obsidian-Dokumenten in ChromaDB — semantisch, praezise, offline.", long_en: "Searches the local knowledge base: 500+ chunks from 74 Obsidian documents in ChromaDB — semantic, precise, offline." },
  { id: "proxmox", emoji: "🖥️", color: "#e8530a", name_de: "Proxmox Agent", name_en: "Proxmox Agent", hint_de: "VMs, Container, Cluster-Management", hint_en: "VMs, containers, cluster management", status: "active", long_de: "Verwaltet VMs, LXC-Container, Snapshots und den Proxmox-Cluster — exklusiv fuer Homelab-Nutzer.", long_en: "Manages VMs, LXC containers, snapshots and the Proxmox cluster — exclusive to homelab users." },
  { id: "monitoring", emoji: "📊", color: "#f9a825", name_de: "Monitoring Agent", name_en: "Monitoring Agent", hint_de: "Prometheus, Grafana, Alerts, Root-Cause", hint_en: "Prometheus, Grafana, alerts, root cause", status: "active", long_de: "Analysiert Prometheus-Metriken und Grafana-Dashboards, wertet Alerts aus und findet die Root-Cause von Problemen.", long_en: "Analyses Prometheus metrics and Grafana dashboards, evaluates alerts and finds the root cause of issues." },
];
const AGENTS_TOTAL = 35;
const TOOLS_TOTAL = 27;

const DEMOS = {
  de: [
    { label: "Fast Brain", brain: "fast", user: "Was ist 127 × 34?", ai: "127 × 34 = **4.318**" },
    { label: "Big Brain", brain: "big", user: "Erklaer mir den Unterschied zwischen Docker Compose und Kubernetes.", ai: "**Docker Compose** orchestriert Container auf einem einzelnen Host — ideal fuer Entwicklung und kleine Setups. Du definierst Services in einer `docker-compose.yml` und startest alles mit einem Befehl.\n\n**Kubernetes** ist ein verteiltes System fuer Produktion: automatisches Scaling, Self-Healing, Rolling Updates ueber mehrere Nodes. Deutlich komplexer, aber fuer grosse Deployments unverzichtbar.\n\n**Faustregel:** Compose fuer Dev/Kleine Setups, K8s fuer Produktion mit >5 Services." },
    { label: "Web Search", brain: "big", user: "Was ist die neueste Version von Node.js?", ai: "Laut meiner Suche ist die aktuelle LTS-Version **Node.js 24** (Codename 'Krypton'). Daneben gibt es die neuere Current-Version mit den letzten Features.\n\nFuer Produktionsumgebungen wird die LTS-Version empfohlen.\n\n---\nQuellen: nodejs.org" },
    { label: "Dokumente", brain: "big", user: "Erstell mir ein PDF mit einer Checkliste fuer Server-Backups.", ai: "Ich habe die Checkliste zusammengestellt und als PDF formatiert.\n\n✅ **backup-checkliste.pdf** ist bereit.\n📝 *8 Punkte — von Snapshot-Pruefung bis Restore-Test, mit Zeitplan-Tabelle.*" },
    { label: "Vision", brain: "fast", user: "Was siehst du auf diesem Bild?", ai: "Ich erkenne auf dem Bild ein **Terminal-Fenster** mit einem Python-Script. Zeile 12 enthaelt einen `TypeError: unsupported operand type(s) for +: 'int' and 'str'` — der Fehler passiert, weil `input()` einen String zurueckgibt und du ihn direkt mit einer Zahl addierst. Fix: `int(input(...))` verwenden." },
    { label: "Code", brain: "big", user: "Erklaer mir async/await in Python mit einem Beispiel.", ai: "**async/await** macht asynchronen Code lesbar wie synchronen:\n\n```python\nimport asyncio\n\nasync def fetch_data(url: str) -> str:\n    await asyncio.sleep(1)  # simuliert Netzwerkwartzeit\n    return f\"Daten von {url}\"\n\nasync def main():\n    # Beide Requests parallel starten\n    r1, r2 = await asyncio.gather(\n        fetch_data(\"api/users\"),\n        fetch_data(\"api/posts\"),\n    )\n    print(r1, r2)\n\nasyncio.run(main())\n```\n\n`await` pausiert nur die aktuelle Coroutine — andere laufen weiter. `gather()` startet mehrere parallel." },
  ],
  en: [
    { label: "Fast Brain", brain: "fast", user: "What is 127 × 34?", ai: "127 × 34 = **4,318**" },
    { label: "Big Brain", brain: "big", user: "Explain the difference between Docker Compose and Kubernetes.", ai: "**Docker Compose** orchestrates containers on a single host — ideal for development and small setups. You define services in a `docker-compose.yml` and start everything with one command.\n\n**Kubernetes** is a distributed system for production: automatic scaling, self-healing, rolling updates across multiple nodes. Much more complex, but essential for large deployments.\n\n**Rule of thumb:** Compose for dev/small setups, K8s for production with >5 services." },
    { label: "Web Search", brain: "big", user: "What's the latest version of Node.js?", ai: "According to my search, the current LTS version is **Node.js 24** (codename 'Krypton'). There's also a newer Current release with the latest features.\n\nFor production environments, the LTS version is recommended.\n\n---\nSources: nodejs.org" },
    { label: "Documents", brain: "big", user: "Create a PDF with a checklist for server backups.", ai: "I've put the checklist together and formatted it as a PDF.\n\n✅ **backup-checklist.pdf** is ready.\n📝 *8 items — from snapshot verification to restore testing, with a schedule table.*" },
    { label: "Vision", brain: "fast", user: "What do you see in this image?", ai: "I can see a **terminal window** with a Python script. Line 12 shows a `TypeError: unsupported operand type(s) for +: 'int' and 'str'` — the error occurs because `input()` returns a string and you're adding it directly to a number. Fix: use `int(input(...))` instead." },
    { label: "Code", brain: "big", user: "Explain async/await in Python with an example.", ai: "**async/await** makes async code readable like sync code:\n\n```python\nimport asyncio\n\nasync def fetch_data(url: str) -> str:\n    await asyncio.sleep(1)  # simulates network delay\n    return f\"Data from {url}\"\n\nasync def main():\n    # Start both requests in parallel\n    r1, r2 = await asyncio.gather(\n        fetch_data(\"api/users\"),\n        fetch_data(\"api/posts\"),\n    )\n    print(r1, r2)\n\nasyncio.run(main())\n```\n\n`await` only pauses the current coroutine — others keep running. `gather()` starts multiple in parallel." },
  ],
};

const SUGGESTIONS = {
  de: [
    { label: "Code", text: "Schreib mir ein Python-Script, das alle .log Dateien aelter als 7 Tage loescht." },
    { label: "Erklaer", text: "Erklaer den Unterschied zwischen Promises und async/await." },
    { label: "Debug", text: "Warum bekomme ich 'CORS error: No Access-Control-Allow-Origin' beim fetch?" },
    { label: "Schreib", text: "Formuliere eine hoefliche E-Mail-Absage auf eine Bewerbung." },
  ],
  en: [
    { label: "Code", text: "Write a Python script that deletes all .log files older than 7 days." },
    { label: "Explain", text: "Explain the difference between Promises and async/await." },
    { label: "Debug", text: "Why do I get 'CORS error: No Access-Control-Allow-Origin' when using fetch?" },
    { label: "Write", text: "Write a polite rejection email for a job application." },
  ],
};

/* ----------------------------------------------------------
   Theme + topbar
   ---------------------------------------------------------- */

function ThemeToggle({ theme, setTheme }) {
  return (
    <div className="theme-toggle-segment" role="group" aria-label="Theme">
      <button type="button" aria-pressed={theme === "dark"} onClick={() => setTheme("dark")} title="Dark mode">
        <Icon.Moon />
      </button>
      <button type="button" aria-pressed={theme === "light"} onClick={() => setTheme("light")} title="Light mode">
        <Icon.Sun />
      </button>
    </div>
  );
}

function SettingsButton({ onClick }) {
  return (
    <button className="icon-btn" onClick={onClick} type="button" aria-label="Settings" title="Einstellungen">
      <Icon.Gear />
    </button>
  );
}

/* ----------------------------------------------------------
   Settings Modal
   ---------------------------------------------------------- */

function SettingsModal({ open, onClose, config, setConfig, user, t }) {
  const [tab, setTab] = useState("appearance");
  const [copied, setCopied] = useState(false);
  const [ragStatus, setRagStatus] = useState(null);
  const [ragIngesting, setRagIngesting] = useState(false);
  const [ragResult, setRagResult] = useState(null);
  const [settingsAgents, setSettingsAgents] = useState([]);

  const isPro = user && (user.is_pro || user.is_admin);
  const isGuest = !user || user.is_guest;
  const isHomelab = !!user?.has_homelab;

  React.useEffect(() => {
    if (!open || isGuest || settingsAgents.length) return;
    fetch("/api/agents").then(r => r.json()).then(data => {
      if (Array.isArray(data)) setSettingsAgents(data);
    }).catch(() => {});
  }, [open, isGuest]);

  if (!open) return null;

  const stop = (e) => e.stopPropagation();
  const toggleAgent = (id) => {
    setConfig(c => ({
      ...c,
      agents: c.agents.includes(id) ? c.agents.filter(a => a !== id) : [...c.agents, id],
    }));
  };

  const copyCmd = () => {
    navigator.clipboard?.writeText("ssh cli@xera-app.com").catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  const tabs = [
    { id: "appearance", label: t.sec_appearance, Icon: Icon.Palette },
    { id: "language", label: t.sec_language, Icon: Icon.Globe },
    { id: "routing", label: t.sec_routing, Icon: Icon.Brain },
    ...(!isGuest ? [{ id: "agents", label: "Agents", Icon: Icon.Server }] : []),
    ...(user?.is_admin ? [{ id: "admin", label: t.sec_admin, Icon: Icon.Shield }] : []),
  ];

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={stop} role="dialog" aria-modal="true">
        <aside className="settings-side">
          <div className="title">{t.settings}</div>
          {tabs.map(({ id, label, Icon: I }) => (
            <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)} type="button">
              <I /> {label}
            </button>
          ))}
          <div className="settings-side-bottom">
            <div className="creator">{t.creator} <span className="name">Miguel Rodriguez</span> & <span className="name">Sascha Bodmer</span></div>
            <div className="ver">XERA AI v3.1</div>
          </div>
        </aside>

        <section className="settings-main">
          <div className="settings-header">
            <h2>{tabs.find(x => x.id === tab)?.label}</h2>
            <button className="close-x" onClick={onClose} type="button" aria-label="Close">
              <Icon.Close />
            </button>
          </div>

          {tab === "appearance" && (
            <>
              <div className="setting-row">
                <div className="label"><div className="name">{t.theme}</div></div>
                <div className="seg">
                  <button className={config.theme === "dark" ? "on" : ""} onClick={() => setConfig(c => ({...c, theme: "dark"}))} type="button"><Icon.Moon /> {t.theme_dark}</button>
                  <button className={config.theme === "light" ? "on" : ""} onClick={() => setConfig(c => ({...c, theme: "light"}))} type="button"><Icon.Sun /> {t.theme_light}</button>
                </div>
              </div>
              <div className="setting-row">
                <div className="label"><div className="name">{t.accent}</div></div>
                <div className="seg">
                  {[
                    { h: 282, n: "Violet" }, { h: 260, n: "Indigo" }, { h: 200, n: "Cyan" }, { h: 320, n: "Pink" },
                  ].map(opt => (
                    <button key={opt.h} className={config.accentHue === opt.h ? "on" : ""} onClick={() => setConfig(c => ({...c, accentHue: opt.h}))} type="button">
                      <span style={{ width: 10, height: 10, borderRadius: "50%", background: `oklch(0.72 0.18 ${opt.h})`, display: "inline-block", boxShadow: `0 0 6px oklch(0.72 0.18 ${opt.h} / 0.6)` }} />
                      {opt.n}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          {tab === "language" && (
            <div className="setting-row">
              <div className="label"><div className="name">{t.language_label}</div></div>
              <select className="sel" value={config.language} onChange={(e) => setConfig(c => ({...c, language: e.target.value}))}>
                <option value="de">Deutsch</option>
                <option value="en">English</option>
              </select>
            </div>
          )}

          {tab === "routing" && (
            <>
              <div className="setting-row">
                <div className="label">
                  <div className="name">{t.routing_select}</div>
                  <div className="hint">{t.routing_hint}</div>
                </div>
                <div className="seg">
                  <button className={config.brain === "auto" ? "on" : ""} onClick={() => setConfig(c => ({...c, brain: "auto"}))} type="button">Auto</button>
                  <button className={config.brain === "big" ? "on" : ""} onClick={() => setConfig(c => ({...c, brain: "big"}))} type="button"><span className="brain-dot brain-dot-big" /> Big</button>
                  <button className={config.brain === "fast" ? "on" : ""} onClick={() => setConfig(c => ({...c, brain: "fast"}))} type="button"><span className="brain-dot brain-dot-fast" /> Fast</button>
                  <button className={config.brain === "code" ? "on" : ""} onClick={() => setConfig(c => ({...c, brain: "code"}))} type="button"><span className="brain-dot brain-dot-code" /> Mini</button>
                </div>
              </div>
              <div className="routing-cards">
                <div className="routing-card">
                  <div className="routing-card-head">
                    <span className="brain-badge brain-big">{t.routing_big_name}</span>
                    <span className="routing-speed">{t.routing_big_speed}</span>
                  </div>
                  <div className="routing-model">{t.routing_big_model}</div>
                  <div className="routing-meta">{t.routing_big_size}</div>
                  <div className="routing-desc">{t.routing_big_desc}</div>
                </div>
                <div className="routing-card">
                  <div className="routing-card-head">
                    <span className="brain-badge brain-fast">{t.routing_fast_name}</span>
                    <span className="routing-speed">{t.routing_fast_speed}</span>
                  </div>
                  <div className="routing-model">{t.routing_fast_model}</div>
                  <div className="routing-meta">{t.routing_fast_size} &middot; Vision+Audio</div>
                  <div className="routing-desc">{t.routing_fast_desc}</div>
                </div>
                <div className="routing-card">
                  <div className="routing-card-head">
                    <span className="brain-badge brain-code">{t.routing_code_name}</span>
                    <span className="routing-speed">{t.routing_code_speed}</span>
                  </div>
                  <div className="routing-model">{t.routing_code_model}</div>
                  <div className="routing-meta">{t.routing_code_size} &middot; Text/Code</div>
                  <div className="routing-desc">{t.routing_code_desc}</div>
                </div>
              </div>
              <div className="setting-row" style={{ marginTop: 16, borderBottom: 0 }}>
                <div className="label">
                  <div className="name">{t.routing_auto}</div>
                  <div className="hint">{t.routing_auto_desc}</div>
                </div>
              </div>
            </>
          )}

          {tab === "agents" && !isGuest && (
            <div className="settings-agents-list">
              {settingsAgents
                .filter(a => isHomelab || a.scope === "general")
                .map(a => (
                <div key={a.id} className="settings-agent-row">
                  <div className="settings-agent-indicator" style={{ background: a.color }} />
                  <div className="settings-agent-body">
                    <div className="settings-agent-name">{a.name}</div>
                    <div className="settings-agent-desc">{a.description}</div>
                  </div>
                  <div className="settings-agent-brain">
                    <span className={`brain-badge brain-${a.brain || "big"}`}>
                      {a.brain === "fast" ? "Fast Brain" : a.brain === "code" ? "Mini Brain" : "Big Brain"}
                    </span>
                  </div>
                </div>
              ))}
              <div className="settings-agent-hint">
                {config.language === "de"
                  ? "Agents werden automatisch anhand deiner Anfrage ausgewählt."
                  : "Agents are selected automatically based on your request."}
              </div>
            </div>
          )}

          {tab === "admin" && user?.is_admin && (
            <>
              <div className="setting-row" style={{ borderBottom: 0 }}>
                <div className="label">
                  <div className="name">{t.rag_title}</div>
                  <div className="hint">{t.rag_hint}</div>
                </div>
              </div>
              <div className="admin-rag-panel">
                <div className="rag-status-row">
                  <button
                    type="button"
                    className={"rag-ingest-btn" + (ragIngesting ? " ingesting" : "")}
                    disabled={ragIngesting}
                    onClick={() => {
                      setRagIngesting(true);
                      setRagResult(null);
                      fetch("/api/rag/ingest", { method: "POST" })
                        .then(r => r.json())
                        .then(data => {
                          setRagIngesting(false);
                          setRagResult(data);
                        })
                        .catch(() => {
                          setRagIngesting(false);
                          setRagResult({ status: "error", message: "Request failed" });
                        });
                    }}
                  >
                    {ragIngesting ? (
                      <><span className="spinner" /> {t.rag_ingesting}</>
                    ) : (
                      <><Icon.Refresh /> {t.rag_ingest}</>
                    )}
                  </button>
                  <button
                    type="button"
                    className="rag-status-btn"
                    onClick={() => {
                      fetch("/api/rag/status").then(r => r.json()).then(setRagStatus).catch(() => {});
                    }}
                  >
                    Status
                  </button>
                </div>
                {ragStatus && (
                  <div className="rag-info">
                    <span className={"rag-dot " + ragStatus.status} />
                    {ragStatus.chunks ?? 0} {t.rag_chunks}
                  </div>
                )}
                {ragResult && (
                  <div className={"rag-result " + ragResult.status}>
                    {ragResult.status === "ok" ? (
                      <><Icon.Check /> {t.rag_success}: {ragResult.documents} {t.rag_docs}, {ragResult.chunks} {t.rag_chunks}</>
                    ) : (
                      <><Icon.Close /> {ragResult.message}</>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------
   Demo chat preview (typewriter effect)
   ---------------------------------------------------------- */

function DemoPreview({ t, lang }) {
  const demos = DEMOS[lang] || DEMOS.de;
  const [active, setActive] = useState(0);
  const [aiText, setAiText] = useState("");
  const [typing, setTyping] = useState(false);
  const intervalRef = useRef(null);
  const timeoutRef = useRef(null);

  const startTyping = useCallback((idx) => {
    clearInterval(intervalRef.current);
    clearTimeout(timeoutRef.current);
    setActive(idx);
    setAiText("");
    setTyping(true);
    let i = 0;
    const full = demos[idx].ai;
    timeoutRef.current = setTimeout(() => {
      intervalRef.current = setInterval(() => {
        i++;
        setAiText(full.slice(0, i));
        if (i >= full.length) {
          clearInterval(intervalRef.current);
          setTyping(false);
          timeoutRef.current = setTimeout(() => {
            startTyping((idx + 1) % demos.length);
          }, 3000);
        }
      }, 14);
    }, 800);
  }, [demos]);

  useEffect(() => {
    startTyping(0);
    return () => { clearInterval(intervalRef.current); clearTimeout(timeoutRef.current); };
  }, [lang]);

  return (
    <section className="landing-demo">
      <h2 className="landing-section-title">{t.landing_demo_title}</h2>
      <div className="demo-tabs-bar">
        {demos.map((d, i) => (
          <button
            key={i}
            type="button"
            className={"demo-tab-pill" + (i === active ? " active" : "")}
            onClick={() => startTyping(i)}
          >
            {d.label}
            {i === active && <div className="demo-tab-progress"><div className="demo-tab-bar" style={{ animationDuration: typing ? "8s" : "3s" }} /></div>}
          </button>
        ))}
      </div>
      <div className="demo-window-wrap">
        <div className="demo-glow" />
        <div className="demo-window">
          <div className="demo-titlebar">
            <div className="demo-dots">
              <span className="demo-dot demo-dot-r" />
              <span className="demo-dot demo-dot-y" />
              <span className="demo-dot demo-dot-g" />
            </div>
            <span className="demo-titlebar-text">xera-app.com</span>
            {demos[active].brain && <span className={"brain-badge brain-" + demos[active].brain}>{demos[active].brain === "fast" ? "Fast Brain" : demos[active].brain === "code" ? "Mini Brain" : "Big Brain"}</span>}
          </div>
          <div className="demo-chat">
            <div className="demo-msg demo-msg-user">
              <div className="demo-msg-bubble demo-bubble-user">{demos[active].user}</div>
            </div>
            <div className="demo-msg demo-msg-ai">
              <div className="demo-msg-avatar"><XMark size={20} radius={6} /></div>
              <div className="demo-msg-bubble demo-bubble-ai">
                {aiText ? renderMarkdown(aiText) : <span className="demo-cursor" />}
                {aiText && typing && <span className="demo-cursor" />}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------
   Feature detail page — /fully-local, /private-secure, /lightning-fast
   ---------------------------------------------------------- */

const FEATURE_MAP = {
  "/fully-local":    { icon: "Server", titleKey: "landing_feat1_title", longKey: "landing_feat1_long", stat: "40 GB", statLabel: "VRAM" },
  "/private-secure": { icon: "Shield", titleKey: "landing_feat2_title", longKey: "landing_feat2_long", stat: "0", statLabel: "Data sent" },
  "/lightning-fast":  { icon: "Speed",  titleKey: "landing_feat3_title", longKey: "landing_feat3_long", stat: "36.4", statLabel: "Tokens/s" },
  "/smart-agents":   { icon: "Robot",  titleKey: "landing_feat4_title", longKey: "landing_feat4_long", stat: "35", statLabel: "Agents" },
};

const FEATURE_HIGHLIGHTS = {
  "/fully-local": {
    de: [
      { icon: "Cpu", title: "5x NVIDIA GPU", desc: "5x Quadro P4000 — alle sm_61, verteilt via llama.cpp auf 40 GB VRAM." },
      { icon: "Server", title: "Bare-Metal Server", desc: "Xeon W-2123, 64 GB RAM, 1.8 TB SSD. Kein Container, kein VM — direkt auf der Hardware." },
      { icon: "Brain", title: "Drei Modelle parallel", desc: "Qwen3-30B + Gemma 4 E2B + Qwen3-4B laufen gleichzeitig auf getrennten Ports." },
      { icon: "Shield", title: "Zero Dependencies", desc: "Kein OpenAI, kein Anthropic, kein HuggingFace. Alles lokal, alles unter Kontrolle." },
    ],
    en: [
      { icon: "Cpu", title: "5x NVIDIA GPU", desc: "5x Quadro P4000 — all sm_61, distributed via llama.cpp across 40 GB VRAM." },
      { icon: "Server", title: "Bare-Metal Server", desc: "Xeon W-2123, 64 GB RAM, 1.8 TB SSD. No container, no VM — direct on hardware." },
      { icon: "Brain", title: "Three Models in Parallel", desc: "Qwen3-30B + Gemma 4 E2B + Qwen3-4B running simultaneously on separate ports." },
      { icon: "Shield", title: "Zero Dependencies", desc: "No OpenAI, no Anthropic, no HuggingFace. Everything local, everything under control." },
    ],
  },
  "/private-secure": {
    de: [
      { icon: "Lock", title: "HTTPS Ende-zu-Ende", desc: "Let's Encrypt Zertifikat via Caddy. Automatische Erneuerung, kein manuelles Setup." },
      { icon: "Server", title: "Isolierte DMZ", desc: "Reverse Proxy in separatem VLAN (40). KI-Server in VLAN 70. Strikte Firewall-Regeln." },
      { icon: "Shield", title: "Keine Telemetrie", desc: "Null Tracking, null Analytics, null Cookies von Drittanbietern. Nicht mal ein Favicon-Request geht raus." },
      { icon: "Lock", title: "SQLite lokal", desc: "Alle Chats in einer lokalen Datenbank auf dem gleichen Server. Kein externer DB-Service." },
    ],
    en: [
      { icon: "Lock", title: "HTTPS End-to-End", desc: "Let's Encrypt certificate via Caddy. Automatic renewal, no manual setup." },
      { icon: "Server", title: "Isolated DMZ", desc: "Reverse proxy in separate VLAN (40). AI server in VLAN 70. Strict firewall rules." },
      { icon: "Shield", title: "No Telemetry", desc: "Zero tracking, zero analytics, zero third-party cookies. Not even a favicon request leaves." },
      { icon: "Lock", title: "Local SQLite", desc: "All chats in a local database on the same server. No external DB service." },
    ],
  },
  "/lightning-fast": {
    de: [
      { icon: "Zap", title: "36.4 Tokens/s", desc: "Big Brain (30B) generiert mit 36.4 t/s, Prompt-Verarbeitung mit 87.6 t/s." },
      { icon: "Speed", title: "~80 Tokens/s", desc: "Fast Brain (Gemma 4 E2B) fuer Vision/Audio — unter einer Sekunde Antwortzeit." },
      { icon: "Cpu", title: "SSE Streaming", desc: "Antworten werden Wort fuer Wort in Echtzeit gestreamt. Kein Warten auf komplette Antwort." },
      { icon: "Brain", title: "Smart Routing", desc: "Automatische Modell-Auswahl basierend auf Laenge, Komplexitaet und Kontext." },
    ],
    en: [
      { icon: "Zap", title: "36.4 Tokens/s", desc: "Big Brain (30B) generates at 36.4 t/s, prompt processing at 87.6 t/s." },
      { icon: "Speed", title: "~80 Tokens/s", desc: "Fast Brain (Gemma 4 E2B) for vision/audio — under one second response time." },
      { icon: "Cpu", title: "SSE Streaming", desc: "Responses are streamed word by word in real time. No waiting for the full answer." },
      { icon: "Brain", title: "Smart Routing", desc: "Automatic model selection based on length, complexity and context." },
    ],
  },
  "/smart-agents": {
    de: [
      { icon: "Robot", title: "35 Agents live", desc: "Code, Recherche, Dokumente, DevOps, Security, Proxmox — ein Orchestrator routet automatisch." },
      { icon: "Zap", title: "Parallel-Ausfuehrung", desc: "Zusammengesetzte Aufgaben laufen auf mehreren Agents gleichzeitig — sichtbar in Echtzeit." },
      { icon: "Cpu", title: "27 Tools", desc: "Dateien, Python, Git, Web-Suche, Docker, SSH, RAG, Dokument-Erstellung — alles lokal." },
      { icon: "Shield", title: "Sicherheitssystem", desc: "Risiko-Klassifizierung, Approval-Flow, Kill-Switch. Destruktive Befehle werden blockiert." },
    ],
    en: [
      { icon: "Robot", title: "35 agents live", desc: "Code, research, documents, DevOps, security, Proxmox — one orchestrator routes automatically." },
      { icon: "Zap", title: "Parallel execution", desc: "Compound tasks run on multiple agents simultaneously — visible in real time." },
      { icon: "Cpu", title: "27 tools", desc: "Files, Python, Git, web search, Docker, SSH, RAG, document creation — all local." },
      { icon: "Shield", title: "Safety system", desc: "Risk classification, approval flow, kill switch. Destructive commands are blocked." },
    ],
  },
};

function FeatureVisual({ path }) {
  if (path === "/fully-local") {
    return (
      <div className="feature-visual">
        <div className="feature-visual-rack">
          {[0,1,2,3,4].map(i => (
            <div key={i} className="rack-gpu" style={{ animationDelay: `${i * 0.15}s` }}>
              <div className="rack-gpu-bar" style={{ width: `${60 + Math.random() * 35}%` }} />
              <span className="rack-gpu-label">GPU {i}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (path === "/private-secure") {
    return (
      <div className="feature-visual">
        <div className="feature-visual-shield">
          <div className="shield-ring ring-1" />
          <div className="shield-ring ring-2" />
          <div className="shield-ring ring-3" />
          <div className="shield-center"><Icon.Lock /></div>
        </div>
      </div>
    );
  }
  if (path === "/lightning-fast") {
    return (
      <div className="feature-visual">
        <div className="feature-visual-speed">
          <div className="speed-bar"><div className="speed-fill speed-fill-big"><span>30B — 36.4 t/s</span></div></div>
          <div className="speed-bar"><div className="speed-fill speed-fill-fast"><span>E2B — ~80 t/s</span></div></div>
        </div>
      </div>
    );
  }
  return null;
}

function FeaturePage({ path, navigate, theme, setTheme, config, t }) {
  const feat = FEATURE_MAP[path];
  if (!feat) return null;
  const IconComp = Icon[feat.icon];
  const lang = config?.language || "de";
  const isAgents = path === "/smart-agents";
  const highlights = FEATURE_HIGHLIGHTS[path]?.[lang] || FEATURE_HIGHLIGHTS[path]?.de || [];
  return (
    <div className="landing-page feature-page">
      <div className="landing-bg">
        <div className="landing-orb landing-orb-1" />
        <div className="landing-orb landing-orb-2" />
      </div>
      <div className="bg-grid" />

      <nav className="landing-nav">
        <div className="landing-nav-brand" onClick={() => navigate("/")} style={{ cursor: "pointer" }}>
          <XMark size={28} />
          <span className="landing-nav-name">XERA<span className="accent"> AI</span></span>
        </div>
        <div className="landing-nav-right">
          <ThemeToggle theme={theme} setTheme={setTheme} />
        </div>
      </nav>

      <section className="feature-detail">
        <button type="button" className="feature-back" onClick={() => navigate("/")}>
          <Icon.ArrowRight style={{ transform: "rotate(180deg)" }} /> {t.back_to_home}
        </button>
        <div className="feature-detail-icon"><IconComp /></div>
        <h1>{t[feat.titleKey]}</h1>
        <div className="feature-detail-stat">
          <span className="landing-stat-num">{feat.stat}</span>
          <span className="landing-stat-label">{feat.statLabel}</span>
        </div>

        <FeatureVisual path={path} />

        <p className="feature-detail-text">{t[feat.longKey]}</p>

        {highlights.length > 0 && (
          <div className="feature-highlights">
            {highlights.map((h, i) => {
              const HIcon = Icon[h.icon];
              return (
                <div key={i} className="feature-highlight-card" style={{ animationDelay: `${i * 0.1}s` }}>
                  <div className="fh-icon"><HIcon /></div>
                  <div className="fh-body">
                    <div className="fh-title">{h.title}</div>
                    <div className="fh-desc">{h.desc}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {isAgents && (
          <div className="agents-detail-section">
            <h2>{t.agents_page_title}</h2>
            <div className="agents-detail-list">
              {AGENTS.map(a => (
                <div key={a.id} className="agent-detail-card">
                  <div className="agent-detail-card-icon agent-detail-card-emoji" style={{ color: a.color }}>{a.emoji}</div>
                  <div className="agent-detail-card-body">
                    <div className="agent-detail-card-header">
                      <span className="agent-detail-card-name">{lang === "en" ? a.name_en : a.name_de}</span>
                      <span className="status-badge active">{t.active_label}</span>
                    </div>
                    <p className="agent-detail-card-hint">{lang === "en" ? a.hint_en : a.hint_de}</p>
                    <p className="agent-detail-card-long">{lang === "en" ? a.long_en : a.long_de}</p>
                  </div>
                </div>
              ))}
            </div>
            <p className="agents-more-note">{t.agents_more}</p>
          </div>
        )}

        <button className="landing-btn-primary" onClick={() => navigate("/c")} type="button">
          {t.try_free} <Icon.ArrowRight />
        </button>
      </section>

      {isAgents && <DemoPreview t={t} lang={lang} />}
    </div>
  );
}

/* ----------------------------------------------------------
   Landing page — xera-app.com/
   ---------------------------------------------------------- */

function useScrollReveal() {
  React.useEffect(() => {
    const els = document.querySelectorAll(".reveal");
    if (!els.length) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add("visible"); io.unobserve(e.target); } });
    }, { threshold: 0.08 });
    els.forEach(el => io.observe(el));
    return () => io.disconnect();
  }, []);
}

function TypingTagline({ phrases }) {
  const [idx, setIdx] = useState(0);
  const [text, setText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const phraseRef = useRef(phrases[0]);
  useEffect(() => {
    phraseRef.current = phrases[idx];
  }, [idx, phrases]);

  useEffect(() => {
    let timeout;
    const tick = () => {
      const full = phraseRef.current;
      if (!deleting) {
        if (text.length < full.length) {
          setText(full.slice(0, text.length + 1));
          timeout = setTimeout(tick, 45);
        } else {
          timeout = setTimeout(() => setDeleting(true), 2200);
        }
      } else {
        if (text.length > 0) {
          setText(full.slice(0, text.length - 1));
          timeout = setTimeout(tick, 22);
        } else {
          setDeleting(false);
          setIdx(i => (i + 1) % phrases.length);
        }
      }
    };
    timeout = setTimeout(tick, 80);
    return () => clearTimeout(timeout);
  }, [text, deleting]);

  return (
    <span className="typing-tagline">
      {text}<span className="typing-cursor">|</span>
    </span>
  );
}

function CountUp({ to, decimals = 0, duration = 1400, prefix = "", suffix = "" }) {
  const [val, setVal] = useState(0);
  const ref = useRef(null);
  const startedRef = useRef(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setVal(to);
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting && !startedRef.current) {
          startedRef.current = true;
          const t0 = performance.now();
          const tick = (now) => {
            const p = Math.min((now - t0) / duration, 1);
            const eased = 1 - Math.pow(1 - p, 3);
            setVal(to * eased);
            if (p < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
          io.disconnect();
        }
      });
    }, { threshold: 0.4 });
    io.observe(el);
    return () => io.disconnect();
  }, [to, duration]);
  return <span ref={ref} className="countup">{prefix}{val.toFixed(decimals)}{suffix}</span>;
}

function HeroVisual({ lang }) {
  const rows = [
    { cls: "big", name: "Big Brain", model: "Qwen3-Coder-30B", val: 36.4, dec: 1, pct: 46, approx: false },
    { cls: "fast", name: "Fast Brain", model: "Gemma 4 E2B", val: 80, dec: 0, pct: 100, approx: true },
    { cls: "code", name: "Mini Brain", model: "Qwen3-4B", val: 45, dec: 0, pct: 56, approx: false },
  ];
  return (
    <div className="hero-visual">
      <div className="hero-visual-card">
        <div className="hv-head">
          <span className="hv-live-dot" />
          <span className="hv-head-title">GPU-Cluster</span>
          <span className="hv-head-meta">5x P4000 · 40 GB VRAM</span>
        </div>
        {rows.map(r => (
          <div key={r.cls} className="hv-row">
            <div className="hv-row-top">
              <span className={"brain-badge brain-" + r.cls}>{r.name}</span>
              <span className="hv-model">{r.model}</span>
              <span className="hv-speed"><CountUp to={r.val} decimals={r.dec} prefix={r.approx ? "~" : ""} /> t/s</span>
            </div>
            <div className="hv-bar"><div className={"hv-fill hv-fill-" + r.cls} style={{ "--w": r.pct + "%" }} /></div>
          </div>
        ))}
        <div className="hv-foot">
          <span>🖼️ Moondream2 · Vision</span>
          <span>🔍 SearXNG · Web</span>
          <span>📚 ChromaDB · RAG</span>
        </div>
      </div>
    </div>
  );
}

function AgentOrbit() {
  const ring1 = ["⌨️", "🌐", "🔍", "🛡️", "🚀", "🐳"];
  const ring2 = ["✍️", "🐍", "🌿", "📚", "🖥️", "📊", "💾", "📧", "📅", "💰"];
  return (
    <div className="orbit-wrap" aria-hidden="true">
      <div className="orbit-glow" />
      <div className="orbit-guide orbit-guide-1" />
      <div className="orbit-guide orbit-guide-2" />
      <div className="orbit-center">
        <div className="orbit-center-pulse" />
        <XMark size={52} radius={15} />
      </div>
      <div className="orbit-ring orbit-ring-1">
        {ring1.map((e, i) => {
          const a = i * (360 / ring1.length);
          return (
            <span key={i} className="orbit-icon" style={{ transform: `rotate(${a}deg) translateX(var(--orbit-r1)) rotate(${-a}deg)` }}>
              <span className="orbit-icon-inner orbit-inner-1">{e}</span>
            </span>
          );
        })}
      </div>
      <div className="orbit-ring orbit-ring-2">
        {ring2.map((e, i) => {
          const a = i * (360 / ring2.length);
          return (
            <span key={i} className="orbit-icon" style={{ transform: `rotate(${a}deg) translateX(var(--orbit-r2)) rotate(${-a}deg)` }}>
              <span className="orbit-icon-inner orbit-inner-2">{e}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

function TerminalDemo({ lang }) {
  const script = lang === "de" ? [
    { k: "cmd", text: 'xera "erstelle ein backup-script fuer /opt"' },
    { k: "dim", text: "◆ Big Brain · CLI Master Agent" },
    { k: "tool", text: "→ write_file  backup.sh" },
    { k: "ok", text: "✓ backup.sh erstellt — 42 Zeilen, rsync + Rotation" },
    { k: "cmd", text: 'cat error.log | xera "warum crasht der Service?"' },
    { k: "dim", text: "◆ Fast Brain · Log-Analyse" },
    { k: "ok", text: "✓ Root-Cause gefunden: Port 8080 bereits belegt" },
    { k: "cmd", text: "xera --continue \"fix es\"" },
    { k: "tool", text: "→ str_replace_file  config.yaml" },
    { k: "ok", text: "✓ Port auf 8085 geaendert — Service laeuft" },
  ] : [
    { k: "cmd", text: 'xera "create a backup script for /opt"' },
    { k: "dim", text: "◆ Big Brain · CLI Master Agent" },
    { k: "tool", text: "→ write_file  backup.sh" },
    { k: "ok", text: "✓ backup.sh created — 42 lines, rsync + rotation" },
    { k: "cmd", text: 'cat error.log | xera "why does the service crash?"' },
    { k: "dim", text: "◆ Fast Brain · log analysis" },
    { k: "ok", text: "✓ Root cause found: port 8080 already in use" },
    { k: "cmd", text: "xera --continue \"fix it\"" },
    { k: "tool", text: "→ str_replace_file  config.yaml" },
    { k: "ok", text: "✓ Port changed to 8085 — service running" },
  ];
  const [step, setStep] = useState(0);
  const [chars, setChars] = useState(0);
  useEffect(() => { setStep(0); setChars(0); }, [lang]);
  useEffect(() => {
    const line = script[step];
    if (!line) {
      const tm = setTimeout(() => { setStep(0); setChars(0); }, 4200);
      return () => clearTimeout(tm);
    }
    if (line.k === "cmd") {
      if (chars < line.text.length) {
        const tm = setTimeout(() => setChars(c => c + 1), 34);
        return () => clearTimeout(tm);
      }
      const tm = setTimeout(() => { setStep(s => s + 1); setChars(0); }, 480);
      return () => clearTimeout(tm);
    }
    const tm = setTimeout(() => { setStep(s => s + 1); setChars(0); }, 620);
    return () => clearTimeout(tm);
  }, [step, chars, lang]);
  const done = script.slice(0, step);
  const current = script[step];
  return (
    <div className="term-window">
      <div className="term-titlebar">
        <div className="demo-dots">
          <span className="demo-dot demo-dot-r" /><span className="demo-dot demo-dot-y" /><span className="demo-dot demo-dot-g" />
        </div>
        <span className="term-titlebar-text">xera-code — zsh</span>
        <span className="term-pro-badge"><Icon.Crown /> PRO</span>
      </div>
      <div className="term-body">
        {done.map((l, i) => (
          <div key={i} className={"term-line term-" + l.k}>
            {l.k === "cmd" && <span className="term-prompt">$ </span>}{l.text}
          </div>
        ))}
        {current && current.k === "cmd" && (
          <div className="term-line term-cmd">
            <span className="term-prompt">$ </span>{current.text.slice(0, chars)}<span className="term-cursor" />
          </div>
        )}
        {!current && <div className="term-line term-cmd"><span className="term-prompt">$ </span><span className="term-cursor" /></div>}
      </div>
    </div>
  );
}

const FAQ_ITEMS = {
  de: [
    { q: "Ist Xera AI wirklich 100 % lokal?", a: "Ja. Alle Modelle laufen auf einem eigenen bare-metal GPU-Server mit 5x NVIDIA Quadro P4000. Kein einziger API-Call geht an OpenAI, Anthropic oder einen anderen Cloud-Anbieter — auch Web-Suche (SearXNG) und Knowledge Base (ChromaDB) sind selbst gehostet." },
    { q: "Welche Modelle laufen im Hintergrund?", a: "Drei Sprachmodelle parallel: Big Brain (Qwen3-Coder-30B) fuer komplexe Aufgaben, Fast Brain (Gemma 4 E2B) mit Vision & Audio, Mini Brain (Qwen3-4B) fuer leichte Anfragen. Dazu Moondream2 als Vision-Service fuer Bildbeschreibungen." },
    { q: "Was koennen die Agents?", a: "35 spezialisierte Agents mit 27 Tools: Code schreiben und debuggen, Web-Recherche mit Quellen, PDF/Word/Excel-Dokumente erstellen, Python ausfuehren, Git bedienen, Docker verwalten und mehr. Ein Orchestrator waehlt automatisch den passenden Agenten — komplexe Aufgaben laufen parallel." },
    { q: "Wie sicher ist das System?", a: "Jede Aktion wird nach Risiko klassifiziert. Destruktive Befehle werden blockiert, kritische brauchen eine explizite Genehmigung im Chat, und ein Kill-Switch stoppt laufende Agents sofort. Die Verbindung laeuft ueber HTTPS, der Reverse Proxy steht in einer isolierten DMZ." },
    { q: "Was ist Xera Pro?", a: "Mit der Xera-Pro-Rolle auf unserem Discord gibt es unlimitierte Prompts, alle Agents und Zugriff auf die Xera Code CLI im Terminal. Ohne Anmeldung kannst du 5 Prompts gratis testen." },
    { q: "Kann ich Xera im Terminal nutzen?", a: "Ja — Xera Code bringt das komplette Agenten-System in die Shell: Dateien lesen und schreiben direkt auf deinem Rechner, Sessions fortsetzen, Pipes und stdin, Brain-Auswahl per Flag. Exklusiv fuer Xera Pro." },
  ],
  en: [
    { q: "Is Xera AI really 100% local?", a: "Yes. All models run on a dedicated bare-metal GPU server with 5x NVIDIA Quadro P4000. Not a single API call goes to OpenAI, Anthropic or any other cloud provider — web search (SearXNG) and the knowledge base (ChromaDB) are self-hosted too." },
    { q: "Which models run under the hood?", a: "Three language models in parallel: Big Brain (Qwen3-Coder-30B) for complex tasks, Fast Brain (Gemma 4 E2B) with vision & audio, Mini Brain (Qwen3-4B) for light requests. Plus Moondream2 as a vision service for image descriptions." },
    { q: "What can the agents do?", a: "35 specialised agents with 27 tools: write and debug code, research the web with sources, create PDF/Word/Excel documents, execute Python, drive Git, manage Docker and more. An orchestrator picks the right agent automatically — complex tasks run in parallel." },
    { q: "How secure is the system?", a: "Every action is risk-classified. Destructive commands are blocked, critical ones require explicit approval in chat, and a kill switch stops running agents instantly. The connection uses HTTPS and the reverse proxy sits in an isolated DMZ." },
    { q: "What is Xera Pro?", a: "The Xera Pro role on our Discord unlocks unlimited prompts, all agents and access to the Xera Code CLI in your terminal. Without signing up you can try 5 prompts for free." },
    { q: "Can I use Xera in the terminal?", a: "Yes — Xera Code brings the full agent system to your shell: read and write files directly on your machine, resume sessions, pipes and stdin, brain selection via flag. Exclusive to Xera Pro." },
  ],
};

function FAQSection({ t, lang }) {
  const items = FAQ_ITEMS[lang] || FAQ_ITEMS.de;
  const [open, setOpen] = useState(0);
  return (
    <section className="landing-faq reveal">
      <h2 className="landing-section-title">{t.faq_title}</h2>
      <div className="faq-list">
        {items.map((it, i) => (
          <div key={i} className={"faq-item" + (open === i ? " open" : "")}>
            <button type="button" className="faq-q" onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}>
              <span>{it.q}</span>
              <span className="faq-chevron"><Icon.ChevronDown /></span>
            </button>
            <div className="faq-a"><p>{it.a}</p></div>
          </div>
        ))}
      </div>
    </section>
  );
}

function LandingPage({ navigate, theme, setTheme, openSettings, config, t }) {
  useScrollReveal();
  const lang = config.language || "de";

  const bento = lang === "de" ? [
    { span: 3, iconKey: "Brain", title: "Big Brain", sub: "Qwen3-Coder-30B · 36.4 t/s", desc: "Komplexe Fragen, Code und tiefe Analysen — auf 3 GPUs mit 128K Context.", href: "/fully-local", featured: true },
    { span: 3, iconKey: "Robot", title: "35 Agents", sub: "27 Tools · Parallel-Ausfuehrung", desc: "Ein Orchestrator routet jede Anfrage automatisch an den passenden Spezialisten.", href: "/smart-agents", featured: true, isNew: true },
    { span: 2, iconKey: "Zap", title: "Fast Brain", sub: "Gemma 4 E2B · ~80 t/s", desc: "Vision & Audio — Bilder und Dokumente blitzschnell verstehen.", href: "/lightning-fast" },
    { span: 2, iconKey: "Cpu", title: "Mini Brain", sub: "Qwen3-4B · 45 t/s", desc: "Leichte Aufgaben mit minimalen Ressourcen — sofort da.", href: "/lightning-fast" },
    { span: 2, iconKey: "Search", title: "Web-Suche", sub: "SearXNG lokal", desc: "Aktuelle Antworten mit Quellen-Links — ohne Tracking.", href: "/smart-agents" },
    { span: 3, iconKey: "Doc", title: "Dokumente erstellen", sub: "PDF · Word · Excel", desc: "Professionelle Dokumente mit Branding direkt im Chat generieren — inklusive Live-Vorschau und Download.", href: "/smart-agents", isNew: true },
    { span: 3, iconKey: "Sparkle", title: "Bild-Erkennung", sub: "Moondream2 Vision", desc: "Bilder einfuegen oder hochladen — Xera beschreibt, analysiert und beantwortet Fragen dazu.", href: "/lightning-fast", isNew: true },
    { span: 2, iconKey: "Mic", title: "Spracheingabe", sub: "Web Speech API", desc: "Sprechen statt tippen — direkt im Browser, ohne Server.", href: "/lightning-fast" },
    { span: 2, iconKey: "History", title: "Self-Learning", sub: "Kontext-Gedaechtnis", desc: "Xera merkt sich, woran du arbeitest — und wird mit jeder Session besser.", href: "/smart-agents", isNew: true },
    { span: 2, iconKey: "Globe", title: "RAG Knowledge Base", sub: "ChromaDB · 500+ Chunks", desc: "Semantische Suche ueber die eigene Dokumentation — offline.", href: "/smart-agents" },
    { span: 3, iconKey: "Code", title: "Xera Code CLI", sub: "Terminal · Xera Pro", desc: "Das komplette Agenten-System in der Shell — mit lokalen Datei-Tools und Sessions.", anchor: "cli-section", isNew: true },
    { span: 3, iconKey: "Shield", title: "100% Privat", sub: "Zero Telemetrie", desc: "Kein API-Call verlaesst dein Netzwerk. Alle Daten auf eigener Hardware, in eigener Hand.", href: "/private-secure" },
  ] : [
    { span: 3, iconKey: "Brain", title: "Big Brain", sub: "Qwen3-Coder-30B · 36.4 t/s", desc: "Complex questions, code and deep analysis — on 3 GPUs with 128K context.", href: "/fully-local", featured: true },
    { span: 3, iconKey: "Robot", title: "35 Agents", sub: "27 tools · parallel execution", desc: "One orchestrator automatically routes every request to the right specialist.", href: "/smart-agents", featured: true, isNew: true },
    { span: 2, iconKey: "Zap", title: "Fast Brain", sub: "Gemma 4 E2B · ~80 t/s", desc: "Vision & audio — understand images and documents blazing fast.", href: "/lightning-fast" },
    { span: 2, iconKey: "Cpu", title: "Mini Brain", sub: "Qwen3-4B · 45 t/s", desc: "Light tasks with minimal resources — instantly there.", href: "/lightning-fast" },
    { span: 2, iconKey: "Search", title: "Web Search", sub: "Local SearXNG", desc: "Current answers with source links — no tracking.", href: "/smart-agents" },
    { span: 3, iconKey: "Doc", title: "Create Documents", sub: "PDF · Word · Excel", desc: "Generate professional branded documents right in the chat — with live preview and download.", href: "/smart-agents", isNew: true },
    { span: 3, iconKey: "Sparkle", title: "Image Recognition", sub: "Moondream2 Vision", desc: "Paste or upload images — Xera describes, analyses and answers questions about them.", href: "/lightning-fast", isNew: true },
    { span: 2, iconKey: "Mic", title: "Voice Input", sub: "Web Speech API", desc: "Talk instead of typing — right in the browser, no server.", href: "/lightning-fast" },
    { span: 2, iconKey: "History", title: "Self-Learning", sub: "Context memory", desc: "Xera remembers what you're working on — and gets better every session.", href: "/smart-agents", isNew: true },
    { span: 2, iconKey: "Globe", title: "RAG Knowledge Base", sub: "ChromaDB · 500+ chunks", desc: "Semantic search across your own documentation — offline.", href: "/smart-agents" },
    { span: 3, iconKey: "Code", title: "Xera Code CLI", sub: "Terminal · Xera Pro", desc: "The complete agent system in your shell — with local file tools and sessions.", anchor: "cli-section", isNew: true },
    { span: 3, iconKey: "Shield", title: "100% Private", sub: "Zero telemetry", desc: "No API call leaves your network. All data on your own hardware, in your own hands.", href: "/private-secure" },
  ];

  const typingPhrases = lang === "de"
    ? ["100% lokal.", "Keine Cloud.", "35 Agents. 27 Tools.", "Deine Daten. Dein Server.", "Privat & schnell."]
    : ["100% local.", "No cloud.", "35 agents. 27 tools.", "Your data. Your server.", "Private & fast."];

  const heroChips = lang === "de"
    ? ["35 Agents", "27 Tools", "3 Brains + Vision", "0 Cloud"]
    : ["35 agents", "27 tools", "3 brains + vision", "0 cloud"];

  const marqueeItems = lang === "de"
    ? ["100% Lokal", "0 Telemetrie", "35 Agents", "27 Tools", "128K Context", "Big Brain 36.4 t/s", "Fast Brain ~80 t/s", "Mini Brain 45 t/s", "Vision & Audio", "PDF · Word · Excel", "Web-Suche lokal", "Self-Learning", "Parallel Agents", "Xera Code CLI", "RAG Knowledge Base", "Eigene Hardware"]
    : ["100% Local", "0 Telemetry", "35 Agents", "27 Tools", "128K Context", "Big Brain 36.4 t/s", "Fast Brain ~80 t/s", "Mini Brain 45 t/s", "Vision & Audio", "PDF · Word · Excel", "Local Web Search", "Self-Learning", "Parallel Agents", "Xera Code CLI", "RAG Knowledge Base", "Own Hardware"];

  const howSteps = lang === "de" ? [
    { num: "01", icon: Icon.Chat, title: "Frag", desc: "Stell deine Frage — oder lade ein Dokument, ein Bild oder eine Sprachnachricht hoch." },
    { num: "02", icon: Icon.Brain, title: "Orchestriere", desc: "Der Orchestrator waehlt Modell und Agenten automatisch — bei Bedarf mehrere parallel, mit Web-Suche und RAG." },
    { num: "03", icon: Icon.Speed, title: "Antworte", desc: "Die Antwort wird auf dem GPU-Server generiert und in Echtzeit gestreamt — keine Cloud." },
  ] : [
    { num: "01", icon: Icon.Chat, title: "Ask", desc: "Ask your question — or upload a document, image or voice note." },
    { num: "02", icon: Icon.Brain, title: "Orchestrate", desc: "The orchestrator picks model and agents automatically — several in parallel if needed, with web search and RAG." },
    { num: "03", icon: Icon.Speed, title: "Answer", desc: "The response is generated on the GPU server and streamed in real time — no cloud." },
  ];

  const onCardClick = (f) => {
    if (f.anchor) {
      const el = document.getElementById(f.anchor);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    } else if (f.href) {
      navigate(f.href);
    }
  };

  return (
    <div className="landing-page landing-v2 landing-v3">
      <div className="landing-bg">
        <div className="landing-orb landing-orb-1" />
        <div className="landing-orb landing-orb-2" />
        <div className="landing-orb landing-orb-3" />
        <div className="landing-orb landing-orb-4" />
      </div>
      <div className="landing-beam" />
      <div className="landing-aurora" />
      <div className="bg-grid" />

      <nav className="landing-nav">
        <div className="landing-nav-brand">
          <XMark size={28} />
          <span className="landing-nav-name">XERA<span className="accent"> AI</span></span>
        </div>
        <div className="landing-nav-right">
          <ThemeToggle theme={theme} setTheme={setTheme} />
          <button className="landing-nav-login" onClick={() => navigate("/login")} type="button">
            {t.login}
          </button>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="landing-hero landing-hero-v3">
        <div className="hero-left">
          <div className="landing-hero-badge">
            <Icon.Lock /> {t.footer}
          </div>
          <h1 className="landing-hero-h1">{t.landing_hero}</h1>
          <div className="landing-hero-typing">
            <TypingTagline phrases={typingPhrases} />
          </div>
          <p className="landing-hero-sub">{t.landing_sub}</p>
          <div className="landing-hero-btns">
            <button className="landing-btn-primary" onClick={() => navigate("/c")} type="button">
              {t.try_free} <Icon.ArrowRight />
            </button>
            <button className="landing-btn-secondary" onClick={() => navigate("/login")} type="button">
              <Icon.Discord /> {t.discord_login}
            </button>
          </div>
          <div className="hero-chips">
            {heroChips.map((c, i) => (
              <span key={i} className="hero-chip" style={{ animationDelay: `${0.6 + i * 0.12}s` }}><Icon.Check /> {c}</span>
            ))}
          </div>
        </div>
        <HeroVisual lang={lang} />
      </section>

      {/* ── Stats bar (marquee) ── */}
      <div className="landing-stats-bar">
        <div className="landing-stats-track">
          {[...marqueeItems, ...marqueeItems].map((s, i) => (
            <React.Fragment key={i}>
              <span className="landing-stats-bar-item">{s}</span>
              <span className="landing-stats-bar-dot" aria-hidden="true">·</span>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* ── Bento features grid ── */}
      <section className="landing-bento reveal">
        <h2 className="landing-section-title">{lang === "de" ? "Was Xera AI kann" : "What Xera AI can do"}</h2>
        <div className="bento-grid">
          {bento.map((f, i) => {
            const FC = f.iconKey ? Icon[f.iconKey] : null;
            return (
              <div
                key={i}
                className={"bento-card span-" + f.span + (f.featured ? " featured" : "")}
                style={{ animationDelay: `${i * 0.06}s` }}
                onClick={() => onCardClick(f)}
                role="link"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter") onCardClick(f); }}
              >
                {f.isNew && <span className="bento-new">{t.landing_new_badge}</span>}
                <div className="bento-icon">{FC && <FC />}</div>
                <div className="bento-title">{f.title}</div>
                <div className="bento-sub">{f.sub}</div>
                <div className="bento-desc">{f.desc}</div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── Agent orchestra (orbit) ── */}
      <section className="landing-orbit reveal">
        <div className="orbit-layout">
          <AgentOrbit />
          <div className="orbit-text">
            <h2 className="landing-section-title orbit-title">{t.orbit_title}</h2>
            <p className="orbit-desc">{t.orbit_desc}</p>
            <div className="orbit-stats">
              <div className="orbit-stat">
                <span className="orbit-stat-n"><CountUp to={35} /></span>
                <span className="orbit-stat-l">{t.orbit_stat_agents}</span>
              </div>
              <div className="orbit-stat">
                <span className="orbit-stat-n"><CountUp to={27} /></span>
                <span className="orbit-stat-l">{t.orbit_stat_tools}</span>
              </div>
              <div className="orbit-stat">
                <span className="orbit-stat-n">∞</span>
                <span className="orbit-stat-l">{t.orbit_stat_parallel}</span>
              </div>
            </div>
            <button className="landing-btn-secondary orbit-btn" onClick={() => navigate("/smart-agents")} type="button">
              {t.orbit_link} <Icon.ArrowRight />
            </button>
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="landing-howworks-v2 reveal">
        <h2 className="landing-section-title">{t.landing_howworks_title}</h2>
        <div className="landing-howworks-v2-grid">
          {howSteps.map((s, i) => (
            <React.Fragment key={i}>
              <div className="landing-hw-v2-step">
                <div className="landing-hw-v2-num">{s.num}</div>
                <div className="landing-hw-v2-icon"><s.icon /></div>
                <h3 className="landing-hw-v2-title">{s.title}</h3>
                <p className="landing-hw-v2-desc">{s.desc}</p>
              </div>
              {i < howSteps.length - 1 && <div className="landing-hw-v2-connector" />}
            </React.Fragment>
          ))}
        </div>
      </section>

      {/* ── Models ── */}
      <section className="landing-models reveal">
        <h2 className="landing-section-title">{t.landing_dual_title}</h2>
        <p className="landing-models-sub">{t.landing_dual_desc}</p>
        <div className="landing-models-cards">
          <div className="landing-model-card landing-model-big">
            <div className="lmc-badge"><span className="brain-badge brain-big">Big Brain</span></div>
            <div className="lmc-model">Qwen3-Coder-30B-A3B</div>
            <div className="lmc-stats-grid">
              <div><span className="lmc-stat-n">18 GB</span><span className="lmc-stat-l">VRAM</span></div>
              <div><span className="lmc-stat-n"><CountUp to={36.4} decimals={1} /></span><span className="lmc-stat-l">t/s</span></div>
              <div><span className="lmc-stat-n">128K</span><span className="lmc-stat-l">Context</span></div>
              <div><span className="lmc-stat-n">3x</span><span className="lmc-stat-l">GPU</span></div>
            </div>
            <div className="lmc-tags">
              <span>Code</span><span>Analyse</span><span>Recherche</span><span>Komplex</span>
            </div>
          </div>
          <div className="landing-model-card landing-model-fast">
            <div className="lmc-badge"><span className="brain-badge brain-fast">Fast Brain</span></div>
            <div className="lmc-model">Gemma 4 E2B</div>
            <div className="lmc-stats-grid">
              <div><span className="lmc-stat-n">~7 GB</span><span className="lmc-stat-l">VRAM</span></div>
              <div><span className="lmc-stat-n"><CountUp to={80} prefix="~" /></span><span className="lmc-stat-l">t/s</span></div>
              <div><span className="lmc-stat-n">128K</span><span className="lmc-stat-l">Context</span></div>
              <div><span className="lmc-stat-n">E2B</span><span className="lmc-stat-l">Arch</span></div>
            </div>
            <div className="lmc-tags">
              <span>Vision</span><span>Audio</span><span>Schnell</span><span>Chat</span>
            </div>
          </div>
          <div className="landing-model-card landing-model-code">
            <div className="lmc-badge"><span className="brain-badge brain-code">Mini Brain</span></div>
            <div className="lmc-model">Qwen3-4B</div>
            <div className="lmc-stats-grid">
              <div><span className="lmc-stat-n">2.4 GB</span><span className="lmc-stat-l">VRAM</span></div>
              <div><span className="lmc-stat-n"><CountUp to={45} /></span><span className="lmc-stat-l">t/s</span></div>
              <div><span className="lmc-stat-n">32K</span><span className="lmc-stat-l">Context</span></div>
              <div><span className="lmc-stat-n">4B</span><span className="lmc-stat-l">Params</span></div>
            </div>
            <div className="lmc-tags">
              <span>Schnell</span><span>Leicht</span><span>Smalltalk</span><span>FAQ</span>
            </div>
          </div>
        </div>
        <div className="landing-vision-strip reveal">
          <span className="vision-strip-icon">🖼️</span>
          <span className="vision-strip-name">Moondream2</span>
          <span className="vision-strip-desc">{lang === "de" ? "Vision-Service · Bildbeschreibung & Analyse · 1.8B" : "Vision service · image description & analysis · 1.8B"}</span>
          <span className="vision-strip-badge">{lang === "de" ? "Immer aktiv" : "Always on"}</span>
        </div>
      </section>

      <DemoPreview t={t} lang={config.language} />

      {/* ── CLI / Terminal ── */}
      <section className="landing-cli reveal" id="cli-section">
        <div className="cli-layout">
          <div className="cli-text">
            <h2 className="landing-section-title cli-title">{t.cli_title}</h2>
            <p className="cli-desc">{t.cli_desc}</p>
            <div className="cli-pills">
              <span><Icon.Doc /> {t.cli_pill_1}</span>
              <span><Icon.History /> {t.cli_pill_2}</span>
              <span><Icon.Brain /> {t.cli_pill_3}</span>
              <span><Icon.Code /> {t.cli_pill_4}</span>
            </div>
            <div className="cli-pro"><Icon.Crown /> {t.cli_pro_hint}</div>
          </div>
          <TerminalDemo lang={lang} />
        </div>
      </section>

      {/* ── Privacy section ── */}
      <section className="landing-privacy reveal">
        <div className="landing-privacy-card">
          <div className="landing-privacy-icon"><Icon.Shield /></div>
          <h2>{lang === "de" ? "Deine Privatsphäre. Garantiert." : "Your privacy. Guaranteed."}</h2>
          <p>{lang === "de"
            ? "Kein einziger API-Call verlässt dein Netzwerk. Alle Chats, alle Modelle, alle Daten — auf deiner eigenen Hardware. Kein Tracking, kein Logging, kein Cloud-Anbieter, der deine Prompts liest."
            : "Not a single API call leaves your network. All chats, all models, all data — on your own hardware. No tracking, no logging, no cloud provider reading your prompts."
          }</p>
          <div className="landing-privacy-pills">
            <span><Icon.Lock /> HTTPS End-to-End</span>
            <span><Icon.Shield /> Isolated DMZ</span>
            <span><Icon.Server /> SQLite Local</span>
            <span><Icon.Globe /> VLAN-Segmentierung</span>
            <span><Icon.Zap /> Zero Telemetry</span>
          </div>
        </div>
      </section>

      {/* ── Team ── */}
      <section className="landing-about reveal">
        <h2 className="landing-section-title">{t.landing_team_title}</h2>
        <div className="landing-about-grid">
          <div className="landing-about-card">
            <div className="landing-about-avatar">MR</div>
            <div>
              <h3>Miguel Rodriguez</h3>
              <p>{t.landing_about_miguel}</p>
            </div>
          </div>
          <div className="landing-about-card">
            <div className="landing-about-avatar">SB</div>
            <div>
              <h3>Sascha Bodmer</h3>
              <p>{t.landing_about_sascha}</p>
            </div>
          </div>
        </div>
      </section>

      <FAQSection t={t} lang={lang} />

      <footer className="landing-footer">
        <span>XERA AI v3.1</span>
        <span className="dot">&bull;</span>
        <span>35 Agents · 27 Tools</span>
        <span className="dot">&bull;</span>
        <span>{t.no_telemetry}</span>
        <span className="dot">&bull;</span>
        <span>Qwen3-30B · Gemma 4 E2B · Qwen3-4B · Moondream2</span>
        <span className="dot">&bull;</span>
        <a href="https://github.com/Mentox07/xera-ai" target="_blank" rel="noopener" className="landing-footer-link">GitHub</a>
      </footer>
    </div>
  );
}

/* ----------------------------------------------------------
   Login page — xera-app.com/login
   ---------------------------------------------------------- */

function LoginPage({ navigate, theme, setTheme, openSettings, t }) {
  return (
    <div className="login-page">
      <div className="bg-grid" />
      <div className="topbar">
        <SettingsButton onClick={openSettings} />
        <ThemeToggle theme={theme} setTheme={setTheme} />
      </div>

      <div className="login-card">
        <div className="brand">
          <Wordmark />
        </div>

        <p className="login-pitch">{t.pitch}</p>

        <div className="feature-grid">
          <div className="feature"><Icon.Zap /><span>{t.f_free}</span></div>
          <div className="feature"><Icon.Sparkle /><span>{t.f_pro}</span></div>
          <div className="feature"><Icon.Cpu /><span>{t.f_stream}</span></div>
          <div className="feature"><Icon.History /><span>{t.f_history}</span></div>
        </div>

        <a href="/auth/login" className="discord-btn">
          <Icon.Discord />
          {t.discord_login}
        </a>

        <div className="divider">{t.or_terminal}</div>

        <button className="guest-btn" onClick={() => navigate("/c")} type="button">
          <Icon.Zap />
          {t.try_free} — 5 {t.prompts}
        </button>

        <p className="login-footer">
          <Icon.Lock /> &nbsp;{t.footer} <span className="dot">&bull;</span> {t.no_telemetry}
        </p>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------
   Markdown renderer
   ---------------------------------------------------------- */

function CodeBlock({ lang, code }) {
  const ref = useRef(null);
  const [copied, setCopied] = useState(false);
  const [pyRunning, setPyRunning] = useState(false);
  const [pyResult, setPyResult] = useState(null);

  useEffect(() => {
    if (ref.current && window.hljs) {
      ref.current.removeAttribute("data-highlighted");
      window.hljs.highlightElement(ref.current);
    }
  }, [code]);

  const copy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const runPython = async () => {
    setPyRunning(true);
    setPyResult(null);
    try {
      const resp = await fetch("/api/python", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      const data = await resp.json();
      setPyResult(data);
    } catch (e) {
      setPyResult({ type: "error", message: L("Netzwerkfehler: ", "Network error: ") + e.message });
    } finally {
      setPyRunning(false);
    }
  };

  const isPython = /^py(thon)?3?$/i.test(lang);

  return (
    <div className="code-block">
      <div className="code-header">
        <span className="code-lang">{lang || "code"}</span>
        <div className="code-header-actions">
          {isPython && (
            <button type="button" className={"code-run-btn" + (pyRunning ? " running" : "")} onClick={runPython} disabled={pyRunning}>
              {pyRunning ? <><span className="spinner-tiny" /> {L("Läuft...", "Running...")}</> : <><Icon.Play /> {L("Ausführen", "Run")}</>}
            </button>
          )}
          <button type="button" className="code-copy-btn" onClick={copy}>
            {copied ? <><Icon.Check /> {L("Kopiert", "Copied")}</> : <><Icon.Copy /> {L("Kopieren", "Copy")}</>}
          </button>
        </div>
      </div>
      <pre><code ref={ref} className={lang ? `language-${lang}` : ""}>{code}</code></pre>
      {pyResult && (
        <div className={"py-result py-result-" + pyResult.type}>
          {pyResult.type === "image" && (
            <img src={"data:image/png;base64," + pyResult.data} alt="Python output" className="py-output-img" />
          )}
          {pyResult.type === "text" && (
            <pre className="py-output-text">{pyResult.output}</pre>
          )}
          {pyResult.type === "error" && (
            <pre className="py-output-error">{pyResult.message}</pre>
          )}
        </div>
      )}
    </div>
  );
}

function SourcesBlock({ sources }) {
  const [open, setOpen] = useState(false);
  if (!sources.length) return null;
  return (
    <div className="sources-block">
      <button type="button" className="sources-toggle" onClick={() => setOpen(!open)}>
        <Icon.Web />
        <span>{sources.length} {sources.length === 1 ? L("Quelle", "source") : L("Quellen", "sources")}</span>
        <span className={"sources-chevron" + (open ? " open" : "")}><Icon.ChevronDown /></span>
      </button>
      {open && (
        <div className="sources-list">
          {sources.map((s, i) => (
            <a key={i} href={s.url} target="_blank" rel="noopener noreferrer" className="source-link">
              <span className="source-num">{i + 1}</span>
              <span className="source-title">{s.title || s.url}</span>
              <Icon.ExternalLink />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function parseSourcesFromContent(text) {
  const re = /\n+(?:---\n)?Quellen:\n/;
  const match = re.exec(text);
  if (!match) return { content: text, sources: [] };
  const content = text.slice(0, match.index);
  const sourcesRaw = text.slice(match.index + match[0].length);
  const sources = [];
  for (const line of sourcesRaw.split("\n")) {
    const m = line.match(/^\[(\d+)\]\s*(.+?)\s*[—\-]\s*(https?:\/\/\S+)/);
    if (m) sources.push({ title: m[2].trim(), url: m[3].trim() });
  }
  return { content, sources };
}

function renderLatexBlock(tex, key) {
  if (!window.katex) return <code key={key}>{tex}</code>;
  try {
    const html = window.katex.renderToString(tex, { throwOnError: false, displayMode: true });
    return <div key={key} className="katex-block" dangerouslySetInnerHTML={{ __html: html }} />;
  } catch { return <code key={key}>{tex}</code>; }
}

function renderLatexInline(tex) {
  if (!window.katex) return <code>{tex}</code>;
  try {
    const html = window.katex.renderToString(tex, { throwOnError: false, displayMode: false });
    return <span className="katex-inline" dangerouslySetInnerHTML={{ __html: html }} />;
  } catch { return <code>{tex}</code>; }
}

// Normalize all LaTeX delimiters to $$ and $ before splitting
function normalizeLatex(text) {
  // \[...\] → $$...$$
  text = text.replace(/\\\[([\s\S]*?)\\\]/g, (_, m) => "$$" + m + "$$");
  // \(...\) → $...$
  text = text.replace(/\\\(([\s\S]*?)\\\)/g, (_, m) => "$" + m + "$");
  return text;
}

function isLetterFormat(text) {
  return /Sehr geehrte|Dear |Mit freundlichen Grüssen|Mit freundlichen Grüßen|Sincerely|Yours sincerely|Freundliche Grüsse|Freundliche Grüße|Hochachtungsvoll|Kind regards/i.test(text);
}

function renderMarkdownTable(tableText, key) {
  const lines = tableText.split("\n").filter(l => l.trim() && l.includes("|"));
  if (lines.length < 2) return null;
  const parseRowSimple = (line) => {
    const cells = line.split("|");
    // remove first and last if empty (from leading/trailing |)
    const trimmed = cells.map(c => c.trim());
    if (trimmed[0] === "") trimmed.shift();
    if (trimmed[trimmed.length - 1] === "") trimmed.pop();
    return trimmed;
  };

  const header = parseRowSimple(lines[0]);
  // lines[1] is the separator row (---|---)
  const body = lines.slice(2).map(l => parseRowSimple(l));

  return (
    <div key={key} className="md-table-wrap">
      <table className="md-table">
        <thead>
          <tr>{header.map((h, i) => <th key={i}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr key={ri}>{row.map((cell, ci) => <td key={ci}>{cell}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderMarkdown(text, enableLatex) {
  if (!text) return [];

  // Normalize LaTeX delimiters
  if (enableLatex) text = normalizeLatex(text);

  // Check for letter format
  const isLetter = isLetterFormat(text);

  const blocks = [];
  // Split on $$...$$ first (display math)
  const latexParts = enableLatex ? text.split(/(\$\$[\s\S]*?\$\$)/) : [text];

  latexParts.forEach((segment, si) => {
    if (enableLatex && segment.startsWith("$$") && segment.endsWith("$$") && segment.length > 4) {
      blocks.push(renderLatexBlock(segment.slice(2, -2).trim(), "latex-" + si));
      return;
    }

    // Split on fenced code blocks
    const parts = segment.split(/```/);
    parts.forEach((part, idx) => {
      if (idx % 2 === 1) {
        // Code block
        const firstLineEnd = part.indexOf("\n");
        const lang = firstLineEnd >= 0 ? part.slice(0, firstLineEnd).trim() : "";
        const code = firstLineEnd >= 0 ? part.slice(firstLineEnd + 1) : part;
        blocks.push(<CodeBlock key={"c" + si + "-" + idx} lang={lang} code={code} />);
      } else {
        // Check for markdown table blocks
        const paragraphs = part.split(/\n\n+/);
        paragraphs.forEach((p, pi) => {
          if (!p.trim()) return;

          // Markdown table detection: lines with | and a separator row
          const pLines = p.split("\n").filter(l => l.trim());
          const isTable = pLines.length >= 2 &&
            pLines[0].includes("|") &&
            pLines[1] && /^\s*\|?[\s\-:|]+\|/.test(pLines[1]);

          if (isTable) {
            const tbl = renderMarkdownTable(p, "tbl-" + si + "-" + idx + "-" + pi);
            if (tbl) { blocks.push(tbl); return; }
          }

          // Heading detection
          if (/^#{1,6}\s/.test(p.trim())) {
            const level = p.match(/^(#{1,6})\s/)[1].length;
            const content = p.replace(/^#{1,6}\s/, "");
            const Tag = "h" + level;
            blocks.push(<Tag key={"h" + si + "-" + idx + "-" + pi} className={"md-h md-h" + level}>{renderInline(content, enableLatex)}</Tag>);
            return;
          }

          // Blockquote
          if (p.split("\n").every(l => l.startsWith(">"))) {
            const cleaned = p.split("\n").map(l => l.replace(/^>\s?/, "")).join("\n");
            blocks.push(
              <blockquote key={"q" + si + "-" + idx + "-" + pi} className="md-blockquote">{cleaned}</blockquote>
            );
            return;
          }

          // Unordered list
          const listLines = p.split("\n");
          if (listLines.every(l => /^[\*\-]\s/.test(l.trim()) || !l.trim())) {
            const items = listLines.filter(l => l.trim()).map(l => l.replace(/^[\*\-]\s/, "").trim());
            blocks.push(
              <ul key={"ul" + si + "-" + idx + "-" + pi} className="md-list">
                {items.map((item, ii) => <li key={ii}>{renderInline(item, enableLatex)}</li>)}
              </ul>
            );
            return;
          }

          // Ordered list
          if (listLines.every(l => /^\d+\.\s/.test(l.trim()) || !l.trim())) {
            const items = listLines.filter(l => l.trim()).map(l => l.replace(/^\d+\.\s/, "").trim());
            if (items.length > 0) {
              blocks.push(
                <ol key={"ol" + si + "-" + idx + "-" + pi} className="md-list md-olist">
                  {items.map((item, ii) => <li key={ii}>{renderInline(item, enableLatex)}</li>)}
                </ol>
              );
              return;
            }
          }

          blocks.push(<p key={"p" + si + "-" + idx + "-" + pi}>{renderInline(p, enableLatex)}</p>);
        });
      }
    });
  });

  if (isLetter && blocks.length > 0) {
    return [<div key="letter" className="letter-format">{blocks}</div>];
  }
  return blocks;
}

function renderInline(text, enableLatex) {
  const out = [];
  // Pattern: links [text](url), inline code, bold, italic, inline math ($...$), strikethrough
  const pattern = enableLatex
    ? /(\[[^\]]+\]\([^)]+\)|`[^`]+`|\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*|~~[^~]+~~|\$[^$\n]+\$)/g
    : /(\[[^\]]+\]\([^)]+\)|`[^`]+`|\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*|~~[^~]+~~)/g;
  let last = 0, m, k = 0;
  while ((m = pattern.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("[")) {
      const linkText = tok.match(/\[([^\]]+)\]/)?.[1] || tok;
      const href = tok.match(/\(([^)]+)\)/)?.[1] || "#";
      const isDownload = href.includes("/api/download/");
      const isExternal = href.startsWith("http");
      out.push(
        <a key={k++} href={href}
           className="md-link"
           target={isExternal ? "_blank" : undefined}
           rel={isExternal ? "noopener noreferrer" : undefined}
           download={isDownload ? href.split("/").pop() : undefined}>
          {linkText}
        </a>
      );
    }
    else if (tok.startsWith("`")) out.push(<code key={k++} className="md-code">{tok.slice(1, -1)}</code>);
    else if (tok.startsWith("***")) out.push(<strong key={k++}><em>{tok.slice(3, -3)}</em></strong>);
    else if (tok.startsWith("**")) out.push(<strong key={k++} style={{ fontWeight: 600 }}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("*")) out.push(<em key={k++}>{tok.slice(1, -1)}</em>);
    else if (tok.startsWith("~~")) out.push(<del key={k++}>{tok.slice(2, -2)}</del>);
    else if (enableLatex && tok.startsWith("$")) out.push(<span key={k++}>{renderLatexInline(tok.slice(1, -1))}</span>);
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function ToolCallBlock({ call, t, onApprove }) {
  const [expanded, setExpanded] = useState(false);
  const isRunning = call.status === "running";
  const isDone = call.status === "done";
  const isApproval = call.status === "approval";
  const label = call.args?.command || call.args?.path || call.args?.query || call.args?.directory || "";
  const statusClass = isApproval ? " approval" : isDone ? (call.success ? " success" : " error") : " running";
  return (
    <div className={"tool-call" + statusClass}>
      <div className="tool-call-header" onClick={() => isDone && setExpanded(!expanded)}>
        <span className="tool-call-icon">{isApproval ? <Icon.Warning /> : isRunning ? <Icon.CircleDot /> : call.success ? <Icon.Check /> : <Icon.Close />}</span>
        <span className="tool-call-name">{call.name}</span>
        {call.level && <span className={"tool-level-badge " + (call.level || "").toLowerCase()}>{call.level}</span>}
        {label && <code className="tool-call-cmd">{label}</code>}
        {isDone && <span className="tool-call-chevron" style={expanded ? { transform: "rotate(0deg)" } : { transform: "rotate(-90deg)" }}><Icon.ChevronDown /></span>}
        {isRunning && <span className="tool-call-status-text">{t.agent_tool_running}</span>}
      </div>
      {isApproval && (
        <div className="approval-actions">
          <button type="button" className="approve-btn" onClick={() => onApprove(call.actionId, true)}>
            <Icon.Check /> {t.approve || "Genehmigen"}
          </button>
          <button type="button" className="deny-btn" onClick={() => onApprove(call.actionId, false)}>
            <Icon.Close /> {t.deny || "Ablehnen"}
          </button>
        </div>
      )}
      {expanded && call.output && (
        <pre className="tool-call-output">{sanitizeOutput(call.output)}</pre>
      )}
    </div>
  );
}

/* ----------------------------------------------------------
   Document Download Card (inline in chat)
   ---------------------------------------------------------- */

function DocumentCard({ doc }) {
  const ext = (doc.doc_type || doc.filename?.split('.').pop() || "pdf").toLowerCase();
  const iconMap = {
    pdf: "📄", docx: "📝", xlsx: "📊",
    py: "🐍", sh: "⚙️", bash: "⚙️",
    js: "🟨", ts: "🔷", jsx: "⚛️", tsx: "⚛️",
    html: "🌐", css: "🎨",
    json: "📋", yaml: "📋", yml: "📋", toml: "📋",
    md: "📓", markdown: "📓",
    sql: "🗄️", go: "🐹", rs: "🦀",
    java: "☕", cpp: "⚡", c: "⚡",
    ps1: "🪟", conf: "⚙️", ini: "⚙️",
  };
  const icon = iconMap[ext] || "📄";
  const size = doc.size
    ? doc.size < 1024 ? `${doc.size} B`
    : doc.size < 1048576 ? `${(doc.size / 1024).toFixed(1)} KB`
    : `${(doc.size / 1048576).toFixed(1)} MB`
    : "";
  // Strip UUID prefix (8 hex chars + _) and extension for display
  const displayName = (doc.filename || "")
    .replace(/^[0-9a-f]{8}_/, "")
    .replace(/\.[a-z0-9]{1,10}$/i, "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, c => c.toUpperCase());
  return (
    <div className="doc-download-card">
      <div className="doc-card-icon">{icon}</div>
      <div className="doc-card-info">
        <div className="doc-card-name">{displayName || doc.filename}</div>
        {size && <div className="doc-card-meta">{ext.toUpperCase()} · {size}</div>}
        {!size && <div className="doc-card-meta">{ext.toUpperCase()}</div>}
      </div>
      <a className="doc-card-btn" href={doc.url} download={doc.filename}>
        <Icon.Download /> {L("Herunterladen", "Download")}
      </a>
    </div>
  );
}

/* ----------------------------------------------------------
   Brain Switch Confirmation Banner
   ---------------------------------------------------------- */

/* ----------------------------------------------------------
   Agent Selector (Homelab tab)
   ---------------------------------------------------------- */

function AgentSelector({ agents, selectedId, onSelect, activeAgent, agentDelegating, lang }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef(null);
  const searchRef = useRef(null);
  const de = lang === "de";

  useEffect(() => {
    if (!open) { setQuery(""); return; }
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    setTimeout(() => searchRef.current?.focus(), 50);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  useEffect(() => {
    const handler = (e) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const current = selectedId ? agents.find(a => a.id === selectedId) : null;
  const displayAgent = activeAgent || current;
  const filtered = query.trim()
    ? agents.filter(a => a.name.toLowerCase().includes(query.toLowerCase()) || a.description.toLowerCase().includes(query.toLowerCase()))
    : agents;

  const BrainDot = ({ brain }) => <span className={"agent-brain-dot " + brain} title={brain === "big" ? "Big Brain (30B)" : brain === "fast" ? "Fast Brain (8B)" : "Mini Brain (4B)"} />;
  const Chevron = () => (
    <svg className="agent-chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 9l6 6 6-6" />
    </svg>
  );

  return (
    <div className="agent-selector" ref={ref}>
      <button
        type="button"
        className={"agent-selector-btn" + (open ? " open" : "")}
        onClick={() => setOpen(o => !o)}
      >
        {agentDelegating ? (
          <span className="agent-delegating-badge">
            <span style={{ fontSize: 11 }}>🔀</span>
            <span className="agent-delegation-text">{agentDelegating.from} → {agentDelegating.to}</span>
          </span>
        ) : displayAgent ? (
          <span className="agent-active-badge" style={{ color: displayAgent.color }}>
            <span style={{ fontSize: 14 }}>{displayAgent.icon}</span>
            <span className="agent-active-name">{displayAgent.name}</span>
            {activeAgent && <span className="agent-live-dot" />}
          </span>
        ) : (
          <span className="agent-auto-label">
            <span className="agent-auto-icon">⚡</span>
            <span style={{ color: "var(--text-3)" }}>Auto</span>
          </span>
        )}
        <Chevron />
      </button>

      {open && (
        <div className="agent-dropdown">
          {/* Search */}
          <div className="agent-dropdown-search">
            <span className="search-icon">🔍</span>
            <input
              ref={searchRef}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder={de ? "Agent suchen..." : "Search agents..."}
            />
          </div>

          {/* Auto option */}
          {!query && (
            <>
              <button
                type="button"
                className={"agent-option" + (!selectedId ? " selected" : "")}
                onClick={() => { onSelect(null); setOpen(false); }}
              >
                <span className="agent-option-icon">⚡</span>
                <div className="agent-option-body">
                  <span className="agent-option-name" style={{ color: "var(--accent)" }}>Auto</span>
                  <div className="agent-option-meta">
                    <span className="agent-option-desc">{de ? "Besten Agent automatisch wählen" : "Automatically pick best agent"}</span>
                  </div>
                </div>
                {!selectedId && <span className="agent-option-check">✓</span>}
              </button>
              <div className="agent-divider" />
              <div className="agent-section-label">{de ? "Agents" : "Agents"} · {agents.length}</div>
            </>
          )}

          {/* Agent list */}
          {filtered.map(a => (
            <button
              key={a.id}
              type="button"
              className={"agent-option" + (selectedId === a.id ? " selected" : "")}
              onClick={() => { onSelect(a.id); setOpen(false); }}
            >
              <span className="agent-option-icon">{a.icon}</span>
              <div className="agent-option-body">
                <span className="agent-option-name" style={{ color: a.color }}>{a.name}</span>
                <div className="agent-option-meta">
                  <BrainDot brain={a.brain} />
                  <span className="agent-option-desc">{a.description}</span>
                </div>
              </div>
              {selectedId === a.id && <span className="agent-option-check">✓</span>}
            </button>
          ))}

          {filtered.length === 0 && (
            <div style={{ padding: "12px 8px", color: "var(--text-3)", fontSize: 12, textAlign: "center" }}>
              {de ? "Kein Agent gefunden" : "No agent found"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function BrainSwitchBanner({ from, to, onConfirm, onReject, lang }) {
  const de = lang === "de";
  const label = { big: "Big Brain", fast: "Fast Brain", code: "Mini Brain" };
  return (
    <div className="brain-switch-banner">
      <div className="brain-switch-text">
        <span className="brain-switch-icon">⚡</span>
        {de
          ? <>Soll auf <strong>{label[to] || to}</strong> wechseln (aktuell: {label[from] || from}). Bestätigen?</>
          : <>Switch to <strong>{label[to] || to}</strong> (current: {label[from] || from})? Confirm?</>}
      </div>
      <div className="brain-switch-actions">
        <button type="button" className="brain-switch-confirm" onClick={onConfirm}>{de ? "Ja" : "Yes"}</button>
        <button type="button" className="brain-switch-reject" onClick={onReject}>{de ? "Nein" : "No"}</button>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------
   Document Preview Sidebar
   ---------------------------------------------------------- */

const _PREVIEW_EXTS = new Set([
  "py","sh","bash","js","ts","jsx","tsx","html","css","json",
  "yaml","yml","toml","sql","go","rs","java","cpp","c","ps1",
  "conf","ini","md","txt","rb","php","kt","swift","dockerfile",
]);
const _HL_LANG = {
  py:"python", python:"python", sh:"bash", bash:"bash", js:"javascript",
  ts:"typescript", jsx:"javascript", tsx:"typescript", html:"html", css:"css",
  json:"json", yaml:"yaml", yml:"yaml", sql:"sql", go:"go", rs:"rust",
  java:"java", cpp:"cpp", c:"c", ps1:"powershell", toml:"ini", rb:"ruby",
  php:"php", kt:"kotlin", swift:"swift", md:"markdown", dockerfile:"dockerfile",
};

// Logical document identity: strip the random 8-char uid prefix the backend
// adds to every file (e.g. "a1b2c3d4_bericht.pdf" -> "bericht.pdf") so that
// re-creating the same document during iteration is recognised as an update,
// not a new document.
function docLogicalKey(filename) {
  if (!filename) return filename;
  const m = filename.match(/^[0-9a-f]{8}_(.+)$/i);
  return m ? m[1] : filename;
}

// Insert or replace a sidebar entry by logical document identity, so editing
// the same document across turns updates one card instead of stacking new ones.
function upsertDocSidebar(setDocSidebar, entry) {
  setDocSidebar(prev => {
    const list = Array.isArray(prev) ? prev : [];
    const key = docLogicalKey(entry.filename);
    const idx = list.findIndex(d => docLogicalKey(d.filename) === key);
    if (idx >= 0) {
      const next = [...list];
      next[idx] = entry;
      return next;
    }
    return [...list, entry];
  });
}

function DocSidebarItem({ doc }) {
  const [fileContent, setFileContent] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [loading, setLoading] = useState(false);
  const codeRef = React.useRef(null);

  useEffect(() => {
    if (showPreview && codeRef.current && fileContent !== null && window.hljs) {
      codeRef.current.textContent = fileContent;
      window.hljs.highlightElement(codeRef.current);
    }
  }, [showPreview, fileContent]);

  const ext = (doc.filename || "").split(".").pop().toLowerCase();
  const canPreview = _PREVIEW_EXTS.has(ext);
  const hlLang = _HL_LANG[ext] || "plaintext";
  const info = _LANG_ICON[ext];
  const displayName = (doc.filename || "").replace(/^[0-9a-f]{8}_/, "").replace(/[-_]/g, " ");
  const sizeLabel = doc.size
    ? doc.size < 1024 ? `${doc.size} B`
    : doc.size < 1048576 ? `${(doc.size / 1024).toFixed(1)} KB`
    : `${(doc.size / 1048576).toFixed(1)} MB`
    : "";
  const dlUrl = doc.url || `/api/download/${encodeURIComponent(doc.filename)}`;

  const loadPreview = () => {
    if (fileContent !== null) { setShowPreview(true); return; }
    setLoading(true);
    fetch(dlUrl)
      .then(r => r.text())
      .then(t => { setFileContent(t); setShowPreview(true); setLoading(false); })
      .catch(() => setLoading(false));
  };

  return (
    <div className="doc-sidebar-item">
      {showPreview && fileContent !== null ? (
        <div className="doc-sidebar-preview">
          <div className="doc-sidebar-preview-bar">
            <span className="doc-sidebar-preview-lang">{info?.label || ext.toUpperCase()}</span>
            <div style={{ display: "flex", gap: 8 }}>
              <a href={dlUrl} download={doc.filename} className="doc-sidebar-btn dl">
                <Icon.Download size={13} /> {L("Herunterladen", "Download")}
              </a>
              <button className="doc-sidebar-btn" onClick={() => setShowPreview(false)}>✕ {L("Schliessen", "Close")}</button>
            </div>
          </div>
          <pre className="doc-sidebar-code-pre"><code ref={codeRef} className={`language-${hlLang}`} /></pre>
        </div>
      ) : (
        <div className="doc-sidebar-info-view">
          <div className="doc-sidebar-file-icon"><DocFileIcon name={doc.filename} size={40} /></div>
          <div className="doc-sidebar-filename">{displayName}</div>
          <div className="doc-sidebar-meta">{(info?.label || ext.toUpperCase())}{sizeLabel ? ` · ${sizeLabel}` : ""}</div>
          <div className="doc-sidebar-actions">
            <a href={dlUrl} download={doc.filename} className="doc-sidebar-btn dl primary">
              <Icon.Download size={14} /> {L("Herunterladen", "Download")}
            </a>
            {canPreview && (
              <button className="doc-sidebar-btn" onClick={loadPreview} disabled={loading}>
                {loading ? L("Lädt...", "Loading...") : L("Vorschau", "Preview")}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function DocSidebar({ docs, onClose }) {
  const open = Array.isArray(docs) && docs.length > 0;
  if (!open) return null;
  const title = docs.length === 1
    ? (docs[0].filename || "").replace(/^[0-9a-f]{8}_/, "").replace(/[-_]/g, " ")
    : `${docs.length} ${L("Dateien", "files")}`;

  return (
    <div className={"doc-sidebar open"}>
      <div className="doc-sidebar-header">
        <span className="doc-sidebar-title">
          {docs.length === 1 ? <DocFileIcon name={docs[0].filename} size={16} /> : <Icon.Download size={16} />}
          <span style={{ marginLeft: 6 }}>{title}</span>
        </span>
        <button type="button" className="doc-sidebar-close" onClick={onClose}><Icon.Close /></button>
      </div>
      <div className="doc-sidebar-body doc-sidebar-multi">
        {docs.map((doc, i) => <DocSidebarItem key={i} doc={doc} />)}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------
   Command Palette (Ctrl+K) — actions + chat search
   ---------------------------------------------------------- */

function CommandPalette({ open, onClose, lang, sessions, actions, onOpenSession }) {
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const inputRef = useRef(null);
  const de = lang === "de";

  useEffect(() => {
    if (open) { setQ(""); setIdx(0); setTimeout(() => inputRef.current?.focus(), 30); }
  }, [open]);

  if (!open) return null;

  const ql = q.trim().toLowerCase();
  const matchedActions = actions.filter(a => !ql || a.label.toLowerCase().includes(ql) || (a.keywords || "").toLowerCase().includes(ql));
  const matchedSessions = ql ? sessions.filter(s => (s.title || "").toLowerCase().includes(ql)).slice(0, 6) : sessions.slice(0, 5);
  const items = [
    ...matchedActions.map(a => ({ kind: "action", ...a })),
    ...matchedSessions.map(s => ({ kind: "session", id: "s" + s.id, label: s.title, session: s })),
  ];
  const safeIdx = Math.min(idx, Math.max(items.length - 1, 0));

  const runItem = (item) => {
    onClose();
    if (item.kind === "session") onOpenSession(item.session.id);
    else item.run();
  };

  const onKey = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setIdx(i => Math.min(i + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setIdx(i => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (items[safeIdx]) runItem(items[safeIdx]); }
    else if (e.key === "Escape") { onClose(); }
  };

  const renderItem = (item, i) => (
    <button key={item.id} type="button"
      className={"cmdk-item" + (i === safeIdx ? " active" : "")}
      onMouseEnter={() => setIdx(i)}
      onClick={() => runItem(item)}>
      <span className="cmdk-item-icon">{item.kind === "session" ? <Icon.Chat /> : item.icon}</span>
      <span className="cmdk-item-label">{item.label}</span>
      {item.hint && <kbd className="cmdk-item-hint">{item.hint}</kbd>}
    </button>
  );

  const nActions = items.filter(i => i.kind === "action").length;

  return (
    <div className="cmdk-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="cmdk" role="dialog" aria-modal="true">
        <div className="cmdk-input-row">
          <Icon.Search />
          <input ref={inputRef} value={q}
            onChange={e => { setQ(e.target.value); setIdx(0); }}
            onKeyDown={onKey}
            placeholder={de ? "Befehl eingeben oder Chat suchen..." : "Type a command or search chats..."} />
          <kbd className="cmdk-esc">ESC</kbd>
        </div>
        <div className="cmdk-list">
          {nActions > 0 && <div className="cmdk-group-label">{de ? "Aktionen" : "Actions"}</div>}
          {items.slice(0, nActions).map((item, i) => renderItem(item, i))}
          {items.length > nActions && <div className="cmdk-group-label">Chats</div>}
          {items.slice(nActions).map((item, i) => renderItem(item, nActions + i))}
          {items.length === 0 && <div className="cmdk-empty">{de ? "Nichts gefunden" : "No results"}</div>}
        </div>
        <div className="cmdk-footer">
          <span><kbd>↑↓</kbd> {de ? "Navigieren" : "Navigate"}</span>
          <span><kbd>↵</kbd> {de ? "Ausführen" : "Run"}</span>
          <span><kbd>Ctrl+K</kbd> {de ? "Schliessen" : "Close"}</span>
        </div>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------
   Copy button with success feedback
   ---------------------------------------------------------- */

function CopyBtn({ content, title }) {
  const [ok, setOk] = useState(false);
  const doCopy = () => {
    const text = Array.isArray(content) ? content.filter(p => p.type === "text").map(p => p.text).join("\n") : content;
    navigator.clipboard.writeText(text).then(() => { setOk(true); setTimeout(() => setOk(false), 1200); }).catch(() => {});
  };
  return (
    <button type="button" className={"msg-action-btn" + (ok ? " ok" : "")} onClick={doCopy} title={title}>
      {ok ? <Icon.Check /> : <Icon.Copy />}
    </button>
  );
}

/* ----------------------------------------------------------
   Chat page — xera-app.com/c and xera-app.com/c/:id
   ---------------------------------------------------------- */

function ChatPage({ user, setUser, navigate, theme, setTheme, openSettings, config, setConfig, t }) {
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamBuf, setStreamBuf] = useState("");
  const [showLimit, setShowLimit] = useState(false);
  const [promptCount, setPromptCount] = useState(user?.prompt_count || 0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchQ, setSearchQ] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState("");
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [sidebarHidden, setSidebarHidden] = useState(false);
  const [headerHidden, setHeaderHidden] = useState(false);
  const [streamToolCalls, setStreamToolCalls] = useState([]);
  const [agentThinking, setAgentThinking] = useState(false);
  const [activeBrain, setActiveBrain] = useState(null);
  const lastUsedBrainRef = useRef(null);
  const [brainSwitchConfirm, setBrainSwitchConfirm] = useState(null);
  const [agentId, setAgentId] = useState(null);          // null = auto
  const [activeAgent, setActiveAgent] = useState(null);   // { id, name, icon, color } — primary/last active
  const activeAgentRef = useRef(null);                     // mirrors activeAgent for closure access
  const [activeAgents, setActiveAgents] = useState([]);   // parallel: all running agents
  const activeAgentsRef = useRef([]);                      // mirrors activeAgents for closure access
  const [agentList, setAgentList] = useState([]);         // fetched from /api/agents
  const [agentDelegating, setAgentDelegating] = useState(null); // { from, to, task }
  const [webSearchOn, setWebSearchOn] = useState(false);
  const [folders, setFolders] = useState([]);
  const [activeFolder, setActiveFolder] = useState(null);
  const [folderMenuId, setFolderMenuId] = useState(null);
  const [pastedImages, setPastedImages] = useState([]);
  const [pastedDocs, setPastedDocs] = useState([]);
  const [docSidebar, setDocSidebar] = useState([]); // [{ url, filename, size }]
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef(null);
  const [cmdkOpen, setCmdkOpen] = useState(false);

  const [activeTab, setActiveTab] = useState(config.activeTab || "chat");
  const agentMode = activeTab === "homelab" || (activeTab === "chat" && webSearchOn);

  const FREE_LIMIT = user?.limit || 5;
  const isPro = user?.is_pro || user?.is_admin;
  const isGuest = !user || user.is_guest;
  const isHomelab = !!user?.has_homelab;

  const switchTab = (tab) => {
    if (isGuest) return;
    if (tab === "homelab" && !isHomelab) return;
    if (tab === "homelab" && !isPro) return;
    if (tab === activeTab) return;
    setActiveTab(tab);
    setConfig(c => ({ ...c, activeTab: tab }));
    if (tab === "code" || tab === "homelab") setWebSearchOn(false);
    setPastedImages([]);
    setActiveId(null);
    setMessages([]);
    setActiveAgent(null);
    setAgentDelegating(null);
    setDocSidebar([]);
    navigate("/c");
  };

  const messagesRef = useRef(null);
  const taRef = useRef(null);
  const searchInputRef = useRef(null);
  const abortRef = useRef(null);
  const requestIdRef = useRef(null);
  const fileInputRef = useRef(null);

  const activeModel = MODELS.find(m => m.id === config.model) || MODELS[0];
  const isEmpty = !messages.length && !streaming;
  const userInitials = (user?.username || "G").slice(0, 2).toUpperCase();

  // Parse session ID from URL
  useEffect(() => {
    const match = window.location.pathname.match(/^\/c\/(\d+)$/);
    if (match) setActiveId(parseInt(match[1]));
  }, []);

  useEffect(() => {
    if (isGuest) return;
    fetch(`/api/sessions?mode=${activeTab}`).then(r => r.json()).then(data => {
      if (Array.isArray(data)) setSessions(data);
    }).catch(() => {});
    fetch(`/api/folders?mode=${activeTab}`).then(r => r.json()).then(data => {
      if (Array.isArray(data)) setFolders(data);
    }).catch(() => {});
  }, [isGuest, activeTab]);

  useEffect(() => {
    if (!activeId) { setMessages([]); setDocSidebar([]); return; }
    if (isGuest) return;
    fetch(`/api/sessions/${activeId}/messages`).then(r => r.json()).then(data => {
      if (Array.isArray(data)) {
        setMessages(data.map(m => ({ role: m.role, content: m.content })));
        // Rebuild the doc sidebar for this session from past download links,
        // deduped by logical filename (later messages overwrite earlier ones —
        // i.e. show the latest version of each document, not every revision).
        let rebuilt = [];
        for (const m of data) {
          const text = typeof m.content === "string" ? m.content : "";
          const re = /\/api\/download\/([^\)\s"]+)/g;
          let match;
          while ((match = re.exec(text)) !== null) {
            const fname = decodeURIComponent(match[1]);
            const key = docLogicalKey(fname);
            const idx = rebuilt.findIndex(d => docLogicalKey(d.filename) === key);
            const entry = { filename: fname, url: `/api/download/${match[1]}` };
            if (idx >= 0) rebuilt[idx] = entry; else rebuilt.push(entry);
          }
        }
        setDocSidebar(rebuilt);
      }
    }).catch(() => {});
  }, [activeId, isGuest]);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }, [input]);

  const userScrolledUp = useRef(false);

  useEffect(() => {
    const el = messagesRef.current;
    if (!el) return;
    if (!userScrolledUp.current) el.scrollTop = el.scrollHeight;
  }, [messages.length, streamBuf]);

  useEffect(() => {
    if (!streaming) userScrolledUp.current = false;
  }, [streaming]);

  useEffect(() => {
    const el = messagesRef.current;
    if (!el) return;
    const onScroll = () => {
      const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
      setShowScrollBtn(gap > 200);
      if (streaming) userScrolledUp.current = gap > 150;
    };
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, [streaming]);

  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "n") {
        e.preventDefault();
        setActiveId(null);
        setMessages([]);
        setSidebarOpen(false);
        window.history.pushState(null, "", "/c");
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setCmdkOpen(o => !o);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Fetch all agents once on mount (homelab users only)
  useEffect(() => {
    if (!isHomelab) return;
    fetch("/api/agents").then(r => r.json()).then(data => {
      if (Array.isArray(data)) setAgentList(data);
    }).catch(() => {});
  }, [isHomelab]);

  const stopStreaming = () => {
    if (requestIdRef.current) {
      fetch("/api/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: requestIdRef.current }),
      }).catch(() => {});
    }
    if (abortRef.current) abortRef.current.abort();
  };

  const handleApproval = (actionId, approved) => {
    fetch(`/api/approve/${actionId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved }),
    }).catch(() => {});
    setStreamToolCalls(prev => prev.map(tc =>
      tc.actionId === actionId ? { ...tc, status: approved ? "running" : "done", success: false, output: approved ? "" : L("Abgelehnt", "Denied") } : tc
    ));
  };

  const scrollToBottom = () => {
    const el = messagesRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  };

  const exportChat = () => {
    if (!messages.length) return;
    const title = sessions.find(s => s.id === activeId)?.title || "xera-chat";
    const parts = messages.map(m => {
      const text = Array.isArray(m.content) ? m.content.filter(p => p.type === "text").map(p => p.text).join("\n") : (m.content || "");
      return "## " + (m.role === "user" ? t.you : "Xera AI") + "\n\n" + text;
    });
    const md = "# " + title + "\n\n" + parts.join("\n\n---\n\n") + "\n";
    const blob = new Blob([md], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = title.replace(/[^\w\-äöüÄÖÜ]+/g, "_").toLowerCase().slice(0, 60) + ".md";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const newChat = () => {
    setActiveId(null);
    setMessages([]);
    setActiveAgent(null);
    setAgentDelegating(null);
    setDocSidebar([]);
    navigate("/c");
    setSidebarOpen(false);
  };

  const openSession = (id) => {
    setActiveId(id);
    navigate(`/c/${id}`);
    setSidebarOpen(false);
  };

  const deleteSession = (id, e) => {
    e.stopPropagation();
    fetch(`/api/sessions/${id}`, { method: "DELETE" }).then(() => {
      setSessions(prev => prev.filter(s => s.id !== id));
      if (activeId === id) newChat();
    });
  };

  const startRename = (s, e) => {
    e.stopPropagation();
    setEditingId(s.id);
    setEditTitle(s.title);
  };

  const commitRename = (id) => {
    const title = editTitle.trim();
    if (!title) { setEditingId(null); return; }
    fetch(`/api/sessions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    }).then(() => {
      setSessions(prev => prev.map(s => s.id === id ? { ...s, title } : s));
      setEditingId(null);
    });
  };

  const moveToFolder = (sessionId, folder) => {
    fetch(`/api/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder: folder || null }),
    }).then(() => {
      setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, folder: folder || null } : s));
      if (folder && !folders.includes(folder)) setFolders(prev => [...prev, folder].sort());
      setFolderMenuId(null);
    });
  };

  const createAndMoveToFolder = (sessionId) => {
    const name = prompt(t.folder_new);
    if (name && name.trim()) moveToFolder(sessionId, name.trim());
  };

  const groupSessions = (list) => {
    const now = new Date();
    const todayStr = now.toISOString().slice(0, 10);
    const yest = new Date(now); yest.setDate(yest.getDate() - 1);
    const yesterdayStr = yest.toISOString().slice(0, 10);
    const weekAgo = new Date(now); weekAgo.setDate(weekAgo.getDate() - 7);

    const groups = { today: [], yesterday: [], week: [], older: [] };
    list.forEach(s => {
      const d = (s.created_at || "").slice(0, 10);
      if (d === todayStr) groups.today.push(s);
      else if (d === yesterdayStr) groups.yesterday.push(s);
      else if (new Date(d) >= weekAgo) groups.week.push(s);
      else groups.older.push(s);
    });
    return groups;
  };

  const filteredSessions = searchQ
    ? sessions.filter(s => s.title.toLowerCase().includes(searchQ.toLowerCase()))
    : sessions;
  const grouped = groupSessions(filteredSessions);

  const fileToBase64 = (file) => new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(file);
  });

  function _predictBrain(msgs) {
    const hasPriorAI = msgs.slice(0, -1).some(m => m && m.role === "assistant");
    if (hasPriorAI) return "big";
    const last = msgs[msgs.length - 1];
    const txt = typeof last?.content === "string" ? last.content :
      (last?.content || []).filter(p => p.type === "text").map(p => p.text).join(" ");
    if (/\b(pdf|docx|xlsx|dokument|document)\b/i.test(txt)) return "big";
    if (/^(hi|hallo|hey|moin|danke|thx|thanks|ok|gut|super|perfekt|cool|ja|nein|klar)[\s!.?]*$/i.test(txt.trim()) || (txt.length < 60 && !/[?]/.test(txt))) return "fast";
    return "big";
  }

  const send = useCallback(async (overrideText, brainForce) => {
    const text = (overrideText ?? input).trim();
    if ((!text && pastedImages.length === 0 && pastedDocs.length === 0) || streaming) return;

    if (!isPro && promptCount >= FREE_LIMIT) {
      setShowLimit(true);
      return;
    }

    setInput("");
    const images = [...pastedImages];
    const docs = [...pastedDocs];
    setPastedImages([]);
    setPastedDocs([]);

    let userContent;
    if (images.length > 0 || docs.length > 0) {
      const parts = [{ type: "text", text }];
      for (const img of images) {
        const dataUrl = await fileToBase64(img);
        parts.push({ type: "image_url", image_url: { url: dataUrl } });
      }
      for (const doc of docs) {
        if (doc.content) {
          parts.push({ type: "text", text: `[Dokument: ${doc.stored_name || doc.name}]\n${doc.content}` });
        } else if (doc.stored_name || doc.name) {
          // Content not yet loaded — pass filename so agent can call read_document
          parts.push({ type: "text", text: `[Dokument-Datei: ${doc.stored_name || doc.name}]` });
        }
      }
      userContent = parts;
    } else {
      userContent = text;
    }

    const newMessages = [...messages, { role: "user", content: userContent }];
    setMessages(newMessages);
    setStreaming(true);
    setStreamBuf("");
    setStreamToolCalls([]);
    setAgentThinking(false);

    // Chat tab: non-guests always use agent system so orchestrator can pick the right agent
    const effectiveMode = activeTab === "homelab" ? "homelab"
      : (activeTab === "chat" && (!isGuest || webSearchOn)) ? "agents"
      : "chat";
    // Code tab: always Big Brain by default; only Mini Brain if explicitly selected
    const effectiveBrain = activeTab === "code" ? (config.brain === "code" ? "code" : "big") : config.brain;

    // Brain switch confirmation: only in pure chat mode (no agent, no websearch)
    if (!brainForce && config.brain === "auto" && lastUsedBrainRef.current && activeTab === "chat" && !webSearchOn && !agentId) {
      const predicted = _predictBrain(newMessages);
      if (predicted !== lastUsedBrainRef.current) {
        setMessages(prev => prev.slice(0, -1));
        setInput(text);
        setPastedImages(images);
        setPastedDocs(docs);
        setBrainSwitchConfirm({ from: lastUsedBrainRef.current, to: predicted, pendingText: text });
        setStreaming(false);
        return;
      }
    }

    const finalBrain = brainForce || effectiveBrain;
    const body = {
      messages: newMessages,
      session_id: activeId || undefined,
      mode: effectiveMode,
      brain: finalBrain,
      ...(agentId ? { agent_id: agentId } : webSearchOn ? { agent_id: "web_search" } : {}),
    };
    const controller = new AbortController();
    abortRef.current = controller;
    requestIdRef.current = null;
    const timeout = setTimeout(() => controller.abort(), 90000);

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    }).then(async (response) => {
      clearTimeout(timeout);
      if (response.status === 403) {
        setStreaming(false);
        setShowLimit(true);
        return;
      }
      if (!response.ok) {
        setStreaming(false);
        setMessages(prev => [...prev, { role: "assistant", content: t.err_server, isError: true }]);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let fullResponse = "";
      let sessionId = activeId;
      let toolCallsLocal = [];
      let isErrorFlag = false;
      let docCards = [];
      setActiveAgent(null);
      activeAgentRef.current = null;
      setActiveAgents([]);
      activeAgentsRef.current = [];
      setAgentDelegating(null);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6);
          if (data === "[DONE]") continue;
          try {
            const parsed = JSON.parse(data);
            if (parsed.brain) {
              setActiveBrain(parsed.brain);
              lastUsedBrainRef.current = parsed.brain;
            }
            if (parsed.type === "parallel_start") {
              const agents = parsed.agents || [];
              setActiveAgents(agents);
              activeAgentsRef.current = agents;
              const first = agents[0];
              if (first) { setActiveAgent(first); activeAgentRef.current = first; }
              setAgentDelegating(null);
            }
            if (parsed.type === "agent_selected") {
              const agentData = { id: parsed.agent_id, name: parsed.agent_name, icon: parsed.agent_icon, color: parsed.agent_color };
              setActiveAgent(agentData);
              activeAgentRef.current = agentData;
              setAgentDelegating(null);
            }
            if (parsed.type === "agent_delegating") {
              setAgentDelegating({ from: parsed.from_name, to: parsed.to_name, task: parsed.task });
            }
            if (parsed.session_id !== undefined && !sessionId) {
              sessionId = parsed.session_id;
              if (sessionId) {
                setActiveId(sessionId);
                window.history.replaceState(null, "", `/c/${sessionId}`);
              }
            }
            if (parsed.request_id) {
              requestIdRef.current = parsed.request_id;
            }
            if (parsed.type === "stopped") {
              break;
            }
            if (parsed.type === "status") {
              setAgentThinking(true);
            } else if (parsed.type === "approval_required") {
              setAgentThinking(false);
              toolCallsLocal.push({
                id: parsed.id, name: parsed.name, args: parsed.args,
                status: "approval", level: parsed.level, actionId: parsed.action_id,
              });
              setStreamToolCalls([...toolCallsLocal]);
            } else if (parsed.type === "tool_call") {
              setAgentThinking(false);
              const existing = toolCallsLocal.findIndex(tc => tc.id === parsed.id);
              if (existing >= 0) {
                toolCallsLocal[existing] = { ...toolCallsLocal[existing], status: "running", level: parsed.level };
              } else {
                toolCallsLocal.push({ id: parsed.id, name: parsed.name, args: parsed.args, status: "running", level: parsed.level });
              }
              setStreamToolCalls([...toolCallsLocal]);
            } else if (parsed.type === "tool_result") {
              const idx = toolCallsLocal.findIndex(tc => tc.id === parsed.id);
              if (idx >= 0) {
                toolCallsLocal[idx] = { ...toolCallsLocal[idx], success: parsed.success, output: parsed.output, status: "done" };
                setStreamToolCalls([...toolCallsLocal]);
                // Doc sidebar entry for create_document is added via the dedicated
                // "document" SSE event below (always emitted by the backend now) —
                // not duplicated here.
              }
            } else if (parsed.type === "document") {
              const newDoc = { url: parsed.url, filename: parsed.filename, size: parsed.size, doc_type: parsed.doc_type };
              docCards = [...docCards, newDoc];
              if (parsed.filename) upsertDocSidebar(setDocSidebar, { filename: parsed.filename, url: parsed.url, size: parsed.size });
            } else if (parsed.type === "doc_ref") {
              // Persist link text to DB but don't show in UI (DocumentCard handles display)
              fullResponse += parsed.content;
            } else if (parsed.type === "content") {
              setAgentThinking(false);
              fullResponse += parsed.content;
              setStreamBuf(fullResponse);
            } else if (parsed.type === "error") {
              setAgentThinking(false);
              fullResponse = parsed.message;
              isErrorFlag = true;
            } else if (parsed.choices) {
              const delta = parsed.choices[0]?.delta?.content || "";
              if (delta) { fullResponse += delta; setStreamBuf(fullResponse); }
            } else if (parsed.content) {
              fullResponse += parsed.content;
              setStreamBuf(fullResponse);
            }
          } catch (e) {}
        }
      }

      setStreaming(false);
      setStreamBuf("");
      setStreamToolCalls([]);
      setAgentThinking(false);
      setActiveBrain(null);
      setAgentDelegating(null);
      if (fullResponse || toolCallsLocal.length || docCards.length) {
        const finalAgent = activeAgentRef.current;
        const finalAgents = activeAgentsRef.current;
        setMessages(prev => [...prev, {
          role: "assistant",
          content: fullResponse,
          ...(toolCallsLocal.length ? { toolCalls: [...toolCallsLocal] } : {}),
          ...(isErrorFlag ? { isError: true } : {}),
          ...(docCards.length ? { docCards } : {}),
          ...(finalAgents.length > 1 ? { agentsInfo: finalAgents, agentInfo: finalAgent } : finalAgent ? { agentInfo: finalAgent } : {}),
        }]);
      }
      setActiveAgents([]);
      activeAgentsRef.current = [];
      setPromptCount(c => c + 1);

      if (!isGuest) {
        fetch(`/api/sessions?mode=${activeTab}`).then(r => r.json()).then(data => {
          if (Array.isArray(data)) setSessions(data);
        }).catch(() => {});
      }

    }).catch((err) => {
      clearTimeout(timeout);
      setStreaming(false);
      setStreamToolCalls([]);
      setAgentThinking(false);
      const msg = err.name === "AbortError" ? t.err_timeout : t.err_connection;
      setMessages(prev => [...prev, { role: "assistant", content: msg, isError: true }]);
    });
  }, [input, streaming, messages, activeId, isPro, promptCount, FREE_LIMIT, isGuest, activeTab, config.brain, webSearchOn, t, navigate]);

  const regenerate = useCallback(() => {
    if (streaming || messages.length < 2) return;
    const lastUserIdx = messages.map(m => m.role).lastIndexOf("user");
    if (lastUserIdx === -1) return;
    const lastUserMsg = messages[lastUserIdx].content;
    setMessages(prev => prev.slice(0, lastUserIdx));
    setTimeout(() => send(lastUserMsg), 50);
  }, [messages, streaming, send]);

  const retryLast = useCallback(() => {
    if (streaming || messages.length < 2) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.role !== "assistant" || !lastMsg.isError) return;
    setMessages(prev => prev.slice(0, -1));
    const lastUserIdx = messages.slice(0, -1).map(m => m.role).lastIndexOf("user");
    if (lastUserIdx === -1) return;
    setTimeout(() => send(messages[lastUserIdx].content), 50);
  }, [messages, streaming, send]);

  const toggleMic = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert(L("Web Speech API nicht verfügbar in diesem Browser.", "Web Speech API is not available in this browser.")); return; }
    if (isRecording) {
      recognitionRef.current?.stop();
      setIsRecording(false);
      return;
    }
    const recognition = new SR();
    recognition.lang = config.language === "de" ? "de-DE" : "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onstart = () => setIsRecording(true);
    recognition.onresult = (e) => {
      const transcript = e.results[0][0].transcript;
      setInput(prev => prev ? prev + " " + transcript : transcript);
    };
    recognition.onerror = () => setIsRecording(false);
    recognition.onend = () => setIsRecording(false);
    recognitionRef.current = recognition;
    recognition.start();
  };

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const de = config.language === "de";
  const cmdkActions = [
    { id: "new", icon: <Icon.Plus />, label: t.new_chat, hint: "Ctrl+N", keywords: "new chat neuer", run: newChat },
    ...(!isGuest ? [
      { id: "tab-chat", icon: <Icon.Chat />, label: de ? "Zu Chat wechseln" : "Switch to Chat", keywords: "tab chat", run: () => switchTab("chat") },
      { id: "tab-code", icon: <Icon.Code />, label: de ? "Zu Code wechseln" : "Switch to Code", keywords: "tab code", run: () => switchTab("code") },
      ...(isHomelab ? [{ id: "tab-homelab", icon: <Icon.Server />, label: de ? "Zu Homelab wechseln" : "Switch to Homelab", keywords: "tab homelab", run: () => switchTab("homelab") }] : []),
    ] : []),
    ...(messages.length ? [{ id: "export", icon: <Icon.Download />, label: de ? "Chat als Markdown exportieren" : "Export chat as Markdown", keywords: "export download markdown speichern save", run: exportChat }] : []),
    { id: "theme", icon: config.theme === "dark" ? <Icon.Sun /> : <Icon.Moon />, label: config.theme === "dark" ? (de ? "Helles Theme" : "Light theme") : (de ? "Dunkles Theme" : "Dark theme"), keywords: "theme dark light hell dunkel", run: () => setTheme(config.theme === "dark" ? "light" : "dark") },
    { id: "lang", icon: <Icon.Globe />, label: de ? "Switch to English" : "Auf Deutsch wechseln", keywords: "language sprache english deutsch", run: () => setConfig(c => ({ ...c, language: de ? "en" : "de" })) },
    { id: "settings", icon: <Icon.Gear />, label: t.settings, keywords: "settings einstellungen options", run: openSettings },
    ...(!isGuest && activeTab === "chat" ? [
      { id: "websearch", icon: <Icon.Web />, label: webSearchOn ? (de ? "Web-Suche deaktivieren" : "Disable web search") : (de ? "Web-Suche aktivieren" : "Enable web search"), keywords: "web search suche internet", run: () => setWebSearchOn(v => !v) },
      ...["auto", "big", "fast", "code"].map(b => ({
        id: "brain-" + b, icon: <Icon.Brain />,
        label: "Brain: " + (b === "auto" ? "Auto" : b === "big" ? "Big Brain" : b === "fast" ? "Fast Brain" : "Mini Brain"),
        keywords: "brain modell model routing " + b,
        run: () => setConfig(c => ({ ...c, brain: b })),
      })),
    ] : []),
  ];

  return (
    <div className="chat-page">
      <div className="bg-grid" />

      <div className={"sidebar-overlay" + (sidebarOpen ? " open" : "")} onClick={() => setSidebarOpen(false)} />
      <div className={"app-shell" + (sidebarHidden ? " sidebar-collapsed" : "")}>
        <aside className={"sidebar" + (sidebarOpen ? " open" : "") + (sidebarHidden ? " hidden-desktop" : "")}>
          <div className="sidebar-header">
            <div className="sidebar-brand" onClick={() => navigate("/")} style={{ cursor: "pointer" }}>
              <XMark size={32} />
              <h2>XERA<span className="accent"> AI</span></h2>
            </div>

            {!isGuest && (
            <div className="tab-selector">
              {[
                { id: "chat", icon: Icon.Chat, label: t.tab_chat, desc: t.tab_chat_desc },
                { id: "code", icon: Icon.Code, label: t.tab_code, desc: t.tab_code_desc },
                ...(isHomelab ? [{ id: "homelab", icon: Icon.Server, label: t.tab_homelab, desc: t.tab_homelab_desc }] : []),
              ].map(tab => (
                <button
                  key={tab.id}
                  className={"tab-btn" + (activeTab === tab.id ? " active" : "")}
                  onClick={() => switchTab(tab.id)}
                  type="button"
                >
                  <span className="tab-icon"><tab.icon /></span>
                  <span className="tab-info">
                    <span className="tab-label">{tab.label}</span>
                    <span className="tab-desc">{tab.desc}</span>
                  </span>
                </button>
              ))}
            </div>
            )}

            <button className="new-chat-btn" onClick={newChat} type="button">
              <Icon.Plus /> {t.new_chat}
            </button>
          </div>

          <div className="sidebar-search">
            <Icon.Search />
            <input
              ref={searchInputRef}
              type="text"
              placeholder={t.search_history}
              value={searchQ}
              onChange={e => setSearchQ(e.target.value)}
            />
            {searchQ && (
              <button type="button" className="sidebar-search-clear" onClick={() => setSearchQ("")}>
                <Icon.Close />
              </button>
            )}
          </div>

          <div className="folder-tree">
            <button type="button" className={"folder-tree-item" + (!activeFolder ? " active" : "")} onClick={() => setActiveFolder(null)}>
              <Icon.Chat />
              <span>{t.folder_none}</span>
              <span className="folder-count">{sessions.length}</span>
            </button>
            {folders.map(f => {
              const count = sessions.filter(s => s.folder === f).length;
              return (
                <button key={f} type="button" className={"folder-tree-item" + (activeFolder === f ? " active" : "")} onClick={() => setActiveFolder(activeFolder === f ? null : f)}>
                  <Icon.Doc />
                  <span>{f}</span>
                  <span className="folder-count">{count}</span>
                </button>
              );
            })}
          </div>

          <div className="sessions-list">
            {[
              { key: "today", label: t.today, items: grouped.today },
              { key: "yesterday", label: t.yesterday, items: grouped.yesterday },
              { key: "week", label: t.last_7_days, items: grouped.week },
              { key: "older", label: t.older, items: grouped.older },
            ].filter(g => g.items.length > 0).map(g => {
              const items = activeFolder ? g.items.filter(s => s.folder === activeFolder) : g.items;
              if (!items.length) return null;
              return (
                <div key={g.key} className="session-group">
                  <div className="session-group-label">{g.label}</div>
                  {items.map(s => (
                    <div
                      key={s.id}
                      className={"session-item" + (s.id === activeId ? " active" : "")}
                      onClick={() => editingId !== s.id && folderMenuId !== s.id && openSession(s.id)}
                    >
                      {editingId === s.id ? (
                        <input
                          className="session-rename-input"
                          value={editTitle}
                          onChange={e => setEditTitle(e.target.value)}
                          onBlur={() => commitRename(s.id)}
                          onKeyDown={e => { if (e.key === "Enter") commitRename(s.id); if (e.key === "Escape") setEditingId(null); }}
                          autoFocus
                          onClick={e => e.stopPropagation()}
                        />
                      ) : (
                        <>
                          <span className="session-title">
                            {s.folder && <span className="session-folder-tag">{s.folder}</span>}
                            {s.title}
                          </span>
                          <div className="session-actions">
                            <button type="button" className="session-action-btn" onClick={e => { e.stopPropagation(); setFolderMenuId(folderMenuId === s.id ? null : s.id); }} title={t.folder_move}>
                              <Icon.Doc />
                            </button>
                            <button type="button" className="session-action-btn" onClick={e => startRename(s, e)} title={t.rename_chat}>
                              <Icon.Pencil />
                            </button>
                            <button type="button" className="session-action-btn session-action-delete" onClick={e => deleteSession(s.id, e)} title={t.delete_chat}>
                              <Icon.Trash />
                            </button>
                          </div>
                          {folderMenuId === s.id && (
                            <div className="folder-menu" onClick={e => e.stopPropagation()}>
                              {s.folder && <button type="button" onClick={() => moveToFolder(s.id, null)}>{t.folder_none}</button>}
                              {folders.filter(f => f !== s.folder).map(f => (
                                <button key={f} type="button" onClick={() => moveToFolder(s.id, f)}>{f}</button>
                              ))}
                              <button type="button" className="folder-menu-new" onClick={() => createAndMoveToFolder(s.id)}>
                                <Icon.Plus /> {t.folder_new}
                              </button>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>

          <div className="sidebar-footer">
            <div className="sidebar-controls">
              <button type="button" className="ctrl-btn" onClick={openSettings} title={t.settings}>
                <Icon.Gear />
              </button>
              <div className="ctrl-divider" />
              <button type="button" className={"ctrl-btn" + (config.theme === "dark" ? " on" : "")} onClick={() => setTheme("dark")} title={t.theme_dark}>
                <Icon.Moon />
              </button>
              <button type="button" className={"ctrl-btn" + (config.theme === "light" ? " on" : "")} onClick={() => setTheme("light")} title={t.theme_light}>
                <Icon.Sun />
              </button>
            </div>

            {isGuest ? (
              <a href="/auth/login" className="discord-btn" style={{ margin: "8px 0 0", fontSize: 13, padding: "8px 12px", textAlign: "center" }}>
                <Icon.Discord />
                {t.discord_login}
              </a>
            ) : (
              <>
                <div className="user-info">
                  <div className="avatar">{userInitials}</div>
                  <div className="user-meta">
                    <div className="user-name" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      {user.username}
                      {isPro && <span className="plan-pill pro"><Icon.Crown /> PRO</span>}
                    </div>
                    <div className="user-status">
                      <span className="dot"></span> {t.connected}
                    </div>
                  </div>
                </div>
                <a href="/auth/logout" className="logout-btn">{t.sign_out}</a>
              </>
            )}
          </div>
        </aside>

        <main className="chat-main">
          {!headerHidden && (
          <div className="chat-header">
            {sidebarHidden && (
              <button className="layout-btn" onClick={() => setSidebarHidden(false)} type="button" title="Show sidebar">
                <Icon.PanelLeft />
              </button>
            )}
            <button className="mobile-hamburger" onClick={() => setSidebarOpen(true)} type="button" aria-label="Menu">
              <Icon.Menu />
            </button>
            <div className="chat-title">
              {sessions.find(s => s.id === activeId)?.title || t.new_chat}
            </div>
            {!isGuest && activeTab === "chat" && (
              <div className="brain-selector-inline">
                {["auto", "big", "fast", "code"].map(b => (
                  <button key={b} type="button" className={"brain-chip" + (config.brain === b ? " active" : "") + (activeBrain === b ? " live" : "")} onClick={() => setConfig(c => ({...c, brain: b}))}>
                    {b === "auto" ? "Auto" : b === "big" ? <><span className="brain-dot brain-dot-big" /> Big</> : b === "fast" ? <><span className="brain-dot brain-dot-fast" /> Fast</> : <><span className="brain-dot brain-dot-code" /> Mini</>}
                  </button>
                ))}
              </div>
            )}
            {!isGuest && activeTab === "code" && (
              <div className="brain-selector-inline">
                {["big", "code"].map(b => (
                  <button key={b} type="button"
                    className={"brain-chip" + ((b === "big" && config.brain !== "code") || (b === "code" && config.brain === "code") ? " active" : "") + (activeBrain === b ? " live" : "")}
                    onClick={() => setConfig(c => ({...c, brain: b === "big" ? "auto" : "code"}))}>
                    {b === "big" ? <><span className="brain-dot brain-dot-big" /> Big</> : <><span className="brain-dot brain-dot-code" /> Mini</>}
                  </button>
                ))}
              </div>
            )}
            <div className="prompt-counter">
              {isPro ? (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <span className="plan-pill pro"><Icon.Crown /> PRO</span>
                  <span>{t.unlimited}</span>
                </span>
              ) : (
                <>
                  <span><span className="num">{promptCount}</span> / {FREE_LIMIT} {t.prompts}</span>
                  <div className="bar"><div style={{ width: (promptCount / FREE_LIMIT * 100) + "%" }} /></div>
                </>
              )}
            </div>
            <div className="layout-controls">
              <button className="layout-btn" onClick={() => setCmdkOpen(true)} type="button" title={config.language === "de" ? "Befehle (Ctrl+K)" : "Commands (Ctrl+K)"}>
                <Icon.Search />
              </button>
              {messages.length > 0 && (
                <button className="layout-btn" onClick={exportChat} type="button" title={config.language === "de" ? "Chat exportieren (.md)" : "Export chat (.md)"}>
                  <Icon.Download />
                </button>
              )}
              <button className="layout-btn" onClick={() => setSidebarHidden(h => !h)} type="button" title="Toggle sidebar">
                <Icon.PanelLeft />
              </button>
              <button className="layout-btn" onClick={() => setHeaderHidden(true)} type="button" title="Hide header">
                <Icon.Minus />
              </button>
              <button className="layout-btn" onClick={() => { window.open(window.location.href, "_blank", "width=500,height=700"); }} type="button" title="Pop out">
                <Icon.ExternalLink />
              </button>
            </div>
          </div>
          )}
          {headerHidden && (
            <button className="header-restore-btn" onClick={() => setHeaderHidden(false)} type="button" title="Show header">
              <Icon.ChevronDown />
            </button>
          )}

          {!isGuest && (() => {
            const lastAgentMsg = [...messages].reverse().find(m => m.role === "assistant" && m.agentInfo);
            const shownAgent = activeAgent || (streaming ? null : lastAgentMsg?.agentInfo || null);
            const de = config.language === "de";
            const thinkingText = de ? "denkt nach..." : "thinking...";
            return (
              <div className="agent-status-bar">
                {agentDelegating ? (
                  <>
                    <span className="agent-status-dot delegating" />
                    <span className="agent-status-text">
                      {agentDelegating.from} <span className="agent-status-arrow">→</span> {agentDelegating.to}
                    </span>
                    <span className="agent-status-badge live">{de ? "Delegiert" : "Delegating"}</span>
                  </>
                ) : streaming && activeAgents.length > 1 ? (
                  <>
                    <span className="agent-status-dot parallel-dot" />
                    <span className="agent-status-text parallel-text">
                      {activeAgents.slice(0, 3).map(a => (
                        <span key={a.id} className="parallel-icon" style={{ color: a.color }}>{a.icon}</span>
                      ))}
                      {activeAgents.length > 3
                        ? <span className="parallel-label">{activeAgents.length}+ Agents {thinkingText}</span>
                        : <span className="parallel-label">{activeAgents.map(a => a.name).join(" + ")} {thinkingText}</span>
                      }
                    </span>
                  </>
                ) : streaming && activeAgent ? (
                  <>
                    <span className="agent-status-dot" style={{ background: activeAgent.color }} />
                    <span className="agent-status-text" style={{ color: activeAgent.color }}>
                      {`Agent(${activeAgent.name}) ${thinkingText}`}
                    </span>
                  </>
                ) : streaming ? (
                  <>
                    <span className="agent-status-dot idle" />
                    <span className="agent-status-text muted">{de ? "Denkt nach..." : "Thinking..."}</span>
                  </>
                ) : shownAgent ? (
                  <>
                    <span className="agent-status-dot" style={{ background: shownAgent.color }} />
                    <span className="agent-status-text" style={{ color: shownAgent.color }}>{shownAgent.name}</span>
                    <span className="agent-status-badge last">{de ? "zuletzt" : "last"}</span>
                  </>
                ) : (
                  <>
                    <span className="agent-status-dot idle" />
                    <span className="agent-status-text muted">{de ? "Kein Agent aktiv · Auto-Routing" : "No agent active · Auto-routing"}</span>
                  </>
                )}
              </div>
            );
          })()}
          <div className="messages" ref={messagesRef}>
            {isEmpty && (
              <div className="welcome-hero">
                <div className="welcome-glow" />
                <div className="welcome-logo-ring">
                  <div className="welcome-logo-pulse" />
                  <XMark size={48} radius={14} />
                </div>
                <h1 className="welcome-greeting">
                  {(() => {
                    const h = new Date().getHours();
                    const g = config.language === "de"
                      ? (h < 5 ? "Gute Nacht" : h < 11 ? "Guten Morgen" : h < 18 ? "Hallo" : "Guten Abend")
                      : (h < 5 ? "Good night" : h < 11 ? "Good morning" : h < 18 ? "Hello" : "Good evening");
                    return isGuest ? g + "." : `${g}, ${user?.username || ""}`;
                  })()}
                </h1>
                <p className="welcome-tagline">{isGuest ? t.guest_welcome : t.welcome_sub}</p>

                <div className="welcome-chips">
                  <span className="welcome-chip"><span className="wc-dot" /> 3 Brains online</span>
                  <span className="welcome-chip">{AGENTS_TOTAL} Agents</span>
                  <span className="welcome-chip">{TOOLS_TOTAL} Tools</span>
                  <span className="welcome-chip">{config.language === "de" ? "100 % lokal" : "100 % local"}</span>
                </div>

                {!isGuest && (
                <div className="welcome-tabs">
                  {[
                    { id: "chat", icon: Icon.Chat, label: t.welcome_chat_title, sub: t.welcome_chat_desc, color: "var(--accent)" },
                    { id: "code", icon: Icon.Code, label: t.welcome_code_title, sub: t.welcome_code_desc, color: "oklch(0.70 0.18 160)" },
                    ...(isHomelab ? [{ id: "homelab", icon: Icon.Server, label: t.welcome_homelab_title, sub: t.welcome_homelab_desc, color: "oklch(0.70 0.18 40)" }] : []),
                  ].map(m => (
                    <button key={m.id} type="button" className={"welcome-tab" + (activeTab === m.id ? " active" : "")} onClick={() => switchTab(m.id)}>
                      <span className="welcome-tab-icon" style={{ "--tab-color": m.color }}><m.icon /></span>
                      <span className="welcome-tab-label">{m.label}</span>
                    </button>
                  ))}
                </div>
                )}

                <div className="welcome-prompts">
                  {(SUGGESTIONS[config.language] || SUGGESTIONS.de).map((s, i) => (
                    <button key={i} className="welcome-prompt" onClick={() => send(s.text)} type="button">
                      <span className="wp-head">
                        <span className="wp-label">{s.label}</span>
                        <span className="wp-icon"><Icon.ArrowRight /></span>
                      </span>
                      <span className="wp-text">{s.text}</span>
                    </button>
                  ))}
                </div>

                <div className="welcome-kbd-hint">
                  <kbd>Ctrl</kbd><kbd>K</kbd>
                  <span>{config.language === "de" ? "für Befehle & Chat-Suche" : "for commands & chat search"}</span>
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={"msg-row " + m.role + (m.isError ? " error" : "")}
                style={m.role === "assistant" && m.agentInfo?.color ? { "--agent-c": m.agentInfo.color } : undefined}>
                <div className="msg-avatar">
                  {m.role === "user" ? userInitials : <XMark size={30} />}
                </div>
                <div className="msg-body">
                  <div className="msg-role">
                    {m.role === "user" ? t.you : (
                      m.agentsInfo && m.agentsInfo.length > 1 ? (
                        <span className="msg-agent-label parallel">
                          {m.agentsInfo.slice(0, 3).map(a => (
                            <span key={a.id} className="msg-agent-icon" style={{ color: a.color }}>{a.icon}</span>
                          ))}
                          <span className="parallel-names">
                            {m.agentsInfo.length > 3
                              ? `${m.agentsInfo.length}+ Agents`
                              : m.agentsInfo.map(a => a.name).join(" + ")}
                          </span>
                        </span>
                      ) : m.agentInfo ? (
                        <span className="msg-agent-label" style={{ color: m.agentInfo.color }}>
                          <span className="msg-agent-icon">{m.agentInfo.icon}</span>
                          {m.agentInfo.name}
                        </span>
                      ) : "Xera AI"
                    )}
                  </div>
                  {m.toolCalls && m.toolCalls.length > 0 && (
                    <div className="tool-calls">
                      {m.toolCalls.map((tc, j) => <ToolCallBlock key={j} call={tc} t={t} onApprove={handleApproval} />)}
                    </div>
                  )}
                  {m.content && (() => {
                    let textContent = '';
                    let imageUrls = [];
                    let docNames = [];
                    const docIcon = n => <DocFileIcon name={n} size={14} />;
                    if (Array.isArray(m.content)) {
                      for (const p of m.content) {
                        if (p.type === "image_url") {
                          imageUrls.push(p.image_url.url);
                        } else if (p.type === "text") {
                          if (p.text.startsWith("[Dokument:")) {
                            const match = p.text.match(/^\[Dokument: (.+?)\]/);
                            if (match) docNames.push(match[1]);
                          } else {
                            textContent += (textContent ? "\n" : "") + p.text;
                          }
                        }
                      }
                    } else {
                      const segs = m.content.split(/(?=\[Dokument: )/);
                      textContent = segs[0].trim();
                      for (const seg of segs.slice(1)) {
                        const match = seg.match(/^\[Dokument: (.+?)\]/);
                        if (match) docNames.push(match[1]);
                      }
                    }
                    const { content: cleanContent, sources } = m.role === "assistant" ? parseSourcesFromContent(textContent) : { content: textContent, sources: [] };
                    return (
                      <>
                        {docNames.length > 0 && (
                          <div className="msg-doc-badges">
                            {docNames.map((name, j) => (
                              <span key={j} className="msg-doc-badge">
                                <span>{docIcon(name)}</span>{name}
                              </span>
                            ))}
                          </div>
                        )}
                        {imageUrls.length > 0 && (
                          <div className="msg-images">{imageUrls.map((url, j) => <img key={j} src={url} alt="" className="msg-image" />)}</div>
                        )}
                        {cleanContent && !(m.docCards?.length && /^Dokument erstellt: \[Download\]/.test(cleanContent.trim())) && (
                          <div className="msg-content">{renderMarkdown(cleanContent, activeTab === "chat")}</div>
                        )}
                        {m.docCards?.length > 0 && m.docCards.map((dc, di) => <DocumentCard key={di} doc={dc} />)}
                        {!m.docCards?.length && cleanContent && /\/api\/download\//.test(cleanContent) && (() => {
                          const m2 = cleanContent.match(/\/api\/download\/([^\)\s]+)/);
                          if (m2) return <DocumentCard doc={{ url: `/api/download/${m2[1]}`, filename: m2[1], doc_type: m2[1].split('.').pop() }} />;
                        })()}
                        {sources.length > 0 && <SourcesBlock sources={sources} />}
                      </>
                    );
                  })()}
                  <div className="msg-actions">
                    <CopyBtn content={m.content} title={t.copy_msg} />
                    {m.role === "assistant" && i === messages.length - 1 && !m.isError && (
                      <button type="button" className="msg-action-btn" onClick={regenerate} title={t.regenerate}>
                        <Icon.Refresh />
                      </button>
                    )}
                    {m.isError && (
                      <button type="button" className="msg-retry-btn" onClick={retryLast}>
                        <Icon.Refresh /> {t.retry}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {streaming && (
              <div className="msg-row assistant" style={activeAgent?.color ? { "--agent-c": activeAgent.color } : undefined}>
                <div className="msg-avatar"><XMark size={30} /></div>
                <div className="msg-body">
                  <div className="msg-role">
                    {activeAgents.length > 1 ? (
                      <span className="msg-agent-label parallel">
                        {activeAgents.slice(0, 3).map(a => (
                          <span key={a.id} className="msg-agent-icon" style={{ color: a.color }}>{a.icon}</span>
                        ))}
                        <span className="parallel-names">
                          {activeAgents.length > 3
                            ? `${activeAgents.length}+ Agents`
                            : activeAgents.map(a => a.name).join(" + ")}
                        </span>
                      </span>
                    ) : activeAgent ? (
                      <span className="msg-agent-label" style={{ color: activeAgent.color }}>
                        <span className="msg-agent-icon">{activeAgent.icon}</span>
                        {activeAgent.name}
                      </span>
                    ) : "Xera AI"}
                    {activeBrain && <span className={`brain-badge brain-${activeBrain}`}>{activeBrain === "fast" ? "Fast Brain" : activeBrain === "code" ? "Mini Brain" : "Big Brain"}</span>}
                  </div>
                  {streamToolCalls.length > 0 && (
                    <div className="tool-calls">
                      {streamToolCalls.map((tc, j) => <ToolCallBlock key={j} call={tc} t={t} onApprove={handleApproval} />)}
                    </div>
                  )}
                  <div className="msg-content">
                    {streamBuf ? (
                      <>{renderMarkdown(streamBuf, activeTab === "chat")}<span className="cursor-blink" /></>
                    ) : (agentThinking || !streamToolCalls.length) ? (
                      <div className="thinking-indicator">
                        <span className="thinking-dot" />
                        <span className="thinking-dot" />
                        <span className="thinking-dot" />
                        <span className="thinking-text">{agentMode && streamToolCalls.length ? t.agent_thinking : t.thinking}</span>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            )}

            {showScrollBtn && (
              <button type="button" className="scroll-bottom-btn" onClick={scrollToBottom}>
                <Icon.ChevronDown />
              </button>
            )}
          </div>

          {brainSwitchConfirm && (
            <BrainSwitchBanner
              from={brainSwitchConfirm.from}
              to={brainSwitchConfirm.to}
              lang={config.language}
              onConfirm={() => {
                const { to, pendingText } = brainSwitchConfirm;
                setBrainSwitchConfirm(null);
                send(pendingText, to);
              }}
              onReject={() => {
                const { from, pendingText } = brainSwitchConfirm;
                setBrainSwitchConfirm(null);
                send(pendingText, from);
              }}
            />
          )}
          <div className="input-area">
            <input type="file" ref={fileInputRef} accept="image/*,.pdf,.docx,.xlsx,.xls,.pptx,.txt,.csv,.md" multiple style={{display: "none"}} onChange={async (e) => {
              const files = Array.from(e.target.files || []);
              for (const file of files) {
                if (file.type.startsWith("image/")) {
                  setPastedImages(prev => [...prev, file]);
                } else {
                  const placeholder = { name: file.name, content: null, images: [], loading: true };
                  setPastedDocs(prev => [...prev, placeholder]);
                  try {
                    const form = new FormData();
                    form.append("file", file);
                    const resp = await fetch("/api/upload", { method: "POST", body: form });
                    const data = await resp.json();
                    setPastedDocs(prev => prev.map(d => d.name === file.name && d.loading ? { ...data, loading: false } : d));
                  } catch {
                    setPastedDocs(prev => prev.map(d => d.name === file.name && d.loading ? { ...d, content: "[Fehler]", loading: false } : d));
                  }
                }
              }
              e.target.value = "";
            }} />
            {(pastedImages.length > 0 || pastedDocs.length > 0) && (
              <div className="pasted-images-bar">
                {pastedImages.map((img, i) => (
                  <div key={"img-" + i} className="pasted-image-thumb">
                    <img src={URL.createObjectURL(img)} alt="" />
                    <button type="button" className="pasted-image-remove" onClick={() => setPastedImages(prev => prev.filter((_, j) => j !== i))}>
                      <Icon.Close />
                    </button>
                  </div>
                ))}
                {pastedDocs.map((doc, i) => (
                  <div key={"doc-" + i} className="pasted-doc-thumb">
                    <span className="doc-icon"><DocFileIcon name={doc.name} size={14} /></span>
                    <span className="doc-name">{doc.name}</span>
                    {doc.loading && <span className="doc-loading">…</span>}
                    <button type="button" className="pasted-image-remove" onClick={() => setPastedDocs(prev => prev.filter((_, j) => j !== i))}>
                      <Icon.Close />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="input-wrapper">
              <div className="input-left-tools">
                <button type="button" className={"input-tool-btn" + (webSearchOn ? " active" : "")} onClick={() => setWebSearchOn(v => !v)} title={t.web_search_toggle}>
                  <Icon.Web />
                </button>
                {config.brain === "fast" && activeTab !== "code" && (
                  <button
                    type="button"
                    className={"input-tool-btn mic-btn" + (isRecording ? " recording" : "")}
                    onClick={toggleMic}
                    title={config.language === "de" ? "Spracheingabe (Fast Brain)" : "Voice input (Fast Brain)"}
                  >
                    <Icon.Mic />
                  </button>
                )}
              </div>
              <textarea
                ref={taRef}
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKey}
                onPaste={(e) => {
                  if (activeTab !== "chat") return;
                  const items = e.clipboardData?.items;
                  if (!items) return;
                  for (const item of items) {
                    if (item.type.startsWith("image/")) {
                      e.preventDefault();
                      const file = item.getAsFile();
                      if (file) {
                        setPastedImages(prev => [...prev, file]);
                      }
                      break;
                    }
                  }
                }}
                placeholder={webSearchOn ? (config.language === "de" ? "Im Web suchen..." : "Search the web...") : activeTab === "homelab" ? (config.language === "de" ? "Homelab-Frage stellen..." : "Ask about your homelab...") : activeTab === "code" ? (config.language === "de" ? "Code-Frage stellen..." : "Ask a code question...") : t.placeholder}
              />
              <div className="input-right-tools">
                {activeTab === "chat" && (
                  <button type="button" className="input-tool-btn" onClick={() => fileInputRef.current?.click()} title={config.language === "de" ? "Datei anfügen" : "Attach file"}>
                    <Icon.Plus />
                  </button>
                )}
                {streaming ? (
                  <button type="button" className="send-btn stop active" onClick={stopStreaming} aria-label="Stop">
                    <Icon.Stop />
                  </button>
                ) : (
                  <button type="button" className={"send-btn" + (input.trim() || pastedImages.length || pastedDocs.length ? " active" : "")} onClick={() => send()} disabled={!input.trim() && !pastedImages.length && !pastedDocs.length} aria-label="Senden">
                    <Icon.Send />
                  </button>
                )}
              </div>
            </div>
            <p className="disclaimer">
              <Icon.Lock /> &nbsp;{t.disclaimer_local} <span className="dot">&bull;</span> {t.disclaimer_text}
            </p>
          </div>

          {showLimit && (
            <div className="limit-overlay" onClick={(e) => { if (e.target === e.currentTarget) setShowLimit(false); }}>
              <div className="limit-card">
                <button className="close-x" onClick={() => setShowLimit(false)} type="button" aria-label="Close">
                  <Icon.Close />
                </button>
                <div className="limit-icon"><Icon.Sparkle /></div>
                <h3>{t.limit_title}</h3>
                <p>{t.limit_body_1}</p>
                {isGuest ? (
                  <>
                    <p>{t.limit_body_guest}</p>
                    <a href="/auth/login" className="discord-btn">
                      <Icon.Discord />
                      {t.discord_login}
                    </a>
                  </>
                ) : (
                  <>
                    <p>{t.limit_body_2}</p>
                    <a href="https://discord.gg/homelab-hq" className="discord-btn" target="_blank" rel="noopener">
                      <Icon.Discord />
                      {t.join_discord}
                    </a>
                  </>
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      <DocSidebar docs={docSidebar} onClose={() => setDocSidebar([])} />

      <CommandPalette
        open={cmdkOpen}
        onClose={() => setCmdkOpen(false)}
        lang={config.language}
        sessions={isGuest ? [] : sessions}
        actions={cmdkActions}
        onOpenSession={openSession}
      />

      {/* Mobile bottom tab bar — logged-in users only */}
      {!isGuest && (
      <nav className="mobile-tab-bar">
        {[
          { id: "chat", icon: Icon.Chat, label: t.tab_chat },
          { id: "code", icon: Icon.Code, label: t.tab_code },
          ...(isHomelab ? [{ id: "homelab", icon: Icon.Server, label: t.tab_homelab }] : []),
        ].map(tab => (
          <button
            key={tab.id}
            className={"mobile-tab-bar-btn" + (activeTab === tab.id ? " active" : "")}
            onClick={() => switchTab(tab.id)}
            type="button"
          >
            <tab.icon />
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>
      )}
    </div>
  );
}

/* ----------------------------------------------------------
   App root — router
   ---------------------------------------------------------- */

function App() {
  const { path, navigate } = useRouter();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const saved = (() => {
    try { return JSON.parse(localStorage.getItem("xera-config") || "{}"); } catch { return {}; }
  })();
  const [config, setConfig] = useState({
    theme: saved.theme || "dark",
    accentHue: saved.accentHue || 282,
    language: saved.language || "de",
    model: saved.model || "qwen3-30b",
    brain: saved.brain || "auto",
    agents: saved.agents || ["code", "search"],
    isPro: false,
  });

  useEffect(() => {
    fetch("/api/me").then(r => r.json()).then(data => {
      setUser(data);
      setConfig(c => ({ ...c, isPro: data.is_pro || data.is_admin }));
      setLoading(false);
    }).catch(() => {
      setUser(null);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", config.theme);
    document.documentElement.style.setProperty("--accent-h", config.accentHue);
    const { isPro, ...toSave } = config;
    localStorage.setItem("xera-config", JSON.stringify(toSave));
  }, [config]);

  useEffect(() => {
    if (!settingsOpen) return;
    const onKey = (e) => { if (e.key === "Escape") setSettingsOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [settingsOpen]);

  const setTheme = (mode) => setConfig(c => ({ ...c, theme: mode }));
  const openSettings = () => setSettingsOpen(true);
  const closeSettings = () => setSettingsOpen(false);
  UI_LANG = config.language;
  const t = STRINGS[config.language] || STRINGS.de;

  if (loading) return null;

  // If logged in and on / or /login → redirect to /c
  if (user && !user.is_guest && (path === "/" || path === "/login")) {
    navigate("/c");
  }

  let page;
  if (path === "/") {
    page = <LandingPage navigate={navigate} theme={config.theme} setTheme={setTheme} openSettings={openSettings} config={config} t={t} />;
  } else if (path === "/login") {
    page = <LoginPage navigate={navigate} theme={config.theme} setTheme={setTheme} openSettings={openSettings} t={t} />;
  } else if (FEATURE_MAP[path]) {
    page = <FeaturePage path={path} navigate={navigate} theme={config.theme} setTheme={setTheme} config={config} t={t} />;
  } else if (path === "/c" || path.startsWith("/c/")) {
    const guestUser = user || { id: "guest", username: "Guest", is_guest: true, is_pro: false, is_admin: false, prompt_count: 0, limit: 5 };
    page = <ChatPage user={guestUser} setUser={setUser} navigate={navigate} theme={config.theme} setTheme={setTheme} openSettings={openSettings} config={config} setConfig={setConfig} t={t} />;
  } else {
    page = <LandingPage navigate={navigate} theme={config.theme} setTheme={setTheme} openSettings={openSettings} config={config} t={t} />;
  }

  return (
    <>
      {page}
      <SettingsModal open={settingsOpen} onClose={closeSettings} config={config} setConfig={setConfig} user={user} t={t}/>
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
