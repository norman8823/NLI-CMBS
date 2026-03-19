export function Footer() {
  return (
    <footer className="border-t border-zinc-100 px-4 py-3 text-xs text-zinc-400 flex items-center justify-between">
      <span>NLI-CMBS | Data sourced from SEC EDGAR | Open Source</span>
      <a
        href="https://github.com/nli-cmbs"
        target="_blank"
        rel="noopener noreferrer"
        className="hover:text-zinc-600 underline"
      >
        GitHub
      </a>
    </footer>
  );
}
