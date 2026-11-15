"use client";

import { Loader2, Upload, X } from "lucide-react";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { GUIDELINE_JOB_EVENT } from "@/lib/use-guideline-jobs";
import type { GuidelineJob } from "@/types/api";

/** Kinds of guideline file the backend can read (app/processing/documents.py). */
const GUIDELINE_FILES = [
  ".pdf",
  ".docx",
  ".pptx",
  ".txt",
  ".md",
  ".csv",
  ".tsv",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "text/plain",
  "text/markdown",
  "text/csv",
  "text/tab-separated-values",
].join(",");

export function UploadCard({
  brandId,
  onStarted,
}: {
  brandId: string;
  onStarted: (job: GuidelineJob) => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [inputKey, setInputKey] = useState(0);
  const [text, setText] = useState("");
  const [mode, setMode] = useState("file");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const form = new FormData();
    if (mode === "file") {
      if (!files.length) return setError("Choose at least one file.");
      if (files.length > 10)
        return setError("Upload at most 10 files at once.");
      files.forEach((f) => form.append("files", f));
    } else {
      if (!text.trim()) return setError("Paste some guideline text first.");
      form.append("text", text);
    }
    setBusy(true);
    try {
      const job = await api<GuidelineJob>(`/brands/${brandId}/guidelines`, {
        form,
      });
      window.dispatchEvent(new Event(GUIDELINE_JOB_EVENT));
      onStarted(job);
      setFiles([]);
      setInputKey((k) => k + 1);
      setText("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Upload guidelines</h2>
        </CardTitle>
        <CardDescription>
          Heimdall splits the guideline into one rule per instruction, then
          checks it for duplicates, contradictions, vague rules and missing
          categories. Extraction runs in the background, so you can keep working
          (for example import facts) while it runs. New rules stay pending until
          you approve them.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <Tabs value={mode} onValueChange={setMode}>
            <TabsList>
              <TabsTrigger value="file">Upload a file</TabsTrigger>
              <TabsTrigger value="text">Paste text</TabsTrigger>
            </TabsList>
            <TabsContent value="file" className="space-y-2 pt-2">
              <Label htmlFor="guideline-file">Guideline files</Label>
              <Input
                key={inputKey}
                id="guideline-file"
                type="file"
                multiple
                accept={GUIDELINE_FILES}
                aria-describedby="guideline-file-help"
                onChange={(e) => {
                  const chosen = Array.from(e.target.files ?? []);
                  setFiles((prev) => {
                    const seen = new Set(prev.map((f) => f.name + f.size));
                    return [
                      ...prev,
                      ...chosen.filter((f) => !seen.has(f.name + f.size)),
                    ];
                  });
                  setInputKey((k) => k + 1);
                }}
              />
              {files.length > 0 && (
                <ul className="space-y-1 text-sm" aria-label="Chosen files">
                  {files.map((f) => (
                    <li
                      key={f.name + f.size}
                      className="bg-muted flex items-center justify-between gap-2 rounded-md px-2 py-1"
                    >
                      <span className="truncate">{f.name}</span>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className="size-7"
                        aria-label={`Remove ${f.name}`}
                        onClick={() =>
                          setFiles((prev) => prev.filter((x) => x !== f))
                        }
                      >
                        <X aria-hidden />
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
              <p
                id="guideline-file-help"
                className="text-sm text-muted-foreground"
              >
                One or more files (up to 10, each up to 10 MB): PDF, Word
                (.docx), PowerPoint (.pptx), text (.txt, .md) or CSV. You can
                pick files several times. For a CSV, put one rule per row; a
                header row such as &ldquo;Category, Rule&rdquo; helps.
              </p>
            </TabsContent>
            <TabsContent value="text" className="space-y-2 pt-2">
              <Label htmlFor="guideline-text">Guideline text</Label>
              <Textarea
                id="guideline-text"
                rows={8}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste the brand guideline here…"
              />
            </TabsContent>
          </Tabs>
          {error && (
            <Alert variant="destructive" role="alert">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <Button type="submit" disabled={busy}>
            {busy ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : (
              <Upload aria-hidden />
            )}
            {busy
              ? "Uploading…"
              : mode === "file" && files.length > 1
                ? `Upload ${files.length} files and extract rules`
                : "Upload and extract rules"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
