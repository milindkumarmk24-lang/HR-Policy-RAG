"use client";

import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { docName, excerptBody, pageLabel } from "@/lib/format";
import type { Source } from "@/lib/types";
import { CloseIcon, ExternalIcon } from "./Icons";

/** Opens the cited PDF at the cited page, with the passage shown above it. */
export default function PdfDrawer({ source, onClose }: { source: Source | null; onClose: () => void }) {
  const closeBtn = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!source) return;
    const prev = document.activeElement as HTMLElement | null;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      prev?.focus?.();
    };
  }, [source, onClose]);

  if (!source) return null;
  const url = api.fileUrl(source.doc_id, source.page);
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <div className="drawer-head">
          <div>
            <h2 id="drawer-title">{source.section ?? "Cited passage"}</h2>
            <p>{docName(source.source)}, {pageLabel(source.page, source.page_end).toLowerCase()}</p>
          </div>
          <div className="actions">
            <a className="btn" href={url} target="_blank" rel="noreferrer">
              <ExternalIcon size={16} /> Open in a new tab
            </a>
            <button ref={closeBtn} className="icon-btn" onClick={onClose} aria-label="Close">
              <CloseIcon />
            </button>
          </div>
        </div>
        <div className="drawer-quote">
          <p className="excerpt"><mark>{excerptBody(source.text, source.section)}</mark></p>
        </div>
        {/* key forces a reload when switching pages: the PDF viewer ignores hash-only changes */}
        <iframe key={url} src={url} title={`${source.source}, page ${source.page}`} />
      </div>
    </>
  );
}
