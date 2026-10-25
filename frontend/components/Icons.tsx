type P = { size?: number; className?: string };
const base = (size = 18) => ({
  width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true,
});

export const MicIcon = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
);
export const SendIcon = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M4 12h15M13 6l6 6-6 6" /></svg>
);
export const StopIcon = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
);
export const CloseIcon = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M6 6l12 12M18 6L6 18" /></svg>
);
export const TrashIcon = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12" /></svg>
);
export const ExternalIcon = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M14 4h6v6M20 4l-9 9M18 14v5H5V6h5" /></svg>
);
export const ChevronIcon = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M9 6l6 6-6 6" /></svg>
);
export const MoonIcon = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" /></svg>
);
export const SunIcon = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
);
export const BookIcon = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5z" /><path d="M8 7h7" /></svg>
);
export const FileIcon = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M14 3H6v18h12V7l-4-4z" /><path d="M14 3v4h4" /></svg>
);
