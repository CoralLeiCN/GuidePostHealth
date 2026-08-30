'use client';

import { KeyboardEvent, SyntheticEvent, useEffect, useRef, useState } from 'react';
import {
  ArrowUp,
  BookOpenText,
  ChevronRight,
  CircleAlert,
  ExternalLink,
  HeartPulse,
  LoaderCircle,
  LockKeyhole,
  MessageCircleQuestion,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const suggestions = [
  'I have had a cough for 5 days',
  'What should I do about a headache?',
  'My child has a high temperature',
];

type Source = {
  id: string;
  title: string;
  section: string;
  url: string;
  fetched_at: string;
  excerpt: string;
};

type Guidance = {
  request_id: string;
  mode: 'codex' | 'retrieval_only' | 'emergency';
  grounded: boolean;
  urgency: 'emergency' | 'urgent' | 'routine' | 'self_care' | 'unknown';
  summary: string;
  next_steps: string[];
  warning_signs: string[];
  follow_up_question: string | null;
  sources: Source[];
  notice: string;
};

type ConversationMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  guidance?: Guidance;
  error?: boolean;
};

export default function Home() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [messages, isLoading]);

  async function ask(question: string) {
    const cleaned = question.trim();
    if (cleaned.length < 2 || isLoading) return;

    const userMessage: ConversationMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: cleaned,
    };
    const history = messages.slice(-8).map((message) => ({
      role: message.role,
      content: message.content,
    }));
    setMessages((current) => [...current, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: cleaned, history }),
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const detail =
          payload && typeof payload === 'object' && 'detail' in payload
            ? String(payload.detail)
            : 'The health guide is not available right now.';
        throw new Error(detail);
      }
      const guidance = payload as Guidance;
      setMessages((current) => [
        ...current,
        {
          id: guidance.request_id,
          role: 'assistant',
          content: guidance.summary,
          guidance,
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content:
            error instanceof Error
              ? error.message
              : 'The health guide is not available right now.',
          error: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    void ask(input);
  }

  function handleKeys(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="border-b border-white/10 bg-[var(--ink)] px-4 py-2.5 text-white">
        <div className="mx-auto flex max-w-7xl items-center justify-center gap-2 text-center text-xs sm:text-sm">
          <CircleAlert className="size-4 shrink-0 text-[var(--urgent-soft)]" />
          <span>
            If someone is seriously ill or their life is at risk, call 999 now.
          </span>
        </div>
      </div>

      <header className="border-b bg-white/85 px-5 py-4 backdrop-blur-xl sm:px-8">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-primary text-primary-foreground shadow-[0_8px_24px_rgba(0,107,105,.2)]">
              <HeartPulse className="size-5" strokeWidth={2.25} />
            </div>
            <div>
              <p className="font-heading text-lg font-semibold tracking-[-0.03em]">
                NextStep
              </p>
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                NHS-guided health assistant
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className="hidden border-[var(--teal-border)] bg-[var(--teal-wash)] text-[var(--teal-strong)] sm:inline-flex"
            >
              <ShieldCheck data-icon="inline-start" /> 25 reviewed guides
            </Badge>
            {messages.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground"
                onClick={() => setMessages([])}
              >
                <RotateCcw data-icon="inline-start" /> New chat
              </Button>
            )}
          </div>
        </div>
      </header>

      <div className="mx-auto grid min-h-[calc(100vh-121px)] max-w-7xl grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section className="flex min-h-[calc(100vh-121px)] min-w-0 flex-col px-5 py-7 sm:px-8 lg:border-r lg:px-12 lg:py-10">
          <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col">
            {messages.length === 0 ? (
              <Welcome onSuggestion={(suggestion) => void ask(suggestion)} />
            ) : (
              <div
                aria-live="polite"
                className="mb-6 flex max-h-[calc(100vh-365px)] min-h-72 flex-1 flex-col gap-5 overflow-y-auto pr-1 sm:max-h-[calc(100vh-315px)]"
              >
                {messages.map((message) => (
                  <ChatMessage key={message.id} message={message} />
                ))}
                {isLoading && <ThinkingMessage />}
                <div ref={endRef} />
              </div>
            )}

            <form
              onSubmit={submit}
              className="mt-auto rounded-[24px] border bg-white p-2 shadow-[0_18px_60px_rgba(16,43,48,.09)]"
            >
              <Textarea
                aria-label="Describe your symptoms"
                className="min-h-20 resize-none border-0 bg-transparent px-3 py-3 text-[15px] shadow-none focus-visible:ring-0"
                placeholder="For example: I've had a dry cough since Monday and feel tired…"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleKeys}
                disabled={isLoading}
              />
              <div className="flex items-center justify-between gap-3 px-2 pb-1 pt-2">
                <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                  <LockKeyhole className="size-3.5" />
                  <span>Chat stays in this browser session</span>
                </div>
                <Button
                  aria-label="Send message"
                  type="submit"
                  size="icon-lg"
                  disabled={input.trim().length < 2 || isLoading}
                  className="rounded-xl shadow-[0_8px_22px_rgba(0,107,105,.24)]"
                >
                  {isLoading ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <ArrowUp className="size-4" />
                  )}
                </Button>
              </div>
            </form>
            <p className="mt-3 text-center text-[11px] leading-5 text-muted-foreground">
              General guidance, not a diagnosis. In England, use NHS 111 if you need
              help now but it is not an emergency.
            </p>
          </div>
        </section>

        <HowItWorks />
      </div>
    </main>
  );
}

function Welcome({ onSuggestion }: { onSuggestion: (suggestion: string) => void }) {
  return (
    <div className="flex flex-1 flex-col">
      <div className="mb-8 flex items-start gap-4">
        <div className="grid size-9 shrink-0 place-items-center rounded-full bg-[var(--teal-wash)] text-primary">
          <Sparkles className="size-4" />
        </div>
        <div className="max-w-2xl">
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.11em] text-primary">
            Health guide
          </p>
          <h1 className="font-heading text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">
            What&apos;s going on today?
          </h1>
          <p className="mt-3 max-w-xl text-[15px] leading-7 text-muted-foreground">
            Describe your symptoms in your own words. I&apos;ll use current NHS guidance
            to help you understand sensible next steps.
          </p>
        </div>
      </div>
      <div className="mb-6 grid gap-2 sm:grid-cols-3">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            className="group flex min-h-20 items-center justify-between gap-3 rounded-2xl border bg-card px-4 py-3 text-left text-sm leading-5 shadow-[0_1px_0_rgba(16,43,48,.03)] transition hover:-translate-y-0.5 hover:border-[var(--teal-border)] hover:shadow-[0_10px_30px_rgba(16,43,48,.07)] focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/40"
            type="button"
            onClick={() => onSuggestion(suggestion)}
          >
            <span>{suggestion}</span>
            <ChevronRight className="size-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-primary" />
          </button>
        ))}
      </div>
    </div>
  );
}

function ChatMessage({ message }: { message: ConversationMessage }) {
  if (message.role === 'user') {
    return (
      <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-[var(--ink)] px-4 py-3 text-sm leading-6 text-white sm:max-w-[72%]">
        {message.content}
      </div>
    );
  }
  if (message.error) {
    return (
      <div className="flex max-w-2xl gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        <TriangleAlert className="mt-0.5 size-4 shrink-0" />
        <div>
          <p className="font-semibold">The local guide is not connected</p>
          <p className="mt-1 leading-6 text-amber-900/80">{message.content}</p>
          <p className="mt-2 text-xs">You can still use the links to official NHS services.</p>
        </div>
      </div>
    );
  }

  const guidance = message.guidance;
  if (!guidance) return null;
  const urgent = guidance.urgency === 'emergency' || guidance.urgency === 'urgent';
  return (
    <article
      className={cn(
        'max-w-2xl rounded-[22px] border bg-white p-5 shadow-[0_8px_35px_rgba(16,43,48,.06)]',
        guidance.urgency === 'emergency' && 'border-red-300 bg-red-50/70',
      )}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge
          variant={urgent ? 'destructive' : 'secondary'}
          className={!urgent ? 'bg-[var(--teal-wash)] text-[var(--teal-strong)]' : undefined}
        >
          {guidance.urgency === 'emergency'
            ? 'Emergency action'
            : guidance.urgency === 'urgent'
              ? 'Get help now'
              : 'NHS-guided answer'}
        </Badge>
        {guidance.mode === 'retrieval_only' && (
          <Badge variant="outline">Source extracts</Badge>
        )}
      </div>
      <p className="text-[15px] font-medium leading-7">{guidance.summary}</p>

      {guidance.next_steps.length > 0 && (
        <GuidanceList title="Sensible next steps" items={guidance.next_steps} />
      )}
      {guidance.warning_signs.length > 0 && (
        <GuidanceList
          title="When to get help"
          items={guidance.warning_signs}
          warning
        />
      )}
      {guidance.follow_up_question && (
        <div className="mt-4 rounded-xl bg-[var(--teal-wash)] px-3.5 py-3 text-sm leading-6 text-[var(--teal-strong)]">
          <span className="font-semibold">It would help to know: </span>
          {guidance.follow_up_question}
        </div>
      )}
      {guidance.sources.length > 0 && <Sources sources={guidance.sources} />}
      <p className="mt-4 border-t pt-3 text-[10px] leading-4 text-muted-foreground">
        {guidance.notice}
      </p>
    </article>
  );
}

function GuidanceList({
  title,
  items,
  warning = false,
}: {
  title: string;
  items: string[];
  warning?: boolean;
}) {
  return (
    <div className="mt-5">
      <h2 className={cn('text-xs font-bold uppercase tracking-[0.09em]', warning && 'text-red-700')}>
        {title}
      </h2>
      <ul className="mt-2 space-y-2 text-sm leading-6 text-foreground/80">
        {items.map((item) => (
          <li key={item} className="flex gap-2.5">
            <span
              className={cn(
                'mt-2.5 size-1.5 shrink-0 rounded-full bg-primary',
                warning && 'bg-red-600',
              )}
            />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Sources({ sources }: { sources: Source[] }) {
  return (
    <div className="mt-5 border-t pt-4">
      <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.09em] text-muted-foreground">
        NHS sources
      </p>
      <div className="flex flex-wrap gap-2">
        {sources.map((source) => (
          <a
            key={`${source.id}-${source.section}`}
            href={source.url}
            target="_blank"
            rel="noreferrer"
            title={`Copied as at ${new Date(source.fetched_at).toLocaleDateString('en-GB')}`}
            className="inline-flex items-center gap-1.5 rounded-full border bg-[var(--paper-deep)] px-3 py-1.5 text-xs font-medium transition hover:border-[var(--teal-border)] hover:text-primary focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/40"
          >
            {source.title} · {source.section}
            <ExternalLink className="size-3" />
          </a>
        ))}
      </div>
    </div>
  );
}

function ThinkingMessage() {
  return (
    <div className="flex items-center gap-3 text-sm text-muted-foreground">
      <span className="grid size-8 place-items-center rounded-full bg-[var(--teal-wash)] text-primary">
        <LoaderCircle className="size-4 animate-spin" />
      </span>
      Searching the NHS guide library…
    </div>
  );
}

function HowItWorks() {
  return (
    <aside className="bg-[var(--paper-deep)] px-5 py-7 sm:px-8 lg:px-7 lg:py-10">
      <div className="mx-auto max-w-3xl lg:max-w-none">
        <p className="mb-4 text-xs font-semibold uppercase tracking-[0.11em] text-muted-foreground">
          How it works
        </p>
        <div className="space-y-3">
          <InfoCard
            icon={<MessageCircleQuestion className="size-4" />}
            title="Tell me what you notice"
            body="Include when it started, what makes it better or worse, and anything else that feels relevant."
          />
          <InfoCard
            icon={<BookOpenText className="size-4" />}
            title="Grounded in NHS guides"
            body="Answers are retrieved from 25 reviewed symptom pages and link to the original guidance."
          />
          <InfoCard
            icon={<ShieldCheck className="size-4" />}
            title="Clear next steps"
            body="See what you can try, when to speak to a pharmacist or GP, and when to seek urgent help."
          />
        </div>

        <a
          className="mt-6 flex items-center justify-between rounded-2xl border border-[var(--teal-border)] bg-[var(--teal-wash)] px-4 py-3 text-sm font-medium text-[var(--teal-strong)] transition hover:bg-[var(--teal-wash-strong)] focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/40"
          href="https://www.nhs.uk/conditions/"
          rel="noreferrer"
          target="_blank"
        >
          Browse NHS health A to Z
          <ExternalLink className="size-4" />
        </a>

        <p className="mt-6 border-t pt-5 text-[11px] leading-5 text-muted-foreground">
          Independent research prototype for England. Not affiliated with or endorsed by
          the NHS. Contains public sector information licensed under the Open Government
          Licence v3.0.
        </p>
      </div>
    </aside>
  );
}

function InfoCard({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-2xl border border-transparent p-3 transition hover:border-border hover:bg-white/60">
      <div className="mb-2 flex items-center gap-2.5">
        <span className="grid size-8 place-items-center rounded-lg bg-white text-primary shadow-[0_1px_5px_rgba(16,43,48,.06)]">
          {icon}
        </span>
        <h2 className="text-sm font-semibold tracking-[-0.015em]">{title}</h2>
      </div>
      <p className="pl-[42px] text-xs leading-5 text-muted-foreground">{body}</p>
    </div>
  );
}
