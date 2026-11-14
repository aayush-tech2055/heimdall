"use client";

import { Loader2, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { RoleGate } from "@/components/auth/role-gate";
import { PageHeader } from "@/components/shell/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { ContentDetail, Me } from "@/types/api";

function NewCheck({ me }: { me: Me }) {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [mode, setMode] = useState("paste");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const form = new FormData();
    form.append("title", title.trim());
    if (mode === "paste") {
      if (!text.trim()) return setError("Paste the content to check.");
      form.append("text", text);
    } else {
      if (!file) return setError("Choose a file to check.");
      form.append("file", file);
    }
    setBusy(true);
    try {
      const created = await api<ContentDetail>("/contents", { form });
      router.push(`/creator/content/${created.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed");
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader
        title="New check"
        description={`Paste a draft or upload a file. Heimdall checks it against ${me.brand_name}'s approved rules and facts.`}
      />
      <form onSubmit={submit} className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="title">Title</Label>
          <Input
            id="title"
            required
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Diwali launch post"
          />
        </div>
        <Tabs value={mode} onValueChange={setMode}>
          <TabsList>
            <TabsTrigger value="paste">Paste text</TabsTrigger>
            <TabsTrigger value="file">Upload a file</TabsTrigger>
          </TabsList>
          <TabsContent value="paste" className="space-y-2 pt-2">
            <Label htmlFor="content-text">Content</Label>
            <Textarea
              id="content-text"
              rows={12}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <p className="text-muted-foreground text-sm">
              {text.length.toLocaleString()} / 100,000 characters
            </p>
          </TabsContent>
          <TabsContent value="file" className="space-y-2 pt-2">
            <Label htmlFor="content-file">
              Text or Markdown file (.txt, .md)
            </Label>
            <Input
              id="content-file"
              type="file"
              accept=".txt,.md,.markdown,text/plain,text/markdown"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </TabsContent>
        </Tabs>
        <p className="text-muted-foreground flex items-start gap-2 text-sm">
          <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
          Emails, phone numbers, ID and card numbers and your brand&apos;s
          confidential terms are masked before any AI service sees the text.
        </p>
        {error && (
          <Alert variant="destructive" role="alert">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <Button type="submit" disabled={busy || !title.trim()}>
          {busy && <Loader2 className="animate-spin" aria-hidden />} Check
          content
        </Button>
      </form>
    </div>
  );
}

export default function NewCheckPage() {
  return (
    <RoleGate roles={["creator"]}>{(me) => <NewCheck me={me} />}</RoleGate>
  );
}
