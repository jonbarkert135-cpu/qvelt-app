"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import { locales, themes, type Locale, type Messages, type Theme } from "../lib/messages";

const paths = {
  plus: "M12 5v14M5 12h14", panel: "M4 4h16v16H4zM9 4v16",
  close: "m6 6 12 12M6 18 18 6", arrow: "M12 19V5m-6 6 6-6 6 6",
  book: "M4 5h6l2 2 2-2h6v14h-6l-2 2-2-2H4zM12 7v14",
  spark: "m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z",
  code: "m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16",
  folder: "M3 7V5h6l2 2h10v13H3z",
} as const;

function Icon({ name }: { name: keyof typeof paths }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={paths[name]} />
  </svg>;
}

function Mark() {
  return <svg viewBox="0 0 40 40" width="34" height="34" fill="none" aria-hidden="true">
    <path d="M30 20a10 10 0 1 0-10 10h13M25 25l8 8" stroke="currentColor"
      strokeWidth="3" strokeLinecap="round" />
  </svg>;
}

export function ChatShell({ locale, theme, t }: { locale: Locale; theme: Theme; t: Messages }) {
  const router = useRouter();
  const [pending, transition] = useTransition();
  const [collapsed, setCollapsed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const composer = useRef<HTMLTextAreaElement>(null);

  const newChat = useCallback(() => {
    if (draft.trim() && !window.confirm(t.discard)) return;
    setDraft("");
    setMenuOpen(false);
    composer.current?.focus();
  }, [draft, t.discard]);

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "o") {
        event.preventDefault();
        newChat();
      }
    }
    document.addEventListener("keydown", shortcut);
    return () => document.removeEventListener("keydown", shortcut);
  }, [newChat]);

  function preference(name: "locale" | "theme", value: string) {
    const allowed: readonly string[] = name === "locale" ? locales : themes;
    if (!allowed.includes(value)) return;
    document.cookie = `qvelt-${name}=${value}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
    transition(() => router.refresh());
  }

  function sidebar(mobile = false) {
    const prefix = mobile ? "mobile-" : "";
    return <>
      <div className="brand-row">
        <span className="brand"><Mark /><span>QVELT</span></span>
        {mobile ? <Dialog.Close className="icon-button" aria-label={t.closeNavigation}><Icon name="close" /></Dialog.Close>
          : <button className="icon-button" aria-label={t.collapse} onClick={() => setCollapsed(true)}><Icon name="panel" /></button>}
      </div>
      <nav aria-label={t.workspace} className="workspace-nav">
        <button id={`${prefix}newchat`} className="new-chat" onClick={newChat}><Icon name="plus" />{t.newChat}</button>
        <div className="nav-section">
          <h2>{t.conversations}</h2>
          <p className="history-empty">{t.history}</p>
        </div>
        <button className="projects-button" disabled><Icon name="folder" /><span>{t.projects}</span><span className="soon">{t.soon}</span></button>
      </nav>
      <div className="preferences">
        <div><label htmlFor={`${prefix}locale`}>{t.language}</label>
          <select id={`${prefix}locale`} value={locale} disabled={pending} onChange={e => preference("locale", e.target.value)}>
            <option value="en" lang="en">English</option><option value="uk" lang="uk">Українська</option><option value="ru" lang="ru">Русский</option>
          </select></div>
        <div><label htmlFor={`${prefix}theme`}>{t.appearance}</label>
          <select id={`${prefix}theme`} value={theme} disabled={pending} onChange={e => preference("theme", e.target.value)}>
            {themes.map(value => <option key={value} value={value}>{t[value]}</option>)}
          </select></div>
      </div>
    </>;
  }

  return <Dialog.Root open={menuOpen} onOpenChange={setMenuOpen}>
    <a className="skip-link" href="#content">{t.skip}</a>
    <div className="shell" data-collapsed={collapsed}>
      <aside className="desktop-sidebar">
        {collapsed ? <div className="sidebar-rail">
          <span className="brand"><Mark /></span>
          <button className="icon-button" aria-label={t.expand} onClick={() => setCollapsed(false)}><Icon name="panel" /></button>
          <button className="icon-button" aria-label={t.newChat} onClick={newChat}><Icon name="plus" /></button>
        </div> : sidebar()}
      </aside>
      <div className="main-column">
        <header className="topbar">
          <Dialog.Trigger className="icon-button mobile-menu" aria-label={t.openNavigation}><Icon name="panel" /></Dialog.Trigger>
          <span className="workspace-name">{t.workspace}</span><span className="topbar-wordmark">QVELT</span>
        </header>
        <main id="content" tabIndex={-1} className="conversation">
          <div className="welcome">
            <div className="welcome-mark"><Mark /></div>
            <p className="eyebrow">{t.eyebrow}</p>
            <h1>{t.heading}</h1><p className="intro">{t.intro}</p>
          </div>
          <form className="composer" onSubmit={e => e.preventDefault()}>
            <label className="sr-only" htmlFor="message">{t.message}</label>
            <textarea ref={composer} id="message" dir="auto" placeholder={t.placeholder} value={draft}
              onChange={e => setDraft(e.target.value)} rows={3} maxLength={100_000} aria-describedby="messaging-status" />
            <div className="composer-toolbar"><span className="composer-brand">QVELT</span>
              <button className="send-button" type="submit" disabled aria-label={t.send}><Icon name="arrow" /></button>
            </div>
          </form>
          <p className="messaging-status" id="messaging-status">{t.unavailable}</p>
          <div className="suggestions">
            {([["concept", "conceptPrompt", "book"], ["idea", "ideaPrompt", "spark"], ["code", "codePrompt", "code"]] as const).map(([label, prompt, icon]) =>
              <button key={label} onClick={() => {
                setDraft(current => current ? `${current}\n\n${t[prompt]}` : t[prompt]);
                composer.current?.focus();
              }}><Icon name={icon} />{t[label]}</button>)}
          </div>
        </main>
        <footer className="page-footer">{t.footer}</footer>
      </div>
    </div>
    <Dialog.Portal>
      <Dialog.Overlay className="drawer-overlay" />
      <Dialog.Content className="drawer" aria-describedby={undefined} onOpenAutoFocus={e => {
        e.preventDefault(); document.getElementById("mobile-newchat")?.focus();
      }}>
        <Dialog.Title className="sr-only">{t.navigation}</Dialog.Title>
        {sidebar(true)}
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
