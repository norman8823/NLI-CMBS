import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { useReport } from "@/hooks/useReport";

interface ReportPanelProps {
  ticker: string;
}

/** Wrap standalone numbers, percentages, and dollar amounts in monospace */
function renderNumbers(text: string, keyBase: number): ReactNode {
  const numRegex = /(\$[\d,.]+[BMK]?|\d+\.?\d*%|\d+\.\d+x)/g;
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = numRegex.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    parts.push(
      <span key={`n${keyBase}_${parts.length}`} className="font-mono">
        {match[1]}
      </span>
    );
    lastIndex = numRegex.lastIndex;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts.length === 1 ? parts[0] : parts;
}

/** Render inline markdown: **bold** and numbers/percentages in monospace */
function renderInline(text: string): ReactNode {
  const parts: ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex)
      parts.push(renderNumbers(text.slice(lastIndex, match.index), parts.length));
    parts.push(
      <strong key={`b${parts.length}`} className="font-semibold text-zinc-800">
        {match[1].replace(/\*\*/g, "")}
      </strong>
    );
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length)
    parts.push(renderNumbers(text.slice(lastIndex), parts.length));
  return parts.length === 1 ? parts[0] : parts;
}

/** Simple markdown-to-JSX renderer for predictable report structure */
function RenderedReport({ text }: { text: string }) {
  const lines = text.split("\n");
  const elements: ReactNode[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      elements.push(
        <p key={elements.length} className="text-sm text-zinc-700 leading-relaxed">
          {renderInline(paragraph.join(" "))}
        </p>
      );
      paragraph = [];
    }
  };

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={elements.length} className="text-sm text-zinc-700 leading-relaxed list-disc pl-5 space-y-1">
          {listItems.map((item, i) => (
            <li key={i}>{renderInline(item)}</li>
          ))}
        </ul>
      );
      listItems = [];
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith("## ")) {
      flushParagraph();
      flushList();
      elements.push(
        <h3 key={elements.length} className="text-base font-semibold text-zinc-800 mt-6 mb-2">
          {trimmed.replace(/^##\s+/, "")}
        </h3>
      );
      continue;
    }

    if (trimmed.startsWith("### ")) {
      flushParagraph();
      flushList();
      elements.push(
        <h4 key={elements.length} className="text-sm font-semibold text-zinc-800 mt-4 mb-1">
          {trimmed.replace(/^###\s+/, "")}
        </h4>
      );
      continue;
    }

    if (/^[-*]\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed)) {
      flushParagraph();
      listItems.push(trimmed.replace(/^[-*]\s+|^\d+\.\s+/, ""));
      continue;
    }

    if (trimmed === "") {
      flushParagraph();
      flushList();
      continue;
    }

    if (listItems.length > 0) flushList();
    paragraph.push(trimmed);
  }

  flushParagraph();
  flushList();

  return <div className="space-y-4">{elements}</div>;
}

export function ReportPanel({ ticker }: ReportPanelProps) {
  const { data: report, isLoading, error, enabled, generate, regenerate } =
    useReport(ticker);

  return (
    <section className="mt-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-zinc-800">
          AI Surveillance Report
        </h2>
        {!enabled && !report && (
          <Button
            onClick={generate}
            className="bg-slate-700 text-white hover:bg-slate-800"
            size="sm"
          >
            Generate Report
          </Button>
        )}
        {isLoading && (
          <Button disabled size="sm" variant="secondary">
            <div className="h-3.5 w-3.5 border-2 border-zinc-400 border-t-transparent rounded-full animate-spin mr-2" />
            Generating…
          </Button>
        )}
        {report && !isLoading && (
          <Button onClick={regenerate} variant="outline" size="sm">
            Regenerate
          </Button>
        )}
      </div>

      {error && (
        <div className="border border-rose-200 bg-rose-50 rounded-md px-4 py-3 text-sm text-rose-700">
          Unable to generate report. Please try again.
        </div>
      )}

      {report && (
        <div className="bg-white border border-zinc-200 rounded-md p-6">
          <RenderedReport text={report.report_text} />
          <div className="mt-6 pt-3 border-t border-zinc-100 text-xs text-zinc-400 space-y-0.5">
            <p>
              Generated{" "}
              {new Date(report.generated_at).toLocaleString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
                hour: "numeric",
                minute: "2-digit",
              })}{" "}
              using {report.model_used}
            </p>
            <p>Based on filing dated {report.filing_date}</p>
          </div>
        </div>
      )}
    </section>
  );
}
